#!/usr/bin/env bash
# PoultryTrack — prove the latest backup actually restores (E9)
#
# Restores a backup into a throw-away PostgreSQL container (never touches the
# live database), checks the core tables have data, then deletes the
# container. Run weekly by deploy/systemd/poultrytrack-backup-verify.timer.
#
# Usage: bash deploy/verify-backup.sh [backup.sql.gz | latest]
# Env:   BACKUP_VERIFY_PING_URL  optional dead-man's-switch URL (/fail on failure)
#        VERIFY_DB_URL           restore into this existing scratch DB instead of
#                                a docker container (used by the test suite)
set -Eeuo pipefail

CONFIG_FILE="${BACKUP_CONFIG:-/etc/poultrytrack/backup.env}"
# shellcheck source=/dev/null
if [[ -f "$CONFIG_FILE" ]]; then set -a; . "$CONFIG_FILE"; set +a; fi

BACKUP_DIR="${BACKUP_DIR:-/root/backups}"
PING="${BACKUP_VERIFY_PING_URL:-}"
PG_IMAGE="${VERIFY_PG_IMAGE:-postgres:16-alpine}"
CONTAINER="poultrytrack-restore-test-$$"
STATUS_FILE="$BACKUP_DIR/last_verify.json"
TARGET="${1:-latest}"

log() { echo "[$(date '+%F %T')] $*"; }
status() {
    cat > "$STATUS_FILE.tmp" <<JSON
{"timestamp": "$(date -Iseconds)", "status": "$1", "backup": "$(basename "${TARGET:-}")", "message": "$2"}
JSON
    mv "$STATUS_FILE.tmp" "$STATUS_FILE"
}
ping_url() { [[ -n "$PING" ]] && curl -fsS -m 10 --retry 3 -o /dev/null "${PING}$1" || true; }
cleanup() { [[ -z "${VERIFY_DB_URL:-}" ]] && docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
fail() { log "❌ RESTORE TEST FAILED: $1"; status "failed" "$1"; ping_url "/fail"; exit 1; }
trap cleanup EXIT
trap 'fail "unexpected error on line $LINENO"' ERR

if [[ "$TARGET" == "latest" ]]; then
    TARGET="$(ls -1 "$BACKUP_DIR"/poultrytrack_*.sql.gz 2>/dev/null | sort -r | head -1 || true)"
    [[ -n "$TARGET" ]] || fail "no backups found in $BACKUP_DIR"
fi
[[ -f "$TARGET" ]] || fail "file not found: $TARGET"
log "→ Verifying $(basename "$TARGET")"

if [[ -f "$TARGET.sha256" ]]; then
    (cd "$(dirname "$TARGET")" && sha256sum -c --status "$(basename "$TARGET").sha256") || fail "checksum mismatch"
fi
gzip -t "$TARGET" 2>/dev/null || fail "archive is corrupt"

if [[ -n "${VERIFY_DB_URL:-}" ]]; then
    PSQL=(psql "$VERIFY_DB_URL")
else
    log "→ Starting throw-away PostgreSQL ($PG_IMAGE)…"
    docker run -d --rm --name "$CONTAINER" -e POSTGRES_PASSWORD=verify -e POSTGRES_USER=poultrytrack \
        -e POSTGRES_DB=poultrytrack "$PG_IMAGE" >/dev/null
    for _ in $(seq 1 60); do
        docker exec "$CONTAINER" pg_isready -U poultrytrack -d poultrytrack >/dev/null 2>&1 && break
        sleep 1
    done
    sleep 2   # the image restarts postgres once after init
    docker exec "$CONTAINER" pg_isready -U poultrytrack -d poultrytrack >/dev/null 2>&1 || fail "scratch PostgreSQL did not start"
    PSQL=(docker exec -i "$CONTAINER" psql -U poultrytrack -d poultrytrack)
fi

log "→ Restoring into scratch database…"
gunzip -c "$TARGET" | "${PSQL[@]}" -q -v ON_ERROR_STOP=1 --single-transaction >/dev/null 2>"$BACKUP_DIR/.verify_err" \
    || fail "restore errored: $(tail -n 3 "$BACKUP_DIR/.verify_err" | tr '\n' ' ')"
rm -f "$BACKUP_DIR/.verify_err"

q() { "${PSQL[@]}" -Atc "$1" 2>/dev/null; }
MIGRATIONS="$(q 'select count(*) from django_migrations' || echo 0)"
[[ "${MIGRATIONS:-0}" -gt 0 ]] || fail "restored database has no django_migrations — not an app backup?"
USERS="$(q 'select count(*) from auth_user' || echo 0)"
[[ "${USERS:-0}" -gt 0 ]] || fail "restored database has no users"
SUMMARY="users=$USERS"
for t in core_farm core_flock core_bill core_dailyentry core_sale; do
    n="$(q "select count(*) from $t" || echo "missing")"
    SUMMARY="$SUMMARY ${t#core_}=$n"
done
log "✅ Restore test passed: $SUMMARY"
status "ok" "$SUMMARY"
ping_url ""
