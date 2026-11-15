#!/usr/bin/env bash
# PoultryTrack — run the PRODUCTION build on this machine at http://localhost:8080
#
#   bash deploy/local.sh up       build + start (first run creates .env.local)
#   bash deploy/local.sh status   containers + health
#   bash deploy/local.sh logs     follow backend logs
#   bash deploy/local.sh down     stop (data kept)
#   bash deploy/local.sh reset    stop AND delete local database + uploads
#
# Same images as the server (DEBUG=False, Postgres 16, gunicorn, nginx), plain
# http only. Needs Docker Desktop running.
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_FILE=.env.local
URL=http://localhost:8080
DC=(docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.local.yml)

die() { echo "❌ $*" >&2; exit 1; }
command -v docker >/dev/null || die "Docker is not installed — install Docker Desktop for Mac."
docker info >/dev/null 2>&1 || die "Docker is not running — open Docker Desktop and wait until it says 'running'."

make_env() {
    [[ -f "$ENV_FILE" ]] && return
    rand() { openssl rand -base64 48 | tr -d '/+=\n' | cut -c1-"$1"; }
    umask 077
    cat > "$ENV_FILE" <<ENV
# Local-only secrets (git-ignored). Delete this file to regenerate.
SECRET_KEY=$(rand 50)
DB_PASSWORD=$(rand 24)
DOMAIN=localhost
SERVER_IP=127.0.0.1
ENV
    echo "→ Created $ENV_FILE with random local secrets"
}

wait_healthy() {
    echo -n "→ Waiting for the app to become healthy"
    for _ in $(seq 1 60); do
        if curl -fsS "$URL/api/health/" >/dev/null 2>&1; then echo " ✅"; return 0; fi
        echo -n "."; sleep 3
    done
    echo; echo "❌ Not healthy after 3 minutes. Recent backend logs:"
    "${DC[@]}" ps; "${DC[@]}" logs --tail 60 backend
    return 1
}

case "${1:-up}" in
    up)
        make_env
        echo "→ Building and starting (first build takes a few minutes)…"
        "${DC[@]}" up -d --build
        wait_healthy
        echo
        echo "  Open $URL"
        if curl -fsS "$URL/api/auth/check-setup/" 2>/dev/null | grep -q '"needs_setup": *true'; then
            echo "  Fresh database → you'll be asked to create the admin account."
        fi
        echo "  Health: $URL/api/health/    Django admin: $URL/admin/"
        echo "  To load a server backup:  BACKUP_DIR=<folder> bash deploy/restore.sh <file.sql.gz>"
        ;;
    status) "${DC[@]}" ps; curl -fsS "$URL/api/health/" && echo ;;
    logs)   "${DC[@]}" logs -f --tail 100 backend ;;
    down)   "${DC[@]}" down; echo "Stopped. Data is kept — 'up' brings it back." ;;
    reset)
        read -r -p "Delete the LOCAL database and uploads? Type 'yes': " ok
        [[ "$ok" == "yes" ]] || { echo "Cancelled."; exit 0; }
        "${DC[@]}" down -v; echo "Local data deleted." ;;
    *) sed -n '2,10p' "$0"; exit 1 ;;
esac
