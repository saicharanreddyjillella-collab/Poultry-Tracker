# Backups & Restore (E9)

Automated, verified backups of the **database** and **uploaded documents**.

| What | When | How |
|---|---|---|
| Backup (DB + documents) | Daily 02:30 IST | `poultrytrack-backup.timer` → `deploy/backup.sh` |
| Restore test into a throw-away DB | Sunday 04:00 IST | `poultrytrack-backup-verify.timer` → `deploy/verify-backup.sh` |
| Missed run (server was off) | Next boot | `Persistent=true` on both timers |

## One-time setup (on the server, as root)

```bash
cd /root/Poultry-Tracker && git pull
bash deploy/install-backups.sh          # installs + starts the timers
nano /etc/poultrytrack/backup.env       # add off-box remote + alert URL (below)
systemctl start poultrytrack-backup     # take the first backup now
journalctl -u poultrytrack-backup -n 30
```

### Off-box copy (do this — a backup on the same droplet dies with it)
```bash
apt-get install -y rclone
rclone config            # create a remote, e.g. "onedrive" or "gdrive" or DigitalOcean Spaces
# then in /etc/poultrytrack/backup.env:
BACKUP_REMOTE=onedrive:PoultryTrack-Backups
```
An existing `onedrive:` rclone remote is used automatically if `BACKUP_REMOTE` is empty.

### Get alerted when backups stop
Create a free check at <https://healthchecks.io> (period 1 day, grace 2 h), put its URL in
`BACKUP_PING_URL`. A second check (period 7 days) for `BACKUP_VERIFY_PING_URL`.
You get an email if a backup **fails or simply doesn't run**.

## What a backup contains
`/root/backups/`
- `poultrytrack_<date>.sql.gz` + `.sha256` — full database, dumped with `--clean`
  so it restores over a live database.
- `media_<date>.tar.gz` + `.sha256` — uploaded documents (agreements, KYC, certificates).
- `last_backup.json`, `last_verify.json` — status of the last run.

Each dump is checked (gzip integrity + pg_dump completion marker) before it counts.
Local copies older than `RETENTION_DAYS` (30) are pruned, but the newest `MIN_KEEP` (7)
are always kept. Off-box copies are pruned after `REMOTE_RETENTION_DAYS` (90).

## Restoring
```bash
bash deploy/restore.sh                    # lists available backups
bash deploy/restore.sh latest             # newest DB + its documents (asks to confirm)
bash deploy/restore.sh /root/backups/poultrytrack_2026-11-15_02-30-00.sql.gz
bash deploy/restore.sh latest --no-media  # database only
```
The restore: checks the checksum (refuses a damaged file), saves the current DB to
`pre_restore_<date>.sql.gz`, stops the backend, restores in **one transaction**
(any error → nothing changes), restarts the backend, then restores documents.

To restore from off-box after losing the server: set up a fresh droplet with
`deploy/setup.sh`, `rclone copy onedrive:PoultryTrack-Backups/<files> /root/backups/`,
then `bash deploy/restore.sh latest`.

## Checking on it
```bash
systemctl list-timers 'poultrytrack-*'
cat /root/backups/last_backup.json /root/backups/last_verify.json
bash deploy/verify-backup.sh latest       # run a restore test any time
```
