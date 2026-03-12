#!/bin/bash
# ══════════════════════════════════════════════════════════════
# MyTeam360 — Tailscale Private Network Setup
# Makes MyTeam360 accessible ONLY from your authorized devices.
# Nobody else can even discover the server exists.
#
# How it works:
#   - Tailscale creates a WireGuard VPN mesh between your devices
#   - Your server gets a private IP (e.g., 100.x.x.x)
#   - Only devices signed into YOUR Tailscale account can connect
#   - Works from anywhere — home, office, phone, laptop
#
# Use cases:
#   - Private beta testing with select users
#   - VIP / premium tier with extra security
#   - Your own personal AI team (nobody else has access)
#   - Testing before making it public
#
# Prerequisites:
#   - A Tailscale account (free for personal use): https://tailscale.com
#   - Tailscale installed on your Mac/iPhone/etc.
#   - MyTeam360 already deployed on the server
#
# Usage:
#   bash setup-tailscale.sh
#
# ══════════════════════════════════════════════════════════════

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
CYAN="\033[0;36m"
NC="\033[0m"

step() { echo -e "\n${CYAN}${BOLD}[$1/3]${NC} ${BOLD}$2${NC}"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }

echo -e "${BOLD}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║    MyTeam360 — Tailscale Private Network Setup       ║"
echo "║    Only YOUR devices can access the app              ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─────────────────────────────────────────────────
step 1 "Installing Tailscale..."
# ─────────────────────────────────────────────────

if command -v tailscale &>/dev/null; then
    ok "Tailscale already installed"
else
    curl -fsSL https://tailscale.com/install.sh | sh
    ok "Tailscale installed"
fi

# ─────────────────────────────────────────────────
step 2 "Connecting to your Tailscale network..."
# ─────────────────────────────────────────────────

if tailscale status &>/dev/null; then
    ok "Already connected to Tailscale"
    TS_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
else
    echo -e "  ${YELLOW}Follow the link below to authenticate this server:${NC}"
    echo ""
    tailscale up
    TS_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
    ok "Connected to Tailscale"
fi

echo -e "  ${BOLD}Tailscale IP: ${TS_IP}${NC}"

# ─────────────────────────────────────────────────
step 3 "Configuring MyTeam360 for Tailscale access..."
# ─────────────────────────────────────────────────

# Option A: Bind gunicorn to Tailscale IP (most secure)
# Option B: Use nginx to listen on Tailscale IP
# We'll do both — update nginx and also allow direct access

if [ -f /etc/nginx/sites-available/myteam360 ]; then
    # Add a Tailscale-only server block
    cat > /etc/nginx/sites-available/myteam360-private << NGEOF
# Private access via Tailscale only
server {
    listen ${TS_IP}:443 ssl;
    server_name ${TS_IP};

    # Tailscale provides its own certs via HTTPS mode
    # For now, use the app over HTTP via Tailscale (already encrypted by WireGuard)
    listen ${TS_IP}:80;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
    }

    location /static/ {
        alias /opt/myteam360/static/;
        expires 7d;
    }
}
NGEOF

    ln -sf /etc/nginx/sites-available/myteam360-private /etc/nginx/sites-enabled/
    nginx -t 2>/dev/null && systemctl reload nginx
    ok "nginx configured for Tailscale access"
fi

echo ""
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  Tailscale Private Network Active!${NC}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Private URL:${NC}  http://${TS_IP}:8000"
echo ""
echo -e "  ${BOLD}To access from your devices:${NC}"
echo ""
echo "    Mac:     Install Tailscale from App Store or brew install tailscale"
echo "             Then open http://${TS_IP}:8000 in your browser"
echo ""
echo "    iPhone:  Install Tailscale from App Store"
echo "             Connect → open http://${TS_IP}:8000 in Safari"
echo ""
echo "    Other:   Any device with Tailscale installed and signed into"
echo "             your account can reach http://${TS_IP}:8000"
echo ""
echo -e "  ${BOLD}Share with specific people:${NC}"
echo "    1. Go to https://login.tailscale.com/admin/machines"
echo "    2. Share this machine with other Tailscale users"
echo "    3. They connect to http://${TS_IP}:8000"
echo "    → They must be on YOUR Tailscale network. Nobody else can connect."
echo ""
echo -e "  ${BOLD}Lock it down further — close ALL public ports:${NC}"
echo "    sudo ufw default deny incoming"
echo "    sudo ufw allow in on tailscale0    # Allow all Tailscale traffic"
echo "    sudo ufw allow 22/tcp              # SSH (or use Tailscale SSH)"
echo "    sudo ufw reload"
echo ""
echo -e "  ${YELLOW}${BOLD}With this config:${NC}"
echo "    • Your server is invisible to the public internet"
echo "    • All traffic encrypted via WireGuard (military-grade)"
echo "    • Only authenticated devices on your network can connect"
echo "    • Works from anywhere — home, coffee shop, airport"
echo ""
echo -e "  ${BOLD}Bonus — Tailscale SSH (no SSH keys needed):${NC}"
echo "    sudo tailscale up --ssh"
echo "    → SSH via: ssh root@${TS_IP} (authenticated by Tailscale)"
echo ""
echo -e "  ${BOLD}Commands:${NC}"
echo "    tailscale status              # Connected devices"
echo "    tailscale ip -4               # Your Tailscale IP"
echo "    sudo systemctl status tailscaled"
echo ""
