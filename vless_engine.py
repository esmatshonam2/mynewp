"""
StanNG - Minimal VLESS-over-WebSocket forwarding engine.
Implements just enough of the VLESS protocol (proxy protocol v0, no encryption
layer beyond outer TLS which is terminated by the platform / Cloudflare edge)
to relay a client's WebSocket stream to the requested remote TCP destination.

This is intentionally dependency-free (uses asyncio streams only) so the whole
panel stays a single Python process / single service, per project scope.
"""
import asyncio
import struct
import socket
import time
from typing import Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketState

VLESS_VERSION = 0


class VlessHeader:
    __slots__ = ("uuid", "addon_len", "cmd", "port", "atype", "addr", "header_len")

    def __init__(self, uuid: str, cmd: int, port: int, atype: int, addr: str, header_len: int):
        self.uuid = uuid
        self.cmd = cmd
        self.port = port
        self.atype = atype
        self.addr = addr
        self.header_len = header_len


def _fmt_uuid(b: bytes) -> str:
    h = b.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def parse_vless_header(buf: bytes) -> Optional[VlessHeader]:
    """Parse the initial VLESS request header from the first WS message."""
    if len(buf) < 24:
        return None
    pos = 0
    version = buf[pos]
    pos += 1
    if version != VLESS_VERSION:
        return None
    uuid_bytes = buf[pos:pos + 16]
    pos += 16
    uuid_str = _fmt_uuid(uuid_bytes)

    addon_len = buf[pos]
    pos += 1
    pos += addon_len  # skip protobuf addons, unused

    if pos >= len(buf):
        return None
    cmd = buf[pos]
    pos += 1

    if cmd not in (1, 2):  # 1 = TCP, 2 = UDP (UDP not supported, ignored)
        return None

    if pos + 2 > len(buf):
        return None
    port = struct.unpack(">H", buf[pos:pos + 2])[0]
    pos += 2

    if pos >= len(buf):
        return None
    atype = buf[pos]
    pos += 1

    if atype == 1:  # IPv4
        if pos + 4 > len(buf):
            return None
        addr = socket.inet_ntoa(buf[pos:pos + 4])
        pos += 4
    elif atype == 2:  # domain
        if pos >= len(buf):
            return None
        dlen = buf[pos]
        pos += 1
        if pos + dlen > len(buf):
            return None
        addr = buf[pos:pos + dlen].decode("utf-8", errors="ignore")
        pos += dlen
    elif atype == 3:  # IPv6
        if pos + 16 > len(buf):
            return None
        addr = socket.inet_ntop(socket.AF_INET6, buf[pos:pos + 16])
        pos += 16
    else:
        return None

    return VlessHeader(uuid_str, cmd, port, atype, addr, pos)


class TrafficCounter:
    """Simple counter object passed by reference to track bytes for a session."""
    def __init__(self):
        self.up = 0
        self.down = 0


async def pump_ws_to_tcp(ws: WebSocket, writer: asyncio.StreamWriter, counter: TrafficCounter, first_payload: bytes):
    try:
        if first_payload:
            writer.write(first_payload)
            counter.up += len(first_payload)
            await writer.drain()
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            data = msg.get("bytes")
            if data is None:
                text = msg.get("text")
                if text is None:
                    continue
                data = text.encode("utf-8")
            writer.write(data)
            counter.up += len(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def pump_tcp_to_ws(ws: WebSocket, reader: asyncio.StreamReader, counter: TrafficCounter, vless_resp_header: bytes):
    try:
        sent_header = False
        while True:
            data = await reader.read(64 * 1024)
            if not data:
                break
            if not sent_header:
                data = vless_resp_header + data
                sent_header = True
            counter.down += len(data)
            if ws.application_state != WebSocketState.CONNECTED:
                break
            await ws.send_bytes(data)
    except Exception:
        pass
    finally:
        try:
            if ws.application_state == WebSocketState.CONNECTED:
                await ws.close()
        except Exception:
            pass


async def relay(ws: WebSocket, uuid_str: str, on_traffic, connect_timeout: float = 8.0) -> TrafficCounter:
    """
    Accepts an already-accepted WebSocket, expects the first frame to contain
    the VLESS header, connects to the target, and relays bidirectionally.
    `on_traffic(up_delta, down_delta)` is invoked periodically for accounting.
    """
    counter = TrafficCounter()
    first_msg = await ws.receive()
    if first_msg.get("type") == "websocket.disconnect":
        return counter
    raw = first_msg.get("bytes")
    if raw is None:
        txt = first_msg.get("text")
        raw = txt.encode("utf-8") if txt else b""

    header = parse_vless_header(raw)
    if header is None or header.uuid != uuid_str:
        await ws.close(code=1008)
        return counter

    payload = raw[header.header_len:]

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host=header.addr, port=header.port),
            timeout=connect_timeout,
        )
    except Exception:
        await ws.close(code=1011)
        return counter

    vless_resp_header = bytes([VLESS_VERSION, 0])  # version + no addons

    up_task = asyncio.create_task(pump_ws_to_tcp(ws, writer, counter, payload))
    down_task = asyncio.create_task(pump_tcp_to_ws(ws, reader, counter, vless_resp_header))

    last_reported = TrafficCounter()
    try:
        while not (up_task.done() and down_task.done()):
            done, _pending = await asyncio.wait({up_task, down_task}, timeout=1.0)
            du = counter.up - last_reported.up
            dd = counter.down - last_reported.down
            if du or dd:
                try:
                    on_traffic(du, dd)
                except Exception:
                    pass
                last_reported.up = counter.up
                last_reported.down = counter.down
            if done:
                break
    finally:
        for t in (up_task, down_task):
            if not t.done():
                t.cancel()
        du = counter.up - last_reported.up
        dd = counter.down - last_reported.down
        if du or dd:
            try:
                on_traffic(du, dd)
            except Exception:
                pass

    return counter
