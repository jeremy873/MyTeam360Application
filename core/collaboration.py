# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# See LICENSE and NOTICE files for full legal terms.
# ═══════════════════════════════════════════════════════════════════

"""
Collaboration — Multi-User Teams Alongside AI Spaces

Turns MyTeam360 from a single-user AI tool into a team platform:
  - Team workspaces with invite system
  - Multiple humans join Roundtables alongside AI Spaces
  - Shared Spaces that any team member can use
  - Presence tracking (who's online)
  - Role-based permissions (owner, admin, member, viewer)
  - Team-wide activity feed

The key insight: a Roundtable with 3 humans + 2 AI Spaces
is something NO product on the market offers.
"""

import json
import uuid
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.collaboration")


# ══════════════════════════════════════════════════════════════
# TEAM MANAGEMENT
# ══════════════════════════════════════════════════════════════

class TeamManager:
    """Manage teams of human users who collaborate together."""

    def create_team(self, owner_id: str, name: str,
                    description: str = "") -> dict:
        tid = f"team_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO teams (id, owner_id, name, description)
                VALUES (?,?,?,?)
            """, (tid, owner_id, name, description))
            # Owner is automatically a member with 'owner' role
            db.execute("""
                INSERT INTO team_members (id, team_id, user_id, role, status)
                VALUES (?,?,?,?,?)
            """, (f"tm_{uuid.uuid4().hex[:10]}", tid, owner_id, "owner", "active"))
        return self.get_team(tid)

    def get_team(self, tid: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM teams WHERE id=?", (tid,)).fetchone()
            if not row: return None
            d = dict(row)
            members = db.execute("""
                SELECT tm.*, u.display_name, u.email, u.avatar_color
                FROM team_members tm
                JOIN users u ON u.id = tm.user_id
                WHERE tm.team_id=? AND tm.status='active'
                ORDER BY tm.role, u.display_name
            """, (tid,)).fetchall()
            d["members"] = [dict(m) for m in members]
            d["member_count"] = len(d["members"])
            return d

    def list_teams(self, user_id: str) -> list:
        """List all teams a user belongs to."""
        with get_db() as db:
            rows = db.execute("""
                SELECT t.*, tm.role as my_role,
                    (SELECT COUNT(*) FROM team_members WHERE team_id=t.id AND status='active') as member_count
                FROM teams t
                JOIN team_members tm ON tm.team_id = t.id
                WHERE tm.user_id=? AND tm.status='active'
                ORDER BY t.created_at DESC
            """, (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def invite_member(self, team_id: str, inviter_id: str,
                      email: str, role: str = "member") -> dict:
        """Invite a user to a team by email."""
        if role not in ("admin", "member", "viewer"):
            role = "member"

        # Check inviter has permission
        if not self._has_role(team_id, inviter_id, ["owner", "admin"]):
            raise PermissionError("Only owners and admins can invite members")

        # Find user by email
        with get_db() as db:
            user = db.execute("SELECT id, display_name, email FROM users WHERE email=?",
                             (email,)).fetchone()

        invite_id = f"inv_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO team_invites
                    (id, team_id, inviter_id, email, target_user_id, role, status)
                VALUES (?,?,?,?,?,?,?)
            """, (invite_id, team_id, inviter_id, email,
                  dict(user)["id"] if user else None, role, "pending"))

        return {
            "invite_id": invite_id,
            "email": email,
            "role": role,
            "status": "pending",
            "user_found": user is not None,
        }

    def accept_invite(self, invite_id: str, user_id: str) -> dict:
        """User accepts a team invitation."""
        with get_db() as db:
            invite = db.execute("SELECT * FROM team_invites WHERE id=? AND status='pending'",
                               (invite_id,)).fetchone()
            if not invite:
                raise ValueError("Invite not found or already used")

            inv = dict(invite)
            # Verify this is the right user
            user = db.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()
            if not user or dict(user)["email"] != inv["email"]:
                raise PermissionError("This invite is not for you")

            # Add as member
            mid = f"tm_{uuid.uuid4().hex[:10]}"
            db.execute("""
                INSERT INTO team_members (id, team_id, user_id, role, status)
                VALUES (?,?,?,?,?)
            """, (mid, inv["team_id"], user_id, inv["role"], "active"))

            # Mark invite used
            db.execute("UPDATE team_invites SET status='accepted' WHERE id=?", (invite_id,))

        return {"team_id": inv["team_id"], "role": inv["role"], "status": "joined"}

    def remove_member(self, team_id: str, remover_id: str,
                      target_user_id: str) -> bool:
        """Remove a member from a team."""
        if not self._has_role(team_id, remover_id, ["owner", "admin"]):
            raise PermissionError("Insufficient permissions")
        # Can't remove the owner
        if self._has_role(team_id, target_user_id, ["owner"]):
            raise PermissionError("Cannot remove the team owner")

        with get_db() as db:
            db.execute(
                "UPDATE team_members SET status='removed' WHERE team_id=? AND user_id=?",
                (team_id, target_user_id))
        return True

    def update_member_role(self, team_id: str, updater_id: str,
                           target_user_id: str, new_role: str) -> dict:
        """Change a member's role."""
        if not self._has_role(team_id, updater_id, ["owner"]):
            raise PermissionError("Only the owner can change roles")
        if new_role not in ("admin", "member", "viewer"):
            raise ValueError("Role must be: admin, member, or viewer")

        with get_db() as db:
            db.execute(
                "UPDATE team_members SET role=? WHERE team_id=? AND user_id=?",
                (new_role, team_id, target_user_id))
        return {"user_id": target_user_id, "new_role": new_role}

    def get_pending_invites(self, user_id: str) -> list:
        """Get invites waiting for a user."""
        with get_db() as db:
            user = db.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()
            if not user: return []
            rows = db.execute("""
                SELECT ti.*, t.name as team_name, u.display_name as inviter_name
                FROM team_invites ti
                JOIN teams t ON t.id = ti.team_id
                JOIN users u ON u.id = ti.inviter_id
                WHERE ti.email=? AND ti.status='pending'
                ORDER BY ti.created_at DESC
            """, (dict(user)["email"],)).fetchall()
        return [dict(r) for r in rows]

    def _has_role(self, team_id: str, user_id: str, roles: list) -> bool:
        with get_db() as db:
            row = db.execute(
                "SELECT role FROM team_members WHERE team_id=? AND user_id=? AND status='active'",
                (team_id, user_id)).fetchone()
        return row and dict(row)["role"] in roles


# ══════════════════════════════════════════════════════════════
# COLLABORATIVE ROUNDTABLE — Humans + AI Together
# ══════════════════════════════════════════════════════════════

class CollaborativeRoundtable:
    """Extends Roundtable to support multiple human participants.

    A meeting with 3 engineers + Strategy AI + Data Analyst AI:
    - Humans type messages in real-time
    - AI Spaces respond during scheduled rounds
    - Everyone sees the same transcript
    - Minutes auto-generated at the end
    """

    def __init__(self, roundtable_manager=None, team_manager=None):
        self.rt = roundtable_manager
        self.teams = team_manager

    def invite_users_to_roundtable(self, rid: str, inviter_id: str,
                                    user_ids: list) -> dict:
        """Invite human users to participate in a Roundtable."""
        with get_db() as db:
            rt = db.execute("SELECT * FROM roundtables WHERE id=?", (rid,)).fetchone()
            if not rt: raise ValueError("Roundtable not found")
            rt_dict = dict(rt)
            if rt_dict["owner_id"] != inviter_id:
                raise PermissionError("Only the moderator can invite participants")

            participants = json.loads(rt_dict.get("participants", "[]") or "[]")
            added = []

            for uid in user_ids:
                # Check not already in
                if any(p.get("user_id") == uid for p in participants):
                    continue

                user = db.execute(
                    "SELECT id, display_name, email, avatar_color FROM users WHERE id=?",
                    (uid,)).fetchone()
                if not user: continue

                u = dict(user)
                participants.append({
                    "type": "human",
                    "user_id": uid,
                    "name": u["display_name"],
                    "icon": "👤",
                    "role": "participant",
                    "avatar_color": u.get("avatar_color", "#a459f2"),
                })
                added.append(u["display_name"])

            db.execute("UPDATE roundtables SET participants=? WHERE id=?",
                      (json.dumps(participants), rid))

        return {"roundtable_id": rid, "users_added": added, "total_participants": len(participants)}

    def human_message(self, rid: str, user_id: str, message: str) -> dict:
        """A human participant (not the moderator) posts a message."""
        with get_db() as db:
            rt = db.execute("SELECT * FROM roundtables WHERE id=?", (rid,)).fetchone()
            if not rt: raise ValueError("Roundtable not found")
            rt_dict = dict(rt)
            participants = json.loads(rt_dict.get("participants", "[]") or "[]")

            # Verify user is a participant
            user_participant = None
            for p in participants:
                if p.get("user_id") == user_id:
                    user_participant = p
                    break

            # Owner/moderator is always allowed
            is_moderator = rt_dict["owner_id"] == user_id

            if not user_participant and not is_moderator:
                raise PermissionError("You are not a participant in this Roundtable")

            # Get user name
            if is_moderator and not user_participant:
                name = "Moderator"
                icon = "👑"
            else:
                name = user_participant.get("name", "Unknown") if user_participant else "Unknown"
                icon = "👤"

            transcript = json.loads(rt_dict.get("transcript", "[]") or "[]")
            entry = {
                "type": "human",
                "speaker": user_id,
                "name": name,
                "icon": icon,
                "content": message,
                "timestamp": datetime.now().isoformat(),
            }
            transcript.append(entry)

            db.execute("UPDATE roundtables SET transcript=?, status='active', updated_at=? WHERE id=?",
                      (json.dumps(transcript), datetime.now().isoformat(), rid))

        return entry

    def get_participants(self, rid: str) -> dict:
        """Get all participants — humans and AI — for a Roundtable."""
        with get_db() as db:
            rt = db.execute("SELECT participants, owner_id FROM roundtables WHERE id=?",
                           (rid,)).fetchone()
            if not rt: raise ValueError("Not found")

            d = dict(rt)
            participants = json.loads(d.get("participants", "[]") or "[]")

            humans = [p for p in participants if p.get("type") == "human"]
            agents = [p for p in participants if p.get("type") != "human"]

            return {
                "roundtable_id": rid,
                "moderator": d["owner_id"],
                "humans": humans,
                "agents": agents,
                "total": len(participants),
            }


# ══════════════════════════════════════════════════════════════
# PRESENCE TRACKING
# ══════════════════════════════════════════════════════════════

class PresenceTracker:
    """Track who's online in a team or Roundtable."""

    def heartbeat(self, user_id: str, context: str = "app",
                  context_id: str = "") -> dict:
        """User sends a heartbeat to indicate they're online."""
        with get_db() as db:
            db.execute("""
                INSERT INTO user_presence (user_id, context, context_id, last_seen)
                VALUES (?,?,?,?)
                ON CONFLICT(user_id, context, context_id) DO UPDATE SET last_seen=?
            """, (user_id, context, context_id, datetime.now().isoformat(),
                  datetime.now().isoformat()))
        return {"status": "online", "context": context}

    def get_online_users(self, context: str = "app",
                         context_id: str = "",
                         timeout_seconds: int = 120) -> list:
        """Get users who sent a heartbeat within the timeout period."""
        with get_db() as db:
            # Simple approach: anyone with heartbeat in last N seconds
            rows = db.execute("""
                SELECT up.user_id, up.last_seen, u.display_name, u.avatar_color
                FROM user_presence up
                JOIN users u ON u.id = up.user_id
                WHERE up.context=? AND up.context_id=?
                ORDER BY up.last_seen DESC
            """, (context, context_id)).fetchall()

        cutoff = datetime.now().timestamp() - timeout_seconds
        online = []
        for r in rows:
            d = dict(r)
            try:
                seen_ts = datetime.fromisoformat(d["last_seen"]).timestamp()
                if seen_ts >= cutoff:
                    d["status"] = "online"
                    online.append(d)
            except (ValueError, TypeError):
                pass
        return online

    def get_roundtable_presence(self, rid: str) -> list:
        """Who's actively viewing a specific Roundtable."""
        return self.get_online_users(context="roundtable", context_id=rid)


# ══════════════════════════════════════════════════════════════
# ACTIVITY FEED
# ══════════════════════════════════════════════════════════════

class ActivityFeed:
    """Team-wide activity feed — who did what, when."""

    def log_activity(self, team_id: str, user_id: str, user_name: str,
                     action: str, detail: str = "",
                     resource_type: str = "", resource_id: str = "") -> dict:
        aid = f"act_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO team_activity
                    (id, team_id, user_id, user_name, action, detail,
                     resource_type, resource_id)
                VALUES (?,?,?,?,?,?,?,?)
            """, (aid, team_id, user_id, user_name, action, detail,
                  resource_type, resource_id))
        return {"id": aid, "action": action}

    def get_feed(self, team_id: str, limit: int = 50) -> list:
        with get_db() as db:
            rows = db.execute("""
                SELECT * FROM team_activity WHERE team_id=?
                ORDER BY created_at DESC LIMIT ?
            """, (team_id, limit)).fetchall()
        return [dict(r) for r in rows]
