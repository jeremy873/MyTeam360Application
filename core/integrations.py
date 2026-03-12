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
MyTeam360 - Integrations & Event System
Webhooks, event bus, notification dispatch.
"""

import json
import uuid
import logging
import secrets
import hashlib
import hmac
import threading
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.integrations")

EVENT_TYPES = [
    "agent.message.completed", "agent.message.failed",
    "workflow.completed", "workflow.failed",
    "budget.warning", "budget.exceeded",
    "user.login", "user.created",
    "department.created", "agent.created",
    "document.uploaded", "system.error",
]


class EventBus:
    def emit(self, event_type, source=None, source_id=None, payload=None, user_id=None):
        payload_json = json.dumps(payload or {})
        with get_db() as db:
            db.execute(
                "INSERT INTO event_log (event_type, source, source_id, payload, user_id)"
                " VALUES (?,?,?,?,?)",
                (event_type, source, source_id, payload_json, user_id))
        threading.Thread(
            target=self._dispatch_webhooks,
            args=(event_type, source, source_id, payload or {}, user_id),
            daemon=True).start()

    def get_events(self, event_type=None, limit=100, offset=0):
        with get_db() as db:
            if event_type:
                rows = db.execute(
                    "SELECT * FROM event_log WHERE event_type=?"
                    " ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (event_type, limit, offset)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM event_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset)).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                try: d["payload"] = json.loads(d.get("payload", "{}"))
                except: pass
                results.append(d)
            return results

    def get_event_counts(self, hours=24):
        with get_db() as db:
            rows = db.execute(
                "SELECT event_type, COUNT(*) as count FROM event_log"
                " WHERE created_at >= datetime('now', ?)"
                " GROUP BY event_type ORDER BY count DESC",
                ("-{} hours".format(hours),)).fetchall()
            return [dict(r) for r in rows]

    def _dispatch_webhooks(self, event_type, source, source_id, payload, user_id):
        try:
            with get_db() as db:
                hooks = db.execute("SELECT * FROM webhook_endpoints WHERE is_active=1").fetchall()
            for hook in hooks:
                events = json.loads(hook["events"] or "[]")
                if events and event_type not in events and "*" not in events:
                    continue
                self._fire_webhook(dict(hook), event_type, source, source_id, payload, user_id)
        except Exception as e:
            logger.error("Webhook dispatch error: {}".format(e))

    def _fire_webhook(self, hook, event_type, source, source_id, payload, user_id):
        try:
            import urllib.request
            body = json.dumps({
                "event": event_type, "source": source, "source_id": source_id,
                "payload": payload, "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }).encode()
            headers = {"Content-Type": "application/json"}
            if hook.get("secret"):
                sig = hmac.new(hook["secret"].encode(), body, hashlib.sha256).hexdigest()
                headers["X-MT360-Signature"] = sig
            extra = json.loads(hook.get("headers", "{}"))
            headers.update(extra)
            req = urllib.request.Request(hook["url"], data=body, headers=headers, method="POST")
            resp = urllib.request.urlopen(req, timeout=10)
            status = resp.getcode()
            with get_db() as db:
                db.execute(
                    "UPDATE webhook_endpoints SET last_triggered=CURRENT_TIMESTAMP,"
                    " last_status=?, failure_count=0 WHERE id=?", (status, hook["id"]))
        except Exception as e:
            logger.warning("Webhook {} failed: {}".format(hook["id"], e))
            with get_db() as db:
                db.execute(
                    "UPDATE webhook_endpoints SET last_triggered=CURRENT_TIMESTAMP,"
                    " last_status=0, failure_count=failure_count+1 WHERE id=?", (hook["id"],))


class WebhookManager:
    def create(self, name, url, events=None, secret=None, headers=None, created_by=None):
        wid = "whk_" + uuid.uuid4().hex[:10]
        if not secret:
            secret = secrets.token_urlsafe(24)
        with get_db() as db:
            db.execute(
                "INSERT INTO webhook_endpoints (id, name, url, secret, events, headers, created_by)"
                " VALUES (?,?,?,?,?,?,?)",
                (wid, name, url, secret, json.dumps(events or ["*"]),
                 json.dumps(headers or {}), created_by))
        return self.get(wid)

    def get(self, wid):
        with get_db() as db:
            row = db.execute("SELECT * FROM webhook_endpoints WHERE id=?", (wid,)).fetchone()
            if row:
                d = dict(row)
                d["events"] = json.loads(d.get("events", "[]"))
                d["headers"] = json.loads(d.get("headers", "{}"))
                return d
        return None

    def list_all(self):
        with get_db() as db:
            rows = db.execute("SELECT * FROM webhook_endpoints ORDER BY created_at DESC").fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["events"] = json.loads(d.get("events", "[]"))
                d["headers"] = json.loads(d.get("headers", "{}"))
                results.append(d)
            return results

    def update(self, wid, data):
        sets, vals = [], []
        for k in ("name", "url", "is_active"):
            if k in data:
                sets.append("{}=?".format(k))
                vals.append(data[k])
        if "events" in data:
            sets.append("events=?")
            vals.append(json.dumps(data["events"]))
        if not sets:
            return self.get(wid)
        vals.append(wid)
        with get_db() as db:
            db.execute("UPDATE webhook_endpoints SET {} WHERE id=?".format(",".join(sets)), vals)
        return self.get(wid)

    def delete(self, wid):
        with get_db() as db:
            db.execute("DELETE FROM webhook_endpoints WHERE id=?", (wid,))
        return True

    def test(self, wid):
        hook = self.get(wid)
        if not hook:
            return {"error": "not found"}
        bus = EventBus()
        bus._fire_webhook(hook, "webhook.test", "system", wid,
                          {"message": "Test event from MyTeam360"}, None)
        return {"sent": True, "url": hook["url"]}
