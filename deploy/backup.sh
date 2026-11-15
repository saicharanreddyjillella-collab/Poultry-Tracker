#!/usr/bin/env bash
# PoultryTrack — automated backup (E9)
#
# Dumps PostgreSQL + the uploaded-documents (media) volume, verifies both,
# writes checksums, prunes old copies, optionally copies off-box with rclone,
# records status, and pings a dead-man's-switch URL. Scheduled daily by
# deploy/systemd/poultrytrack-backup.timer (see deploy/install-backups.sh).
#
# Settings come from the environment or /etc/poultrytrack/backup.env:
#   BACKUP_DIR          where backups live            (default /root/backups)
#   RETENTION_DAYS      delete local copies older than (default 30)
#   MIN_KEEP            always keep at least this many newest backups (default 7)
#   BACKUP_REMOTE       rclone destination, e.g. onedrive:PoultryTrack-Backups
#                       or b2:my-bucket/poultry (empty = auto-use an rclone
#                       "onedrive:" remote if one exists, else local only)
#   REMOTE_RETENTION_DAYS  prune off-box copies older than this (default 90; 0 = never)
#   BACKUP_PING_URL     e.g. https://hc-ping.com/<uuid> — pinged on success,
#                       <url>/fail on failure
#   BACKUP_MEDIA        1 = also back up uploaded documents (default 1)
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$(dirname "$SCRIPT_DIR")}"
CONFIG_FILE="${BACKUP_CONFIG:-/etc/poultrytrack/backup.env}"
# shellcheck source=/dev/null
if [[ -f "$CONFIG_FILE" ]]; then set -a; . "$CONFIG_FILE"; set +a; fi

BACKUP_DIR="${BACKUP_DIR:-/root/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
MIN_KEEP="${MIN_KEEP:-7}"
REMOTE_RETENTION_DAYS="${REMOTE_RETENTION_DAYS:-90}"
BACKUP_REMOTE="${BACKUP_REMOTE:-}"
BACKUP_PING_URL="${BACKUP_PING_URL:-}"
BACKUP_MEDIA="${BACKUP_MEDIA:-1}"
DB_USER="${DB_USER:-poultrytrack}"
DB_NAME="${DB_NAME:-poultrytrack}"
COMPOSE="docker compose -f $APP_DIR/docker-compose.yml"
# Overridable for tests / non-docker installs.
PG_DUMP_CMD="${PG_DUMP_CMD:-$COMPOSE exec -T db pg_dump -U $DB_USER -d $DB_NAME}"
MEDIA_TAR_CMD="${MEDIA_TAR_CMD:-$COMPOSE exec -T backend tar -C /app -cf - media}"

STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
DB_FILE="poultrytrack_${STAMP}.sql.gz"
MEDIA_FILE="media_${STAMP}.tar.gz"
STATUS_FILE="$BACKUP_DIR/last_backup.json"
OFFSITE="skipped"
MEDIA_OUT=""

log() { echo "[$(date '+%F %T')] $*"; }

ping_url() {  # $1 = "" for success, "/fail" for failure
    [[ -n "$BACKUP_PING_URL" ]] || return 0
    curl -fsS -m 10 --retry 3 -o /dev/null "${BACKUP_PING_URL}$1" || log "WARN: ping to monitoring URL failed"
}

write_status() {  # $1 status, $2 message
    local db_bytes=0
    [[ -f "$BACKUP_DIR/$DB_FILE" ]] && db_bytes=$(stat -c %s "$BACKUP_DIR/$DB_FILE")
    cat > "$STATUS_FILE.tmp" <<JSON
{"timestamp": "$(date -Iseconds)", "status": "$1", "message": "$2",
 "db_file": "$([[ -f "$BACKUP_DIR/$DB_FILE" ]] && echo "$DB_FILE")", "db_bytes": $db_bytes,
 "media_file": "$MEDIA_OUT", "offsite": "$OFFSITE"}
JSON
    mv "$STATUS_FILE.tmp" "$STATUS_FILE"
}

fail() {
    log "❌ BACKUP FAILED: $1"
    rm -f "$BACKUP_DIR"/*.partial
    write_status "failed" "$1"
    ping_url "/fail"
    exit 1
}
trap 'fail "unexpected error on line $LINENO"' ERR

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
umask 077

# One backup at a time.
exec 9>"$BACKUP_DIR/.backup.lock"
if ! flock -n 9; then
    log "Another backup is already running — exiting."
    exit 1
fi

# ── 1. Database ────────────────────────────────────────────────────────────
# --clean --if-exists makes the dump drop-and-recreate on restore, so it can
# be restored over a live database without duplicate/conflict errors.
log "→ Dumping database…"
if ! bash -c "$PG_DUMP_CMD --clean --if-exists --no-owner" | gzip -6 > "$BACKUP_DIR/$DB_FILE.partial"; then
    fail "pg_dump failed"
fi
gzip -t "$BACKUP_DIR/$DB_FILE.partial" || fail "database archive is corrupt"
if ! gunzip -c "$BACKUP_DIR/$DB_FILE.partial" | tail -n 5 | grep -q "PostgreSQL database dump complete"; then
    fail "database dump is incomplete (no completion marker)"
fi
mv "$BACKUP_DIR/$DB_FILE.partial" "$BACKUP_DIR/$DB_FILE"
(cd "$BACKUP_DIR" && sha256sum "$DB_FILE" > "$DB_FILE.sha256")
log "✅ Database: $DB_FILE ($(du -h "$BACKUP_DIR/$DB_FILE" | cut -f1))"

# ── 2. Uploaded documents (media volume) ──────────────────────────────────
if [[ "$BACKUP_MEDIA" == "1" ]]; then
    log "→ Archiving uploaded documents…"
    if ! bash -c "$MEDIA_TAR_CMD" | gzip -6 > "$BACKUP_DIR/$MEDIA_FILE.partial"; then
        fail "media archive failed (database backup $DB_FILE was kept)"
    fi
    gzip -t "$BACKUP_DIR/$MEDIA_FILE.partial" || fail "media archive is corrupt"
    mv "$BACKUP_DIR/$MEDIA_FILE.partial" "$BACKUP_DIR/$MEDIA_FILE"
    (cd "$BACKUP_DIR" && sha256sum "$MEDIA_FILE" > "$MEDIA_FILE.sha256")
    MEDIA_OUT="$MEDIA_FILE"
    log "✅ Documents: $MEDIA_FILE ($(du -h "$BACKUP_DIR/$MEDIA_FILE" | cut -f1))"
fi

# ── 3. Local retention (never below MIN_KEEP newest) ──────────────────────
prune() {  # $1 = glob prefix, e.g. poultrytrack_  / media_
    local i=0 f
    # Names embed a sortable timestamp → reverse name order = newest first.
    while IFS= read -r f; do
        i=$((i + 1))
        (( i <= MIN_KEEP )) && continue
        if [[ -n "$(find "$f" -maxdepth 0 -mtime +"$RETENTION_DAYS" 2>/dev/null)" ]]; then
            rm -f "$f" "$f.sha256"
            log "🗑️  Pruned $(basename "$f")"
        fi
    done < <(ls -1 "$BACKUP_DIR"/"$1"*.gz 2>/dev/null | sort -r)
}
prune "poultrytrack_"
prune "media_"

# ── 4. Off-box copy ───────────────────────────────────────────────────────
if [[ -z "$BACKUP_REMOTE" ]] && command -v rclone >/dev/null 2>&1 && rclone listremotes 2>/dev/null | grep -q "^onedrive:$"; then
    BACKUP_REMOTE="onedrive:PoultryTrack-Backups"   # backwards compatible with the old script
fi
if [[ -n "$BACKUP_REMOTE" ]]; then
    command -v rclone >/dev/null 2>&1 || fail "BACKUP_REMOTE is set but rclone is not installed"
    log "→ Copying off-box to $BACKUP_REMOTE…"
    files=("$DB_FILE" "$DB_FILE.sha256")
    [[ -n "$MEDIA_OUT" ]] && files+=("$MEDIA_OUT" "$MEDIA_OUT.sha256")
    for f in "${files[@]}"; do
        rclone copy "$BACKUP_DIR/$f" "$BACKUP_REMOTE/" || { OFFSITE="failed"; fail "off-box copy of $f failed"; }
    done
    OFFSITE="ok"
    if [[ "$REMOTE_RETENTION_DAYS" != "0" ]]; then
        rclone delete --min-age "${REMOTE_RETENTION_DAYS}d" "$BACKUP_REMOTE/" || log "WARN: remote prune failed"
    fi
    log "☁️  Off-box copy done"
else
    log "ℹ️  No off-box destination configured (BACKUP_REMOTE) — backup is on this server only."
fi

write_status "ok" "backup complete"
ping_url ""
log "✅ Backup complete. Local backups: $(ls -1 "$BACKUP_DIR"/poultrytrack_*.sql.gz 2>/dev/null | wc -l)"
