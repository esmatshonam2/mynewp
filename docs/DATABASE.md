# Database

Single-file JSON store (`<DATA_DIR>/db.json`), atomic writes
(write-temp + fsync + rename), in-process async lock. No external DB needed.

Collections: `admins`, `inbounds` (users), `plans`, `servers`, `bot_users`,
`topup_requests`, `api_tokens`, `audit_log` (cap 500), `notifications`
(cap 200), `backups` (metadata; files in `<DATA_DIR>/backups/`),
`settings`, `login_attempts`, `notified`, `stats.hourly` (cap 72 buckets).

## Migrations

`schema_version` (current: 9) upgrades automatically on load: new keys are
backfilled, legacy `admin` becomes an `owner` in `admins[]`, users receive
`sub_token`s, seed plans are added. Old sessions stay valid (same hashes).

## Safety

- Backups: use **Backup view** (manual + scheduled) or download
  `/api/backup/export`. Restore preserves the session secret.
- Never hand-edit `db.json` while the panel runs; stop it first.
- Hourly traffic older than ~72h is pruned (Analytics flags `partial`).
