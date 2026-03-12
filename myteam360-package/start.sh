#!/bin/bash
set -e; cd "$(dirname "$0")"
echo "╔══════════════════════════════════════════════════╗"
echo "║           MyTeam360 — Starting Up                ║"
echo "╚══════════════════════════════════════════════════╝"
command -v python3 &>/dev/null || { echo "ERROR: Python 3 required"; exit 1; }
echo "  Python: $(python3 --version)"
pip3 install flask cryptography qrcode requests pillow --break-system-packages -q 2>/dev/null || pip3 install flask cryptography qrcode requests pillow -q 2>/dev/null || true
[ -n "$1" ] && export ANTHROPIC_API_KEY="$1" && echo "  API Key: provided" || { [ -z "$ANTHROPIC_API_KEY" ] && export ANTHROPIC_API_KEY="test" && echo "  API Key: test mode"; }
echo ""; echo "  Dashboard:  http://127.0.0.1:5000"; echo "  Voice Chat: http://127.0.0.1:5000/voice-chat"
echo "  Login:      admin@localhost / admin123"; echo "  Ctrl+C to stop"; echo ""
python3 app.py
