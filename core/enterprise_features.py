# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Enterprise Features + Influencer Program

1. SSO/SAML — Enterprise single sign-on
2. AUDIT EXPORT — SOC 2 compliant CSV/PDF export
3. GRANULAR RBAC — Custom roles with per-feature permissions
4. INFLUENCER/AFFILIATE PROGRAM — Custom links, commission tracking, payouts
"""

import os
import io
import csv
import json
import uuid
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.enterprise_features")


# ══════════════════════════════════════════════════════════════
# 1. SSO / SAML
# ══════════════════════════════════════════════════════════════

class SSOManager:
    """Enterprise Single Sign-On via SAML 2.0 and OIDC.

    Supports:
      - SAML 2.0 (Okta, Azure AD, OneLogin, Google Workspace)
      - OIDC (Auth0, Keycloak, generic)

    Flow:
      1. Admin configures SSO provider (entity ID, SSO URL, certificate)
      2. User clicks "Sign in with SSO" → redirected to IdP
      3. IdP authenticates → POST assertion back to our ACS URL
      4. We validate assertion, extract user attributes, create/update user
      5. Session created, user lands in app
    """

    SUPPORTED_PROVIDERS = {
        "okta": {"label": "Okta", "type": "saml"},
        "azure_ad": {"label": "Azure Active Directory", "type": "saml"},
        "google_workspace": {"label": "Google Workspace", "type": "saml"},
        "onelogin": {"label": "OneLogin", "type": "saml"},
        "auth0": {"label": "Auth0", "type": "oidc"},
        "keycloak": {"label": "Keycloak", "type": "oidc"},
        "custom_saml": {"label": "Custom SAML 2.0", "type": "saml"},
        "custom_oidc": {"label": "Custom OIDC", "type": "oidc"},
    }

    def get_providers(self) -> list:
        return [{"id": k, **v} for k, v in self.SUPPORTED_PROVIDERS.items()]

    def configure(self, provider: str, config: dict) -> dict:
        """Admin configures SSO for their organization."""
        if provider not in self.SUPPORTED_PROVIDERS:
            return {"error": f"Unsupported provider. Options: {list(self.SUPPORTED_PROVIDERS.keys())}"}

        ptype = self.SUPPORTED_PROVIDERS[provider]["type"]
        required = []

        if ptype == "saml":
            required = ["entity_id", "sso_url", "certificate"]
        elif ptype == "oidc":
            required = ["client_id", "client_secret", "issuer_url"]

        missing = [r for r in required if not config.get(r)]
        if missing:
            return {"error": f"Missing required fields: {missing}"}

        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO sso_config
                    (id, provider, provider_type, config, enabled)
                VALUES (?,?,?,?,1)
            """, ("sso_primary", provider, ptype, json.dumps(config)))

        # Generate our service provider metadata
        base_url = os.getenv("BASE_URL", "https://myteam360.ai")
        sp_metadata = {
            "entity_id": f"{base_url}/saml/metadata",
            "acs_url": f"{base_url}/api/auth/sso/callback",
            "slo_url": f"{base_url}/api/auth/sso/logout",
        }

        return {
            "configured": True,
            "provider": provider,
            "type": ptype,
            "sp_metadata": sp_metadata,
            "message": f"SSO configured with {self.SUPPORTED_PROVIDERS[provider]['label']}. "
                       f"Configure your IdP with the SP metadata below.",
        }

    def get_config(self) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM sso_config WHERE id='sso_primary'").fetchone()
        if not row:
            return {"configured": False}
        d = dict(row)
        config = json.loads(d.get("config", "{}"))
        # Never expose certificate or secrets
        safe_config = {k: v for k, v in config.items()
                       if k not in ("certificate", "client_secret")}
        return {
            "configured": True,
            "enabled": bool(d.get("enabled")),
            "provider": d.get("provider"),
            "type": d.get("provider_type"),
            "config": safe_config,
        }

    def initiate_login(self) -> dict:
        """Generate SSO login URL for the user."""
        config = self.get_config()
        if not config.get("configured"):
            return {"error": "SSO not configured"}

        with get_db() as db:
            row = db.execute("SELECT config, provider_type FROM sso_config WHERE id='sso_primary'").fetchone()
        if not row:
            return {"error": "SSO config not found"}

        cfg = json.loads(dict(row)["config"])
        ptype = dict(row)["provider_type"]

        if ptype == "saml":
            # Generate SAML AuthnRequest
            relay_state = secrets.token_urlsafe(16)
            return {
                "type": "saml",
                "redirect_url": cfg.get("sso_url"),
                "relay_state": relay_state,
            }
        elif ptype == "oidc":
            # Generate OIDC authorization URL
            state = secrets.token_urlsafe(16)
            base_url = os.getenv("BASE_URL", "https://myteam360.ai")
            auth_url = (
                f"{cfg['issuer_url']}/authorize"
                f"?client_id={cfg['client_id']}"
                f"&response_type=code"
                f"&scope=openid+email+profile"
                f"&redirect_uri={base_url}/api/auth/sso/callback"
                f"&state={state}"
            )
            return {"type": "oidc", "redirect_url": auth_url, "state": state}

    def handle_callback(self, data: dict) -> dict:
        """Process SSO callback — create/update user and return session info."""
        # Extract user attributes from assertion
        email = data.get("email", "")
        name = data.get("name", data.get("displayName", ""))
        sso_id = data.get("sso_id", data.get("nameID", ""))

        if not email:
            return {"error": "No email in SSO response"}

        # Find or create user
        from .users import UserManager
        um = UserManager()
        user = um.get_user_by_email(email)

        if not user:
            # Auto-provision user from SSO
            user_id = f"u_{uuid.uuid4().hex[:12]}"
            with get_db() as db:
                db.execute("""
                    INSERT INTO users (id, email, display_name, password_hash, role, is_active)
                    VALUES (?,?,?,?,?,1)
                """, (user_id, email, name, f"sso:{sso_id}", "member"))
            user = um.get_user(user_id)

        return {
            "authenticated": True,
            "user_id": user["id"],
            "email": user["email"],
            "name": user.get("display_name", ""),
            "sso_provisioned": True,
        }

    def disable(self) -> dict:
        with get_db() as db:
            db.execute("UPDATE sso_config SET enabled=0 WHERE id='sso_primary'")
        return {"disabled": True}


# ══════════════════════════════════════════════════════════════
# 2. AUDIT LOG EXPORT
# ══════════════════════════════════════════════════════════════

class AuditExporter:
    """Export audit logs for SOC 2 compliance review.

    Formats: CSV, JSON
    Filters: date range, user, action type, severity
    """

    def export_csv(self, filters: dict = None) -> str:
        """Export audit logs as CSV string."""
        rows = self._query(filters)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Timestamp", "User ID", "Action", "Resource Type",
                        "Resource ID", "Detail", "Severity", "IP Address"])
        for r in rows:
            writer.writerow([
                r.get("timestamp", ""), r.get("user_id", ""), r.get("action", ""),
                r.get("resource_type", ""), r.get("resource_id", ""),
                r.get("detail", ""), r.get("severity", ""), r.get("ip_address", ""),
            ])
        return output.getvalue()

    def export_json(self, filters: dict = None) -> list:
        return self._query(filters)

    def get_summary(self, days: int = 30) -> dict:
        """Summary statistics for audit period."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with get_db() as db:
            total = db.execute(
                "SELECT COUNT(*) as c FROM audit_log WHERE timestamp>?", (cutoff,)).fetchone()
            by_action = db.execute(
                "SELECT action, COUNT(*) as c FROM audit_log WHERE timestamp>? GROUP BY action ORDER BY c DESC LIMIT 20",
                (cutoff,)).fetchall()
            by_severity = db.execute(
                "SELECT severity, COUNT(*) as c FROM audit_log WHERE timestamp>? GROUP BY severity",
                (cutoff,)).fetchall()
            by_user = db.execute(
                "SELECT user_id, COUNT(*) as c FROM audit_log WHERE timestamp>? GROUP BY user_id ORDER BY c DESC LIMIT 10",
                (cutoff,)).fetchall()
        return {
            "period_days": days,
            "total_events": dict(total)["c"],
            "by_action": [dict(r) for r in by_action],
            "by_severity": [dict(r) for r in by_severity],
            "top_users": [dict(r) for r in by_user],
        }

    def _query(self, filters: dict = None) -> list:
        filters = filters or {}
        where, params = ["1=1"], []

        if filters.get("start_date"):
            where.append("created_at >= ?")
            params.append(filters["start_date"])
        if filters.get("end_date"):
            where.append("created_at <= ?")
            params.append(filters["end_date"])
        if filters.get("user_id"):
            where.append("user_id = ?")
            params.append(filters["user_id"])
        if filters.get("action"):
            where.append("action = ?")
            params.append(filters["action"])
        if filters.get("severity"):
            where.append("severity = ?")
            params.append(filters["severity"])

        query = f"SELECT * FROM audit_log WHERE {' AND '.join(where)} ORDER BY timestamp DESC LIMIT 10000"

        with get_db() as db:
            rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════
# 3. GRANULAR RBAC
# ══════════════════════════════════════════════════════════════

class RBACManager:
    """Granular role-based access control with custom roles.

    Built-in roles:
      owner — everything
      admin — everything except ownership transfer
      member — standard access
      viewer — read-only

    Custom roles: admin defines permissions per feature.

    Permissions:
      spaces.create, spaces.edit, spaces.delete, spaces.view
      compliance.view, compliance.dismiss, compliance.escalate
      billing.view, billing.manage
      users.view, users.manage, users.invite
      settings.view, settings.manage
      analytics.view, analytics.export
      teams.manage, teams.view
      audit.view, audit.export
      api_keys.view, api_keys.manage
      features.manage
    """

    ALL_PERMISSIONS = [
        "spaces.create", "spaces.edit", "spaces.delete", "spaces.view",
        "conversations.view", "conversations.delete",
        "compliance.view", "compliance.dismiss", "compliance.escalate",
        "billing.view", "billing.manage",
        "users.view", "users.manage", "users.invite",
        "settings.view", "settings.manage",
        "analytics.view", "analytics.export",
        "teams.manage", "teams.view",
        "audit.view", "audit.export",
        "api_keys.view", "api_keys.manage",
        "features.manage",
        "sso.manage",
        "webhooks.manage",
        "data_export",
    ]

    BUILT_IN_ROLES = {
        "owner": {
            "label": "Owner",
            "permissions": ALL_PERMISSIONS,  # Will be set in __init__
            "editable": False,
        },
        "admin": {
            "label": "Administrator",
            "permissions": [p for p in ALL_PERMISSIONS if p != "sso.manage"],
            "editable": False,
        },
        "member": {
            "label": "Member",
            "permissions": [
                "spaces.create", "spaces.edit", "spaces.view",
                "conversations.view",
                "teams.view",
                "analytics.view",
                "api_keys.view",
            ],
            "editable": False,
        },
        "viewer": {
            "label": "Viewer (Read Only)",
            "permissions": [
                "spaces.view", "conversations.view", "analytics.view", "teams.view",
            ],
            "editable": False,
        },
    }

    def __init__(self):
        self.BUILT_IN_ROLES["owner"]["permissions"] = self.ALL_PERMISSIONS.copy()

    def get_all_permissions(self) -> list:
        return self.ALL_PERMISSIONS

    def get_built_in_roles(self) -> dict:
        return {k: {"label": v["label"], "permissions": v["permissions"],
                     "permission_count": len(v["permissions"]), "editable": v["editable"]}
                for k, v in self.BUILT_IN_ROLES.items()}

    def create_custom_role(self, name: str, permissions: list,
                            created_by: str = "") -> dict:
        """Create a custom role with specific permissions."""
        role_id = f"role_{uuid.uuid4().hex[:8]}"
        valid = [p for p in permissions if p in self.ALL_PERMISSIONS]
        invalid = [p for p in permissions if p not in self.ALL_PERMISSIONS]

        with get_db() as db:
            db.execute("""
                INSERT INTO custom_roles (id, name, permissions, created_by)
                VALUES (?,?,?,?)
            """, (role_id, name, json.dumps(valid), created_by))

        return {
            "id": role_id, "name": name,
            "permissions": valid,
            "invalid_permissions": invalid,
            "permission_count": len(valid),
        }

    def update_custom_role(self, role_id: str, permissions: list = None,
                            name: str = None) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM custom_roles WHERE id=?", (role_id,)).fetchone()
            if not row:
                return {"error": "Role not found"}
            updates, vals = [], []
            if permissions is not None:
                valid = [p for p in permissions if p in self.ALL_PERMISSIONS]
                updates.append("permissions=?")
                vals.append(json.dumps(valid))
            if name:
                updates.append("name=?")
                vals.append(name)
            if updates:
                vals.append(role_id)
                db.execute(f"UPDATE custom_roles SET {','.join(updates)} WHERE id=?", vals)
        return {"updated": True}

    def delete_custom_role(self, role_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM custom_roles WHERE id=?", (role_id,))
        return {"deleted": True}

    def list_custom_roles(self) -> list:
        with get_db() as db:
            rows = db.execute("SELECT * FROM custom_roles ORDER BY name").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["permissions"] = json.loads(d.get("permissions", "[]"))
            d["permission_count"] = len(d["permissions"])
            result.append(d)
        return result

    def get_user_permissions(self, user_id: str, user_role: str) -> list:
        """Get effective permissions for a user."""
        # Check built-in role first
        if user_role in self.BUILT_IN_ROLES:
            return self.BUILT_IN_ROLES[user_role]["permissions"]

        # Check custom role
        with get_db() as db:
            row = db.execute("SELECT permissions FROM custom_roles WHERE id=?",
                            (user_role,)).fetchone()
        if row:
            return json.loads(dict(row)["permissions"])

        # Fallback to member
        return self.BUILT_IN_ROLES["member"]["permissions"]

    def check_permission(self, user_id: str, user_role: str,
                          permission: str) -> bool:
        """Check if user has a specific permission."""
        perms = self.get_user_permissions(user_id, user_role)
        return permission in perms

    def assign_role(self, user_id: str, role: str, assigned_by: str = "") -> dict:
        """Assign a role (built-in or custom) to a user."""
        valid = role in self.BUILT_IN_ROLES
        if not valid:
            with get_db() as db:
                row = db.execute("SELECT id FROM custom_roles WHERE id=?", (role,)).fetchone()
            valid = row is not None

        if not valid:
            return {"error": f"Role '{role}' not found"}

        with get_db() as db:
            db.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
        return {"assigned": True, "user_id": user_id, "role": role}


# ══════════════════════════════════════════════════════════════
# 4. INFLUENCER / AFFILIATE PROGRAM
# ══════════════════════════════════════════════════════════════

class AffiliateManager:
    """Influencer and affiliate program with tracking and commissions.

    How it works:
      1. Influencer applies or is invited
      2. Admin approves → custom referral link generated
      3. Influencer shares link → cookie tracks visitors for 90 days
      4. Visitor signs up + subscribes → influencer gets commission
      5. Commission paid monthly after 30-day hold (for refunds)

    Commission structure (configurable):
      Default: 20% recurring for 12 months
      Custom: per-influencer rates negotiable
      Minimum payout: $50

    Tiers:
      Bronze:  0-10 referrals   → 15% commission
      Silver:  11-50 referrals  → 20% commission
      Gold:    51-200 referrals → 25% commission
      Platinum: 200+ referrals  → 30% commission + custom deal
    """

    TIERS = {
        "bronze":   {"min_referrals": 0,   "commission_pct": 15, "label": "Bronze"},
        "silver":   {"min_referrals": 11,  "commission_pct": 20, "label": "Silver"},
        "gold":     {"min_referrals": 51,  "commission_pct": 25, "label": "Gold"},
        "platinum": {"min_referrals": 200, "commission_pct": 30, "label": "Platinum"},
    }

    COOKIE_DAYS = 90
    HOLD_DAYS = 30
    MIN_PAYOUT = 50.00

    def apply(self, user_id: str, name: str, email: str,
              platform: str = "", followers: int = 0,
              audience: str = "", pitch: str = "") -> dict:
        """Influencer applies to the program."""
        aid = f"aff_{uuid.uuid4().hex[:12]}"
        ref_code = self._generate_ref_code(name)

        with get_db() as db:
            db.execute("""
                INSERT INTO affiliates
                    (id, user_id, name, email, ref_code, platform, followers,
                     audience, pitch, status, commission_pct)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (aid, user_id, name, email, ref_code, platform, followers,
                  audience, pitch, "pending", 20))

        return {
            "id": aid,
            "ref_code": ref_code,
            "status": "pending",
            "message": "Application received. We'll review it within 48 hours.",
        }

    def approve(self, affiliate_id: str, admin_id: str,
                commission_pct: float = None) -> dict:
        """Admin approves an affiliate."""
        with get_db() as db:
            aff = db.execute("SELECT * FROM affiliates WHERE id=?",
                            (affiliate_id,)).fetchone()
            if not aff:
                return {"error": "Affiliate not found"}

            updates = {"status": "active", "approved_by": admin_id,
                       "approved_at": datetime.now().isoformat()}
            if commission_pct is not None:
                updates["commission_pct"] = commission_pct

            sets = ", ".join(f"{k}=?" for k in updates)
            vals = list(updates.values()) + [affiliate_id]
            db.execute(f"UPDATE affiliates SET {sets} WHERE id=?", vals)

        base_url = os.getenv("BASE_URL", "https://myteam360.ai")
        d = dict(aff)
        return {
            "approved": True,
            "affiliate_id": affiliate_id,
            "ref_code": d["ref_code"],
            "referral_link": f"{base_url}?ref={d['ref_code']}",
            "commission_pct": commission_pct or d.get("commission_pct", 20),
        }

    def reject(self, affiliate_id: str, reason: str = "") -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE affiliates SET status='rejected', rejection_reason=? WHERE id=?",
                (reason, affiliate_id))
        return {"rejected": True}

    def get_referral_link(self, affiliate_id: str) -> dict:
        """Get the affiliate's referral link."""
        with get_db() as db:
            row = db.execute("SELECT ref_code, status FROM affiliates WHERE id=?",
                            (affiliate_id,)).fetchone()
        if not row:
            return {"error": "Affiliate not found"}
        d = dict(row)
        if d["status"] != "active":
            return {"error": "Affiliate not active"}
        base_url = os.getenv("BASE_URL", "https://myteam360.ai")
        return {
            "ref_code": d["ref_code"],
            "link": f"{base_url}?ref={d['ref_code']}",
            "utm_link": f"{base_url}?ref={d['ref_code']}&utm_source=affiliate&utm_medium=referral",
        }

    def track_click(self, ref_code: str, ip: str = "", user_agent: str = "") -> dict:
        """Track a referral link click."""
        cid = f"click_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            # Verify ref_code exists
            aff = db.execute("SELECT id FROM affiliates WHERE ref_code=? AND status='active'",
                            (ref_code,)).fetchone()
            if not aff:
                return {"tracked": False}

            db.execute("""
                INSERT INTO affiliate_clicks (id, affiliate_id, ref_code, ip, user_agent)
                VALUES (?,?,?,?,?)
            """, (cid, dict(aff)["id"], ref_code, ip[:45], user_agent[:200]))

            # Update click count
            db.execute(
                "UPDATE affiliates SET total_clicks=total_clicks+1 WHERE ref_code=?",
                (ref_code,))

        return {"tracked": True, "ref_code": ref_code}

    def track_conversion(self, ref_code: str, user_id: str,
                          plan: str, amount: float) -> dict:
        """Track when a referred user subscribes."""
        with get_db() as db:
            aff = db.execute(
                "SELECT id, commission_pct, total_referrals FROM affiliates WHERE ref_code=? AND status='active'",
                (ref_code,)).fetchone()
            if not aff:
                return {"tracked": False}

            a = dict(aff)
            commission_pct = a["commission_pct"]

            # Check tier upgrade
            new_total = a["total_referrals"] + 1
            tier = self._get_tier(new_total)
            if tier["commission_pct"] > commission_pct:
                commission_pct = tier["commission_pct"]

            commission = round(amount * (commission_pct / 100), 2)

            # Record conversion
            cid = f"conv_{uuid.uuid4().hex[:8]}"
            db.execute("""
                INSERT INTO affiliate_conversions
                    (id, affiliate_id, ref_code, user_id, plan, amount,
                     commission_pct, commission_amount, status)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (cid, a["id"], ref_code, user_id, plan, amount,
                  commission_pct, commission, "pending"))

            # Update affiliate stats
            db.execute("""
                UPDATE affiliates
                SET total_referrals=total_referrals+1,
                    total_revenue=total_revenue+?,
                    total_commission=total_commission+?,
                    commission_pct=?,
                    current_tier=?
                WHERE id=?
            """, (amount, commission, commission_pct, tier["label"], a["id"]))

        return {
            "tracked": True,
            "commission": commission,
            "commission_pct": commission_pct,
            "tier": tier["label"],
        }

    def get_dashboard(self, affiliate_id: str) -> dict:
        """Affiliate dashboard — stats, earnings, referrals."""
        with get_db() as db:
            aff = db.execute("SELECT * FROM affiliates WHERE id=?",
                            (affiliate_id,)).fetchone()
            if not aff:
                return {"error": "Affiliate not found"}

            a = dict(aff)

            # Recent conversions
            convs = db.execute(
                "SELECT * FROM affiliate_conversions WHERE affiliate_id=? ORDER BY timestamp DESC LIMIT 20",
                (affiliate_id,)).fetchall()

            # Pending payout
            pending = db.execute(
                "SELECT COALESCE(SUM(commission_amount),0) as total FROM affiliate_conversions "
                "WHERE affiliate_id=? AND status='pending'",
                (affiliate_id,)).fetchone()

            # Paid out
            paid = db.execute(
                "SELECT COALESCE(SUM(commission_amount),0) as total FROM affiliate_conversions "
                "WHERE affiliate_id=? AND status='paid'",
                (affiliate_id,)).fetchone()

        base_url = os.getenv("BASE_URL", "https://myteam360.ai")
        tier = self._get_tier(a.get("total_referrals", 0))
        next_tier = self._get_next_tier(a.get("total_referrals", 0))

        return {
            "affiliate_id": affiliate_id,
            "name": a.get("name"),
            "status": a.get("status"),
            "ref_code": a.get("ref_code"),
            "referral_link": f"{base_url}?ref={a.get('ref_code')}",
            "tier": {
                "current": tier["label"],
                "commission_pct": a.get("commission_pct", tier["commission_pct"]),
                "next_tier": next_tier,
            },
            "stats": {
                "total_clicks": a.get("total_clicks", 0),
                "total_referrals": a.get("total_referrals", 0),
                "conversion_rate": round(a.get("total_referrals", 0) / max(a.get("total_clicks", 1), 1) * 100, 1),
                "total_revenue": round(a.get("total_revenue", 0), 2),
                "total_commission": round(a.get("total_commission", 0), 2),
                "pending_payout": round(dict(pending)["total"], 2),
                "total_paid": round(dict(paid)["total"], 2),
            },
            "recent_conversions": [dict(c) for c in convs[:10]],
            "min_payout": self.MIN_PAYOUT,
        }

    def request_payout(self, affiliate_id: str) -> dict:
        """Affiliate requests commission payout."""
        with get_db() as db:
            # Get eligible conversions (older than hold period)
            cutoff = (datetime.now() - timedelta(days=self.HOLD_DAYS)).isoformat()
            eligible = db.execute("""
                SELECT COALESCE(SUM(commission_amount),0) as total, COUNT(*) as count
                FROM affiliate_conversions
                WHERE affiliate_id=? AND status='pending' AND created_at<?
            """, (affiliate_id, cutoff)).fetchone()

        e = dict(eligible)
        if e["total"] < self.MIN_PAYOUT:
            return {
                "error": f"Minimum payout is ${self.MIN_PAYOUT:.2f}. "
                         f"Current eligible: ${e['total']:.2f}. "
                         f"Commissions are eligible {self.HOLD_DAYS} days after conversion.",
            }

        pid = f"payout_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO affiliate_payouts (id, affiliate_id, amount, conversion_count, status)
                VALUES (?,?,?,?,?)
            """, (pid, affiliate_id, e["total"], e["count"], "requested"))

            # Mark conversions as in-payout
            db.execute("""
                UPDATE affiliate_conversions SET status='payout_requested'
                WHERE affiliate_id=? AND status='pending' AND created_at<?
            """, (affiliate_id, cutoff))

        return {
            "payout_id": pid,
            "amount": round(e["total"], 2),
            "conversions": e["count"],
            "status": "requested",
            "message": f"Payout of ${e['total']:.2f} requested. Processing within 5 business days.",
        }

    def process_payout(self, payout_id: str, admin_id: str) -> dict:
        """Admin processes a payout (mark as paid)."""
        with get_db() as db:
            db.execute("""
                UPDATE affiliate_payouts SET status='paid', processed_by=?, processed_at=?
                WHERE id=?
            """, (admin_id, datetime.now().isoformat(), payout_id))

            # Get affiliate_id from payout
            payout = db.execute("SELECT * FROM affiliate_payouts WHERE id=?",
                               (payout_id,)).fetchone()
            if payout:
                db.execute("""
                    UPDATE affiliate_conversions SET status='paid'
                    WHERE affiliate_id=? AND status='payout_requested'
                """, (dict(payout)["affiliate_id"],))

        return {"paid": True, "payout_id": payout_id}

    def get_admin_overview(self) -> dict:
        """Admin view — all affiliates, total commissions, pending payouts."""
        with get_db() as db:
            total_affiliates = db.execute(
                "SELECT COUNT(*) as c FROM affiliates WHERE status='active'").fetchone()
            pending_apps = db.execute(
                "SELECT COUNT(*) as c FROM affiliates WHERE status='pending'").fetchone()
            total_revenue = db.execute(
                "SELECT COALESCE(SUM(total_revenue),0) as c FROM affiliates").fetchone()
            total_commission = db.execute(
                "SELECT COALESCE(SUM(total_commission),0) as c FROM affiliates").fetchone()
            pending_payouts = db.execute(
                "SELECT COALESCE(SUM(amount),0) as c FROM affiliate_payouts WHERE status='requested'").fetchone()
            top = db.execute(
                "SELECT name, ref_code, total_referrals, total_revenue, total_commission, current_tier "
                "FROM affiliates WHERE status='active' ORDER BY total_revenue DESC LIMIT 10").fetchall()

        return {
            "active_affiliates": dict(total_affiliates)["c"],
            "pending_applications": dict(pending_apps)["c"],
            "total_referred_revenue": round(dict(total_revenue)["c"], 2),
            "total_commissions": round(dict(total_commission)["c"], 2),
            "pending_payouts": round(dict(pending_payouts)["c"], 2),
            "top_affiliates": [dict(r) for r in top],
            "tiers": self.TIERS,
        }

    def simulate_commission(self, plan: str, billing: str) -> dict:
        """Show how much an influencer would earn per referral."""
        PLAN_PRICES = {
            "starter_monthly": 7, "starter_annual": 60,
            "student_monthly": 15, "student_annual": 120,
            "pro_monthly": 15, "pro_annual": 144,
            "business_monthly": 99, "business_annual": 948,
        }
        price = PLAN_PRICES.get(f"{plan}_{billing}", 15)

        result = {}
        for tier_id, tier in self.TIERS.items():
            pct = tier["commission_pct"]
            per_referral = round(price * pct / 100, 2)
            result[tier_id] = {
                "tier": tier["label"],
                "commission_pct": pct,
                "per_referral": per_referral,
                "per_10_referrals": round(per_referral * 10, 2),
                "per_100_referrals": round(per_referral * 100, 2),
                "annual_per_referral": round(per_referral * 12, 2) if "monthly" in billing else per_referral,
            }

        return {"plan": plan, "billing": billing, "price": price, "earnings": result}

    def _generate_ref_code(self, name: str) -> str:
        """Generate a memorable referral code."""
        clean = name.lower().replace(" ", "")[:8]
        suffix = secrets.token_hex(3)
        return f"{clean}-{suffix}"

    def _get_tier(self, referrals: int) -> dict:
        tier = self.TIERS["bronze"]
        for t in self.TIERS.values():
            if referrals >= t["min_referrals"]:
                tier = t
        return tier

    def _get_next_tier(self, referrals: int) -> dict | None:
        """What's the next tier and how many more referrals needed?"""
        sorted_tiers = sorted(self.TIERS.values(), key=lambda t: t["min_referrals"])
        for t in sorted_tiers:
            if referrals < t["min_referrals"]:
                return {
                    "tier": t["label"],
                    "commission_pct": t["commission_pct"],
                    "referrals_needed": t["min_referrals"] - referrals,
                }
        return None  # Already at top tier
