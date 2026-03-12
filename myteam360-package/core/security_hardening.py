"""
Security Hardening — Enterprise security layer for MyTeam360.
1. Encryption at rest (Fernet) for API keys, OAuth secrets, tokens
2. Password policies (complexity, expiry, history, breach detection)
3. Session management (timeout, max sessions, device tracking)
4. MFA/TOTP (authenticator app support with QR provisioning)
5. DLP (Data Loss Prevention) — scans prompts for PII/sensitive data
"""

import os
import re
import json
import hmac
import time
import uuid
import base64
import hashlib
import struct
import secrets
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.security_hardening")


# ══════════════════════════════════════════════════════════════
# 1. ENCRYPTION AT REST — Fernet-based field encryption
# ══════════════════════════════════════════════════════════════

class FieldEncryptor:
    """Encrypt/decrypt sensitive fields (API keys, tokens, secrets).
    Uses Fernet symmetric encryption with a master key derived from
    an environment variable or auto-generated and stored locally."""

    def __init__(self):
        self._fernet = None
        self._init_key()

    def _init_key(self):
        from cryptography.fernet import Fernet

        # Priority: env var > key file > generate new
        master = os.getenv("MT360_ENCRYPTION_KEY", "")
        if master:
            self._fernet = Fernet(master.encode() if isinstance(master, str) else master)
            return

        key_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", ".encryption_key")
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                self._fernet = Fernet(f.read().strip())
            return

        # Generate and save new key
        key = Fernet.generate_key()
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        with open(key_path, "wb") as f:
            f.write(key)
        os.chmod(key_path, 0o600)  # Owner read/write only
        self._fernet = Fernet(key)
        logger.info("Generated new encryption key")

    def encrypt(self, plaintext):
        """Encrypt a string. Returns base64 token prefixed with 'enc:'."""
        if not plaintext or not self._fernet:
            return plaintext
        if isinstance(plaintext, str):
            plaintext = plaintext.encode()
        token = self._fernet.encrypt(plaintext)
        return "enc:" + token.decode()

    def decrypt(self, ciphertext):
        """Decrypt an 'enc:' prefixed string. Returns plaintext."""
        if not ciphertext or not self._fernet:
            return ciphertext
        if not ciphertext.startswith("enc:"):
            return ciphertext  # Not encrypted, return as-is (backward compat)
        try:
            token = ciphertext[4:].encode()
            return self._fernet.decrypt(token).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None

    def is_encrypted(self, value):
        return isinstance(value, str) and value.startswith("enc:")

    def rotate_key(self, new_key=None):
        """Re-encrypt all sensitive fields with a new key."""
        from cryptography.fernet import Fernet

        old_fernet = self._fernet
        new_key = new_key or Fernet.generate_key()
        new_fernet = Fernet(new_key)

        reencrypted = 0
        with get_db() as db:
            # Re-encrypt provider_auth fields
            rows = db.execute("SELECT id, api_key, oauth_client_secret, oauth_access_token, oauth_refresh_token FROM provider_auth").fetchall()
            for row in rows:
                updates, vals = [], []
                for field in ["api_key", "oauth_client_secret", "oauth_access_token", "oauth_refresh_token"]:
                    val = row[field]
                    if val and val.startswith("enc:"):
                        # Decrypt with old key, re-encrypt with new
                        plain = old_fernet.decrypt(val[4:].encode()).decode()
                        new_val = "enc:" + new_fernet.encrypt(plain.encode()).decode()
                        updates.append(f"{field}=?")
                        vals.append(new_val)
                        reencrypted += 1
                if updates:
                    vals.append(row["id"])
                    db.execute(f"UPDATE provider_auth SET {','.join(updates)} WHERE id=?", vals)

            # Re-encrypt MFA secrets
            mfa_rows = db.execute("SELECT user_id, totp_secret FROM mfa_config WHERE totp_secret IS NOT NULL").fetchall()
            for row in mfa_rows:
                val = row["totp_secret"]
                if val and val.startswith("enc:"):
                    plain = old_fernet.decrypt(val[4:].encode()).decode()
                    new_val = "enc:" + new_fernet.encrypt(plain.encode()).decode()
                    db.execute("UPDATE mfa_config SET totp_secret=? WHERE user_id=?", (new_val, row["user_id"]))
                    reencrypted += 1

        # Save new key
        self._fernet = new_fernet
        key_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", ".encryption_key")
        with open(key_path, "wb") as f:
            f.write(new_key if isinstance(new_key, bytes) else new_key.encode())
        os.chmod(key_path, 0o600)

        logger.info(f"Key rotation complete: {reencrypted} fields re-encrypted")
        return {"rotated": True, "fields_reencrypted": reencrypted}


# Singleton instance
_encryptor = None
def get_encryptor():
    global _encryptor
    if _encryptor is None:
        _encryptor = FieldEncryptor()
    return _encryptor


# ══════════════════════════════════════════════════════════════
# 2. PASSWORD POLICIES — Complexity, expiry, history, breach
# ══════════════════════════════════════════════════════════════

DEFAULT_PASSWORD_POLICY = {
    "min_length": 10,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_digit": True,
    "require_special": True,
    "max_age_days": 90,           # Force reset after N days (0 = never)
    "history_count": 5,           # Prevent reuse of last N passwords
    "max_failed_attempts": 5,     # Lock account after N failures
    "lockout_duration_min": 15,   # Account lockout duration
    "check_breached": True,       # Check HaveIBeenPwned (k-anonymity)
}


class PasswordPolicyManager:
    """Enforce password complexity, rotation, history, and breach detection."""

    def __init__(self):
        self.policy = dict(DEFAULT_PASSWORD_POLICY)

    def get_policy(self):
        """Get current password policy settings."""
        return dict(self.policy)

    def update_policy(self, updates):
        """Update password policy (admin only)."""
        for k, v in updates.items():
            if k in self.policy:
                self.policy[k] = v
        return self.policy

    def validate_password(self, password, user_id=None):
        """Validate password against policy. Returns {valid, errors[]}."""
        errors = []
        p = self.policy

        if len(password) < p["min_length"]:
            errors.append(f"Must be at least {p['min_length']} characters")
        if p["require_uppercase"] and not re.search(r"[A-Z]", password):
            errors.append("Must contain at least one uppercase letter")
        if p["require_lowercase"] and not re.search(r"[a-z]", password):
            errors.append("Must contain at least one lowercase letter")
        if p["require_digit"] and not re.search(r"\d", password):
            errors.append("Must contain at least one number")
        if p["require_special"] and not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]", password):
            errors.append("Must contain at least one special character")

        # Common password check
        common = ["password", "123456", "qwerty", "admin", "letmein", "welcome",
                  "monkey", "dragon", "master", "abc123", "password1", "changeme"]
        if password.lower() in common:
            errors.append("This password is too common")

        # History check
        if user_id and p["history_count"] > 0:
            if self._check_history(password, user_id, p["history_count"]):
                errors.append(f"Cannot reuse your last {p['history_count']} passwords")

        return {"valid": len(errors) == 0, "errors": errors}

    def check_breached(self, password):
        """Check password against HaveIBeenPwned using k-anonymity.
        Sends only first 5 chars of SHA1 hash — the full password never leaves the server."""
        if not self.policy.get("check_breached"):
            return {"breached": False, "count": 0}

        try:
            import urllib.request
            sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
            prefix, suffix = sha1[:5], sha1[5:]

            req = urllib.request.Request(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={"User-Agent": "MyTeam360-Security"})
            resp = urllib.request.urlopen(req, timeout=5)
            body = resp.read().decode()

            for line in body.splitlines():
                h, count = line.strip().split(":")
                if h == suffix:
                    return {"breached": True, "count": int(count)}

            return {"breached": False, "count": 0}
        except Exception as e:
            logger.warning(f"Breach check failed: {e}")
            return {"breached": False, "count": 0, "error": "Check unavailable"}

    def record_password_change(self, user_id, password_hash):
        """Record password hash in history for reuse prevention."""
        with get_db() as db:
            db.execute(
                "INSERT INTO password_history (id, user_id, password_hash)"
                " VALUES (?, ?, ?)",
                (f"ph_{uuid.uuid4().hex[:8]}", user_id, password_hash))
            # Prune old entries
            count = self.policy["history_count"]
            old = db.execute(
                "SELECT id FROM password_history WHERE user_id=? ORDER BY created_at DESC"
                " LIMIT -1 OFFSET ?", (user_id, count)).fetchall()
            for row in old:
                db.execute("DELETE FROM password_history WHERE id=?", (row["id"],))

    def _check_history(self, password, user_id, count):
        """Check if password matches any recent password hashes."""
        with get_db() as db:
            rows = db.execute(
                "SELECT password_hash FROM password_history WHERE user_id=?"
                " ORDER BY created_at DESC LIMIT ?", (user_id, count)).fetchall()

        for row in rows:
            # Use bcrypt-style check if available, otherwise SHA256 comparison
            stored = row["password_hash"]
            test_hash = hashlib.sha256(password.encode()).hexdigest()
            if stored == test_hash:
                return True
        return False

    def check_password_expiry(self, user_id):
        """Check if user's password has expired."""
        max_age = self.policy["max_age_days"]
        if max_age <= 0:
            return {"expired": False}

        with get_db() as db:
            row = db.execute(
                "SELECT created_at FROM password_history WHERE user_id=?"
                " ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()

        if not row:
            return {"expired": False, "no_history": True}

        try:
            last_change = datetime.fromisoformat(row["created_at"])
            expires_at = last_change + timedelta(days=max_age)
            now = datetime.utcnow()
            return {
                "expired": now > expires_at,
                "last_changed": last_change.isoformat(),
                "expires_at": expires_at.isoformat(),
                "days_remaining": max(0, (expires_at - now).days),
            }
        except Exception:
            return {"expired": False}

    def check_lockout(self, user_id):
        """Check if account is locked due to failed attempts."""
        with get_db() as db:
            row = db.execute(
                "SELECT failed_attempts, locked_until FROM account_lockout WHERE user_id=?",
                (user_id,)).fetchone()

        if not row:
            return {"locked": False, "attempts": 0}

        if row["locked_until"]:
            try:
                locked_until = datetime.fromisoformat(row["locked_until"])
                if datetime.utcnow() < locked_until:
                    remaining = (locked_until - datetime.utcnow()).total_seconds()
                    return {"locked": True, "attempts": row["failed_attempts"],
                            "locked_until": row["locked_until"], "remaining_seconds": int(remaining)}
            except Exception:
                pass

        return {"locked": False, "attempts": row["failed_attempts"]}

    def record_failed_attempt(self, user_id):
        """Record a failed login attempt and potentially lock the account."""
        with get_db() as db:
            row = db.execute(
                "SELECT failed_attempts FROM account_lockout WHERE user_id=?",
                (user_id,)).fetchone()

            if row:
                new_count = row["failed_attempts"] + 1
                locked_until = None
                if new_count >= self.policy["max_failed_attempts"]:
                    locked_until = (datetime.utcnow() + timedelta(
                        minutes=self.policy["lockout_duration_min"])).isoformat()
                db.execute(
                    "UPDATE account_lockout SET failed_attempts=?, locked_until=? WHERE user_id=?",
                    (new_count, locked_until, user_id))
            else:
                db.execute(
                    "INSERT INTO account_lockout (user_id, failed_attempts) VALUES (?, 1)",
                    (user_id,))

    def clear_failed_attempts(self, user_id):
        """Clear failed attempts after successful login."""
        with get_db() as db:
            db.execute(
                "UPDATE account_lockout SET failed_attempts=0, locked_until=NULL WHERE user_id=?",
                (user_id,))


# ══════════════════════════════════════════════════════════════
# 3. SESSION MANAGEMENT — Timeout, device tracking, limits
# ══════════════════════════════════════════════════════════════

DEFAULT_SESSION_POLICY = {
    "idle_timeout_min": 30,       # Logout after N min of inactivity
    "absolute_timeout_hours": 12, # Max session length regardless of activity
    "max_sessions_per_user": 5,   # Max concurrent sessions
}


class SessionManager:
    """Track active sessions with timeout and device info."""

    def __init__(self):
        self.policy = dict(DEFAULT_SESSION_POLICY)

    def create_session(self, user_id, ip_address=None, user_agent=None):
        """Create a tracked session."""
        session_id = f"ses_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        device = self._parse_user_agent(user_agent or "")

        with get_db() as db:
            # Enforce max sessions
            active = db.execute(
                "SELECT id FROM active_sessions WHERE user_id=? AND is_active=1"
                " ORDER BY last_activity DESC",
                (user_id,)).fetchall()

            if len(active) >= self.policy["max_sessions_per_user"]:
                # Kill oldest session
                oldest = active[-1]["id"]
                db.execute("UPDATE active_sessions SET is_active=0 WHERE id=?", (oldest,))

            db.execute(
                "INSERT INTO active_sessions (id, user_id, ip_address, user_agent,"
                " device_type, last_activity, created_at) VALUES (?,?,?,?,?,?,?)",
                (session_id, user_id, ip_address, user_agent, device, now, now))

        return session_id

    def validate_session(self, session_id):
        """Check if session is still valid. Returns user_id or None."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM active_sessions WHERE id=? AND is_active=1",
                (session_id,)).fetchone()

        if not row:
            return None

        now = datetime.utcnow()

        # Check idle timeout
        try:
            last_activity = datetime.fromisoformat(row["last_activity"])
            idle_limit = timedelta(minutes=self.policy["idle_timeout_min"])
            if now - last_activity > idle_limit:
                self.end_session(session_id, reason="idle_timeout")
                return None
        except Exception:
            pass

        # Check absolute timeout
        try:
            created = datetime.fromisoformat(row["created_at"])
            abs_limit = timedelta(hours=self.policy["absolute_timeout_hours"])
            if now - created > abs_limit:
                self.end_session(session_id, reason="absolute_timeout")
                return None
        except Exception:
            pass

        # Update last activity
        with get_db() as db:
            db.execute(
                "UPDATE active_sessions SET last_activity=? WHERE id=?",
                (now.isoformat(), session_id))

        return row["user_id"]

    def end_session(self, session_id, reason="manual"):
        with get_db() as db:
            db.execute(
                "UPDATE active_sessions SET is_active=0, ended_at=CURRENT_TIMESTAMP WHERE id=?",
                (session_id,))

    def end_all_sessions(self, user_id, except_session=None):
        """Kill all sessions for a user (password change, security event)."""
        with get_db() as db:
            if except_session:
                db.execute(
                    "UPDATE active_sessions SET is_active=0, ended_at=CURRENT_TIMESTAMP"
                    " WHERE user_id=? AND is_active=1 AND id!=?",
                    (user_id, except_session))
            else:
                db.execute(
                    "UPDATE active_sessions SET is_active=0, ended_at=CURRENT_TIMESTAMP"
                    " WHERE user_id=? AND is_active=1", (user_id,))

    def list_sessions(self, user_id):
        with get_db() as db:
            rows = db.execute(
                "SELECT id, ip_address, device_type, last_activity, created_at"
                " FROM active_sessions WHERE user_id=? AND is_active=1"
                " ORDER BY last_activity DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def _parse_user_agent(self, ua):
        ua_lower = ua.lower()
        if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
            return "mobile"
        elif "tablet" in ua_lower or "ipad" in ua_lower:
            return "tablet"
        elif "macintosh" in ua_lower or "windows" in ua_lower or "linux" in ua_lower:
            return "desktop"
        return "unknown"


# ══════════════════════════════════════════════════════════════
# 4. MFA / TOTP — Authenticator App Support
# ══════════════════════════════════════════════════════════════

class MFAManager:
    """TOTP-based multi-factor authentication.
    Compatible with Google Authenticator, Authy, 1Password, etc."""

    ISSUER = "MyTeam360"

    def setup_totp(self, user_id):
        """Generate a new TOTP secret and provisioning URI for QR code."""
        import pyotp

        secret = pyotp.random_base32()
        enc = get_encryptor()
        encrypted_secret = enc.encrypt(secret)

        with get_db() as db:
            user = db.execute("SELECT email, display_name FROM users WHERE id=?", (user_id,)).fetchone()
            email = user["email"] if user else user_id

            # Store secret (not yet verified)
            db.execute("""
                INSERT OR REPLACE INTO mfa_config
                (user_id, method, totp_secret, is_verified, is_enabled, created_at)
                VALUES (?, 'totp', ?, 0, 0, CURRENT_TIMESTAMP)
            """, (user_id, encrypted_secret))

        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(name=email, issuer_name=self.ISSUER)

        # Generate QR code as base64 PNG
        qr_b64 = self._generate_qr(provisioning_uri)

        # Generate backup codes
        backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
        with get_db() as db:
            db.execute(
                "UPDATE mfa_config SET backup_codes=? WHERE user_id=?",
                (json.dumps(backup_codes), user_id))

        return {
            "secret": secret,  # Show once during setup
            "provisioning_uri": provisioning_uri,
            "qr_code": qr_b64,
            "backup_codes": backup_codes,
        }

    def verify_setup(self, user_id, code):
        """Verify the first TOTP code to activate MFA."""
        secret = self._get_secret(user_id)
        if not secret:
            return {"verified": False, "error": "MFA not configured"}

        import pyotp
        totp = pyotp.TOTP(secret)
        if totp.verify(code, valid_window=1):
            with get_db() as db:
                db.execute(
                    "UPDATE mfa_config SET is_verified=1, is_enabled=1 WHERE user_id=?",
                    (user_id,))
            logger.info(f"MFA enabled for user {user_id}")
            return {"verified": True, "mfa_enabled": True}

        return {"verified": False, "error": "Invalid code. Try again."}

    def verify_code(self, user_id, code):
        """Verify a TOTP code during login."""
        # Check backup codes first
        if self._check_backup_code(user_id, code):
            return {"verified": True, "method": "backup_code"}

        secret = self._get_secret(user_id)
        if not secret:
            return {"verified": False, "error": "MFA not configured"}

        import pyotp
        totp = pyotp.TOTP(secret)
        if totp.verify(code, valid_window=1):
            return {"verified": True, "method": "totp"}

        return {"verified": False, "error": "Invalid code"}

    def is_enabled(self, user_id):
        """Check if MFA is enabled for a user."""
        with get_db() as db:
            row = db.execute(
                "SELECT is_enabled, is_verified FROM mfa_config WHERE user_id=?",
                (user_id,)).fetchone()
        if not row:
            return False
        return bool(row["is_enabled"] and row["is_verified"])

    def disable(self, user_id, admin_id=None):
        """Disable MFA for a user (requires admin or self)."""
        with get_db() as db:
            db.execute(
                "UPDATE mfa_config SET is_enabled=0 WHERE user_id=?", (user_id,))
        logger.info(f"MFA disabled for {user_id} by {admin_id or user_id}")
        return {"disabled": True}

    def get_status(self, user_id):
        with get_db() as db:
            row = db.execute(
                "SELECT method, is_verified, is_enabled, created_at FROM mfa_config WHERE user_id=?",
                (user_id,)).fetchone()
        if not row:
            return {"configured": False, "enabled": False}
        return {
            "configured": True,
            "enabled": bool(row["is_enabled"]),
            "verified": bool(row["is_verified"]),
            "method": row["method"],
            "configured_at": row["created_at"],
        }

    def _get_secret(self, user_id):
        with get_db() as db:
            row = db.execute(
                "SELECT totp_secret FROM mfa_config WHERE user_id=? AND is_enabled=1",
                (user_id,)).fetchone()
        if not row or not row["totp_secret"]:
            return None

        enc = get_encryptor()
        return enc.decrypt(row["totp_secret"])

    def _check_backup_code(self, user_id, code):
        code = code.strip().upper()
        with get_db() as db:
            row = db.execute(
                "SELECT backup_codes FROM mfa_config WHERE user_id=?",
                (user_id,)).fetchone()
        if not row or not row["backup_codes"]:
            return False

        try:
            codes = json.loads(row["backup_codes"])
            if code in codes:
                codes.remove(code)
                with get_db() as db:
                    db.execute(
                        "UPDATE mfa_config SET backup_codes=? WHERE user_id=?",
                        (json.dumps(codes), user_id))
                logger.info(f"Backup code used for {user_id}, {len(codes)} remaining")
                return True
        except Exception:
            pass
        return False

    def _generate_qr(self, data):
        """Generate QR code as base64 PNG."""
        try:
            import qrcode
            import io
            qr = qrcode.QRCode(version=1, box_size=8, border=2)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            logger.warning(f"QR generation failed: {e}")
            return ""


# ══════════════════════════════════════════════════════════════
# 5. DLP — Data Loss Prevention / PII Scanning
# ══════════════════════════════════════════════════════════════

class DLPScanner:
    """Scan user input and AI output for sensitive data patterns.
    Detects: SSN, credit cards, bank accounts, passwords, API keys, emails, phone numbers.
    Can redact or block based on policy."""

    PATTERNS = {
        "ssn": {
            "pattern": re.compile(r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b'),
            "label": "Social Security Number",
            "severity": "critical",
            "action": "block",
        },
        "credit_card": {
            "pattern": re.compile(r'\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))\d{8,12}\b'),
            "label": "Credit Card Number",
            "severity": "critical",
            "action": "block",
        },
        "credit_card_formatted": {
            "pattern": re.compile(r'\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}\b'),
            "label": "Credit Card Number (formatted)",
            "severity": "critical",
            "action": "block",
        },
        "api_key_generic": {
            "pattern": re.compile(r'\b(?:sk-[a-zA-Z0-9]{20,}|sk-ant-[a-zA-Z0-9-]{20,}|xai-[a-zA-Z0-9]{20,}|AIza[a-zA-Z0-9_-]{35})\b'),
            "label": "API Key",
            "severity": "high",
            "action": "warn",
        },
        "aws_key": {
            "pattern": re.compile(r'\b(?:AKIA|ABIA|ACCA)[A-Z0-9]{16}\b'),
            "label": "AWS Access Key",
            "severity": "critical",
            "action": "block",
        },
        "private_key": {
            "pattern": re.compile(r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----'),
            "label": "Private Key",
            "severity": "critical",
            "action": "block",
        },
        "password_in_text": {
            "pattern": re.compile(r'(?i)(?:password|passwd|pwd)\s*[:=]\s*\S{6,}'),
            "label": "Password in Text",
            "severity": "high",
            "action": "warn",
        },
        "bank_account": {
            "pattern": re.compile(r'(?i)\b\d{8,17}\b.*(?:routing|account|iban|swift|bic)|\b(?:routing|account|iban|swift|bic)\b.*\d{8,17}'),
            "label": "Bank Account / Routing Number",
            "severity": "high",
            "action": "warn",
        },
        "phone_us": {
            "pattern": re.compile(r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
            "label": "US Phone Number",
            "severity": "low",
            "action": "flag",
        },
        "email_address": {
            "pattern": re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'),
            "label": "Email Address",
            "severity": "low",
            "action": "flag",
        },
    }

    # DLP policy defaults
    DEFAULT_POLICY = {
        "enabled": True,
        "scan_input": True,          # Scan user messages
        "scan_output": False,        # Scan AI responses
        "block_on_critical": True,   # Block messages with critical PII
        "warn_on_high": True,        # Show warning for high severity
        "log_detections": True,      # Log to audit trail
        "redact_in_logs": True,      # Redact PII in audit log entries
        "custom_patterns": [],       # Admin-defined patterns
        "exempted_roles": ["owner"], # Roles that bypass DLP
    }

    def __init__(self):
        self.policy = dict(self.DEFAULT_POLICY)

    def scan(self, text, context="input"):
        """Scan text for sensitive data. Returns {clean, findings[], action}."""
        if not self.policy["enabled"]:
            return {"clean": True, "findings": [], "action": "allow"}
        if context == "input" and not self.policy["scan_input"]:
            return {"clean": True, "findings": [], "action": "allow"}
        if context == "output" and not self.policy["scan_output"]:
            return {"clean": True, "findings": [], "action": "allow"}

        findings = []
        for pid, pdef in self.PATTERNS.items():
            matches = pdef["pattern"].findall(text)
            if matches:
                findings.append({
                    "pattern_id": pid,
                    "label": pdef["label"],
                    "severity": pdef["severity"],
                    "action": pdef["action"],
                    "match_count": len(matches),
                    "matches": [self._redact_match(m) for m in matches[:3]],  # Redact in response
                })

        if not findings:
            return {"clean": True, "findings": [], "action": "allow"}

        # Determine overall action
        severities = [f["severity"] for f in findings]
        if "critical" in severities and self.policy["block_on_critical"]:
            action = "block"
        elif "high" in severities and self.policy["warn_on_high"]:
            action = "warn"
        else:
            action = "flag"

        return {
            "clean": False,
            "findings": findings,
            "action": action,
            "message": self._build_message(findings, action),
        }

    def redact_text(self, text):
        """Replace detected PII with redaction markers."""
        redacted = text
        for pid, pdef in self.PATTERNS.items():
            redacted = pdef["pattern"].sub(f"[{pdef['label'].upper()} REDACTED]", redacted)
        return redacted

    def log_detection(self, user_id, text, scan_result, context="input"):
        """Log DLP detection to audit trail."""
        if not self.policy["log_detections"]:
            return

        detail = f"DLP {context}: {len(scan_result['findings'])} findings, action={scan_result['action']}"
        for f in scan_result["findings"]:
            detail += f" | {f['label']}({f['severity']}): {f['match_count']} matches"

        try:
            with get_db() as db:
                db.execute(
                    "INSERT INTO audit_log (id, user_id, action, resource_type, detail, severity)"
                    " VALUES (?, ?, 'dlp_detection', 'security', ?, ?)",
                    (f"aud_{uuid.uuid4().hex[:8]}", user_id, detail,
                     "critical" if scan_result["action"] == "block" else "warning"))
        except Exception as e:
            logger.error(f"DLP log failed: {e}")

    def get_policy(self):
        return dict(self.policy)

    def update_policy(self, updates):
        for k, v in updates.items():
            if k in self.policy:
                self.policy[k] = v
        return self.policy

    def _redact_match(self, match):
        """Redact a matched string, showing only first/last 2 chars."""
        m = str(match)
        if len(m) <= 6:
            return "***"
        return m[:2] + "*" * (len(m) - 4) + m[-2:]

    def _build_message(self, findings, action):
        labels = list(set(f["label"] for f in findings))
        if action == "block":
            return f"Message blocked — detected sensitive data: {', '.join(labels)}. Please remove before sending."
        elif action == "warn":
            return f"Warning — potential sensitive data detected: {', '.join(labels)}. Proceed with caution."
        return f"Note: detected {', '.join(labels)} in your message."
