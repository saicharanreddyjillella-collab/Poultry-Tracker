#!/usr/bin/env bash
# PoultryTrack — restore a backup (E9)
#
# Usage:
#   bash deploy/restore.sh latest                       # newest DB backup (+ its documents)
#   bash deploy/restore.sh /root/backups/poultrytrack_2026-11-15_02-30-00.sql.gz
#   bash deploy/restore.sh latest --no-media            # database only
#   bash deploy/restore.sh <file> --yes                 # no confirmation prompt
#
# Safety: verifies the checksum, takes a pre-restore backup of the current
# database, stops the backend while restoring, and restores in a single
# transaction (all-or-nothing). Documents from the same backup run are
# restored too when present.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$(dirname "$SCRIPT_DIR")}"
CONFIG_FILE="${BACKUP_CONFIG:-/etc/poultrytrack/backup.env}"
# shellcheck source=/dev/null
if [[ -f "$CONFIG_FILE" ]]; then set -a; . "$CONFIG_FILE"; set +a; fi

BACKUP_DIR="${BACKUP_DIR:-/root/backups}"
DB_USER="${DB_USER:-poultrytrack}"
DB_NAME="${DB_NAME:-poultrytrack}"
COMPOSE="docker compose -f $APP_DIR/docker-compose.yml"
PG_DUMP_CMD="${PG_DUMP_CMD:-$COMPOSE exec -T db pg_dump -U $DB_USER -d $DB_NAME}"
PSQL_CMD="${PSQL_CMD:-$COMPOSE exec -T db psql -U $DB_USER -d $DB_NAME}"
MEDIA_RESTORE_CMD="${MEDIA_RESTORE_CMD:-$COMPOSE exec -T backend sh -c 'mkdir -p /app/media && find /app/media -mindepth 1 -delete && tar -C /app -xf -'}"
STOP_CMD="${STOP_CMD:-$COMPOSE stop backend}"
START_CMD="${START_CMD:-$COMPOSE start backend}"

log() { echo "[$(date '+%F %T')] $*"; }
die() { log "❌ $*"; exit 1; }

TARGET="" ; ASSUME_YES=0 ; WITH_MEDIA=1
for arg in "$@"; do
    case "$arg" in
        --yes|-y) ASSUME_YES=1 ;;
        --no-media) WITH_MEDIA=0 ;;
        -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
        *) TARGET="$arg" ;;
    esac
done

if [[ -z "$TARGET" ]]; then
    sed -n '2,13p' "$0"
    echo; echo "Available backups:"
    ls -1t "$BACKUP_DIR"/poultrytrack_*.sql.gz 2>/dev/null | head -20 || true
    exit 1
fi
if [[ "$TARGET" == "latest" ]]; then
    TARGET="$(ls -1 "$BACKUP_DIR"/poultrytrack_*.sql.gz 2>/dev/null | sort -r | head -1 || true)"
    [[ -n "$TARGET" ]] || die "No backups found in $BACKUP_DIR"
fi
[[ -f "$TARGET" ]] || die "File not found: $TARGET"

# ── Verify before touching anything ───────────────────────────────────────
if [[ -f "$TARGET.sha256" ]]; then
    (cd "$(dirname "$TARGET")" && sha256sum -c --status "$(basename "$TARGET").sha256") \
        || die "Checksum mismatch — $TARGET is damaged. Not restoring."
    log "✓ Checksum OK"
else
    log "⚠️  No checksum file for this backup (older backup?) — checking archive only."
fi
gzip -t "$TARGET" || die "Archive is corrupt: $TARGET"

MEDIA_ARCHIVE=""
if [[ "$WITH_MEDIA" == "1" ]]; then
    stamp="$(basename "$TARGET" .sql.gz)"; stamp="${stamp#poultrytrack_}"
    candidate="$(dirname "$TARGET")/media_${stamp}.tar.gz"
    if [[ -f "$candidate" ]]; then
        if [[ -f "$candidate.sha256" ]]; then
            (cd "$(dirname "$candidate")" && sha256sum -c --status "$(basename "$candidate").sha256") \
                || die "Checksum mismatch on $candidate. Not restoring."
        fi
        MEDIA_ARCHIVE="$candidate"
    else
        log "ℹ️  No documents archive from the same run — restoring database only."
    fi
fi

echo
echo "⚠️  This REPLACES the current database${MEDIA_ARCHIVE:+ and uploaded documents} with:"
echo "    $TARGET"
[[ -n "$MEDIA_ARCHIVE" ]] && echo "    $MEDIA_ARCHIVE"
if [[ "$ASSUME_YES" != "1" ]]; then
    read -r -p "Type 'yes' to continue: " CONFIRM
    [[ "$CONFIRM" == "yes" ]] || { echo "Cancelled."; exit 0; }
fi

# ── Pre-restore safety copy ───────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"
SAFETY="$BACKUP_DIR/pre_restore_$(date +%Y-%m-%d_%H-%M-%S).sql.gz"
log "→ Saving current database to $(basename "$SAFETY") first…"
bash -c "$PG_DUMP_CMD --clean --if-exists --no-owner" | gzip > "$SAFETY" \
    || die "Could not take a pre-restore backup — aborting, nothing changed."

# ── Restore ───────────────────────────────────────────────────────────────
log "→ Stopping backend…"
bash -c "$STOP_CMD"
restart_backend() { log "→ Starting backend…"; bash -c "$START_CMD" || log "WARN: could not start backend"; }
trap restart_backend EXIT

log "→ Restoring database (single transaction)…"
if ! gunzip -c "$TARGET" | bash -c "$PSQL_CMD -q -v ON_ERROR_STOP=1 --single-transaction" > /dev/null; then
    die "Database restore failed and was rolled back — data is unchanged. (Safety copy: $SAFETY)"
fi
log "✅ Database restored"

if [[ -n "$MEDIA_ARCHIVE" ]]; then
    restart_backend; trap - EXIT          # documents are restored through the running backend container
    log "→ Restoring uploaded documents…"
    gunzip -c "$MEDIA_ARCHIVE" | bash -c "$MEDIA_RESTORE_CMD" || die "Documents restore failed (database was restored)."
    log "✅ Documents restored"
fi
log "Done. Safety copy of the previous data: $SAFETY"
