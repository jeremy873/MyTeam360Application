# Building the MyTeam360 macOS DMG — Quick Reference

## One-Time Setup (5-10 minutes)

If you don't have the tools yet, run these one at a time:

```bash
# 1. Xcode Command Line Tools (if not already installed)
xcode-select --install

# 2. Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 3. Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"

# 4. Node.js
brew install node

# 5. Tauri CLI
cargo install tauri-cli --version "^2"
```

Close and reopen your terminal after installing Rust.

## Build the DMG

```bash
cd myteam360-package
chmod +x build-dmg.sh
./build-dmg.sh
```

First build takes 5-10 minutes (downloads + compiles Rust dependencies).
Subsequent builds take 1-2 minutes.

The DMG lands in: `src-tauri/target/release/bundle/dmg/`

## Install

1. Double-click the `.dmg` file
2. Drag **MyTeam360** to **Applications**
3. Right-click → **Open** (first time, to bypass Gatekeeper)
4. The app auto-starts the Python backend and opens the dashboard

## What the App Does

When you launch MyTeam360.app:

1. **Finds Python 3** on your system (`python3`, `/opt/homebrew/bin/python3`, etc.)
2. **Picks a free port** (so it doesn't conflict with anything)
3. **Starts `app.py`** as a background process on that port
4. **Opens a native window** pointed at `http://127.0.0.1:{port}`
5. **Adds a system tray icon** with Show / Lock / Restart Backend / Quit
6. **Closing the window** hides to tray (click tray icon to reopen)
7. **Quitting** cleanly stops the Python backend

## Features in the Native App

| Feature | How It Works |
|---------|-------------|
| System Tray | Tray icon with menu — show, lock, restart backend, quit |
| Touch ID Lock | Lock the app from tray; unlock requires biometric |
| Keychain Storage | API keys stored in macOS Keychain (encrypted by OS) |
| Auto-Start | Optional launch at login via LaunchAgent |
| Auto-Update | Framework ready (needs update server URL) |
| Window Management | Remembers size, hides to tray on close |

## Common Build Issues

### "xcrun: error: unable to find utility"
```bash
sudo xcode-select --reset
xcode-select --install
```

### Cargo can't find openssl
```bash
brew install openssl
export OPENSSL_DIR=$(brew --prefix openssl)
```

### "Blocking waiting for file lock on package cache"
Another cargo process is running. Wait or:
```bash
rm -rf ~/.cargo/.package-cache
```

### Build succeeds but app crashes on launch
Check if Python 3 is in your PATH:
```bash
which python3
python3 --version
```
The app looks for python3 at: `python3`, `/usr/local/bin/python3`, `/opt/homebrew/bin/python3`, `/usr/bin/python3`

### "unidentified developer" warning
Right-click the app → Open → Click Open in the dialog. This only needs to be done once. For distribution, sign with an Apple Developer ID ($99/year).

### Build takes forever
First build compiles all Rust dependencies (~200 crates). This is normal.
After that, only your changes recompile (seconds).

## Cleaning Up

```bash
# Clean build artifacts (forces full rebuild)
cd src-tauri && cargo clean

# Remove installed app
rm -rf /Applications/MyTeam360.app

# Remove app data
rm -rf ~/Library/Application\ Support/com.myteam360.app
```
