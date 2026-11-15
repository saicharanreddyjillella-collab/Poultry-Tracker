#!/bin/bash
# PoultryTrack — Server Setup & Deploy Script
# Run this on your DigitalOcean droplet as root

set -e

echo "═══════════════════════════════════════"
echo "  PoultryTrack Server Setup"
echo "═══════════════════════════════════════"

# 1. Update system
echo "→ Updating system..."
apt-get update && apt-get upgrade -y

# 2. Install Docker
echo "→ Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 3. Install Docker Compose
echo "→ Installing Docker Compose..."
if ! command -v docker compose &> /dev/null; then
    apt-get install -y docker-compose-plugin
fi

# 4. Install Git
echo "→ Installing Git..."
apt-get install -y git

# 5. Clone repo
echo "→ Cloning repository..."
cd /root
if [ -d "Poultry-Tracker" ]; then
    cd Poultry-Tracker
    git pull
else
    git clone https://github.com/saicharanreddyjillella-collab/Poultry-Tracker.git
    cd Poultry-Tracker
fi

# 6. Create .env if not exists
if [ ! -f .env ]; then
    echo "→ Creating .env file..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(16))")
    cat > .env << ENVEOF
SECRET_KEY=${SECRET_KEY}
DB_PASSWORD=${DB_PASSWORD}
SERVER_IP=$(curl -s ifconfig.me)
DOMAIN=$(curl -s ifconfig.me)
# Optional error monitoring (E7): paste a Sentry DSN to enable
SENTRY_DSN=
ENVEOF
    echo "→ .env created with secure random keys"
fi

# 7. Build and start
echo "→ Building and starting services..."
docker compose up -d --build

# 8. Wait for DB to be ready
echo "→ Waiting for database..."
sleep 10

# 9. Create admin user (random strong password, shown once)
echo "→ Creating admin user..."
ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(12))")
if docker compose exec -T -e ADMIN_PASSWORD="$ADMIN_PASSWORD" backend python manage.py create_admin \
        | tee /dev/stderr | grep -q "created"; then
    ADMIN_LOGIN="admin / $ADMIN_PASSWORD   (shown once — save it, then change it)"
else
    ADMIN_LOGIN="admin user already existed — use your existing password"
fi

# 10. Automated, verified backups (daily 02:30 IST + weekly restore test)
echo "→ Installing automated backups..."
bash deploy/install-backups.sh || echo "⚠️  Backup install failed — run: bash deploy/install-backups.sh"

# 11. Show status
echo ""
echo "═══════════════════════════════════════"
echo "  ✅ PoultryTrack is LIVE!"
echo "═══════════════════════════════════════"
echo ""
echo "  URL: http://$(curl -s ifconfig.me)"
echo "  Login: $ADMIN_LOGIN"
echo ""
echo "  Backups: daily to /root/backups — add an off-box copy + alerts in"
echo "           /etc/poultrytrack/backup.env (see docs/BACKUPS.md)"
echo ""
echo "═══════════════════════════════════════"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f        # View logs"
echo "  docker compose restart        # Restart all"
echo "  docker compose down           # Stop all"
echo "  docker compose up -d --build  # Rebuild & start"
echo ""
