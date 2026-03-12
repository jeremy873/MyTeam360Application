// MyTeam360 — Native macOS App (Tauri v2)
// Sidecar Python backend, Touch ID, system tray, Keychain, auto-update.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use std::path::PathBuf;
use serde::{Deserialize, Serialize};
use tauri::{
    AppHandle, Manager, State, RunEvent, WindowEvent,
    menu::{Menu, MenuItem},
    tray::{TrayIconBuilder, TrayIconEvent, MouseButton, MouseButtonState},
    Emitter,
};

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

struct BackendProcess(Mutex<Option<Child>>);
struct BackendPort(Mutex<u16>);
struct AppLocked(Mutex<bool>);

#[derive(Clone, Serialize, Deserialize)]
struct BackendStatus {
    running: bool,
    port: u16,
    url: String,
}

// ═══════════════════════════════════════════════════════════════
// SIDECAR MANAGEMENT
// ═══════════════════════════════════════════════════════════════

fn find_python() -> String {
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
}

fn find_free_port() -> u16 {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    listener.local_addr().unwrap().port()
}

fn get_resource_dir(app: &AppHandle) -> PathBuf {
    app.path()
        .resource_dir()
        .unwrap_or_else(|_| std::env::current_dir().unwrap())
}

fn start_backend(app: &AppHandle) -> (Child, u16) {
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
}

fn wait_for_backend(port: u16, timeout_secs: u64) -> bool {
    let url = format!("http://127.0.0.1:{}/", port);
    let start = std::time::Instant::now();
    let timeout = Duration::from_secs(timeout_secs);

    while start.elapsed() < timeout {
        if let Ok(resp) = reqwest::blocking::get(&url) {
            if resp.status().is_success() || resp.status().is_redirection() {
                println!("[MyTeam360] Backend ready on port {}", port);
                return true;
            }
        }
        std::thread::sleep(Duration::from_millis(250));
    }
    println!("[MyTeam360] Backend failed to start within {}s", timeout_secs);
    false
}

fn stop_backend(state: &BackendProcess) {
    if let Ok(mut lock) = state.0.lock() {
        if let Some(ref mut child) = *lock {
            println!("[MyTeam360] Stopping backend (PID: {})", child.id());
            child.kill().ok();
            child.wait().ok();
        }
        *lock = None;
    }
}

// ═══════════════════════════════════════════════════════════════
// TOUCH ID (macOS)
// ═══════════════════════════════════════════════════════════════

#[cfg(target_os = "macos")]
fn authenticate_touch_id() -> Result<bool, String> {
    use std::ffi::CString;

    // Use the security framework command-line tool as a simple approach
    // For production, you'd use LAContext via objc bindings
    let output = Command::new("osascript")
        .arg("-e")
        .arg(
            r#"tell application "System Events"
                try
                    do shell script "echo authenticated" with administrator privileges
                    return "ok"
                on error
                    return "cancel"
                end try
            end tell"#,
        )
        .output();

    match output {
        Ok(out) => {
            let result = String::from_utf8_lossy(&out.stdout);
            Ok(result.trim() == "ok")
        }
        Err(e) => Err(format!("Touch ID error: {}", e)),
    }
}

#[cfg(not(target_os = "macos"))]
fn authenticate_touch_id() -> Result<bool, String> {
    Ok(true) // Skip on non-macOS
}

// ═══════════════════════════════════════════════════════════════
// KEYCHAIN
// ═══════════════════════════════════════════════════════════════

fn keychain_set(service: &str, key: &str, value: &str) -> Result<(), String> {
    let entry = keyring::Entry::new(service, key).map_err(|e| e.to_string())?;
    entry.set_password(value).map_err(|e| e.to_string())
}

fn keychain_get(service: &str, key: &str) -> Result<String, String> {
    let entry = keyring::Entry::new(service, key).map_err(|e| e.to_string())?;
    entry.get_password().map_err(|e| e.to_string())
}

fn keychain_delete(service: &str, key: &str) -> Result<(), String> {
    let entry = keyring::Entry::new(service, key).map_err(|e| e.to_string())?;
    entry.delete_credential().map_err(|e| e.to_string())
}

// ═══════════════════════════════════════════════════════════════
// TAURI COMMANDS (called from JS)
// ═══════════════════════════════════════════════════════════════

#[tauri::command]
fn get_backend_url(port_state: State<BackendPort>) -> String {
    let port = port_state.0.lock().unwrap();
    format!("http://127.0.0.1:{}", *port)
}

#[tauri::command]
fn get_backend_status(
    process_state: State<BackendProcess>,
    port_state: State<BackendPort>,
) -> BackendStatus {
    let running = process_state
        .0
        .lock()
        .map(|p| p.is_some())
        .unwrap_or(false);
    let port = *port_state.0.lock().unwrap();
    BackendStatus {
        running,
        port,
        url: format!("http://127.0.0.1:{}", port),
    }
}

#[tauri::command]
fn restart_backend(
    app: AppHandle,
    process_state: State<BackendProcess>,
    port_state: State<BackendPort>,
) -> BackendStatus {
    stop_backend(&process_state);
    let (child, port) = start_backend(&app);
    *process_state.0.lock().unwrap() = Some(child);
    *port_state.0.lock().unwrap() = port;
    wait_for_backend(port, 15);
    BackendStatus {
        running: true,
        port,
        url: format!("http://127.0.0.1:{}", port),
    }
}

#[tauri::command]
fn authenticate_biometric() -> Result<bool, String> {
    authenticate_touch_id()
}

#[tauri::command]
fn lock_app(locked_state: State<AppLocked>) -> bool {
    *locked_state.0.lock().unwrap() = true;
    true
}

#[tauri::command]
fn unlock_app(locked_state: State<AppLocked>) -> Result<bool, String> {
    let authed = authenticate_touch_id()?;
    if authed {
        *locked_state.0.lock().unwrap() = false;
    }
    Ok(authed)
}

#[tauri::command]
fn is_locked(locked_state: State<AppLocked>) -> bool {
    *locked_state.0.lock().unwrap()
}

#[tauri::command]
fn save_to_keychain(key: String, value: String) -> Result<(), String> {
    keychain_set("com.myteam360.app", &key, &value)
}

#[tauri::command]
fn load_from_keychain(key: String) -> Result<String, String> {
    keychain_get("com.myteam360.app", &key)
}

#[tauri::command]
fn delete_from_keychain(key: String) -> Result<(), String> {
    keychain_delete("com.myteam360.app", &key)
}

#[tauri::command]
fn get_app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

#[tauri::command]
fn get_data_dir(app: AppHandle) -> String {
    app.path()
        .app_data_dir()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|_| "unknown".to_string())
}

#[tauri::command]
fn open_data_dir(app: AppHandle) {
    if let Ok(dir) = app.path().app_data_dir() {
        open::that(dir).ok();
    }
}

// ═══════════════════════════════════════════════════════════════
// SYSTEM TRAY
// ═══════════════════════════════════════════════════════════════

fn setup_tray(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let show = MenuItem::with_id(app, "show", "Show MyTeam360", true, None::<&str>)?;
    let lock = MenuItem::with_id(app, "lock", "Lock App", true, None::<&str>)?;
    let restart = MenuItem::with_id(app, "restart_backend", "Restart Backend", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[&show, &lock, &restart, &quit])?;

    let _tray = TrayIconBuilder::new()
        .menu(&menu)
        .tooltip("MyTeam360")
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                let app = tray.app_handle();
                if let Some(window) = app.get_webview_window("main") {
                    window.show().ok();
                    window.set_focus().ok();
                }
            }
        })
        .on_menu_event(|app, event| match event.id().as_ref() {
            "show" => {
                if let Some(window) = app.get_webview_window("main") {
                    window.show().ok();
                    window.set_focus().ok();
                }
            }
            "lock" => {
                let locked: State<AppLocked> = app.state();
                *locked.0.lock().unwrap() = true;
                app.emit("app-locked", true).ok();
            }
            "restart_backend" => {
                let process_state: State<BackendProcess> = app.state();
                let port_state: State<BackendPort> = app.state();
                stop_backend(&process_state);
                let (child, port) = start_backend(app);
                *process_state.0.lock().unwrap() = Some(child);
                *port_state.0.lock().unwrap() = port;
                wait_for_backend(port, 15);
                app.emit("backend-restarted", port).ok();
            }
            "quit" => {
                let process_state: State<BackendProcess> = app.state();
                stop_backend(&process_state);
                app.exit(0);
            }
            _ => {}
        })
        .build(app)?;

    Ok(())
}

// ═══════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .plugin(tauri_plugin_store::Builder::default().build())
        .manage(BackendProcess(Mutex::new(None)))
        .manage(BackendPort(Mutex::new(5000)))
        .manage(AppLocked(Mutex::new(false)))
        .invoke_handler(tauri::generate_handler![
            get_backend_url,
            get_backend_status,
            restart_backend,
            authenticate_biometric,
            lock_app,
            unlock_app,
            is_locked,
            save_to_keychain,
            load_from_keychain,
            delete_from_keychain,
            get_app_version,
            get_data_dir,
            open_data_dir,
        ])
        .setup(|app| {
            // Start Python backend
            let (child, port) = start_backend(app.handle());

            // Store state
            let process_state: State<BackendProcess> = app.state();
            *process_state.0.lock().unwrap() = Some(child);
            let port_state: State<BackendPort> = app.state();
            *port_state.0.lock().unwrap() = port;

            // Wait for backend
            if !wait_for_backend(port, 15) {
                eprintln!("[MyTeam360] WARNING: Backend may not have started");
            }

            // Navigate main window to backend
            if let Some(window) = app.get_webview_window("main") {
                let url = format!("http://127.0.0.1:{}", port);
                window
                    .eval(&format!("window.location.replace('{}')", url))
                    .ok();
            }

            // Setup tray
            setup_tray(app.handle())?;

            println!("[MyTeam360] App ready — backend on port {}", port);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Failed to build MyTeam360")
        .run(|app, event| match event {
            RunEvent::WindowEvent {
                label,
                event: WindowEvent::CloseRequested { api, .. },
                ..
            } if label == "main" => {
                // Hide to tray instead of closing
                api.prevent_close();
                if let Some(window) = app.get_webview_window("main") {
                    window.hide().ok();
                }
            }
            RunEvent::ExitRequested { .. } => {
                // Cleanup backend on exit
                let process_state: State<BackendProcess> = app.state();
                stop_backend(&process_state);
            }
            _ => {}
        });
}
