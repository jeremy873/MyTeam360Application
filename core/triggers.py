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
Agent Triggers — Your AI works while you sleep.

Supports:
  - Schedule: cron-like recurring tasks ("Every Monday 8am, summarize news")
  - Webhook: external services trigger an agent via HTTP POST
  - Event: internal platform events trigger agents (new file, new message)

Each trigger fires an agent with a templated input and routes the output
to a configurable action (store, email, webhook, conversation).
"""

import json
import uuid
import time
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.triggers")


class TriggerManager:
    """Manages automated agent triggers."""

    def __init__(self, agent_manager=None):
        self.agents = agent_manager

    # ── CRUD ──

    def create_trigger(self, owner_id: str, agent_id: str, name: str,
                       trigger_type: str, config: dict,
                       input_template: str = "",
                       output_action: str = "store",
                       output_config: dict = None) -> dict:
        tid = f"trg_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO agent_triggers
                    (id, owner_id, agent_id, name, trigger_type, config,
                     input_template, output_action, output_config)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (tid, owner_id, agent_id, name, trigger_type,
                  json.dumps(config), input_template, output_action,
                  json.dumps(output_config or {})))
        return self.get_trigger(tid)

    def get_trigger(self, trigger_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM agent_triggers WHERE id=?", (trigger_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["config"] = json.loads(d.get("config", "{}"))
            d["output_config"] = json.loads(d.get("output_config", "{}"))
            return d

    def list_triggers(self, owner_id: str = None, agent_id: str = None) -> list:
        with get_db() as db:
            if agent_id:
                rows = db.execute("SELECT * FROM agent_triggers WHERE agent_id=? ORDER BY created_at DESC", (agent_id,)).fetchall()
            elif owner_id:
                rows = db.execute("SELECT * FROM agent_triggers WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM agent_triggers ORDER BY created_at DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["config"] = json.loads(d.get("config", "{}"))
            d["output_config"] = json.loads(d.get("output_config", "{}"))
            result.append(d)
        return result

    def update_trigger(self, trigger_id: str, data: dict) -> dict:
        allowed = {"name", "config", "input_template", "output_action", "output_config", "is_active"}
        updates = {}
        for k, v in data.items():
            if k in allowed:
                updates[k] = json.dumps(v) if k in ("config", "output_config") else v
        if not updates:
            return self.get_trigger(trigger_id)
        updates["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [trigger_id]
        with get_db() as db:
            db.execute(f"UPDATE agent_triggers SET {sets} WHERE id=?", vals)
        return self.get_trigger(trigger_id)

    def delete_trigger(self, trigger_id: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM agent_triggers WHERE id=?", (trigger_id,)).rowcount > 0

    def toggle_trigger(self, trigger_id: str, active: bool) -> dict:
        with get_db() as db:
            db.execute("UPDATE agent_triggers SET is_active=? WHERE id=?", (int(active), trigger_id))
        return self.get_trigger(trigger_id)

    # ── Execution ──

    def fire_trigger(self, trigger_id: str, input_data: dict = None) -> dict:
        """Execute a trigger — run its agent with the templated input."""
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            raise ValueError("Trigger not found")
        if not trigger.get("is_active"):
            return {"status": "skipped", "reason": "trigger disabled"}

        start = time.time()
        log_id = f"tlog_{uuid.uuid4().hex[:10]}"

        try:
            # Build input from template
            template = trigger.get("input_template", "")
            if input_data:
                for k, v in input_data.items():
                    template = template.replace(f"{{{{{k}}}}}", str(v))

            if not template.strip():
                template = json.dumps(input_data or {})

            # Run the agent
            if self.agents:
                result = self.agents.run_agent(
                    trigger["agent_id"], template,
                    user_id=trigger["owner_id"]
                )
            else:
                result = {"text": "[Agent manager not connected]", "error": True}

            output = result.get("text", "")
            tokens = result.get("usage", {}).get("total_tokens", 0)
            duration = int((time.time() - start) * 1000)

            # Handle output action
            self._handle_output(trigger, output, input_data)

            # Log success
            self._log_execution(log_id, trigger_id, "success", template, output, tokens, duration)

            # Update trigger stats
            with get_db() as db:
                db.execute("""
                    UPDATE agent_triggers SET fire_count=fire_count+1,
                    last_fired_at=? WHERE id=?
                """, (datetime.now().isoformat(), trigger_id))

            return {
                "status": "success",
                "trigger_id": trigger_id,
                "output": output,
                "tokens_used": tokens,
                "duration_ms": duration,
            }

        except Exception as e:
            duration = int((time.time() - start) * 1000)
            self._log_execution(log_id, trigger_id, "error", str(input_data), "", 0, duration, str(e))
            with get_db() as db:
                db.execute("""
                    UPDATE agent_triggers SET error_count=error_count+1,
                    last_error=? WHERE id=?
                """, (str(e), trigger_id))
            raise

    def _handle_output(self, trigger: dict, output: str, input_data: dict = None):
        """Route trigger output to configured action."""
        action = trigger.get("output_action", "store")
        config = trigger.get("output_config", {})

        if action == "store":
            pass  # Already logged
        elif action == "webhook":
            url = config.get("url")
            if url:
                import urllib.request
                data = json.dumps({"output": output, "trigger": trigger["name"]}).encode()
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                try:
                    urllib.request.urlopen(req, timeout=10)
                except Exception as e:
                    logger.warning(f"Trigger webhook failed: {e}")
        # Future: email, conversation, slack, etc.

    def _log_execution(self, log_id, trigger_id, status, input_data, output, tokens, duration, error=""):
        with get_db() as db:
            db.execute("""
                INSERT INTO trigger_log (id, trigger_id, status, input_data, output_data,
                    tokens_used, duration_ms, error_message)
                VALUES (?,?,?,?,?,?,?,?)
            """, (log_id, trigger_id, status, str(input_data)[:5000],
                  str(output)[:5000], tokens, duration, error))

    def get_trigger_log(self, trigger_id: str, limit: int = 20) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM trigger_log WHERE trigger_id=? ORDER BY created_at DESC LIMIT ?",
                (trigger_id, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Webhook Endpoint ──

    def fire_webhook(self, trigger_id: str, payload: dict) -> dict:
        """Fire a trigger via webhook with validation."""
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            raise ValueError("Trigger not found")
        if trigger["trigger_type"] != "webhook":
            raise ValueError("Not a webhook trigger")
        return self.fire_trigger(trigger_id, input_data=payload)

    # ── Schedule Check ──

    def get_due_triggers(self) -> list:
        """Get all schedule triggers that are due to fire.
        Called by a background task or cron job."""
        triggers = self.list_triggers()
        due = []
        now = datetime.now()
        for t in triggers:
            if t["trigger_type"] != "schedule" or not t["is_active"]:
                continue
            config = t.get("config", {})
            interval = config.get("interval_minutes", 0)
            if not interval:
                continue
            last = t.get("last_fired_at")
            if last:
                last_dt = datetime.fromisoformat(last) if isinstance(last, str) else last
                if now - last_dt < timedelta(minutes=interval):
                    continue
            due.append(t)
        return due
