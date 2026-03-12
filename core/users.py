# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# This software and all associated intellectual property are owned
# exclusively by Praxis Holdings LLC, a Nevada limited-liability company.
# Licensed to MyTeam360 LLC for operation.
#
# UNAUTHORIZED ACCESS, COPYING, MODIFICATION, DISTRIBUTION, OR USE
# OF THIS SOFTWARE IS STRICTLY PROHIBITED AND MAY RESULT IN CIVIL
# LIABILITY AND CRIMINAL PROSECUTION UNDER FEDERAL AND STATE LAW,
# INCLUDING THE DEFEND TRADE SECRETS ACT (18 U.S.C. § 1836),
# THE COMPUTER FRAUD AND ABUSE ACT (18 U.S.C. § 1030), AND THE
# NEVADA UNIFORM TRADE SECRETS ACT (NRS 600A).
#
# See LICENSE and NOTICE files for full legal terms.
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Users — Multi-user accounts, roles, profiles, preferences, and API key management.
"""

import os
import uuid
import json
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.users")

ROLES = ["owner", "admin", "member", "viewer"]
ROLE_PERMISSIONS = {
    "owner":  {"manage_users", "manage_workspace", "manage_billing", "create_agents", "share_agents", "create_workflows", "run_workflows", "chat", "view_analytics", "manage_clients", "approve"},
    "admin":  {"manage_users", "create_agents", "share_agents", "create_workflows", "run_workflows", "chat", "view_analytics", "manage_clients", "approve"},
    "member": {"create_agents", "create_workflows", "run_workflows", "chat", "share_agents"},
    "viewer": {"chat"},  # can only use shared agents
}


class UserManager:
    """Manages user accounts, authentication, and profiles."""

    def __init__(self):
        self._ensure_owner()

    # ── Password Hashing ──
    def _hash_password(self, password: str) -> str:
        salt = os.getenv("PASSWORD_SALT", "mt360-salt-change-me")
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()

    def _verify_password(self, password: str, password_hash: str) -> bool:
        return self._hash_password(password) == password_hash

    # ── Owner Bootstrap ──
    def _ensure_owner(self):
        """Create default owner account on first run."""
        with get_db() as db:
            owner = db.execute("SELECT id FROM users WHERE role='owner'").fetchone()
            if owner:
                return

            owner_email = os.getenv("OWNER_EMAIL", "admin@localhost")
            owner_pass = os.getenv("OWNER_PASSWORD", "admin123")
            if not owner_pass:
                owner_pass = secrets.token_urlsafe(16)
            logger.warning("=" * 60)
            logger.warning("  DEFAULT OWNER ACCOUNT CREATED")
            logger.warning(f"  Email:    {owner_email}")
            logger.warning(f"  Password: {owner_pass}")
            logger.warning("  Change this immediately after first login!")
            logger.warning("=" * 60)
            # Save to file for retrieval
            cred_file = os.path.join("data", "initial_credentials.txt")
            os.makedirs("data", exist_ok=True)
            with open(cred_file, "w") as f:
                f.write(f"Email: {owner_email}\nPassword: {owner_pass}\nRole: owner\n\nNote: You can also register new accounts at the login screen.\nOpen registration is enabled.\n")
            try:
                os.chmod(cred_file, 0o600)
            except OSError:
                pass

            user_id = f"usr_{uuid.uuid4().hex[:12]}"
            db.execute("""
                INSERT INTO users (id, email, display_name, password_hash, role, avatar_color)
                VALUES (?, ?, ?, ?, 'owner', '#a459f2')
            """, (user_id, owner_email, "Owner", self._hash_password(owner_pass)))

            db.execute("""
                INSERT INTO user_profiles (user_id) VALUES (?)
            """, (user_id,))

    # ── CRUD ──
    def create_user(self, email: str, display_name: str, password: str,
                    role: str = "member", invited_by: str = None) -> dict:
        if role not in ROLES:
            raise ValueError(f"Invalid role: {role}")
        user_id = f"usr_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if existing:
                raise ValueError(f"Email already registered: {email}")
            db.execute("""
                INSERT INTO users (id, email, display_name, password_hash, role, invited_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, email, display_name, self._hash_password(password), role, invited_by))
            db.execute("INSERT INTO user_profiles (user_id) VALUES (?)", (user_id,))
        return self.get_user(user_id)

    def get_user(self, user_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                return None
            return {k: row[k] for k in row.keys()}

    def get_user_by_email(self, email: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if not row:
                return None
            return {k: row[k] for k in row.keys()}

    def list_users(self) -> list:
        with get_db() as db:
            rows = db.execute("SELECT id, email, display_name, role, avatar_color, is_active, created_at, last_login FROM users ORDER BY created_at").fetchall()
            return [dict(r) for r in rows]

    def update_user(self, user_id: str, data: dict) -> dict | None:
        allowed = {"display_name", "role", "avatar_color", "is_active"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return self.get_user(user_id)
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [user_id]
        with get_db() as db:
            db.execute(f"UPDATE users SET {sets} WHERE id=?", vals)
        return self.get_user(user_id)

    def delete_user(self, user_id: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM users WHERE id=? AND role != 'owner'", (user_id,)).rowcount > 0

    def change_password(self, user_id: str, new_password: str):
        with get_db() as db:
            db.execute("UPDATE users SET password_hash=? WHERE id=?",
                       (self._hash_password(new_password), user_id))

    # ── Authentication ──
    def authenticate(self, email: str, password: str) -> dict | None:
        user = self.get_user_by_email(email)
        if not user:
            return None
        if not user["is_active"]:
            return None
        if not self._verify_password(password, user["password_hash"]):
            return None
        with get_db() as db:
            db.execute("UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE id=?", (user["id"],))
        return user

    # ── Permissions ──
    def has_permission(self, user_id: str, permission: str) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        return permission in ROLE_PERMISSIONS.get(user["role"], set())

    def get_permissions(self, user_id: str) -> set:
        user = self.get_user(user_id)
        if not user:
            return set()
        return ROLE_PERMISSIONS.get(user["role"], set())

    # ── Profile ──
    def get_profile(self, user_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
            if not row:
                return {}
            d = dict(row)
            d.pop("user_id", None)
            if d.get("custom_fields"):
                try:
                    d["custom_fields"] = json.loads(d["custom_fields"])
                except Exception:
                    d["custom_fields"] = {}
            return d

    def update_profile(self, user_id: str, data: dict) -> dict:
        allowed = {"name", "title", "company", "industry", "role_description",
                   "expertise_areas", "target_audience", "competitors",
                   "writing_tone", "formality_level", "preferred_length", "avoid_phrases"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if "custom_fields" in data:
            updates["custom_fields"] = json.dumps(data["custom_fields"])
        if not updates:
            return self.get_profile(user_id)
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [user_id]
        with get_db() as db:
            db.execute(f"UPDATE user_profiles SET {sets} WHERE user_id=?", vals)
        return self.get_profile(user_id)

    def get_profile_context(self, user_id: str) -> str:
        """Build context string for agent prompt injection."""
        p = self.get_profile(user_id)
        if not p or not any(p.get(k) for k in ["name", "title", "company"]):
            return ""
        parts = ["[USER PROFILE]"]
        field_map = {"name": "Name", "title": "Title", "company": "Company",
                     "industry": "Industry", "role_description": "Role",
                     "expertise_areas": "Expertise", "target_audience": "Target Audience",
                     "competitors": "Competitors"}
        for key, label in field_map.items():
            if p.get(key):
                parts.append(f"{label}: {p[key]}")
        if isinstance(p.get("custom_fields"), dict):
            for k, v in p["custom_fields"].items():
                parts.append(f"{k}: {v}")
        return "\n".join(parts)

    def get_style_context(self, user_id: str) -> str:
        p = self.get_profile(user_id)
        if not p:
            return ""
        parts = []
        if p.get("writing_tone"):
            parts.append(f"Tone: {p['writing_tone']}")
        if p.get("formality_level"):
            parts.append(f"Formality: {p['formality_level']}")
        if p.get("preferred_length"):
            parts.append(f"Length preference: {p['preferred_length']}")
        if p.get("avoid_phrases"):
            parts.append(f"Avoid: {p['avoid_phrases']}")
        return "\n".join(parts) if parts else ""

    # ── Preferences ──
    def get_preferences(self, user_id: str) -> dict:
        with get_db() as db:
            rows = db.execute("SELECT key, value FROM user_preferences WHERE user_id=?", (user_id,)).fetchall()
            return {r["key"]: r["value"] for r in rows}

    def set_preference(self, user_id: str, key: str, value: str):
        with get_db() as db:
            db.execute("INSERT OR REPLACE INTO user_preferences (user_id, key, value) VALUES (?, ?, ?)",
                       (user_id, key, value))

    # ── Usage & Budget ──
    def log_usage(self, user_id: str, agent_id: str, provider: str, model: str,
                  tokens_in: int, tokens_out: int, cost: float):
        with get_db() as db:
            db.execute("""
                INSERT INTO usage_log (user_id, agent_id, provider, model, tokens_in, tokens_out, cost_estimate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, agent_id, provider, model, tokens_in, tokens_out, cost))

    def get_monthly_usage(self, user_id: str) -> dict:
        with get_db() as db:
            row = db.execute("""
                SELECT COALESCE(SUM(tokens_in),0) as tokens_in,
                       COALESCE(SUM(tokens_out),0) as tokens_out,
                       COALESCE(SUM(cost_estimate),0) as cost,
                       COUNT(*) as requests
                FROM usage_log
                WHERE user_id=? AND created_at >= date('now','start of month')
            """, (user_id,)).fetchone()
            return dict(row)

    def get_workspace_usage(self) -> dict:
        with get_db() as db:
            row = db.execute("""
                SELECT COALESCE(SUM(cost_estimate),0) as total_cost,
                       COUNT(*) as total_requests,
                       COUNT(DISTINCT user_id) as active_users
                FROM usage_log WHERE created_at >= date('now','start of month')
            """).fetchone()
            return dict(row)

    def check_budget(self, user_id: str) -> dict:
        """Check if user is within budget. Returns {allowed, remaining, limit, used, pct}."""
        usage = self.get_monthly_usage(user_id)
        with get_db() as db:
            # Check user limit
            user_limit = db.execute(
                "SELECT monthly_limit, warning_pct, hard_stop FROM budget_limits WHERE scope='user' AND scope_id=?",
                (user_id,)).fetchone()
            # Check workspace limit
            ws_limit = db.execute(
                "SELECT monthly_limit, warning_pct, hard_stop FROM budget_limits WHERE scope='workspace'").fetchone()

        limit = 999999
        hard_stop = False
        if user_limit:
            limit = user_limit["monthly_limit"]
            hard_stop = bool(user_limit["hard_stop"])
        elif ws_limit:
            limit = ws_limit["monthly_limit"]
            hard_stop = bool(ws_limit["hard_stop"])

        used = usage["cost"]
        pct = (used / limit * 100) if limit > 0 else 0
        allowed = not (hard_stop and used >= limit)
        return {"allowed": allowed, "remaining": max(0, limit - used),
                "limit": limit, "used": used, "pct": round(pct, 1)}
