#!/bin/bash
# ══════════════════════════════════════════════════════════════
# MyTeam360 — Cloudflare Tunnel Setup
# Routes all traffic through Cloudflare's network.
# Your server exposes ZERO ports to the public internet.
#
# Benefits:
#   - No open ports (even port 80/443 can be closed)
#   - Free DDoS protection
#   - Bot filtering & rate limiting via Cloudflare dashboard
#   - Zero Trust access policies (require email verification)
#   - SSL handled by Cloudflare (no certbot needed)
#   - Hides your server's real IP address
#
# Prerequisites:
#   - A Cloudflare account (free): https://dash.cloudflare.com
#   - Your domain (myteam360.ai) added to Cloudflare
#   - MyTeam360 already deployed (deploy.sh or manually running)
#
# Usage:
#   bash setup-tunnel.sh
#
# ══════════════════════════════════════════════════════════════

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
NC="\033[0m"

step() { echo -e "\n${CYAN}${BOLD}[$1/4]${NC} ${BOLD}$2${NC}"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }

echo -e "${BOLD}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║    MyTeam360 — Cloudflare Tunnel Setup               ║"
echo "║    Zero-port, encrypted tunnel to Cloudflare         ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─────────────────────────────────────────────────
step 1 "Installing cloudflared..."
# ─────────────────────────────────────────────────

if command -v cloudflared &>/dev/null; then
    ok "cloudflared already installed ($(cloudflared --version 2>&1 | head -1))"
else
    echo "  Downloading cloudflared..."
    # Detect architecture
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb"
    elif [ "$ARCH" = "aarch64" ]; then
        URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb"
    else
        echo -e "  ${RED}Unsupported architecture: $ARCH${NC}"
        echo "  Download manually from: https://github.com/cloudflare/cloudflared/releases"
        exit 1
    fi
    curl -sL "$URL" -o /tmp/cloudflared.deb
    dpkg -i /tmp/cloudflared.deb > /dev/null 2>&1
    rm -f /tmp/cloudflared.deb
    ok "cloudflared installed"
fi

# ─────────────────────────────────────────────────
step 2 "Authenticating with Cloudflare..."
# ─────────────────────────────────────────────────

echo -e "  ${YELLOW}A browser window will open (or you'll get a URL to visit).${NC}"
echo -e "  ${YELLOW}Log into your Cloudflare account and authorize the tunnel.${NC}"
echo ""

if [ -f "$HOME/.cloudflared/cert.pem" ]; then
    ok "Already authenticated"
else
    cloudflared tunnel login
    ok "Authenticated with Cloudflare"
fi

# ─────────────────────────────────────────────────
step 3 "Creating tunnel..."
# ─────────────────────────────────────────────────

TUNNEL_NAME="myteam360"

# Check if tunnel already exists
if cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
    ok "Tunnel '$TUNNEL_NAME' already exists"
    TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}')
else
    cloudflared tunnel create "$TUNNEL_NAME"
    TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}')
    ok "Created tunnel: $TUNNEL_NAME (ID: $TUNNEL_ID)"
fi

# Create tunnel config
mkdir -p /etc/cloudflared

cat > /etc/cloudflared/config.yml << CFEOF
tunnel: ${TUNNEL_ID}
credentials-file: /root/.cloudflared/${TUNNEL_ID}.json

ingress:
  # Main app
  - hostname: myteam360.ai
    service: http://127.0.0.1:8000
    originRequest:
      noTLSVerify: true
      connectTimeout: 30s

  # Catch-all (required by cloudflared)
  - service: http_status:404
CFEOF

ok "Tunnel config created at /etc/cloudflared/config.yml"

# ─────────────────────────────────────────────────
step 4 "Setting up DNS & starting tunnel..."
# ─────────────────────────────────────────────────

echo "  Routing myteam360.ai through the tunnel..."
cloudflared tunnel route dns "$TUNNEL_NAME" myteam360.ai 2>/dev/null || {
    echo -e "  ${YELLOW}DNS route may already exist — that's fine${NC}"
}

# Install as system service
cloudflared service install 2>/dev/null || true
systemctl enable cloudflared --quiet 2>/dev/null || true
systemctl restart cloudflared

# Wait for tunnel
echo "  Waiting for tunnel to connect..."
sleep 5
if systemctl is-active cloudflared &>/dev/null; then
    ok "Tunnel is running!"
else
    echo -e "  ${YELLOW}Tunnel may still be starting. Check: systemctl status cloudflared${NC}"
fi

echo ""
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  Cloudflare Tunnel Active!${NC}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Your app:${NC}  https://myteam360.ai"
echo -e "  ${BOLD}Tunnel ID:${NC} ${TUNNEL_ID}"
echo ""
echo -e "  ${BOLD}What's protected:${NC}"
echo "    • Server IP is hidden (only Cloudflare knows it)"
echo "    • Zero open ports (you can close 80/443 in firewall)"
echo "    • Free DDoS protection"
echo "    • All traffic encrypted end-to-end"
echo ""
echo -e "  ${BOLD}Optional — close all public ports:${NC}"
echo "    sudo ufw default deny incoming"
echo "    sudo ufw allow 22/tcp    # SSH only"
echo "    sudo ufw reload"
echo ""
echo -e "  ${BOLD}Optional — add Zero Trust access control:${NC}"
echo "    1. Go to https://one.dash.cloudflare.com"
echo "    2. Access → Applications → Add Application"
echo "    3. Self-hosted → myteam360.ai"
echo "    4. Add policy: 'Require email ending in @yourdomain.com'"
echo "    → Users must verify their email before they even see the login page"
echo ""
echo -e "  ${BOLD}Commands:${NC}"
echo "    sudo systemctl status cloudflared    # Tunnel status"
echo "    sudo systemctl restart cloudflared   # Restart tunnel"
echo "    sudo cloudflared tunnel list         # List tunnels"
echo "    sudo journalctl -u cloudflared -f    # Live logs"
echo ""
