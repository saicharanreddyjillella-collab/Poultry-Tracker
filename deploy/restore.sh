#!/bin/bash
# Restore PostgreSQL backup for PoultryTrack
# Usage: bash restore.sh /root/backups/poultrytrack_2026-07-12_03-00.sql.gz

if [ -z "$1" ]; then
    echo "Usage: bash restore.sh <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    ls -lh /root/backups/poultrytrack_*.sql.gz 2>/dev/null
    exit 1
fi

if [ ! -f "$1" ]; then
    echo "❌ File not found: $1"
    exit 1
fi

echo "⚠️  This will REPLACE all current data with the backup."
read -p "Are you sure? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

echo "→ Restoring from $1..."
gunzip -c "$1" | docker compose -f /root/Poultry-Tracker/docker-compose.yml exec -T db psql -U poultrytrack -d poultrytrack

echo "✅ Restore complete. Restarting backend..."
docker compose -f /root/Poultry-Tracker/docker-compose.yml restart backend
echo "Done."
