"""Shared test fixtures for ALOO PANEL Phase 3 tests."""
import os
import sys
import json
import time
import shutil
import asyncio
import copy
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets a fresh, isolated in-memory DB."""
    import storage
    import secrets as _secrets

    # Build a fresh DB dict (no filesystem needed for tests)
    fresh_db = copy.deepcopy(storage.DEFAULT_DB)
    fresh_db["secret_key"] = _secrets.token_hex(32)

    # Create a new Store and point both storage.store and main.store at it
    new_store = storage.Store.__new__(storage.Store)
    new_store.db = fresh_db

    monkeypatch.setattr(storage, "store", new_store)
    # main.py does `from storage import store` so we must also patch main.store
    import main as _main
    monkeypatch.setattr(_main, "store", new_store)

    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    monkeypatch.setattr("storage.DATA_DIR", data_dir)
    monkeypatch.setattr("storage.DB_PATH", os.path.join(data_dir, "db.json"))
    monkeypatch.setattr(_main, "DATA_DIR", data_dir)
    monkeypatch.setattr(_main, "DB_PATH", os.path.join(data_dir, "db.json"))
    monkeypatch.setattr("storage._lock", asyncio.Lock())

    yield new_store
