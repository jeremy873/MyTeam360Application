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
MyTeam360 - Advanced Chat Features
Pins, attachments, sharing, export, search.
"""

import os
import json
import uuid
import secrets
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.chat_advanced")
UPLOAD_DIR = os.path.join("data", "uploads")


class ChatAdvanced:

    def __init__(self):
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    def pin_message(self, conv_id, message_id, user_id, note=None):
        with get_db() as db:
            db.execute("INSERT OR REPLACE INTO conversation_pins (conversation_id, message_id, pinned_by, note) VALUES (?,?,?,?)",
                (conv_id, message_id, user_id, note))
        return {"pinned": True, "conversation_id": conv_id, "message_id": message_id}

    def unpin_message(self, conv_id, message_id):
        with get_db() as db:
            db.execute("DELETE FROM conversation_pins WHERE conversation_id=? AND message_id=?", (conv_id, message_id))
        return {"unpinned": True}

    def get_pins(self, conv_id):
        with get_db() as db:
            rows = db.execute(
                "SELECT p.*, m.content, m.role, m.created_at as msg_time, u.display_name as pinned_by_name"
                " FROM conversation_pins p"
                " LEFT JOIN messages m ON p.message_id = m.id"
                " LEFT JOIN users u ON p.pinned_by = u.id"
                " WHERE p.conversation_id=? ORDER BY p.created_at DESC", (conv_id,)).fetchall()
            return [dict(r) for r in rows]

    def save_attachment(self, conv_id, message_id, filename, data_bytes, mime_type, user_id):
        fid = "att_" + uuid.uuid4().hex[:10]
        safe_name = fid + "_" + filename.replace("/", "_").replace("\\", "_")
        path = os.path.join(UPLOAD_DIR, safe_name)
        with open(path, "wb") as f:
            f.write(data_bytes)
        with get_db() as db:
            db.execute(
                "INSERT INTO file_attachments (id, message_id, conversation_id, filename, mime_type, size_bytes, storage_path, uploaded_by) VALUES (?,?,?,?,?,?,?,?)",
                (fid, message_id, conv_id, filename, mime_type, len(data_bytes), path, user_id))
        return {"id": fid, "filename": filename, "size": len(data_bytes), "mime_type": mime_type}

    def get_attachments(self, conv_id):
        with get_db() as db:
            rows = db.execute(
                "SELECT id, message_id, filename, mime_type, size_bytes, created_at"
                " FROM file_attachments WHERE conversation_id=? ORDER BY created_at", (conv_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_attachment_file(self, att_id):
        with get_db() as db:
            row = db.execute("SELECT * FROM file_attachments WHERE id=?", (att_id,)).fetchone()
            if not row: return None
            d = dict(row)
            if os.path.exists(d["storage_path"]):
                with open(d["storage_path"], "rb") as f:
                    d["data"] = f.read()
            return d

    def create_share(self, conv_id, user_id, expires_hours=72):
        sid = "shr_" + uuid.uuid4().hex[:10]
        token = secrets.token_urlsafe(32)
        expires = None
        if expires_hours:
            expires = (datetime.now() + timedelta(hours=expires_hours)).isoformat()
        with get_db() as db:
            db.execute("INSERT INTO conversation_shares (id, conversation_id, shared_by, share_token, expires_at) VALUES (?,?,?,?,?)",
                (sid, conv_id, user_id, token, expires))
        return {"id": sid, "token": token, "expires_at": expires, "url": "/shared/" + token}

    def get_shared(self, token):
        with get_db() as db:
            row = db.execute(
                "SELECT s.*, c.title as conv_title FROM conversation_shares s"
                " LEFT JOIN conversations c ON s.conversation_id = c.id"
                " WHERE s.share_token=? AND s.is_active=1", (token,)).fetchone()
            if not row: return None
            d = dict(row)
            if d.get("expires_at"):
                if datetime.fromisoformat(d["expires_at"]) < datetime.now():
                    return None
            msgs = db.execute(
                "SELECT id, role, content, agent_id, created_at FROM messages WHERE conversation_id=? ORDER BY created_at",
                (d["conversation_id"],)).fetchall()
            d["messages"] = [dict(m) for m in msgs]
            return d

    def revoke_share(self, share_id):
        with get_db() as db:
            db.execute("UPDATE conversation_shares SET is_active=0 WHERE id=?", (share_id,))
        return {"revoked": True}

    def export_markdown(self, conv_id):
        with get_db() as db:
            conv = db.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
            if not conv: return None
            msgs = db.execute(
                "SELECT m.*, a.name as agent_name FROM messages m LEFT JOIN agents a ON m.agent_id = a.id"
                " WHERE m.conversation_id=? ORDER BY m.created_at", (conv_id,)).fetchall()
        lines = ["# " + (conv["title"] or "Conversation")]
        lines.append("*Exported: " + datetime.now().strftime("%Y-%m-%d %H:%M") + "*")
        for m in msgs:
            role = m["role"].upper()
            if m["role"] == "assistant" and m.get("agent_name"): role = m["agent_name"]
            lines.append("**" + role + "** (" + str(m["created_at"])[:16] + "):")
            lines.append(m["content"])
            lines.append("")
        return "\n".join(lines)

    def export_json(self, conv_id):
        with get_db() as db:
            conv = db.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
            if not conv: return None
            msgs = db.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at", (conv_id,)).fetchall()
        return json.dumps({"conversation": dict(conv), "messages": [dict(m) for m in msgs],
            "exported_at": datetime.now().isoformat()}, indent=2, default=str)

    def search_messages(self, query, user_id=None, limit=50):
        with get_db() as db:
            q_param = "%" + query + "%"
            if user_id:
                rows = db.execute(
                    "SELECT m.id, m.conversation_id, m.role, m.content, m.created_at, c.title as conv_title"
                    " FROM messages m JOIN conversations c ON m.conversation_id = c.id"
                    " WHERE m.content LIKE ? AND c.user_id=? ORDER BY m.created_at DESC LIMIT ?",
                    (q_param, user_id, limit)).fetchall()
            else:
                rows = db.execute(
                    "SELECT m.id, m.conversation_id, m.role, m.content, m.created_at, c.title as conv_title"
                    " FROM messages m JOIN conversations c ON m.conversation_id = c.id"
                    " WHERE m.content LIKE ? ORDER BY m.created_at DESC LIMIT ?",
                    (q_param, limit)).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                idx = d["content"].lower().find(query.lower())
                start = max(0, idx - 60)
                end = min(len(d["content"]), idx + len(query) + 60)
                d["snippet"] = "..." + d["content"][start:end] + "..."
                del d["content"]
                results.append(d)
            return results
