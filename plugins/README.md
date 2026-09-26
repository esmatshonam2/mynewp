# ALOO PANEL — writing a plugin

Plugins are directories under `plugins/<id>/` with a `manifest.json`:

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "you",
  "description": "What it adds.",
  "enabled": true
}
```

Rules:

- `id` must match `[a-zA-Z0-9_-]{1,64}` and equal the directory name.
- Optional `widget.py` with `get_cards(db) -> list` contributes live cards
  to the Extensions view (`{"title": {"fa","en"} | str, "value", "hint"}`).
- Widget code runs in-process on every Extensions-view load: keep it fast,
  dependency-free, and exception-safe (the registry isolates failures
  per plugin, but slow code slows the page).
- Only admins can toggle plugins (`settings.manage`); plugin files are
  trusted code — install only from sources you trust.

See `plugins/system_extra/` for a complete working example.
