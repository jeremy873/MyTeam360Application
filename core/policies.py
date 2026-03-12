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
Policies — Acceptable Use Policy, Terms of Service, and compliance policy management.
Admins can create/update policies. Users must accept before accessing the platform.
"""

import uuid
import json
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.policies")


# ══════════════════════════════════════════════════════════════
# DEFAULT AUP TEMPLATE
# ══════════════════════════════════════════════════════════════

DEFAULT_AUP = """# Acceptable Use Policy

## Purpose
This policy governs the acceptable use of AI tools and services provided through this platform. All users must read and agree to these terms before accessing the system.

## Acceptable Use
- Use AI assistants for legitimate business purposes only
- Verify AI-generated content before sharing externally or making decisions
- Report any concerning, biased, or inaccurate AI outputs to your administrator
- Respect data classification levels when sharing information with AI assistants
- Follow your organization's data handling and privacy policies

## Prohibited Activities
- Sharing sensitive personal data (SSN, credit cards, passwords) with AI assistants
- Attempting to bypass content filters or safety guidelines
- Using AI to generate misleading, fraudulent, or harmful content
- Sharing proprietary or classified information beyond authorized levels
- Using AI outputs as sole basis for legal, medical, or financial decisions
- Automated bulk querying or API abuse

## Data & Privacy
- Conversations may be logged for security, compliance, and quality purposes
- AI providers may process data according to their respective privacy policies
- Do not assume AI conversations are private — administrators may review logs
- Data retention follows your organization's policies

## Responsibility
- You are responsible for reviewing and validating all AI-generated content
- AI assistants may produce inaccurate or incomplete information
- Final decisions and actions remain your responsibility
- Report security incidents to your IT administrator immediately

## Compliance
Violation of this policy may result in account suspension, access revocation, or disciplinary action per your organization's policies.

---
*By clicking "I Agree," you acknowledge that you have read, understood, and agree to abide by this Acceptable Use Policy.*
"""


class PolicyManager:
    """Manages organizational policies with versioning and acceptance tracking."""

    def seed_default_aup(self):
        """Create default AUP if none exists."""
        with get_db() as db:
            existing = db.execute(
                "SELECT id FROM policies WHERE policy_type='aup' AND is_active=1"
            ).fetchone()
            if existing:
                return False

            policy_id = f"pol_{uuid.uuid4().hex[:12]}"
            db.execute(
                "INSERT INTO policies (id, policy_type, version, title, content,"
                " is_active, requires_acceptance, published_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (policy_id, "aup", 1, "Acceptable Use Policy",
                 DEFAULT_AUP, 1, 1, datetime.utcnow().isoformat()))
            return True

    # ── Policy CRUD ──

    def get_active_policy(self, policy_type="aup"):
        """Get the currently active policy of a given type."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM policies WHERE policy_type=? AND is_active=1"
                " ORDER BY version DESC LIMIT 1", (policy_type,)
            ).fetchone()
        return dict(row) if row else None

    def get_policy(self, policy_id):
        with get_db() as db:
            row = db.execute("SELECT * FROM policies WHERE id=?", (policy_id,)).fetchone()
        return dict(row) if row else None

    def list_policies(self, policy_type=None):
        with get_db() as db:
            if policy_type:
                rows = db.execute(
                    "SELECT * FROM policies WHERE policy_type=? ORDER BY version DESC",
                    (policy_type,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM policies ORDER BY policy_type, version DESC").fetchall()
        return [dict(r) for r in rows]

    def create_policy(self, policy_type, title, content, created_by=None, requires_acceptance=True):
        """Create a new policy version. Deactivates previous versions of same type."""
        with get_db() as db:
            # Get next version number
            row = db.execute(
                "SELECT MAX(version) as max_v FROM policies WHERE policy_type=?",
                (policy_type,)).fetchone()
            next_version = (row["max_v"] or 0) + 1

            # Deactivate old versions
            db.execute(
                "UPDATE policies SET is_active=0 WHERE policy_type=?", (policy_type,))

            policy_id = f"pol_{uuid.uuid4().hex[:12]}"
            db.execute(
                "INSERT INTO policies (id, policy_type, version, title, content,"
                " is_active, requires_acceptance, created_by, published_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (policy_id, policy_type, next_version, title, content,
                 1, 1 if requires_acceptance else 0, created_by,
                 datetime.utcnow().isoformat()))

        return {
            "id": policy_id, "policy_type": policy_type,
            "version": next_version, "title": title,
        }

    def update_policy(self, policy_id, title=None, content=None, requires_acceptance=None):
        with get_db() as db:
            updates, vals = [], []
            if title is not None:
                updates.append("title=?"); vals.append(title)
            if content is not None:
                updates.append("content=?"); vals.append(content)
            if requires_acceptance is not None:
                updates.append("requires_acceptance=?"); vals.append(1 if requires_acceptance else 0)
            if not updates:
                return {"error": "No updates"}
            vals.append(policy_id)
            db.execute(f"UPDATE policies SET {','.join(updates)} WHERE id=?", vals)
        return {"updated": True}

    # ── Acceptance ──

    def check_user_acceptance(self, user_id, policy_type="aup"):
        """Check if user has accepted the current active policy."""
        with get_db() as db:
            policy = db.execute(
                "SELECT id, requires_acceptance FROM policies"
                " WHERE policy_type=? AND is_active=1 ORDER BY version DESC LIMIT 1",
                (policy_type,)).fetchone()

            if not policy:
                return {"required": False, "accepted": True}

            if not policy["requires_acceptance"]:
                return {"required": False, "accepted": True}

            acceptance = db.execute(
                "SELECT id, accepted_at FROM policy_acceptances"
                " WHERE policy_id=? AND user_id=?",
                (policy["id"], user_id)).fetchone()

            return {
                "required": True,
                "accepted": bool(acceptance),
                "accepted_at": acceptance["accepted_at"] if acceptance else None,
                "policy_id": policy["id"],
            }

    def accept_policy(self, user_id, policy_id, ip_address=None, user_agent=None):
        """Record user acceptance of a policy."""
        with get_db() as db:
            # Verify policy exists and is active
            policy = db.execute(
                "SELECT id, title, version FROM policies WHERE id=? AND is_active=1",
                (policy_id,)).fetchone()
            if not policy:
                return {"error": "Policy not found or inactive"}

            # Check if already accepted
            existing = db.execute(
                "SELECT id FROM policy_acceptances WHERE policy_id=? AND user_id=?",
                (policy_id, user_id)).fetchone()
            if existing:
                return {"already_accepted": True, "policy_id": policy_id}

            acc_id = f"acc_{uuid.uuid4().hex[:12]}"
            db.execute(
                "INSERT INTO policy_acceptances (id, policy_id, user_id, ip_address, user_agent)"
                " VALUES (?,?,?,?,?)",
                (acc_id, policy_id, user_id, ip_address, user_agent))

        logger.info(f"User {user_id} accepted policy {policy_id} (v{policy['version']})")
        return {
            "accepted": True,
            "policy_id": policy_id,
            "policy_title": policy["title"],
            "version": policy["version"],
        }

    def get_acceptance_log(self, policy_id=None, limit=100):
        """Get acceptance records for compliance reporting."""
        with get_db() as db:
            if policy_id:
                rows = db.execute(
                    "SELECT pa.*, p.title, p.version, u.email"
                    " FROM policy_acceptances pa"
                    " JOIN policies p ON pa.policy_id=p.id"
                    " LEFT JOIN users u ON pa.user_id=u.id"
                    " WHERE pa.policy_id=? ORDER BY pa.accepted_at DESC LIMIT ?",
                    (policy_id, limit)).fetchall()
            else:
                rows = db.execute(
                    "SELECT pa.*, p.title, p.version, u.email"
                    " FROM policy_acceptances pa"
                    " JOIN policies p ON pa.policy_id=p.id"
                    " LEFT JOIN users u ON pa.user_id=u.id"
                    " ORDER BY pa.accepted_at DESC LIMIT ?",
                    (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_non_compliant_users(self, policy_type="aup"):
        """Get users who haven't accepted the current policy."""
        with get_db() as db:
            policy = db.execute(
                "SELECT id FROM policies WHERE policy_type=? AND is_active=1"
                " ORDER BY version DESC LIMIT 1", (policy_type,)).fetchone()
            if not policy:
                return []

            rows = db.execute(
                "SELECT u.id, u.email, u.display_name, u.role, u.created_at"
                " FROM users u WHERE u.is_active=1 AND u.id NOT IN"
                " (SELECT user_id FROM policy_acceptances WHERE policy_id=?)",
                (policy["id"],)).fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════
# DATA RETENTION
# ══════════════════════════════════════════════════════════════

DEFAULT_RETENTION = [
    {"resource_type": "conversations", "retention_days": 365, "description": "Chat conversations and messages"},
    {"resource_type": "audit_log", "retention_days": 730, "description": "Security and audit records"},
    {"resource_type": "usage_log", "retention_days": 365, "description": "AI usage and token tracking"},
    {"resource_type": "auth_log", "retention_days": 90, "description": "Login and authentication events"},
    {"resource_type": "file_attachments", "retention_days": 180, "description": "Uploaded files and images"},
    {"resource_type": "kb_documents", "retention_days": 0, "description": "Knowledge base (0 = keep forever)"},
]


class DataRetentionManager:
    """Manages data retention policies for compliance."""

    def seed_defaults(self):
        with get_db() as db:
            existing = db.execute("SELECT COUNT(*) as c FROM data_retention_policies").fetchone()
            if existing["c"] > 0:
                return False
            for d in DEFAULT_RETENTION:
                db.execute(
                    "INSERT INTO data_retention_policies (id, resource_type, retention_days)"
                    " VALUES (?,?,?)",
                    (f"drp_{d['resource_type']}", d["resource_type"], d["retention_days"]))
            return True

    def list_policies(self):
        with get_db() as db:
            rows = db.execute("SELECT * FROM data_retention_policies ORDER BY resource_type").fetchall()
        result = []
        lookup = {d["resource_type"]: d["description"] for d in DEFAULT_RETENTION}
        for r in rows:
            d = dict(r)
            d["description"] = lookup.get(d["resource_type"], "")
            result.append(d)
        return result

    def update_policy(self, resource_type, retention_days, auto_delete=False, configured_by=None):
        with get_db() as db:
            db.execute(
                "UPDATE data_retention_policies SET retention_days=?, auto_delete=?,"
                " configured_by=? WHERE resource_type=?",
                (retention_days, 1 if auto_delete else 0, configured_by, resource_type))
        return {"updated": True, "resource_type": resource_type}


# ══════════════════════════════════════════════════════════════
# IP ALLOWLIST
# ══════════════════════════════════════════════════════════════

class IPAllowlistManager:
    """Manages IP allowlisting for network-level access control."""

    def is_enabled(self):
        with get_db() as db:
            row = db.execute(
                "SELECT COUNT(*) as c FROM ip_allowlist WHERE is_enabled=1").fetchone()
        return row["c"] > 0

    def check_ip(self, ip_address):
        """Returns True if IP is allowed (or if allowlist is empty/disabled)."""
        with get_db() as db:
            count = db.execute(
                "SELECT COUNT(*) as c FROM ip_allowlist WHERE is_enabled=1").fetchone()
            if count["c"] == 0:
                return True  # No allowlist = allow all

            # Check exact match
            exact = db.execute(
                "SELECT id FROM ip_allowlist WHERE ip_address=? AND is_enabled=1",
                (ip_address,)).fetchone()
            if exact:
                return True

            # Check CIDR ranges
            ranges = db.execute(
                "SELECT cidr_range FROM ip_allowlist WHERE cidr_range IS NOT NULL AND is_enabled=1"
            ).fetchall()
            for r in ranges:
                if self._ip_in_cidr(ip_address, r["cidr_range"]):
                    return True
        return False

    def list_entries(self):
        with get_db() as db:
            rows = db.execute("SELECT * FROM ip_allowlist ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def add_entry(self, ip_address, description="", cidr_range=None, created_by=None):
        entry_id = f"ip_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute(
                "INSERT INTO ip_allowlist (id, ip_address, cidr_range, description, created_by)"
                " VALUES (?,?,?,?,?)",
                (entry_id, ip_address, cidr_range, description, created_by))
        return {"id": entry_id, "ip_address": ip_address}

    def remove_entry(self, entry_id):
        with get_db() as db:
            db.execute("DELETE FROM ip_allowlist WHERE id=?", (entry_id,))
        return {"deleted": True}

    def _ip_in_cidr(self, ip, cidr):
        """Basic CIDR check (supports /8, /16, /24, /32)."""
        try:
            net, bits = cidr.split("/")
            bits = int(bits)
            ip_parts = [int(x) for x in ip.split(".")]
            net_parts = [int(x) for x in net.split(".")]
            mask_bytes = bits // 8
            for i in range(mask_bytes):
                if ip_parts[i] != net_parts[i]:
                    return False
            return True
        except Exception:
            return False
