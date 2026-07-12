#!/bin/bash
# Daily PostgreSQL backup for PoultryTrack
# Keeps last 30 days of backups

BACKUP_DIR="/root/backups"
mkdir -p "$BACKUP_DIR"

DATE=$(date +%Y-%m-%d_%H-%M)
FILENAME="poultrytrack_${DATE}.sql.gz"

# Dump and compress
docker compose -f /root/Poultry-Tracker/docker-compose.yml exec -T db pg_dump -U poultrytrack poultrytrack | gzip > "$BACKUP_DIR/$FILENAME"

# Check if backup was created
if [ -s "$BACKUP_DIR/$FILENAME" ]; then
    echo "✅ Backup created: $FILENAME ($(du -h "$BACKUP_DIR/$FILENAME" | cut -f1))"
else
    echo "❌ Backup failed!"
    rm -f "$BACKUP_DIR/$FILENAME"
    exit 1
fi

# Delete backups older than 30 days
find "$BACKUP_DIR" -name "poultrytrack_*.sql.gz" -mtime +30 -delete
echo "🗑️  Old backups cleaned. Current backups:"
ls -lh "$BACKUP_DIR"/poultrytrack_*.sql.gz 2>/dev/null | wc -l

# Upload to OneDrive (if rclone is configured)
if command -v rclone &> /dev/null && rclone listremotes | grep -q "onedrive:"; then
    rclone copy "$BACKUP_DIR/$FILENAME" onedrive:PoultryTrack-Backups/
    echo "☁️  Uploaded to OneDrive"
fi
