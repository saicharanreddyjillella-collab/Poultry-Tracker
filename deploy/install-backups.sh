#!/usr/bin/env bash
# PoultryTrack — install automated backups (E9). Run as root on the server:
#   bash deploy/install-backups.sh
# Idempotent: safe to re-run after pulling updates.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
[[ $EUID -eq 0 ]] || { echo "Run as root."; exit 1; }

mkdir -p /etc/poultrytrack
if [[ ! -f /etc/poultrytrack/backup.env ]]; then
    cp "$SCRIPT_DIR/backup.env.example" /etc/poultrytrack/backup.env
    chmod 600 /etc/poultrytrack/backup.env
    echo "→ Created /etc/poultrytrack/backup.env (edit it to add an off-box remote + alert URL)"
fi

for unit in poultrytrack-backup.service poultrytrack-backup.timer \
            poultrytrack-backup-verify.service poultrytrack-backup-verify.timer; do
    sed "s#@APP_DIR@#$APP_DIR#g" "$SCRIPT_DIR/systemd/$unit" > "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable --now poultrytrack-backup.timer poultrytrack-backup-verify.timer

# Retire the old cron entry if someone had added one by hand.
if crontab -l 2>/dev/null | grep -q "deploy/backup.sh"; then
    crontab -l | grep -v "deploy/backup.sh" | crontab -
    echo "→ Removed old backup.sh crontab entry (now handled by systemd timer)"
fi

echo "✅ Automated backups installed."
systemctl list-timers 'poultrytrack-*' --no-pager
echo
echo "Run one now:        systemctl start poultrytrack-backup && journalctl -u poultrytrack-backup -n 30"
echo "Test a restore:     systemctl start poultrytrack-backup-verify && journalctl -u poultrytrack-backup-verify -n 30"
grep -q '^BACKUP_REMOTE=$' /etc/poultrytrack/backup.env && \
    echo "⚠️  No off-box destination yet — set BACKUP_REMOTE in /etc/poultrytrack/backup.env"
exit 0
