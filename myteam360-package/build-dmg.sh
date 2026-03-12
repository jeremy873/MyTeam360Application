#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  MyTeam360 — Build macOS DMG                                ║
# ║  Run this on your Mac to create MyTeam360.app + .dmg        ║
# ╚══════════════════════════════════════════════════════════════╝
#
# Prerequisites (this script will check and guide you):
#   - Xcode Command Line Tools
#   - Rust (rustup)
#   - Node.js 18+
#   - Tauri CLI
#
# Usage:
#   chmod +x build-dmg.sh
#   ./build-dmg.sh
#
# Output:
#   src-tauri/target/release/bundle/dmg/MyTeam360_1.0.0_aarch64.dmg
#   (or x64 depending on your Mac)

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
CYAN="\033[0;36m"
NC="\033[0m"

step() { echo -e "\n${CYAN}${BOLD}[$1/8]${NC} ${BOLD}$2${NC}"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           MyTeam360 — DMG Builder for macOS             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

cd "$(dirname "$0")"
ROOT=$(pwd)

# ─────────────────────────────────────────────────────────────
step 1 "Checking prerequisites..."
# ─────────────────────────────────────────────────────────────

MISSING=0

# Xcode CLI Tools
if xcode-select -p &>/dev/null; then
    ok "Xcode Command Line Tools"
else
    fail "Xcode Command Line Tools not found"
    echo "    Install with: xcode-select --install"
    MISSING=1
fi

# Rust
if command -v rustc &>/dev/null; then
    RUST_VER=$(rustc --version | awk '{print $2}')
    ok "Rust $RUST_VER"
else
    fail "Rust not found"
    echo "    Install with: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    echo "    Then restart your terminal and run this script again."
    MISSING=1
fi

# Node.js
if command -v node &>/dev/null; then
    NODE_VER=$(node --version)
    ok "Node.js $NODE_VER"
else
    fail "Node.js not found"
    echo "    Install with: brew install node"
    echo "    Or download from: https://nodejs.org"
    MISSING=1
fi

# Python 3
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version)
    ok "$PY_VER"
else
    fail "Python 3 not found"
    echo "    Install with: brew install python3"
    MISSING=1
fi

if [ $MISSING -eq 1 ]; then
    echo ""
    fail "Missing prerequisites. Install them and run this script again."
    exit 1
fi

# ─────────────────────────────────────────────────────────────
step 2 "Installing Tauri CLI..."
# ─────────────────────────────────────────────────────────────

if command -v cargo-tauri &>/dev/null || cargo tauri --version &>/dev/null 2>&1; then
    TAURI_VER=$(cargo tauri --version 2>/dev/null || echo "installed")
    ok "Tauri CLI ($TAURI_VER)"
else
    echo "  Installing tauri-cli via cargo (this takes 2-3 minutes first time)..."
    cargo install tauri-cli --version "^2"
    ok "Tauri CLI installed"
fi

# ─────────────────────────────────────────────────────────────
step 3 "Installing Python dependencies..."
# ─────────────────────────────────────────────────────────────

pip3 install flask cryptography qrcode requests pillow --break-system-packages -q 2>/dev/null || \
pip3 install flask cryptography qrcode requests pillow -q 2>/dev/null || \
warn "Some packages may need manual install"
ok "Python packages ready"

# ─────────────────────────────────────────────────────────────
step 4 "Generating macOS app icon (icon.icns)..."
# ─────────────────────────────────────────────────────────────

ICONSET="$ROOT/src-tauri/icons/MyTeam360.iconset"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"

# Source icon (use largest available)
SRC_ICON="$ROOT/static/logo.png"
if [ ! -f "$SRC_ICON" ]; then
    SRC_ICON="$ROOT/src-tauri/icons/icon.png"
fi

if [ -f "$SRC_ICON" ]; then
    # Generate all required sizes for macOS iconset
    sips -z 16 16     "$SRC_ICON" --out "$ICONSET/icon_16x16.png"      >/dev/null 2>&1
    sips -z 32 32     "$SRC_ICON" --out "$ICONSET/icon_16x16@2x.png"   >/dev/null 2>&1
    sips -z 32 32     "$SRC_ICON" --out "$ICONSET/icon_32x32.png"      >/dev/null 2>&1
    sips -z 64 64     "$SRC_ICON" --out "$ICONSET/icon_32x32@2x.png"   >/dev/null 2>&1
    sips -z 128 128   "$SRC_ICON" --out "$ICONSET/icon_128x128.png"    >/dev/null 2>&1
    sips -z 256 256   "$SRC_ICON" --out "$ICONSET/icon_128x128@2x.png" >/dev/null 2>&1
    sips -z 256 256   "$SRC_ICON" --out "$ICONSET/icon_256x256.png"    >/dev/null 2>&1
    sips -z 512 512   "$SRC_ICON" --out "$ICONSET/icon_256x256@2x.png" >/dev/null 2>&1
    sips -z 512 512   "$SRC_ICON" --out "$ICONSET/icon_512x512.png"    >/dev/null 2>&1
    sips -z 512 512   "$SRC_ICON" --out "$ICONSET/icon_512x512@2x.png" >/dev/null 2>&1

    # Convert iconset to icns
    iconutil -c icns "$ICONSET" -o "$ROOT/src-tauri/icons/icon.icns"
    rm -rf "$ICONSET"
    ok "Generated icon.icns from logo"
else
    warn "No source icon found — using default"
fi

# ─────────────────────────────────────────────────────────────
step 5 "Creating requirements.txt..."
# ─────────────────────────────────────────────────────────────

cat > "$ROOT/requirements.txt" << 'EOF'
flask>=3.0
cryptography>=42.0
qrcode>=7.4
requests>=2.31
pillow>=10.0
EOF
ok "requirements.txt created"

# ─────────────────────────────────────────────────────────────
step 6 "Preparing frontend for bundling..."
# ─────────────────────────────────────────────────────────────

# Tauri needs an index.html in the frontendDist directory
# Our app loads from the Python backend, but Tauri needs a placeholder
# that redirects once the backend is up
if [ ! -f "$ROOT/templates/index.html" ]; then
    cat > "$ROOT/templates/index.html" << 'HTMLEOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>MyTeam360</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0a0a0f;
            color: #e8e8f0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
        }
        .loader {
            text-align: center;
        }
        .orb {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: radial-gradient(circle at 35% 35%, #a78bfa, #7c5cfc, #4d3db5);
            margin: 0 auto 24px;
            animation: pulse 2s ease-in-out infinite;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 0.8; }
            50% { transform: scale(1.1); opacity: 1; }
        }
        h1 { font-size: 24px; margin-bottom: 8px; }
        p { color: #888; font-size: 14px; }
    </style>
</head>
<body>
    <div class="loader">
        <div class="orb"></div>
        <h1>MyTeam360</h1>
        <p>Starting up...</p>
    </div>
    <script>
        // The Tauri Rust backend will navigate us to the Python server
        // once it's ready. This is just a loading screen.
        async function waitForBackend() {
            const ports = [5000, 5001, 5002, 5003, 5004, 5005];
            for (let attempt = 0; attempt < 60; attempt++) {
                for (const port of ports) {
                    try {
                        const resp = await fetch(`http://127.0.0.1:${port}/api/status`);
                        if (resp.ok) {
                            window.location.replace(`http://127.0.0.1:${port}`);
                            return;
                        }
                    } catch {}
                }
                await new Promise(r => setTimeout(r, 500));
            }
            document.querySelector('p').textContent = 'Backend failed to start. Check Console for errors.';
        }
        // Only poll if Tauri hasn't already navigated us
        setTimeout(waitForBackend, 2000);
    </script>
</body>
</html>
HTMLEOF
    ok "Created loading page (index.html)"
else
    ok "index.html already exists"
fi

# ─────────────────────────────────────────────────────────────
step 7 "Building release DMG (this takes 3-5 minutes)..."
# ─────────────────────────────────────────────────────────────

echo "  Compiling Rust + bundling resources..."
echo "  (First build downloads and compiles dependencies — may take 5-10 min)"
echo ""

cd "$ROOT"
cargo tauri build 2>&1 | while IFS= read -r line; do
    # Show progress without overwhelming output
    case "$line" in
        *Compiling*) echo -e "  ${CYAN}▸${NC} $line" ;;
        *Finished*)  echo -e "  ${GREEN}▸${NC} $line" ;;
        *Bundling*)  echo -e "  ${GREEN}▸${NC} $line" ;;
        *Error*)     echo -e "  ${RED}▸${NC} $line" ;;
        *warning*)   ;; # suppress warnings
        *)           ;; # suppress other output
    esac
done

# ─────────────────────────────────────────────────────────────
step 8 "Locating output..."
# ─────────────────────────────────────────────────────────────

# Find the DMG
DMG_PATH=$(find "$ROOT/src-tauri/target/release/bundle/dmg" -name "*.dmg" 2>/dev/null | head -1)
APP_PATH=$(find "$ROOT/src-tauri/target/release/bundle/macos" -name "*.app" 2>/dev/null | head -1)

echo ""
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  Build Complete!${NC}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""

if [ -n "$DMG_PATH" ]; then
    DMG_SIZE=$(du -sh "$DMG_PATH" | cut -f1)
    ok "DMG: $DMG_PATH ($DMG_SIZE)"
    echo ""
    echo -e "  ${BOLD}To install:${NC}"
    echo "    1. Double-click the .dmg file"
    echo "    2. Drag MyTeam360 to Applications"
    echo "    3. Open MyTeam360 from Applications"
    echo ""
    echo -e "  ${BOLD}Or open it now:${NC}"
    echo "    open \"$DMG_PATH\""
else
    warn "DMG not found in expected location"
    echo "  Check: ls src-tauri/target/release/bundle/"
fi

if [ -n "$APP_PATH" ]; then
    APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
    ok "App: $APP_PATH ($APP_SIZE)"
fi

echo ""
echo -e "  ${BOLD}What's inside the app:${NC}"
echo "    • Native macOS window with system tray"
echo "    • Embedded Python backend (auto-starts)"
echo "    • Touch ID / biometric lock"
echo "    • macOS Keychain for API key storage"
echo "    • Auto-updater framework"
echo ""
echo -e "  ${YELLOW}Note:${NC} macOS may show \"unidentified developer\" warning."
echo "  Right-click → Open to bypass, or sign with your Apple Developer ID."
echo ""
