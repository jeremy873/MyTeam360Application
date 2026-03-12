"""
MyTeam360 — Security Module
Multi-user authentication, rate limiting, IP whitelisting, audit logging.
© 2026 MyTeam360. All Rights Reserved.
"""

import os
import time
import uuid
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from flask import request, jsonify, session, g, redirect
from .database import get_db
from .audit import AuditLogger

logger = logging.getLogger("MyTeam360.security")
audit = AuditLogger()


class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        self.blocked = {}
        self.limits = {
            "api": {"window": 60, "max": int(os.getenv("RATE_LIMIT_API", "200"))},
            "auth": {"window": 300, "max": int(os.getenv("RATE_LIMIT_AUTH", "10"))},
            "chat": {"window": 60, "max": int(os.getenv("RATE_LIMIT_CHAT", "30"))},
        }

    def is_limited(self, key: str, category: str = "api") -> bool:
        now = time.time()
        if key in self.blocked and now < self.blocked[key]:
            return True
        elif key in self.blocked:
            del self.blocked[key]
        limit = self.limits.get(category, self.limits["api"])
        bucket = f"{category}:{key}"
        self.requests[bucket] = [t for t in self.requests.get(bucket, []) if now - t < limit["window"]]
        if len(self.requests[bucket]) >= limit["max"]:
            return True
        self.requests[bucket].append(now)
        return False

    def block_ip(self, ip: str, seconds: int = 900):
        self.blocked[ip] = time.time() + seconds


class IPWhitelist:
    def __init__(self):
        raw = os.getenv("IP_WHITELIST", "").strip()
        self.enabled = bool(raw)
        self.ips = set()
        if self.enabled:
            self.ips = {ip.strip() for ip in raw.split(",") if ip.strip()}
            self.ips.update(["127.0.0.1", "::1"])

    def allowed(self, ip: str) -> bool:
        return not self.enabled or ip in self.ips


def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers.pop("Server", None)
    return response


class SecurityManager:
    """Multi-user authentication and security middleware."""

    def __init__(self, app=None, user_manager=None):
        self.limiter = RateLimiter()
        self.whitelist = IPWhitelist()
        self.users = user_manager
        self.failed_attempts = defaultdict(int)
        if app:
            self.init_app(app)

    def init_app(self, app):
        app.secret_key = os.getenv("SESSION_SECRET", secrets.token_hex(32))
        app.config["SESSION_COOKIE_HTTPONLY"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        if os.getenv("HTTPS_ENABLED", "").lower() == "true":
            app.config["SESSION_COOKIE_SECURE"] = True
        app.before_request(self._before_request)
        app.after_request(add_security_headers)
        self._register_routes(app)

    def _get_ip(self) -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.headers.get("X-Real-IP", request.remote_addr)

    def _before_request(self):
        ip = self._get_ip()
        g.client_ip = ip

        if not self.whitelist.allowed(ip):
            return jsonify({"error": "Access denied"}), 403

        # Public routes (no auth required)
        public = ["/auth/", "/api/auth/", "/static/", "/integrations/",
                  "/api/policy/active", "/api/shared/", "/api/calendar/feed/",
                  "/api/billing/webhook"]
        if any(request.path.startswith(p) for p in public):
            return None

        # Root serves the SPA shell (auth happens client-side)
        if request.path == "/" or request.path == "/favicon.ico" or request.path == "/voice-chat" or request.path == "/security" or request.path == "/app" or request.path == "/terms":
            return None

        if self.limiter.is_limited(ip):
            return jsonify({"error": "Rate limited"}), 429

        auth_result = self._check_auth(ip)
        if auth_result is not None:
            return auth_result

        # AUP bypass — these need auth but skip policy acceptance check
        aup_bypass = ["/api/policy/", "/api/setup/state",
                      "/api/security/mfa/verify", "/api/security/mfa/status"]

        # Policy acceptance check (skip for bypassed endpoints)
        if hasattr(g, "user_id") and request.path.startswith("/api/") \
                and not any(request.path.startswith(p) for p in aup_bypass):
            try:
                from .policies import PolicyManager
                pm = PolicyManager()
                check = pm.check_user_acceptance(g.user_id)
                if check.get("required") and not check.get("accepted"):
                    return jsonify({
                        "error": "policy_acceptance_required",
                        "policy_id": check.get("policy_id"),
                        "message": "You must accept the Acceptable Use Policy before continuing.",
                    }), 403
            except Exception:
                pass  # Don't block on policy check failures

        return None

    def _check_auth(self, ip: str):
        # 1. Bearer token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return self._validate_token(token, ip)

        # 2. Session
        if session.get("user_id"):
            user = self.users.get_user(session["user_id"]) if self.users else None
            if user and user["is_active"]:
                g.user = user
                g.user_id = user["id"]
                return None
            session.clear()

        # 3. Query param token (for SSE)
        qt = request.args.get("token")
        if qt:
            return self._validate_token(qt, ip)

        # Not authenticated
        if request.path.startswith("/api/"):
            return jsonify({"error": "Authentication required"}), 401
        return redirect("/auth/login")

    def _validate_token(self, token: str, ip: str):
        salt = os.getenv("TOKEN_SALT", "mt360-salt")
        token_hash = hashlib.sha256(f"{salt}:{token}".encode()).hexdigest()
        with get_db() as db:
            row = db.execute("""
                SELECT t.*, u.id as uid, u.display_name, u.role, u.is_active
                FROM api_tokens t JOIN users u ON t.user_id=u.id
                WHERE t.token_hash=? AND t.enabled=1
            """, (token_hash,)).fetchone()
            if not row or not row["is_active"]:
                self.failed_attempts[ip] += 1
                if self.failed_attempts[ip] >= 5:
                    self.limiter.block_ip(ip)
                return jsonify({"error": "Invalid token"}), 401
            if row["expires_at"]:
                if datetime.fromisoformat(row["expires_at"]) < datetime.now():
                    return jsonify({"error": "Token expired"}), 401
            db.execute("UPDATE api_tokens SET last_used=CURRENT_TIMESTAMP WHERE id=?", (row["id"],))
        self.failed_attempts[ip] = 0
        g.user = {"id": row["uid"], "display_name": row["display_name"], "role": row["role"]}
        g.user_id = row["uid"]
        return None

    def create_token(self, user_id: str, name: str = "default",
                     scopes: str = "*", expires_days: int = None) -> dict:
        token = f"mt360_{secrets.token_urlsafe(32)}"
        token_id = f"tok_{uuid.uuid4().hex[:8]}"
        salt = os.getenv("TOKEN_SALT", "mt360-salt")
        token_hash = hashlib.sha256(f"{salt}:{token}".encode()).hexdigest()
        expires = None
        if expires_days:
            expires = (datetime.now() + timedelta(days=expires_days)).isoformat()
        with get_db() as db:
            db.execute("""
                INSERT INTO api_tokens (id, user_id, name, token_hash, token_prefix, scopes, expires_at)
                VALUES (?,?,?,?,?,?,?)
            """, (token_id, user_id, name, token_hash, token[:12] + "...", scopes, expires))
        return {"id": token_id, "token": token, "name": name, "prefix": token[:12] + "..."}

    def _register_routes(self, app):

        @app.route("/api/auth/login", methods=["POST"])
        def api_login():
            data = request.json
            ip = self._get_ip()
            if self.limiter.is_limited(ip, "auth"):
                return jsonify({"error": "Too many attempts"}), 429
            if not self.users:
                return jsonify({"error": "User system not ready"}), 500

            # Check account lockout
            try:
                from .security_hardening import PasswordPolicyManager
                pw_mgr = PasswordPolicyManager()
                # Look up user by email first to check lockout
                with get_db() as db:
                    user_row = db.execute("SELECT id FROM users WHERE email=?", (data.get("email", ""),)).fetchone()
                if user_row:
                    lockout = pw_mgr.check_lockout(user_row["id"])
                    if lockout.get("locked"):
                        return jsonify({
                            "error": "Account locked due to too many failed attempts",
                            "locked_until": lockout.get("locked_until"),
                            "remaining_seconds": lockout.get("remaining_seconds"),
                        }), 423
            except Exception:
                pass

            user = self.users.authenticate(data.get("email", ""), data.get("password", ""))
            if not user:
                self.failed_attempts[ip] += 1
                audit.log_auth(None, ip, "/api/auth/login", "POST", "failed", data.get("email", ""))
                audit.log("login_failed", ip_address=ip, detail=data.get("email", ""), severity="warning")
                # Record failed attempt for lockout
                try:
                    if user_row:
                        pw_mgr.record_failed_attempt(user_row["id"])
                except Exception:
                    pass
                if self.failed_attempts[ip] >= 5:
                    self.limiter.block_ip(ip)
                    audit.log("ip_blocked", ip_address=ip, detail="5 failed attempts", severity="critical")
                return jsonify({"error": "Invalid email or password"}), 401

            # Clear lockout on success
            try:
                pw_mgr.clear_failed_attempts(user["id"])
            except Exception:
                pass

            # Check if MFA is enabled
            try:
                from .security_hardening import MFAManager
                mfa = MFAManager()
                if mfa.is_enabled(user["id"]):
                    # MFA required — return partial auth, user must submit TOTP code
                    mfa_token = secrets.token_hex(32)
                    # Store pending MFA session (reuse failed_attempts dict temporarily)
                    self._pending_mfa = getattr(self, "_pending_mfa", {})
                    self._pending_mfa[mfa_token] = {
                        "user_id": user["id"],
                        "user": user,
                        "expires": time.time() + 300,  # 5 min
                    }
                    return jsonify({
                        "mfa_required": True,
                        "mfa_token": mfa_token,
                        "user_id": user["id"],
                    })
            except Exception:
                pass

            session["user_id"] = user["id"]
            session.permanent = True
            app.permanent_session_lifetime = timedelta(hours=int(os.getenv("SESSION_HOURS", "24")))
            self.failed_attempts[ip] = 0
            audit.log_auth(user["id"], ip, "/api/auth/login", "POST", "success")
            audit.log("login_success", user_id=user["id"], user_email=user["email"], ip_address=ip)
            # Also return a token for SPA use
            token_info = self.create_token(user["id"], name="web-session", expires_days=7)
            return jsonify({
                "success": True,
                "token": token_info["token"],
                "user": {
                    "id": user["id"], "email": user["email"],
                    "display_name": user["display_name"], "role": user["role"],
                    "avatar_color": user.get("avatar_color", "#6366f1"),
                    "is_active": user["is_active"]
                }
            })

        @app.route("/api/auth/mfa-complete", methods=["POST"])
        def api_mfa_complete():
            """Complete login after MFA verification."""
            data = request.json or {}
            mfa_token = data.get("mfa_token", "")
            code = data.get("code", "")
            pending = getattr(self, "_pending_mfa", {})
            entry = pending.get(mfa_token)

            if not entry or time.time() > entry.get("expires", 0):
                pending.pop(mfa_token, None)
                return jsonify({"error": "MFA session expired, please login again"}), 401

            from .security_hardening import MFAManager
            mfa = MFAManager()
            result = mfa.verify_code(entry["user_id"], code)
            if not result.get("verified"):
                return jsonify({"error": result.get("error", "Invalid MFA code")}), 401

            # MFA verified — complete login
            pending.pop(mfa_token, None)
            user = entry["user"]
            session["user_id"] = user["id"]
            session.permanent = True
            app.permanent_session_lifetime = timedelta(hours=int(os.getenv("SESSION_HOURS", "24")))
            ip = self._get_ip()
            self.failed_attempts[ip] = 0
            audit.log_auth(user["id"], ip, "/api/auth/login", "POST", "success")
            audit.log("login_mfa_success", user_id=user["id"], ip_address=ip)
            token_info = self.create_token(user["id"], name="web-session", expires_days=7)
            return jsonify({
                "success": True,
                "token": token_info["token"],
                "user": {
                    "id": user["id"], "email": user["email"],
                    "display_name": user["display_name"], "role": user["role"],
                    "avatar_color": user.get("avatar_color", "#6366f1"),
                    "is_active": user["is_active"]
                }
            })

        @app.route("/api/auth/register", methods=["POST"])
        def api_register():
            data = request.json
            # Check if any users exist — if not, first user becomes owner
            with get_db() as db:
                count = db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
            if count == 0:
                role = "owner"
            else:
                # Check open registration setting
                with get_db() as db:
                    setting = db.execute("SELECT value FROM workspace_settings WHERE key='open_registration'").fetchone()
                    if not setting or setting["value"] != "1":
                        return jsonify({"error": "Registration is invite-only"}), 403
                role = "member"
            try:
                user = self.users.create_user(
                    email=data.get("email", ""),
                    display_name=data.get("display_name", data.get("name", "")),
                    password=data.get("password", ""),
                    role=role
                )
                session["user_id"] = user["id"]
                token_info = self.create_token(user["id"], name="web-session", expires_days=7)
                return jsonify({
                    "success": True, "token": token_info["token"],
                    "user": {
                        "id": user["id"], "email": user["email"],
                        "display_name": user["display_name"], "role": user["role"],
                        "avatar_color": user.get("avatar_color", "#6366f1"),
                        "is_active": user["is_active"]
                    }
                }), 201
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

        @app.route("/auth/login")
        def login_page():
            return app.send_static_file("login.html") if os.path.exists("static/login.html") else _login_html()

        @app.route("/auth/login", methods=["POST"])
        def login_submit():
            data = request.json
            ip = self._get_ip()
            if self.limiter.is_limited(ip, "auth"):
                return jsonify({"error": "Too many attempts"}), 429
            if not self.users:
                return jsonify({"error": "User system not ready"}), 500
            user = self.users.authenticate(data.get("email", ""), data.get("password", ""))
            if not user:
                self.failed_attempts[ip] += 1
                if self.failed_attempts[ip] >= 5:
                    self.limiter.block_ip(ip)
                return jsonify({"error": "Invalid email or password"}), 401
            session["user_id"] = user["id"]
            session.permanent = True
            app.permanent_session_lifetime = timedelta(hours=int(os.getenv("SESSION_HOURS", "24")))
            self.failed_attempts[ip] = 0
            return jsonify({"success": True, "user": {"id": user["id"], "name": user["display_name"], "role": user["role"]}})

        @app.route("/auth/logout", methods=["POST"])
        def logout():
            session.clear()
            return jsonify({"success": True})

        @app.route("/auth/register", methods=["POST"])
        def register():
            data = request.json
            # Check if registration is open
            with get_db() as db:
                setting = db.execute("SELECT value FROM workspace_settings WHERE key='open_registration'").fetchone()
                if not setting or setting["value"] != "true":
                    return jsonify({"error": "Registration is invite-only"}), 403
            try:
                user = self.users.create_user(
                    email=data.get("email", ""),
                    display_name=data.get("name", ""),
                    password=data.get("password", ""),
                    role="member"
                )
                return jsonify({"success": True, "user_id": user["id"]})
            except ValueError as e:
                return jsonify({"error": str(e)}), 400

        @app.route("/api/auth/tokens", methods=["GET"])
        def list_tokens():
            with get_db() as db:
                rows = db.execute("""
                    SELECT id, name, token_prefix, scopes, created_at, last_used, expires_at, enabled
                    FROM api_tokens WHERE user_id=? ORDER BY created_at
                """, (g.user_id,)).fetchall()
                return jsonify({"tokens": [dict(r) for r in rows]})

        @app.route("/api/auth/tokens", methods=["POST"])
        def create_token_route():
            data = request.json or {}
            info = self.create_token(g.user_id, name=data.get("name", "new-token"))
            return jsonify({"token": info}), 201


def _login_html():
    return '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MyTeam360 — Sign In</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#06060b;color:#ececf4;display:flex;align-items:center;justify-content:center;height:100vh}
.card{background:#0c0c14;border:1px solid #252540;border-radius:16px;padding:40px;width:380px;text-align:center}
.logo{width:48px;height:48px;background:linear-gradient(135deg,#7c5cfc,#a78bfa);border-radius:12px;display:inline-flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;color:#fff;margin-bottom:16px}
h1{font-size:20px;margin-bottom:4px}
.sub{color:#8b8ba8;font-size:13px;margin-bottom:28px}
.field{text-align:left;margin-bottom:14px}
.field label{font-size:11px;color:#8b8ba8;text-transform:uppercase;letter-spacing:.8px;display:block;margin-bottom:4px}
input{width:100%;background:#111119;border:1px solid #252540;border-radius:8px;padding:11px 14px;color:#ececf4;font-family:inherit;font-size:13px;outline:none}
input:focus{border-color:#7c5cfc}
button{width:100%;background:#7c5cfc;border:none;border-radius:8px;padding:12px;color:#fff;font-size:14px;font-weight:600;cursor:pointer;margin-top:8px;transition:.15s}
button:hover{background:#6b4ee0}
.error{color:#f87171;font-size:12px;margin-top:12px;display:none}
</style></head><body>
<div class="card">
<div class="logo">M</div>
<h1>MyTeam360</h1>
<p class="sub">Sign in to your workspace</p>
<form onsubmit="return login(event)">
<div class="field"><label>Email</label><input type="email" id="email" placeholder="you@company.com" autocomplete="email"></div>
<div class="field"><label>Password</label><input type="password" id="pass" placeholder="••••••••" autocomplete="current-password"></div>
<button type="submit">Sign In</button>
</form>
<div class="error" id="err"></div>
</div>
<script>
async function login(e){
e.preventDefault();
const r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({email:document.getElementById('email').value,password:document.getElementById('pass').value})});
const d=await r.json();
if(d.success){window.location.href='/'}
else{const el=document.getElementById('err');el.textContent=d.error||'Login failed';el.style.display='block'}
}
</script></body></html>'''
