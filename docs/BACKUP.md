# Backup & restore

## Snapshot backups (Backup view)

- **Instant server backup** (`POST /api/backups`) + scheduled daily
  backup (hour/minute/keep-N + optional Telegram document shipping).
- Files: `<DATA_DIR>/backups/aloo-backup-*.json`; history capped at
  `backup_keep` (old files pruned automatically).
- **Download** any snapshot; **delete** removes file + record.
- **Restore** requires your password; sessions survive (secret kept),
  xray config regenerates, users/settings/servers roll back to the file.
  Restoring also rolls back the backup *history* (snapshot semantics).

## Portable export

`/api/backup/export` downloads `{version, exported_at, db}` for
off-site copies; re-import with merge (dedupe by uid) or replace mode.

## Disaster recovery

1. Fresh deploy + volume, restore the newest snapshot file via the API
   or place a `db.json` into the data dir while stopped.
2. Run **Diagnostics** to verify xray/database/network.
