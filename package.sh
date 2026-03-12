#!/bin/bash
# Package MyTeam360 for distribution
set -e

DIST="myteam360-package"
rm -rf "$DIST" "$DIST.zip"
mkdir -p "$DIST"

echo "Copying source..."
# Core Python
cp app.py "$DIST/"
cp -r core "$DIST/"
rm -rf "$DIST/core/__pycache__" "$DIST"/core/*.pyc

# Templates & Static
mkdir -p "$DIST/templates" "$DIST/static"
cp templates/app.html "$DIST/templates/"
cp templates/voice-chat.html "$DIST/templates/"
cp templates/native-bridge.js "$DIST/templates/"
cp static/logo.png "$DIST/static/"

# Docs
mkdir -p "$DIST/docs"
cp docs/MyTeam360_Setup_Guide.pdf "$DIST/docs/"
cp docs/MyTeam360_User_Guide.pdf "$DIST/docs/"
cp TEST_PLAN.md "$DIST/docs/"

# Native app (Tauri)
mkdir -p "$DIST/src-tauri/src"
cp src-tauri/src/main.rs "$DIST/src-tauri/src/"
cp src-tauri/Cargo.toml "$DIST/src-tauri/" 2>/dev/null || true
cp src-tauri/tauri.conf.json "$DIST/src-tauri/" 2>/dev/null || true

# Data directory (empty, will be created at runtime)
mkdir -p "$DIST/data"
echo "*.db" > "$DIST/data/.gitignore"
echo ".encryption_key" >> "$DIST/data/.gitignore"
echo "initial_credentials.txt" >> "$DIST/data/.gitignore"

# Startup scripts
cat > "$DIST/start.sh" << 'STARTSH'
#!/bin/bash
# MyTeam360 — Quick Start
# Usage: ./start.sh [api_key]

set -e
cd "$(dirname "$0")"

echo "╔══════════════════════════════════════════════════╗"
echo "║           MyTeam360 — Starting Up                ║"
echo "╚══════════════════════════════════════════════════╝"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required. Install from python.org"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python: $PY_VER"

# Install dependencies
echo "  Installing dependencies..."
pip3 install flask cryptography qrcode requests pillow --break-system-packages -q 2>/dev/null || \
pip3 install flask cryptography qrcode requests pillow -q 2>/dev/null || \
echo "  Warning: Some packages may need manual install"

# Set API key
if [ -n "$1" ]; then
    export ANTHROPIC_API_KEY="$1"
    echo "  API Key: provided (${#1} chars)"
elif [ -z "$ANTHROPIC_API_KEY" ]; then
    export ANTHROPIC_API_KEY="test"
    echo "  API Key: test mode (no real AI responses)"
fi

echo ""
echo "  Starting server..."
echo "  Dashboard: http://127.0.0.1:5000"
echo "  Voice Chat: http://127.0.0.1:5000/voice-chat"
echo ""
echo "  Default login: admin@localhost / admin123"
echo "  Press Ctrl+C to stop"
echo ""

python3 app.py
STARTSH
chmod +x "$DIST/start.sh"

cat > "$DIST/start.command" << 'STARTCMD'
#!/bin/bash
# Double-click this file on macOS to start MyTeam360
cd "$(dirname "$0")"
./start.sh
STARTCMD
chmod +x "$DIST/start.command"

# README
cat > "$DIST/README.md" << 'README'
# MyTeam360 — AI-Powered Workplace Platform

## Quick Start (macOS)

**Option A: Double-click** `start.command` in Finder.

**Option B: Terminal**
```bash
cd myteam360-package
./start.sh
```

**Option C: With a real API key**
```bash
./start.sh sk-ant-your-real-key-here
```

Then open **http://127.0.0.1:5000** in Chrome.

## What's Inside

```
myteam360-package/
├── start.sh              ← Start the server (Terminal)
├── start.command          ← Start the server (double-click on Mac)
├── app.py                ← Main application (213 API routes)
├── core/                 ← 22 backend modules
│   ├── database.py       ← Schema (58 tables)
│   ├── providers.py      ← 6 AI provider integrations
│   ├── voice_chat.py     ← TTS providers, sentence chunking, sessions
│   ├── analytics.py      ← 6-pattern recommendation engine
│   ├── security_hardening.py ← Encryption, MFA, DLP, passwords
│   ├── features.py       ← Export, templates, quotas, branding
│   └── ...
├── templates/
│   ├── app.html          ← Main dashboard UI
│   └── voice-chat.html   ← Voice chat (pulsing orb)
├── static/
│   └── logo.png          ← Platform logo
├── docs/
│   ├── MyTeam360_Setup_Guide.pdf
│   ├── MyTeam360_User_Guide.pdf
│   └── TEST_PLAN.md
├── src-tauri/            ← Native macOS app (optional)
└── data/                 ← Created at runtime (DB, keys)
```

## Default Credentials

- **Email:** admin@localhost
- **Password:** admin123
- Change immediately after first login!

## Testing Without API Costs

Run with `ANTHROPIC_API_KEY=test` (the default). Everything works except
actual AI chat responses. Voice chat, security, templates, quotas, branding,
export — all fully functional.

## Documentation

- **docs/MyTeam360_Setup_Guide.pdf** — Installation & configuration
- **docs/MyTeam360_User_Guide.pdf** — Complete feature reference
- **docs/TEST_PLAN.md** — 48-test validation plan with curl commands

## Platform Stats

| Metric | Count |
|--------|-------|
| Lines of code | 14,179 |
| API endpoints | 213 |
| Database tables | 58 |
| Core modules | 22 |
| AI providers | 6 |
| Pre-built agents | 18 |
| Departments | 8 |
README

echo "Creating zip..."
cd /home/claude/myteam360
zip -r "$DIST.zip" "$DIST/" -x "*.pyc" "*__pycache__*" "*.db" > /dev/null

echo "Package ready: $(du -sh $DIST.zip | cut -f1)"
ls -la "$DIST.zip"
