# MyTeam360 — Your AI Team

## Quick Start (local testing)
```bash
pip3 install flask flask-cors cryptography qrcode requests pillow
export PORT=8080
python3 app.py
```
Open http://127.0.0.1:8080 → Login: admin@localhost / admin123

## Deploy to VPS (production)
```bash
scp -r myteam360-package root@YOUR_SERVER_IP:/tmp/
ssh root@YOUR_SERVER_IP
bash /tmp/myteam360-package/deploy/deploy.sh myteam360.ai
```

## Secure Tunnel Options

### Cloudflare Tunnel (zero exposed ports, DDoS protection, free)
```bash
bash deploy/setup-tunnel.sh
```

### Tailscale Private Network (only your devices can access)
```bash
bash deploy/setup-tailscale.sh
```

See `deploy/SECURITY.md` for full details on all three security modes.

## Google OAuth Setup
1. https://console.cloud.google.com/apis/credentials
2. Create OAuth Client → Redirect URI: `https://myteam360.ai/api/auth/google/callback`
3. Add Client ID + Secret to `/opt/myteam360/.env`
4. `sudo systemctl restart myteam360`

## What's Inside
- 213 API endpoints, 22 modules, 18 AI agents, 8 departments
- Google OAuth + email/password auth
- BYOK: Anthropic, OpenAI, xAI, Google AI, Ollama
- Voice chat with per-agent TTS voices
- DLP scanning, AES encryption, MFA/TOTP
- Cloudflare Tunnel + Tailscale VPN support
- Conversation export, analytics, usage quotas
