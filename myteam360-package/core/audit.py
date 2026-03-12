"""
MyTeam360 — Audit Logger
Tracks all platform actions for compliance, security, and analytics.
© 2026 MyTeam360. All Rights Reserved.
"""

import logging
from .database import get_db

logger = logging.getLogger("MyTeam360.audit")


class AuditLogger:

    def log(self, action, user_id=None, user_email=None, ip_address=None,
            resource_type=None, resource_id=None, detail=None, severity="info"):
        try:
            with get_db() as db:
                db.execute("""
                    INSERT INTO audit_log
                    (user_id, user_email, ip_address, action, resource_type, resource_id, detail, severity)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (user_id, user_email, ip_address, action,
                      resource_type, resource_id, detail, severity))
        except Exception as e:
            logger.error(f"Audit log write failed: {e}")

    def log_auth(self, user_id, ip, endpoint, method, status, detail=None):
        try:
            with get_db() as db:
                db.execute("""
                    INSERT INTO auth_log (user_id, ip, endpoint, method, status, detail)
                    VALUES (?,?,?,?,?,?)
                """, (user_id, ip, endpoint, method, status, detail))
        except Exception as e:
            logger.error(f"Auth log write failed: {e}")

    def get_audit_log(self, limit=100, offset=0, user_id=None, action=None,
                      severity=None, since=None, resource_type=None):
        conditions = []
        params = []
        if user_id:
            conditions.append("user_id=?")
            params.append(user_id)
        if action:
            conditions.append("action LIKE ?")
            params.append(f"%{action}%")
        if severity:
            conditions.append("severity=?")
            params.append(severity)
        if since:
            conditions.append("timestamp>=?")
            params.append(since)
        if resource_type:
            conditions.append("resource_type=?")
            params.append(resource_type)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with get_db() as db:
            total = db.execute(f"SELECT COUNT(*) as c FROM audit_log{where}", params).fetchone()["c"]
            rows = db.execute(f"""
                SELECT * FROM audit_log{where}
                ORDER BY timestamp DESC LIMIT ? OFFSET ?
            """, params + [limit, offset]).fetchall()
            return {"entries": [dict(r) for r in rows], "total": total}

    def get_auth_log(self, limit=100, ip=None, status=None):
        conditions = []
        params = []
        if ip:
            conditions.append("ip=?")
            params.append(ip)
        if status:
            conditions.append("status=?")
            params.append(status)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with get_db() as db:
            rows = db.execute(f"""
                SELECT * FROM auth_log{where}
                ORDER BY timestamp DESC LIMIT ?
            """, params + [limit]).fetchall()
            return [dict(r) for r in rows]

    def get_security_summary(self):
        with get_db() as db:
            failed_24h = db.execute("""
                SELECT COUNT(*) as c FROM auth_log
                WHERE status='failed' AND timestamp >= datetime('now', '-24 hours')
            """).fetchone()["c"]
            critical_24h = db.execute("""
                SELECT COUNT(*) as c FROM audit_log
                WHERE severity='critical' AND timestamp >= datetime('now', '-24 hours')
            """).fetchone()["c"]
            total_actions_24h = db.execute("""
                SELECT COUNT(*) as c FROM audit_log
                WHERE timestamp >= datetime('now', '-24 hours')
            """).fetchone()["c"]
            active_users_24h = db.execute("""
                SELECT COUNT(DISTINCT user_id) as c FROM audit_log
                WHERE timestamp >= datetime('now', '-24 hours') AND user_id IS NOT NULL
            """).fetchone()["c"]
            return {
                "failed_logins_24h": failed_24h,
                "critical_events_24h": critical_24h,
                "total_actions_24h": total_actions_24h,
                "active_users_24h": active_users_24h,
            }

    def export_csv(self, since=None, until=None):
        conditions = []
        params = []
        if since:
            conditions.append("timestamp>=?")
            params.append(since)
        if until:
            conditions.append("timestamp<=?")
            params.append(until)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with get_db() as db:
            rows = db.execute(f"SELECT * FROM audit_log{where} ORDER BY timestamp", params).fetchall()
            lines = ["timestamp,user_id,user_email,ip_address,action,resource_type,resource_id,detail,severity"]
            for r in rows:
                d = dict(r)
                line = ",".join(str(d.get(k, "")).replace(",", ";") for k in
                    ["timestamp", "user_id", "user_email", "ip_address",
                     "action", "resource_type", "resource_id", "detail", "severity"])
                lines.append(line)
            return "\n".join(lines)
