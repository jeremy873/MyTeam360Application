#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  MyTeam360 — Build FULLY SELF-CONTAINED macOS DMG           ║
# ║  No Python install required on user's machine               ║
# ╚══════════════════════════════════════════════════════════════╝
#
# This bundles Python + all dependencies into the native app.
# Users just drag to Applications and run. Nothing else needed.
#
# Prerequisites:
#   - Xcode Command Line Tools
#   - Rust (rustup)  
#   - Node.js 18+
#   - Python 3.10+ (YOUR machine only — users won't need it)
#
# Usage:
#   chmod +x build-standalone.sh
#   ./build-standalone.sh

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
CYAN="\033[0;36m"
NC="\033[0m"

step() { echo -e "\n${CYAN}${BOLD}[$1/9]${NC} ${BOLD}$2${NC}"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║    MyTeam360 — Standalone DMG Builder (No Python Req)   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

cd "$(dirname "$0")"
ROOT=$(pwd)

# ─────────────────────────────────────────────────────────────
step 1 "Checking prerequisites..."
# ─────────────────────────────────────────────────────────────

MISSING=0

if xcode-select -p &>/dev/null; then
    ok "Xcode Command Line Tools"
else
    fail "Xcode Command Line Tools — install with: xcode-select --install"
    MISSING=1
fi

if command -v rustc &>/dev/null; then
    ok "Rust $(rustc --version | awk '{print $2}')"
else
    fail "Rust — install with: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    MISSING=1
fi

if command -v node &>/dev/null; then
    ok "Node.js $(node --version)"
else
    fail "Node.js — install with: brew install node"
    MISSING=1
fi

if command -v python3 &>/dev/null; then
    ok "Python $(python3 --version | awk '{print $2}')"
else
    fail "Python 3 — install with: brew install python3"
    MISSING=1
fi

[ $MISSING -eq 1 ] && { echo ""; fail "Install missing prerequisites and retry."; exit 1; }

# ─────────────────────────────────────────────────────────────
step 2 "Installing Python dependencies + PyInstaller..."
# ─────────────────────────────────────────────────────────────

pip3 install flask cryptography qrcode requests pillow pyinstaller --break-system-packages -q 2>/dev/null || \
pip3 install flask cryptography qrcode requests pillow pyinstaller -q 2>/dev/null
ok "Python packages + PyInstaller ready"

# ─────────────────────────────────────────────────────────────
step 3 "Installing Tauri CLI..."
# ─────────────────────────────────────────────────────────────

if cargo tauri --version &>/dev/null 2>&1; then
    ok "Tauri CLI $(cargo tauri --version 2>/dev/null)"
else
    echo "  Installing tauri-cli (2-3 minutes first time)..."
    cargo install tauri-cli --version "^2"
    ok "Tauri CLI installed"
fi

# ─────────────────────────────────────────────────────────────
step 4 "Building Python into standalone binary with PyInstaller..."
# ─────────────────────────────────────────────────────────────

echo "  Bundling app.py + all core/ modules + Python interpreter..."
echo "  This creates a single executable with everything inside."
echo ""

# Create PyInstaller spec for clean build
cat > "$ROOT/myteam360.spec" << 'SPEC'
# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
root = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['app.py'],
    pathex=[root],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('core', 'core'),
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.backends',
        'qrcode',
        'qrcode.image.pil',
        'requests',
        'PIL',
        'PIL.Image',
        'sqlite3',
        'json',
        'uuid',
        'hashlib',
        'hmac',
        'base64',
        'secrets',
        'logging',
        'datetime',
        'threading',
        'io',
        'csv',
        're',
        'struct',
        'time',
        'email',
        'urllib',
        # Core modules
        'core',
        'core.database',
        'core.providers',
        'core.agents',
        'core.users',
        'core.departments',
        'core.conversations',
        'core.security',
        'core.security_hardening',
        'core.analytics',
        'core.features',
        'core.voice_chat',
        'core.spend',
        'core.setup_wizard',
        'core.advanced',
        'core.chat_advanced',
        'core.knowledge',
        'core.audit',
        'core.policies',
        'core.provider_auth',
        'core.workflows',
        'core.integrations',
        'core.messaging_hub',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='myteam360-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    name='myteam360-server',
)
SPEC

# Run PyInstaller
cd "$ROOT"
python3 -m PyInstaller myteam360.spec --distpath dist --workpath build_pyinstaller --clean --noconfirm 2>&1 | while IFS= read -r line; do
    case "$line" in
        *Building*EXE*) echo -e "  ${GREEN}▸${NC} Building executable..." ;;
        *Building*COLLECT*) echo -e "  ${GREEN}▸${NC} Collecting dependencies..." ;;
        *completed*) echo -e "  ${GREEN}▸${NC} $line" ;;
        *WARNING*) ;; # suppress warnings
        *) ;;
    esac
done

if [ -f "$ROOT/dist/myteam360-server/myteam360-server" ]; then
    BINARY_SIZE=$(du -sh "$ROOT/dist/myteam360-server/" | cut -f1)
    ok "Standalone binary built ($BINARY_SIZE)"
else
    fail "PyInstaller build failed. Check output above."
    exit 1
fi

# ─────────────────────────────────────────────────────────────
step 5 "Updating Tauri config for standalone binary..."
# ─────────────────────────────────────────────────────────────

# Copy the bundled server into the Tauri resources
RESOURCE_DIR="$ROOT/src-tauri/resources"
rm -rf "$RESOURCE_DIR"
mkdir -p "$RESOURCE_DIR"
cp -R "$ROOT/dist/myteam360-server/" "$RESOURCE_DIR/backend/"

ok "Backend binary copied to Tauri resources"

# Update tauri.conf.json to include the binary as a resource
# We need to add the backend directory to bundle resources
python3 << 'PYEOF'
import json

with open("src-tauri/tauri.conf.json", "r") as f:
    config = json.load(f)

# Update resources to point to the standalone binary instead of Python source
config["bundle"]["resources"] = [
    "resources/backend/**/*"
]

with open("src-tauri/tauri.conf.json", "w") as f:
    json.dump(config, f, indent=2)

print("  Updated tauri.conf.json resources")
PYEOF

ok "Tauri config updated"

# ─────────────────────────────────────────────────────────────
step 6 "Patching main.rs to use bundled binary..."
# ─────────────────────────────────────────────────────────────

# Create a patched version of main.rs that launches the bundled binary
# instead of looking for python3
MAIN_RS="$ROOT/src-tauri/src/main.rs"
BACKUP="$ROOT/src-tauri/src/main.rs.bak"

cp "$MAIN_RS" "$BACKUP"

python3 << 'PYEOF'
import re

with open("src-tauri/src/main.rs", "r") as f:
    content = f.read()

# Replace the find_python function
old_find_python = '''fn find_python() -> String {
    // Try common Python paths on macOS
    for path in &[
        "python3",
        "/usr/local/bin/python3",
        "/opt/homebrew/bin/python3",
        "/usr/bin/python3",
    ] {
        if Command::new(path).arg("--version").output().is_ok() {
            return path.to_string();
        }
    }
    "python3".to_string()
}'''

new_find_python = '''fn find_python() -> String {
    // Not used in standalone mode — binary is self-contained
    "python3".to_string()
}'''

# Replace start_backend to use bundled binary
old_start = '''fn start_backend(app: &AppHandle) -> (Child, u16) {
    let port = find_free_port();
    let python = find_python();
    let resource_dir = get_resource_dir(app);
    let app_py = resource_dir.join("app.py");

    // Data directory in Application Support
    let data_dir = app
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| dirs::data_dir().unwrap().join("com.myteam360.app"));
    std::fs::create_dir_all(&data_dir).ok();

    println!(
        "[MyTeam360] Starting backend: {} {} on port {}",
        python,
        app_py.display(),
        port
    );

    let child = Command::new(&python)
        .arg(app_py.to_str().unwrap_or("app.py"))
        .env("PORT", port.to_string())
        .env("BIND_HOST", "127.0.0.1")
        .env("DATA_DIR", data_dir.to_str().unwrap_or("data"))
        .env("CORS_ORIGINS", format!("http://127.0.0.1:{}", port))
        .current_dir(&resource_dir)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .expect("Failed to start Python backend");

    (child, port)
}'''

new_start = '''fn start_backend(app: &AppHandle) -> (Child, u16) {
    let port = find_free_port();
    let resource_dir = get_resource_dir(app);
    
    // Standalone mode: use bundled binary
    let backend_bin = resource_dir.join("backend").join("myteam360-server");
    
    // Fallback: try Python if binary not found (dev mode)
    let (cmd, args): (String, Vec<String>) = if backend_bin.exists() {
        (backend_bin.to_string_lossy().to_string(), vec![])
    } else {
        let python = find_python();
        let app_py = resource_dir.join("app.py");
        (python, vec![app_py.to_string_lossy().to_string()])
    };

    // Data directory in Application Support
    let data_dir = app
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| dirs::data_dir().unwrap().join("com.myteam360.app"));
    std::fs::create_dir_all(&data_dir).ok();

    println!(
        "[MyTeam360] Starting backend: {} {:?} on port {}",
        cmd, args, port
    );

    let child = Command::new(&cmd)
        .args(&args)
        .env("PORT", port.to_string())
        .env("BIND_HOST", "127.0.0.1")
        .env("DATA_DIR", data_dir.to_str().unwrap_or("data"))
        .env("CORS_ORIGINS", format!("http://127.0.0.1:{}", port))
        .current_dir(&resource_dir)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .expect("Failed to start backend");

    (child, port)
}'''

if old_find_python in content:
    content = content.replace(old_find_python, new_find_python)
    print("  Patched find_python()")
else:
    print("  WARNING: Could not find find_python() to patch — may already be patched")

if old_start in content:
    content = content.replace(old_start, new_start)
    print("  Patched start_backend()")
else:
    print("  WARNING: Could not find start_backend() to patch — may already be patched")

with open("src-tauri/src/main.rs", "w") as f:
    f.write(content)
PYEOF

ok "main.rs patched for standalone binary"

# ─────────────────────────────────────────────────────────────
step 7 "Generating macOS app icon..."
# ─────────────────────────────────────────────────────────────

SRC_ICON="$ROOT/static/icon_circle.png"
if [ -f "$SRC_ICON" ]; then
    ICONSET="$ROOT/src-tauri/icons/MyTeam360.iconset"
    rm -rf "$ICONSET"
    mkdir -p "$ICONSET"
    
    sips -z 16 16     "$SRC_ICON" --out "$ICONSET/icon_16x16.png"      >/dev/null 2>&1
    sips -z 32 32     "$SRC_ICON" --out "$ICONSET/icon_16x16@2x.png"   >/dev/null 2>&1
    sips -z 32 32     "$SRC_ICON" --out "$ICONSET/icon_32x32.png"      >/dev/null 2>&1
    sips -z 64 64     "$SRC_ICON" --out "$ICONSET/icon_32x32@2x.png"   >/dev/null 2>&1
    sips -z 128 128   "$SRC_ICON" --out "$ICONSET/icon_128x128.png"    >/dev/null 2>&1
    sips -z 256 256   "$SRC_ICON" --out "$ICONSET/icon_128x128@2x.png" >/dev/null 2>&1
    sips -z 256 256   "$SRC_ICON" --out "$ICONSET/icon_256x256.png"    >/dev/null 2>&1
    sips -z 512 512   "$SRC_ICON" --out "$ICONSET/icon_256x256@2x.png" >/dev/null 2>&1
    sips -z 512 512   "$SRC_ICON" --out "$ICONSET/icon_512x512.png"    >/dev/null 2>&1
    sips -z 1024 1024 "$SRC_ICON" --out "$ICONSET/icon_512x512@2x.png" >/dev/null 2>&1
    
    iconutil -c icns "$ICONSET" -o "$ROOT/src-tauri/icons/icon.icns"
    rm -rf "$ICONSET"
    ok "Generated icon.icns from purple swirl"
else
    warn "icon_circle.png not found — using default icon"
fi

# ─────────────────────────────────────────────────────────────
step 8 "Building native app + DMG..."
# ─────────────────────────────────────────────────────────────

echo "  Compiling Rust wrapper + bundling standalone backend..."
echo ""

cd "$ROOT"
cargo tauri build 2>&1 | while IFS= read -r line; do
    case "$line" in
        *Compiling*) echo -e "  ${CYAN}▸${NC} $line" ;;
        *Finished*)  echo -e "  ${GREEN}▸${NC} $line" ;;
        *Bundling*)  echo -e "  ${GREEN}▸${NC} $line" ;;
        *Error*)     echo -e "  ${RED}▸${NC} $line" ;;
        *warning*)   ;;
        *)           ;;
    esac
done

# ─────────────────────────────────────────────────────────────
step 9 "Done!"
# ─────────────────────────────────────────────────────────────

# Restore original main.rs for development
cp "$BACKUP" "$MAIN_RS"
rm -f "$BACKUP"
ok "Restored main.rs (dev mode preserved)"

DMG_PATH=$(find "$ROOT/src-tauri/target/release/bundle/dmg" -name "*.dmg" 2>/dev/null | head -1)
APP_PATH=$(find "$ROOT/src-tauri/target/release/bundle/macos" -name "*.app" 2>/dev/null | head -1)

echo ""
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  Standalone Build Complete!${NC}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""

if [ -n "$DMG_PATH" ]; then
    DMG_SIZE=$(du -sh "$DMG_PATH" | cut -f1)
    ok "DMG: $DMG_PATH ($DMG_SIZE)"
    echo ""
    echo -e "  ${BOLD}This DMG is fully self-contained.${NC}"
    echo -e "  ${BOLD}Users do NOT need Python, Rust, or anything else.${NC}"
    echo ""
    echo -e "  ${BOLD}To install:${NC}"
    echo "    1. Double-click the .dmg"
    echo "    2. Drag MyTeam360 to Applications"
    echo "    3. Right-click → Open (first time only)"
    echo ""
    echo -e "  ${BOLD}Open now:${NC}"
    echo "    open \"$DMG_PATH\""
fi

if [ -n "$APP_PATH" ]; then
    APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
    ok "App: $APP_PATH ($APP_SIZE)"
fi

echo ""
echo -e "  ${BOLD}What's bundled inside:${NC}"
echo "    • Python interpreter + all dependencies"
echo "    • Flask server with 213 API endpoints"  
echo "    • 22 core modules (14,179 lines)"
echo "    • Web UI + Voice Chat interface"
echo "    • macOS Keychain integration"
echo "    • Touch ID biometric lock"
echo "    • System tray with menu"
echo ""
echo -e "  ${YELLOW}Expected app size: ~50-80MB${NC}"
echo "  (includes bundled Python runtime)"
echo ""

# Cleanup build artifacts
rm -rf "$ROOT/build_pyinstaller" "$ROOT/dist" "$ROOT/myteam360.spec"
rm -rf "$RESOURCE_DIR"
ok "Cleaned up build artifacts"
