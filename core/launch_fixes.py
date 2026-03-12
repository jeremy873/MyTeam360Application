# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Launch Critical Fixes — 8 gaps that users hit in week 1.

1. Billing: Plan upgrade/downgrade flow
2. Billing: Cancellation with reason + exit survey
3. Conversations: Bulk delete + folders/categories
4. Roundtable: Max participant limit + transcript export
5. Spend: Budget alerts
6. Analytics: Export to Excel
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.launch_fixes")


# ══════════════════════════════════════════════════════════════
# 1. BILLING — PLAN CHANGE (UPGRADE / DOWNGRADE)
# ══════════════════════════════════════════════════════════════

class PlanChangeManager:
    """Handle upgrades, downgrades, and plan switches.

    Upgrade: Immediate — prorated credit applied
    Downgrade: End of billing period — features available until then
    """

    PLAN_ORDER = ["starter", "pro", "business", "enterprise"]

    def preview_change(self, current_plan: str, new_plan: str) -> dict:
        """Show what changes when switching plans."""
        from .onboarding import PRICING_TIERS
        current = PRICING_TIERS.get(current_plan, {})
        new = PRICING_TIERS.get(new_plan, {})
        if not new:
            return {"error": f"Unknown plan: {new_plan}"}

        current_idx = self.PLAN_ORDER.index(current_plan) if current_plan in self.PLAN_ORDER else 0
        new_idx = self.PLAN_ORDER.index(new_plan) if new_plan in self.PLAN_ORDER else 0
        is_upgrade = new_idx > current_idx

        # Features gained/lost
        current_features = set(current.get("features_included", []))
        new_features = set(new.get("features_included", []))
        gained = new_features - current_features
        lost = current_features - new_features

        # Limit changes
        current_limits = current.get("limits", {})
        new_limits = new.get("limits", {})
        limit_changes = {}
        for k in set(list(current_limits.keys()) + list(new_limits.keys())):
            old_v = current_limits.get(k, 0)
            new_v = new_limits.get(k, 0)
            if old_v != new_v:
                limit_changes[k] = {"from": old_v, "to": new_v,
                                     "improved": (new_v == -1 or (isinstance(new_v, (int, float)) and new_v > old_v))}

        return {
            "current_plan": current_plan,
            "new_plan": new_plan,
            "is_upgrade": is_upgrade,
            "direction": "upgrade" if is_upgrade else "downgrade",
            "price_change": {
                "from": current.get("price_monthly", 0),
                "to": new.get("price_monthly", 0),
                "difference": new.get("price_monthly", 0) - current.get("price_monthly", 0),
            },
            "features_gained": list(gained),
            "features_lost": list(lost),
            "limit_changes": limit_changes,
            "effective": "Immediately" if is_upgrade else "End of current billing period",
            "proration": "Credit applied for unused time on current plan" if is_upgrade else "N/A",
        }

    def execute_change(self, user_id: str, new_plan: str,
                        current_plan: str = "") -> dict:
        """Execute the plan change."""
        if new_plan == "enterprise":
            return {"error": "Enterprise requires contacting sales.",
                    "contact": "sales@myteam360.ai"}

        is_upgrade = self.PLAN_ORDER.index(new_plan) > self.PLAN_ORDER.index(current_plan) \
            if current_plan in self.PLAN_ORDER and new_plan in self.PLAN_ORDER else True

        with get_db() as db:
            if is_upgrade:
                db.execute(
                    "UPDATE subscriptions SET plan=?, updated_at=? WHERE user_id=?",
                    (new_plan, datetime.now().isoformat(), user_id))
                db.execute(
                    "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES (?, ?)",
                    (f"plan_{user_id}", new_plan))
            else:
                # Schedule downgrade for end of period
                db.execute("""
                    INSERT OR REPLACE INTO workspace_settings (key, value) VALUES (?, ?)
                """, (f"pending_downgrade_{user_id}",
                      json.dumps({"new_plan": new_plan, "scheduled": datetime.now().isoformat()})))

        return {
            "changed": True,
            "plan": new_plan,
            "effective": "now" if is_upgrade else "end_of_billing_period",
            "message": f"{'Upgraded' if is_upgrade else 'Downgrade scheduled'} to {new_plan}.",
        }


# ══════════════════════════════════════════════════════════════
# 2. BILLING — CANCELLATION FLOW
# ══════════════════════════════════════════════════════════════

class CancellationManager:
    """Cancellation with exit survey and retention offers."""

    CANCEL_REASONS = [
        "too_expensive", "not_using_enough", "missing_features",
        "switching_to_competitor", "business_closing", "poor_experience",
        "technical_issues", "other",
    ]

    def preview_cancellation(self, user_id: str) -> dict:
        """Show what the user loses if they cancel."""
        with get_db() as db:
            conv_count = db.execute(
                "SELECT COUNT(*) as c FROM conversations WHERE user_id=?",
                (user_id,)).fetchone()
            agent_count = db.execute(
                "SELECT COUNT(*) as c FROM agents WHERE owner_id=?",
                (user_id,)).fetchone()
        return {
            "you_will_lose": {
                "conversations": dict(conv_count)["c"],
                "spaces": dict(agent_count)["c"],
                "voice_profile": "Your learned communication style",
                "business_data": "CRM contacts, deals, invoices, tasks, goals",
            },
            "data_retained_for": "30 days after cancellation (then permanently deleted)",
            "can_export_first": True,
            "export_url": "/api/data-export/full",
        }

    def submit_cancellation(self, user_id: str, reason: str,
                             feedback: str = "", would_return: str = "") -> dict:
        """Process cancellation with exit survey."""
        cid = f"cancel_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO cancellation_surveys
                    (id, user_id, reason, feedback, would_return)
                VALUES (?,?,?,?,?)
            """, (cid, user_id, reason, feedback[:1000], would_return))

            # Mark subscription for cancellation at period end
            db.execute("""
                UPDATE subscriptions SET cancel_at_period_end=1,
                    cancel_reason=?, updated_at=? WHERE user_id=?
            """, (reason, datetime.now().isoformat(), user_id))

        logger.info(f"Cancellation submitted: user={user_id} reason={reason}")
        return {
            "cancelled": True,
            "effective": "end_of_current_billing_period",
            "message": "Your subscription will be cancelled at the end of your current "
                       "billing period. You can continue using all features until then. "
                       "You can reactivate anytime before the period ends.",
            "survey_id": cid,
        }

    def reactivate(self, user_id: str) -> dict:
        """Cancel the cancellation (user changed their mind)."""
        with get_db() as db:
            db.execute(
                "UPDATE subscriptions SET cancel_at_period_end=0 WHERE user_id=?",
                (user_id,))
        return {"reactivated": True,
                "message": "Your subscription has been reactivated. Welcome back!"}

    def get_churn_analytics(self) -> dict:
        """Admin: why are people leaving?"""
        with get_db() as db:
            by_reason = db.execute(
                "SELECT reason, COUNT(*) as c FROM cancellation_surveys GROUP BY reason ORDER BY c DESC"
            ).fetchall()
            total = db.execute("SELECT COUNT(*) as c FROM cancellation_surveys").fetchone()
            recent = db.execute(
                "SELECT * FROM cancellation_surveys ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
        return {
            "total_cancellations": dict(total)["c"],
            "by_reason": [dict(r) for r in by_reason],
            "recent": [dict(r) for r in recent],
        }


# ══════════════════════════════════════════════════════════════
# 3. CONVERSATIONS — BULK DELETE + FOLDERS
# ══════════════════════════════════════════════════════════════

class ConversationOrganizer:
    """Folders, bulk operations, and organization for conversations."""

    def create_folder(self, owner_id: str, name: str,
                       color: str = "#94a3b8", icon: str = "📁") -> dict:
        fid = f"folder_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO conversation_folders (id, owner_id, name, color, icon)
                VALUES (?,?,?,?,?)
            """, (fid, owner_id, name, color, icon))
        return {"id": fid, "name": name}

    def list_folders(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT f.*, COUNT(cf.conversation_id) as conversation_count "
                "FROM conversation_folders f "
                "LEFT JOIN conversation_folder_items cf ON f.id = cf.folder_id "
                "WHERE f.owner_id=? GROUP BY f.id ORDER BY f.name",
                (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def rename_folder(self, folder_id: str, name: str) -> dict:
        with get_db() as db:
            db.execute("UPDATE conversation_folders SET name=? WHERE id=?",
                      (name, folder_id))
        return {"renamed": True}

    def delete_folder(self, folder_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM conversation_folder_items WHERE folder_id=?",
                      (folder_id,))
            db.execute("DELETE FROM conversation_folders WHERE id=?", (folder_id,))
        return {"deleted": True}

    def move_to_folder(self, conversation_id: str, folder_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO conversation_folder_items (conversation_id, folder_id) VALUES (?,?)",
                (conversation_id, folder_id))
        return {"moved": True}

    def remove_from_folder(self, conversation_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "DELETE FROM conversation_folder_items WHERE conversation_id=?",
                (conversation_id,))
        return {"removed": True}

    def get_folder_conversations(self, folder_id: str, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute("""
                SELECT c.* FROM conversations c
                JOIN conversation_folder_items cf ON c.id = cf.conversation_id
                WHERE cf.folder_id=? AND c.user_id=?
                ORDER BY c.updated_at DESC
            """, (folder_id, owner_id)).fetchall()
        return [dict(r) for r in rows]

    def bulk_delete(self, owner_id: str, conversation_ids: list) -> dict:
        """Delete multiple conversations at once."""
        deleted = 0
        with get_db() as db:
            for cid in conversation_ids:
                db.execute("DELETE FROM messages WHERE conversation_id=? AND user_id=?",
                          (cid, owner_id))
                result = db.execute("DELETE FROM conversations WHERE id=? AND user_id=?",
                                   (cid, owner_id))
                if hasattr(result, 'rowcount'):
                    deleted += result.rowcount
                else:
                    deleted += 1
                db.execute("DELETE FROM conversation_folder_items WHERE conversation_id=?",
                          (cid,))
        return {"deleted": deleted, "requested": len(conversation_ids)}

    def bulk_archive(self, owner_id: str, conversation_ids: list) -> dict:
        """Archive multiple conversations."""
        with get_db() as db:
            for cid in conversation_ids:
                db.execute(
                    "UPDATE conversations SET archived=1 WHERE id=? AND user_id=?",
                    (cid, owner_id))
        return {"archived": len(conversation_ids)}


# ══════════════════════════════════════════════════════════════
# 4. ROUNDTABLE — LIMITS + EXPORT
# ══════════════════════════════════════════════════════════════

ROUNDTABLE_MAX_PARTICIPANTS = 8

def validate_roundtable_participants(participants: list) -> dict:
    """Validate participant count before creating a roundtable."""
    if len(participants) > ROUNDTABLE_MAX_PARTICIPANTS:
        return {
            "valid": False,
            "error": f"Maximum {ROUNDTABLE_MAX_PARTICIPANTS} participants per Roundtable Meeting. "
                     f"You selected {len(participants)}.",
            "max": ROUNDTABLE_MAX_PARTICIPANTS,
        }
    if len(participants) < 2:
        return {"valid": False, "error": "At least 2 participants required."}
    return {"valid": True}


# ══════════════════════════════════════════════════════════════
# 5. SPEND ALERTS
# ══════════════════════════════════════════════════════════════

class SpendAlertManager:
    """Budget alerts — warn when approaching or exceeding spend limits."""

    def set_budget(self, owner_id: str, monthly_budget: float,
                    alert_at_pct: int = 80) -> dict:
        """Set a monthly AI spend budget."""
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO spend_budgets
                    (owner_id, monthly_budget, alert_at_pct)
                VALUES (?,?,?)
            """, (owner_id, monthly_budget, alert_at_pct))
        return {"budget": monthly_budget, "alert_at": f"{alert_at_pct}%"}

    def get_budget(self, owner_id: str) -> dict:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM spend_budgets WHERE owner_id=?",
                (owner_id,)).fetchone()
        if not row:
            return {"budget_set": False}
        return dict(row)

    def check_budget(self, owner_id: str, current_spend: float) -> dict:
        """Check if current spend triggers an alert."""
        budget = self.get_budget(owner_id)
        if not budget.get("monthly_budget"):
            return {"alert": False, "budget_set": False}

        monthly = budget["monthly_budget"]
        alert_pct = budget.get("alert_at_pct", 80)
        usage_pct = round(current_spend / monthly * 100, 1) if monthly > 0 else 0

        alert = None
        if current_spend >= monthly:
            alert = {
                "level": "exceeded",
                "message": f"You've exceeded your monthly AI budget of ${monthly:.2f}. "
                           f"Current spend: ${current_spend:.2f} ({usage_pct}%).",
            }
        elif usage_pct >= alert_pct:
            alert = {
                "level": "warning",
                "message": f"You've used {usage_pct}% of your monthly AI budget "
                           f"(${current_spend:.2f} of ${monthly:.2f}).",
            }

        return {
            "budget": monthly,
            "current_spend": current_spend,
            "usage_pct": usage_pct,
            "alert": alert,
        }

    def delete_budget(self, owner_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM spend_budgets WHERE owner_id=?", (owner_id,))
        return {"deleted": True}
