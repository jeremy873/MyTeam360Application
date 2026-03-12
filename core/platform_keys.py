# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Platform Key Policy — Admin-gated API key governance.

RULE: MyTeam360 may hold its own API keys ONLY for platform-internal
operations, and ONLY when explicitly approved by the platform owner.

  USER-FACING AI:    ALWAYS user's own key (BYOK). No exceptions.
  PLATFORM INTERNAL: ONLY with owner approval, logged, auditable.

Approved use cases (must be added by owner):
  - System health monitoring
  - Platform update notifications to users
  - Generating release notes
  - Admin analytics/reporting
  - Onboarding content generation (welcome emails, etc.)

NEVER approved:
  - User conversations
  - User's CRM/task/invoice operations
  - Content generation on behalf of users
  - Any feature the user interacts with directly

Every platform key call is:
  1. Checked against approved use case list
  2. Logged with full audit trail
  3. Rate-limited (no runaway costs)
  4. Visible to owner in admin dashboard
"""

import json
import uuid
import os
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.platform_keys")


# ══════════════════════════════════════════════════════════════
# POLICY ENFORCEMENT
# ══════════════════════════════════════════════════════════════

class PlatformKeyPolicy:
    """Governs when/how platform-owned API keys can be used."""

    # Use cases that are NEVER allowed with platform keys
    FORBIDDEN_USE_CASES = [
        "user_conversation",
        "user_content_generation",
        "user_crm_operation",
        "user_task_operation",
        "user_invoice_operation",
        "user_social_media",
        "user_email_compose",
        "user_meeting_prep",
        "user_roundtable",
        "any_user_facing_feature",
    ]

    def get_approved_use_cases(self) -> list:
        """Get owner-approved platform key use cases."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM platform_key_approvals WHERE revoked=0 ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def approve_use_case(self, owner_id: str, use_case: str,
                          description: str, max_calls_per_day: int = 50,
                          max_cost_per_day: float = 1.0) -> dict:
        """Owner explicitly approves a platform key use case."""
        # Verify this is the platform owner
        if not self._is_owner(owner_id):
            return {"error": "Only the platform owner can approve use cases"}

        # Block forbidden use cases
        if use_case in self.FORBIDDEN_USE_CASES:
            return {"error": f"'{use_case}' is FORBIDDEN for platform keys. "
                            f"User-facing AI must use BYOK (user's own keys)."}

        aid = f"approval_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO platform_key_approvals
                    (id, approved_by, use_case, description,
                     max_calls_per_day, max_cost_per_day)
                VALUES (?,?,?,?,?,?)
            """, (aid, owner_id, use_case, description,
                  max_calls_per_day, max_cost_per_day))

        logger.info(f"Platform key use case approved: {use_case} by {owner_id}")
        return {"id": aid, "approved": True, "use_case": use_case,
                "limits": {"max_calls_per_day": max_calls_per_day,
                           "max_cost_per_day": max_cost_per_day}}

    def revoke_use_case(self, owner_id: str, approval_id: str) -> dict:
        """Owner revokes a previously approved use case."""
        if not self._is_owner(owner_id):
            return {"error": "Only the platform owner can revoke use cases"}
        with get_db() as db:
            db.execute(
                "UPDATE platform_key_approvals SET revoked=1, revoked_at=? WHERE id=?",
                (datetime.now().isoformat(), approval_id))
        return {"revoked": True}

    def can_use_platform_key(self, use_case: str) -> dict:
        """Check if a platform key call is allowed RIGHT NOW."""
        # Check forbidden list
        if use_case in self.FORBIDDEN_USE_CASES:
            return {"allowed": False,
                    "reason": f"'{use_case}' is forbidden for platform keys"}

        # Check if approved
        with get_db() as db:
            approval = db.execute(
                "SELECT * FROM platform_key_approvals WHERE use_case=? AND revoked=0",
                (use_case,)).fetchone()

        if not approval:
            return {"allowed": False,
                    "reason": f"'{use_case}' has not been approved by the platform owner"}

        approval = dict(approval)

        # Check daily limits
        today = datetime.now().strftime("%Y-%m-%d")
        with get_db() as db:
            today_calls = db.execute(
                "SELECT COUNT(*) as c, COALESCE(SUM(estimated_cost),0) as cost "
                "FROM platform_key_audit WHERE use_case=? AND DATE(created_at)=?",
                (use_case, today)).fetchone()

        calls_today = dict(today_calls)["c"]
        cost_today = dict(today_calls)["cost"]

        if calls_today >= approval["max_calls_per_day"]:
            return {"allowed": False,
                    "reason": f"Daily call limit reached ({calls_today}/{approval['max_calls_per_day']})"}

        if cost_today >= approval["max_cost_per_day"]:
            return {"allowed": False,
                    "reason": f"Daily cost limit reached (${cost_today:.4f}/${approval['max_cost_per_day']:.2f})"}

        return {"allowed": True, "use_case": use_case,
                "calls_remaining": approval["max_calls_per_day"] - calls_today}

    def log_platform_call(self, use_case: str, provider: str, model: str,
                           input_tokens: int = 0, output_tokens: int = 0,
                           estimated_cost: float = 0, detail: str = "") -> dict:
        """Log every platform key API call for audit."""
        lid = f"pklog_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO platform_key_audit
                    (id, use_case, provider, model, input_tokens, output_tokens,
                     estimated_cost, detail)
                VALUES (?,?,?,?,?,?,?,?)
            """, (lid, use_case, provider, model, input_tokens, output_tokens,
                  estimated_cost, detail))
        return {"logged": True}

    def get_audit_log(self, owner_id: str, days: int = 30) -> dict:
        """Full audit log of all platform key usage."""
        if not self._is_owner(owner_id):
            return {"error": "Only the platform owner can view the audit log"}

        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with get_db() as db:
            entries = db.execute(
                "SELECT * FROM platform_key_audit WHERE created_at>=? ORDER BY created_at DESC",
                (cutoff,)).fetchall()
            total_cost = db.execute(
                "SELECT COALESCE(SUM(estimated_cost),0) as t FROM platform_key_audit WHERE created_at>=?",
                (cutoff,)).fetchone()
            by_use_case = db.execute("""
                SELECT use_case, COUNT(*) as calls, COALESCE(SUM(estimated_cost),0) as cost
                FROM platform_key_audit WHERE created_at>=?
                GROUP BY use_case ORDER BY cost DESC
            """, (cutoff,)).fetchall()

        return {
            "period_days": days,
            "total_calls": len(entries),
            "total_cost": round(dict(total_cost)["t"], 4),
            "by_use_case": [dict(r) for r in by_use_case],
            "entries": [dict(e) for e in entries[:100]],
        }

    def get_policy_summary(self) -> dict:
        """Human-readable policy summary."""
        approvals = self.get_approved_use_cases()
        return {
            "model": "BYOK (Bring Your Own Key)",
            "user_facing_ai": "ALWAYS uses user's own API key. No exceptions.",
            "platform_internal": {
                "requires": "Explicit owner approval per use case",
                "approved_count": len(approvals),
                "approved_use_cases": [a["use_case"] for a in approvals],
            },
            "forbidden_for_platform_keys": self.FORBIDDEN_USE_CASES,
            "audit": "Every platform key call is logged with full details",
            "limits": "Each use case has daily call + cost limits set by owner",
        }

    def _is_owner(self, user_id: str) -> bool:
        """Check if user is the platform owner."""
        with get_db() as db:
            row = db.execute(
                "SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
        return row and dict(row).get("role") == "owner"
