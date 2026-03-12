"""
MyTeam360 — Google OAuth Integration
Handles Google Sign-In flow: redirect → callback → create/login user → token.

Setup:
1. Go to https://console.cloud.google.com/apis/credentials
2. Create OAuth 2.0 Client ID (Web application)
3. Add authorized redirect URI: https://yourdomain.com/api/auth/google/callback
4. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env
"""

import os
import json
import secrets
import logging
import urllib.parse
from datetime import timedelta

import requests
from flask import request, jsonify, redirect, session

from .database import get_db
from .users import UserManager

logger = logging.getLogger("OAuth")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class GoogleOAuth:
    def __init__(self, app=None, security_manager=None, user_manager=None):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        self.enabled = bool(self.client_id and self.client_secret)
        self.security = security_manager
        self.users = user_manager
        self._pending_states = {}  # state → {redirect, expires}

        if app:
            self._register_routes(app)

        if self.enabled:
            logger.info("Google OAuth enabled")
        else:
            logger.info("Google OAuth disabled (no GOOGLE_CLIENT_ID set)")

    def _get_redirect_uri(self):
        """Build callback URL from request or env."""
        base = os.getenv("APP_URL", "").rstrip("/")
        if base:
            return f"{base}/api/auth/google/callback"
        # Infer from request
        scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
        host = request.headers.get("X-Forwarded-Host", request.host)
        return f"{scheme}://{host}/api/auth/google/callback"

    def _register_routes(self, app):

        @app.route("/api/auth/google/status")
        def google_oauth_status():
            """Check if Google OAuth is available."""
            return jsonify({"enabled": self.enabled})

        @app.route("/api/auth/google/start")
        def google_oauth_start():
            """Redirect user to Google consent screen."""
            if not self.enabled:
                return jsonify({"error": "Google OAuth not configured"}), 501

            state = secrets.token_urlsafe(32)
            self._pending_states[state] = True

            params = {
                "client_id": self.client_id,
                "redirect_uri": self._get_redirect_uri(),
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "access_type": "offline",
                "prompt": "select_account",
            }
            url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
            return redirect(url)

        @app.route("/api/auth/google/callback")
        def google_oauth_callback():
            """Handle Google's redirect with auth code."""
            if not self.enabled:
                return _error_page("Google OAuth not configured")

            error = request.args.get("error")
            if error:
                return _error_page(f"Google denied access: {error}")

            code = request.args.get("code")
            state = request.args.get("state")

            if not code:
                return _error_page("No authorization code received")

            if state not in self._pending_states:
                return _error_page("Invalid state — possible CSRF. Try again.")
            del self._pending_states[state]

            # Exchange code for tokens
            try:
                token_resp = requests.post(GOOGLE_TOKEN_URL, data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self._get_redirect_uri(),
                    "grant_type": "authorization_code",
                }, timeout=10)

                if token_resp.status_code != 200:
                    logger.error(f"Token exchange failed: {token_resp.text}")
                    return _error_page("Failed to verify with Google")

                tokens = token_resp.json()
                access_token = tokens.get("access_token")
            except Exception as e:
                logger.error(f"Token exchange error: {e}")
                return _error_page("Failed to connect to Google")

            # Get user info
            try:
                user_resp = requests.get(GOOGLE_USERINFO_URL, headers={
                    "Authorization": f"Bearer {access_token}"
                }, timeout=10)

                if user_resp.status_code != 200:
                    return _error_page("Failed to get user info from Google")

                guser = user_resp.json()
            except Exception as e:
                logger.error(f"Userinfo error: {e}")
                return _error_page("Failed to get user info")

            email = guser.get("email", "")
            name = guser.get("name", email.split("@")[0])
            picture = guser.get("picture", "")
            google_id = guser.get("id", "")

            if not email:
                return _error_page("No email returned from Google")

            logger.info(f"Google OAuth: {email} ({name})")

            # Find or create user
            user = self._find_or_create_user(email, name, google_id, picture)
            if not user:
                return _error_page("Failed to create account")

            # Create session + token
            session["user_id"] = user["id"]
            session.permanent = True
            app.permanent_session_lifetime = timedelta(hours=24)

            token_info = self.security.create_token(user["id"], name="google-oauth", expires_days=7)

            # Redirect to app with token in fragment (never in URL params for security)
            return _success_page(token_info["token"], user)

    def _find_or_create_user(self, email, name, google_id, picture):
        """Find existing user by email or create a new one."""
        with get_db() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        if row:
            # Existing user — update google_id if not set
            user = dict(row)
            try:
                with get_db() as db:
                    db.execute(
                        "UPDATE users SET google_id=?, avatar_url=? WHERE id=?",
                        (google_id, picture, user["id"])
                    )
            except Exception:
                pass  # Column might not exist yet
            return user

        # New user — check if this is the first user (becomes owner)
        with get_db() as db:
            count = db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]

        role = "owner" if count == 0 else "member"

        try:
            # Create with a random password (they'll use OAuth to login)
            random_pass = secrets.token_urlsafe(32)
            user = self.users.create_user(
                email=email,
                display_name=name,
                password=random_pass,
                role=role
            )
            # Store google_id
            try:
                with get_db() as db:
                    db.execute(
                        "UPDATE users SET google_id=?, avatar_url=? WHERE id=?",
                        (google_id, picture, user["id"])
                    )
            except Exception:
                pass

            logger.info(f"Created new user via Google OAuth: {email} ({role})")
            return user
        except Exception as e:
            logger.error(f"Failed to create OAuth user: {e}")
            return None


def _error_page(message):
    """Return a simple error page that redirects to login."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Login Error</title>
    <style>body{{font-family:system-ui;background:#050509;color:#eee;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px}}
    .msg{{color:#f87171;font-size:16px;max-width:400px;text-align:center}}a{{color:#8b5cf6;text-decoration:none}}</style></head>
    <body><div class="msg">{message}</div><a href="/app">← Back to Login</a></body></html>"""


def _success_page(token, user):
    """Page that stores the token and redirects to the app."""
    user_json = json.dumps({
        "id": user["id"],
        "email": user["email"],
        "display_name": user.get("display_name", ""),
        "role": user.get("role", "member"),
        "avatar_color": user.get("avatar_color", "#6366f1"),
        "is_active": user.get("is_active", 1),
    })
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Signing in...</title>
    <style>body{{font-family:system-ui;background:#050509;color:#eee;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:12px}}
    .spin{{width:40px;height:40px;border:3px solid #1c1c36;border-top-color:#8b5cf6;border-radius:50%;animation:s 0.8s linear infinite}}
    @keyframes s{{to{{transform:rotate(360deg)}}}}</style></head>
    <body><div class="spin"></div><div>Signing you in...</div>
    <script>
    localStorage.setItem('mt_t','{token}');
    localStorage.setItem('mt_u',JSON.stringify({user_json}));
    window.location.href='/app';
    </script></body></html>"""
