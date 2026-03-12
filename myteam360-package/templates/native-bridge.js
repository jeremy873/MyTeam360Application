/**
 * MyTeam360 Native Bridge
 * Connects the web frontend to Tauri native capabilities.
 * Gracefully degrades to web-only mode when not in Tauri.
 */

(function () {
  "use strict";

  const IS_TAURI = !!(window.__TAURI__ || window.__TAURI_INTERNALS__);

  // ── Tauri invoke helper ──
  async function invoke(cmd, args) {
    if (!IS_TAURI) return null;
    try {
      const { invoke: tauriInvoke } = window.__TAURI__
        ? window.__TAURI__.core
        : window.__TAURI_INTERNALS__;
      return await tauriInvoke(cmd, args || {});
    } catch (e) {
      console.warn("[NativeBridge]", cmd, "failed:", e);
      return null;
    }
  }

  // ── Backend URL ──
  // In Tauri, backend runs on a dynamic port; in browser, it's the page origin.
  let _backendUrl = null;

  async function getBackendUrl() {
    if (_backendUrl) return _backendUrl;
    if (IS_TAURI) {
      _backendUrl = await invoke("get_backend_url");
    }
    if (!_backendUrl) {
      _backendUrl = window.location.origin;
    }
    return _backendUrl;
  }

  // Override the global API variable used by the frontend
  async function patchApiBase() {
    const url = await getBackendUrl();
    if (window.API !== undefined) {
      window.API = url;
    }
    // Also patch any fetch calls
    window._nativeBackendUrl = url;
    console.log("[NativeBridge] Backend URL:", url);
  }

  // ── Touch ID / Biometric ──

  async function authenticateBiometric() {
    if (!IS_TAURI) return true; // No-op in browser
    const result = await invoke("authenticate_biometric");
    return result === true;
  }

  async function lockApp() {
    if (!IS_TAURI) return;
    await invoke("lock_app");
    showLockScreen();
  }

  async function unlockApp() {
    if (!IS_TAURI) return true;
    const result = await invoke("unlock_app");
    if (result === true) {
      hideLockScreen();
      return true;
    }
    return false;
  }

  async function isLocked() {
    if (!IS_TAURI) return false;
    return (await invoke("is_locked")) === true;
  }

  // ── Lock Screen UI ──

  function showLockScreen() {
    let overlay = document.getElementById("native-lock-screen");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "native-lock-screen";
      overlay.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
          height:100vh;background:var(--bg-0,#0a0a0f);color:var(--t1,#e8e8f0);font-family:system-ui">
          <div style="font-size:48px;margin-bottom:16px">🔒</div>
          <h2 style="margin:0 0 8px">MyTeam360 Locked</h2>
          <p style="color:var(--t3,#888);margin:0 0 24px;font-size:14px">
            Use Touch ID or click below to unlock
          </p>
          <button id="native-unlock-btn" style="
            padding:10px 32px;border-radius:8px;border:none;
            background:var(--accent,#7c5cfc);color:white;font-size:14px;
            cursor:pointer;font-weight:600">
            🔓 Unlock with Touch ID
          </button>
          <p id="native-unlock-error" style="color:#ef4444;margin-top:12px;font-size:12px;display:none">
            Authentication failed. Try again.
          </p>
        </div>`;
      document.body.appendChild(overlay);
      document.getElementById("native-unlock-btn").addEventListener("click", async () => {
        const err = document.getElementById("native-unlock-error");
        err.style.display = "none";
        const ok = await unlockApp();
        if (!ok) err.style.display = "block";
      });
    }
    overlay.style.display = "block";
    overlay.style.position = "fixed";
    overlay.style.inset = "0";
    overlay.style.zIndex = "99999";
  }

  function hideLockScreen() {
    const overlay = document.getElementById("native-lock-screen");
    if (overlay) overlay.style.display = "none";
  }

  // ── Keychain ──

  async function saveToKeychain(key, value) {
    if (!IS_TAURI) {
      // Fallback: in-memory only (no localStorage per artifact rules)
      window._keychainFallback = window._keychainFallback || {};
      window._keychainFallback[key] = value;
      return;
    }
    await invoke("save_to_keychain", { key, value });
  }

  async function loadFromKeychain(key) {
    if (!IS_TAURI) {
      return (window._keychainFallback || {})[key] || null;
    }
    return await invoke("load_from_keychain", { key });
  }

  async function deleteFromKeychain(key) {
    if (!IS_TAURI) {
      if (window._keychainFallback) delete window._keychainFallback[key];
      return;
    }
    await invoke("delete_from_keychain", { key });
  }

  // ── Backend Management ──

  async function getBackendStatus() {
    return await invoke("get_backend_status");
  }

  async function restartBackend() {
    const status = await invoke("restart_backend");
    if (status && status.url) {
      _backendUrl = status.url;
      window._nativeBackendUrl = status.url;
      if (window.API !== undefined) window.API = status.url;
    }
    return status;
  }

  // ── App Info ──

  async function getAppVersion() {
    if (!IS_TAURI) return "web";
    return await invoke("get_app_version");
  }

  async function getDataDir() {
    return await invoke("get_data_dir");
  }

  async function openDataDir() {
    await invoke("open_data_dir");
  }

  // ── Event Listeners ──

  function setupEventListeners() {
    if (!IS_TAURI) return;

    try {
      const { listen } = window.__TAURI__
        ? window.__TAURI__.event
        : window.__TAURI_INTERNALS__;

      listen("app-locked", () => showLockScreen());
      listen("backend-restarted", (event) => {
        const port = event.payload;
        _backendUrl = `http://127.0.0.1:${port}`;
        window._nativeBackendUrl = _backendUrl;
        if (window.API !== undefined) window.API = _backendUrl;
        console.log("[NativeBridge] Backend restarted on port", port);
      });
    } catch (e) {
      console.warn("[NativeBridge] Event setup failed:", e);
    }
  }

  // ── Keyboard Shortcut: Cmd+L to lock ──

  document.addEventListener("keydown", (e) => {
    if (IS_TAURI && (e.metaKey || e.ctrlKey) && e.key === "l") {
      e.preventDefault();
      lockApp();
    }
  });

  // ── Auto-Update Check ──

  async function checkForUpdates() {
    if (!IS_TAURI) return null;
    try {
      const { check } = window.__TAURI__
        ? window.__TAURI__.updater
        : {};
      if (check) {
        const update = await check();
        if (update && update.available) {
          return {
            available: true,
            version: update.version,
            body: update.body,
          };
        }
      }
    } catch (e) {
      console.warn("[NativeBridge] Update check failed:", e);
    }
    return { available: false };
  }

  // ── Initialize ──

  async function init() {
    console.log("[NativeBridge] Mode:", IS_TAURI ? "NATIVE" : "WEB");
    await patchApiBase();
    setupEventListeners();

    // Check lock state
    if (IS_TAURI && (await isLocked())) {
      showLockScreen();
    }

    // Version badge in settings
    const version = await getAppVersion();
    if (version && version !== "web") {
      const badge = document.createElement("div");
      badge.style.cssText =
        "position:fixed;bottom:8px;right:8px;font-size:10px;color:var(--t4,#555);z-index:1000;font-family:monospace";
      badge.textContent = "v" + version;
      document.body.appendChild(badge);
    }
  }

  // ── Expose Public API ──

  window.NativeBridge = {
    IS_TAURI,
    getBackendUrl,
    authenticateBiometric,
    lockApp,
    unlockApp,
    isLocked,
    saveToKeychain,
    loadFromKeychain,
    deleteFromKeychain,
    getBackendStatus,
    restartBackend,
    getAppVersion,
    getDataDir,
    openDataDir,
    checkForUpdates,
    init,
  };

  // Auto-init when DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
