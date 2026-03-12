#!/bin/bash
# ══════════════════════════════════════════════════════════════
# MyTeam360 — VPS Deploy Script
# Sets up a fresh Ubuntu 22+ server with nginx, SSL, and the app
#
# Usage:
#   1. Get a VPS (DigitalOcean, Linode, Vultr, Hetzner, etc.)
#   2. Point your domain's DNS A record to the server IP
#   3. SSH in:  ssh root@your-server-ip
#   4. Upload this package:  scp -r myteam360-package root@your-server-ip:/tmp/
#   5. Run:     bash /tmp/myteam360-package/deploy/deploy.sh yourdomain.com
#
# What this does:
#   - Installs Python 3, pip, nginx, certbot
#   - Creates /opt/myteam360 with your app
#   - Sets up gunicorn as a systemd service
#   - Configures nginx with HTTPS (Let's Encrypt)
#   - Starts everything
#
# After deploy, set up Google OAuth:
#   1. Go to https://console.cloud.google.com/apis/credentials
#   2. Create OAuth 2.0 Client ID → Web application
#   3. Authorized redirect URI: https://yourdomain.com/api/auth/google/callback
#   4. Edit /opt/myteam360/.env → set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET
#   5. sudo systemctl restart myteam360
# ══════════════════════════════════════════════════════════════

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
CYAN="\033[0;36m"
NC="\033[0m"

DOMAIN="${1}"
APP_DIR="/opt/myteam360"
DATA_DIR="/opt/myteam360/data"
USER="myteam360"

if [ -z "$DOMAIN" ]; then
  echo -e "${RED}Usage: bash deploy.sh yourdomain.com${NC}"
  echo "  Make sure the domain's DNS A record points to this server first."
  exit 1
fi

echo -e "${BOLD}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║    MyTeam360 — Production Deploy                     ║"
echo "║    Domain: ${DOMAIN}                                 "
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

step() { echo -e "\n${CYAN}${BOLD}[$1/7]${NC} ${BOLD}$2${NC}"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }

# ─────────────────────────────────────────────────
step 1 "Installing system packages..."
# ─────────────────────────────────────────────────

apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv nginx certbot python3-certbot-nginx ufw > /dev/null 2>&1
ok "Python 3, nginx, certbot installed"

# ─────────────────────────────────────────────────
step 2 "Setting up app directory..."
# ─────────────────────────────────────────────────

# Create service user
id -u $USER &>/dev/null || useradd -r -s /bin/false $USER
ok "Service user: $USER"

# Copy app files
mkdir -p "$APP_DIR" "$DATA_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(dirname "$SCRIPT_DIR")"

cp "$PACKAGE_DIR/app.py" "$APP_DIR/"
cp -r "$PACKAGE_DIR/core" "$APP_DIR/"
cp -r "$PACKAGE_DIR/templates" "$APP_DIR/"
cp -r "$PACKAGE_DIR/static" "$APP_DIR/"
ok "App files copied to $APP_DIR"

# Python virtual environment
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q flask flask-cors cryptography qrcode requests pillow gunicorn stripe
ok "Python venv created + dependencies installed"

# Environment file
if [ ! -f "$APP_DIR/.env" ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  cat > "$APP_DIR/.env" << ENVEOF
APP_URL=https://${DOMAIN}
PORT=8000
BIND_HOST=127.0.0.1
SECRET_KEY=${SECRET}
DEBUG=false
DB_PATH=${DATA_DIR}/myteam360.db
SESSION_HOURS=24

# Google OAuth — fill these in after creating credentials at:
# https://console.cloud.google.com/apis/credentials
# Redirect URI: https://${DOMAIN}/api/auth/google/callback
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# AI Providers
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Stripe Billing — set up at https://dashboard.stripe.com
STRIPE_SECRET_KEY=
STRIPE_PRICE_MONTHLY=
STRIPE_PRICE_ANNUAL=
STRIPE_WEBHOOK_SECRET=
ENVEOF
  ok "Created .env (edit later for OAuth + API keys)"
else
  ok ".env already exists — keeping it"
fi

chown -R $USER:$USER "$APP_DIR"
chmod 600 "$APP_DIR/.env"

# ─────────────────────────────────────────────────
step 3 "Creating systemd service..."
# ─────────────────────────────────────────────────

cat > /etc/systemd/system/myteam360.service << SVCEOF
[Unit]
Description=MyTeam360 AI Platform
After=network.target

[Service]
Type=exec
User=${USER}
Group=${USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/gunicorn \
    --bind 127.0.0.1:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile /var/log/myteam360/access.log \
    --error-logfile /var/log/myteam360/error.log \
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

mkdir -p /var/log/myteam360
chown $USER:$USER /var/log/myteam360

systemctl daemon-reload
systemctl enable myteam360 --quiet
ok "Systemd service created"

# ─────────────────────────────────────────────────
step 4 "Configuring nginx..."
# ─────────────────────────────────────────────────

cat > /etc/nginx/sites-available/myteam360 << NGEOF
server {
    listen 80;
    server_name ${DOMAIN};

    # Redirect all HTTP to HTTPS (certbot will handle this later)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket support (for future use)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts for long AI responses
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }

    # Static files — served directly by nginx (faster)
    location /static/ {
        alias ${APP_DIR}/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Max upload size
    client_max_body_size 20M;
}
NGEOF

ln -sf /etc/nginx/sites-available/myteam360 /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

nginx -t 2>/dev/null
systemctl restart nginx
ok "nginx configured for ${DOMAIN}"

# ─────────────────────────────────────────────────
step 5 "Setting up HTTPS with Let's Encrypt..."
# ─────────────────────────────────────────────────

# Configure firewall
ufw allow 22/tcp > /dev/null 2>&1
ufw allow 80/tcp > /dev/null 2>&1
ufw allow 443/tcp > /dev/null 2>&1
ufw --force enable > /dev/null 2>&1
ok "Firewall configured (22, 80, 443)"

echo "  Requesting SSL certificate for ${DOMAIN}..."
echo "  (If this fails, make sure DNS is pointing to this server)"
echo ""

certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos \
  --register-unsafely-without-email --redirect 2>&1 | tail -3

ok "HTTPS enabled"

# ─────────────────────────────────────────────────
step 6 "Starting MyTeam360..."
# ─────────────────────────────────────────────────

systemctl start myteam360

# Wait for it to come up
echo "  Waiting for server..."
for i in {1..15}; do
  if curl -sf http://127.0.0.1:8000/ > /dev/null 2>&1; then
    ok "Server is running"
    break
  fi
  sleep 1
done

# ─────────────────────────────────────────────────
step 7 "Done!"
# ─────────────────────────────────────────────────

echo ""
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  MyTeam360 is LIVE!${NC}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Your app:${NC}  https://${DOMAIN}"
echo -e "  ${BOLD}Login:${NC}     admin@localhost / admin123"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo ""
echo "  1. ${YELLOW}Change the default password${NC} after first login"
echo ""
echo "  2. ${YELLOW}Set up Google OAuth:${NC}"
echo "     → Go to https://console.cloud.google.com/apis/credentials"
echo "     → Create OAuth 2.0 Client ID (Web application)"
echo "     → Authorized redirect URI: https://${DOMAIN}/api/auth/google/callback"
echo "     → Edit ${APP_DIR}/.env"
echo "     → Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET"
echo "     → sudo systemctl restart myteam360"
echo ""
echo "  3. ${YELLOW}Add an AI provider key:${NC}"
echo "     → Edit ${APP_DIR}/.env"
echo "     → Set ANTHROPIC_API_KEY or OPENAI_API_KEY"
echo "     → sudo systemctl restart myteam360"
echo ""
echo "  4. ${YELLOW}Set up Stripe billing:${NC}"
echo "     → Go to https://dashboard.stripe.com"
echo "     → Get API keys → set STRIPE_SECRET_KEY"
echo "     → Create a Product with two prices:"
echo "       Monthly: \$15/mo recurring"
echo "       Annual: \$129/yr recurring"
echo "     → Set STRIPE_PRICE_MONTHLY and STRIPE_PRICE_ANNUAL"
echo "     → Add webhook: https://${DOMAIN}/api/billing/webhook"
echo "       Events: checkout.session.completed,"
echo "               customer.subscription.updated,"
echo "               customer.subscription.deleted,"
echo "               invoice.payment_failed"
echo "     → Set STRIPE_WEBHOOK_SECRET"
echo "     → sudo systemctl restart myteam360"
echo ""
echo -e "  ${BOLD}Useful commands:${NC}"
echo "     sudo systemctl status myteam360    # Check status"
echo "     sudo systemctl restart myteam360   # Restart"
echo "     sudo journalctl -u myteam360 -f    # Live logs"
echo "     sudo tail -f /var/log/myteam360/error.log"
echo "     sudo nano ${APP_DIR}/.env          # Edit config"
echo ""
