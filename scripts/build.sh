#!/bin/bash
# MyTeam360 — Build Script
# Builds the native macOS .app bundle using Tauri.
#
# Prerequisites (installed by this script if missing):
#   - Rust (rustup)
#   - Node.js 18+ (for Tauri CLI)
#   - Python 3.10+
#   - Xcode Command Line Tools

set -e

echo "╔══════════════════════════════════════════╗"
echo "║      MyTeam360 — Mac App Builder         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Check Prerequisites ──

check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        return 1
    fi
    return 0
}

echo "Checking prerequisites..."

# Xcode CLI tools
if ! xcode-select -p &>/dev/null; then
    echo "  Installing Xcode Command Line Tools..."
    xcode-select --install
    echo "  Please complete the Xcode installation and re-run this script."
    exit 1
fi
echo "  ✓ Xcode CLI tools"

# Rust
if ! check_cmd rustc; then
    echo "  Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi
echo "  ✓ Rust $(rustc --version | awk '{print $2}')"

# Node.js
if ! check_cmd node; then
    echo "  ERROR: Node.js not found. Install from https://nodejs.org/"
    echo "  Or: brew install node"
    exit 1
fi
echo "  ✓ Node.js $(node --version)"

# Python
if ! check_cmd python3; then
    echo "  ERROR: Python 3 not found."
    exit 1
fi
echo "  ✓ Python $(python3 --version | awk '{print $2}')"

# ── Install Tauri CLI ──

if ! check_cmd cargo-tauri 2>/dev/null && ! cargo tauri --version &>/dev/null 2>&1; then
    echo ""
    echo "Installing Tauri CLI..."
    cargo install tauri-cli --version "^2"
fi
echo "  ✓ Tauri CLI"

# ── Install Python Dependencies ──

echo ""
echo "Installing Python dependencies..."
pip3 install -q -r requirements.txt 2>/dev/null || pip3 install -q flask requests
echo "  ✓ Python packages"

# ── Generate Icons ──

echo ""
if [ ! -f "src-tauri/icons/icon.png" ]; then
    echo "Generating placeholder icons..."
    chmod +x scripts/generate-icons.sh
    bash scripts/generate-icons.sh
else
    echo "Icons already exist. To regenerate:"
    echo "  ./scripts/generate-icons.sh [your-icon.png]"
fi

# ── Build ──

echo ""
echo "Building MyTeam360.app..."
echo "This may take several minutes on first build (compiling Rust dependencies)."
echo ""

MODE="${1:-release}"

if [ "$MODE" = "dev" ]; then
    echo "Starting in development mode..."
    cargo tauri dev
elif [ "$MODE" = "release" ]; then
    cargo tauri build

    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║            Build Complete!                ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""

    # Find the output
    APP_PATH="src-tauri/target/release/bundle/macos/MyTeam360.app"
    DMG_PATH="src-tauri/target/release/bundle/dmg"

    if [ -d "$APP_PATH" ]; then
        echo "  .app:  $APP_PATH"
        echo "  Size:  $(du -sh "$APP_PATH" | cut -f1)"
    fi

    if [ -d "$DMG_PATH" ]; then
        DMG_FILE=$(ls "$DMG_PATH"/*.dmg 2>/dev/null | head -1)
        if [ -n "$DMG_FILE" ]; then
            echo "  .dmg:  $DMG_FILE"
            echo "  Size:  $(du -sh "$DMG_FILE" | cut -f1)"
        fi
    fi

    echo ""
    echo "To install:"
    echo "  1. Open the .dmg file"
    echo "  2. Drag MyTeam360 to Applications"
    echo "  3. Launch from Applications or Spotlight"
    echo ""
    echo "To run directly:"
    echo "  open $APP_PATH"
else
    echo "Usage: ./scripts/build.sh [dev|release]"
    exit 1
fi
