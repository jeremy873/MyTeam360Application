# MyTeam360 — Security & Deployment Guide

## Three Access Modes

You can run MyTeam360 in three security configurations. Each builds on the last.

### Mode 1: Standard (nginx + HTTPS)
**Who it's for:** Public app at myteam360.ai, anyone can sign up.

```bash
bash deploy/deploy.sh myteam360.ai
```

What you get:
- HTTPS via Let's Encrypt
- nginx reverse proxy
- Firewall (ports 22, 80, 443 only)
- Rate limiting and DLP built into the app

### Mode 2: Cloudflare Tunnel (recommended)
**Who it's for:** Public app, but with zero exposed ports and DDoS protection.

```bash
# First deploy normally
bash deploy/deploy.sh myteam360.ai

# Then add the tunnel
bash deploy/setup-tunnel.sh
```

What you get (on top of Mode 1):
- Server IP completely hidden
- Zero open ports (close 80/443 after tunnel setup)
- Free Cloudflare DDoS protection
- Bot filtering
- Optional: Zero Trust email verification before login page loads
- Optional: Country-level blocking

After tunnel is running, lock down the firewall:
```bash
sudo ufw default deny incoming
sudo ufw allow 22/tcp
sudo ufw reload
```

### Mode 3: Tailscale Private Network
**Who it's for:** Private access only — you, your team, select beta users.

```bash
# First deploy normally
bash deploy/deploy.sh myteam360.ai

# Then add private network
bash deploy/setup-tailscale.sh
```

What you get:
- App only reachable from authorized devices
- WireGuard encryption (military-grade VPN)
- Invisible to the public internet
- Works from any device with Tailscale installed

You can run Cloudflare Tunnel AND Tailscale at the same time:
- Public users → myteam360.ai (through Cloudflare)
- VIP/admin access → http://100.x.x.x:8000 (through Tailscale)


## Combining Modes

The most secure production setup uses all three:

```
Public users → Cloudflare Tunnel → nginx → gunicorn → MyTeam360
Your devices → Tailscale VPN → direct → gunicorn → MyTeam360
```

Public users get Cloudflare's protection layer.
You get direct, fast, private access from anywhere.


## Security Built Into the App

Regardless of which mode you choose, MyTeam360 has:

- **AES-256 encryption at rest** — all conversations encrypted in the database
- **DLP scanning** — blocks messages containing SSNs, credit cards, API keys
- **MFA/TOTP** — any authenticator app (Google, Authy, etc.)
- **Rate limiting** — brute force protection on login
- **Account lockout** — auto-locks after failed attempts
- **Password policies** — configurable complexity requirements
- **Audit logging** — every action tracked with IP, timestamp, user
- **Session management** — configurable expiry, one-click revoke
- **API token system** — scoped tokens with expiration
- **IP allowlisting** — restrict access to specific IPs (optional)


## Google OAuth Security

OAuth tokens are stored server-side. The callback flow:
1. User clicks "Continue with Google"
2. Redirected to Google's consent screen
3. Google redirects back to https://myteam360.ai/api/auth/google/callback
4. Server exchanges code for token (server-to-server, never exposed)
5. User account created/linked, session token issued
6. Redirect to app

State parameter prevents CSRF. Tokens are short-lived.


## Environment Variables

All secrets live in `/opt/myteam360/.env` with permissions `600` (owner-only read).

```bash
sudo nano /opt/myteam360/.env     # Edit
sudo systemctl restart myteam360  # Apply changes
```

Never commit `.env` to git. Never share it. The deploy script generates a random SECRET_KEY automatically.
