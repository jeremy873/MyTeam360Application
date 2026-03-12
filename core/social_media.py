# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Social Media Campaign Manager — Create, schedule, and publish across platforms.

Flow:
  1. User creates campaign (objective, audience, platforms, date range)
  2. AI generates content calendar with posts for each platform
  3. User reviews/edits posts in a visual calendar
  4. Posts are queued at scheduled times
  5. Platform publishes via API integrations
  6. Analytics tracked per post

Supported platforms:
  - Twitter/X (via API v2)
  - LinkedIn (via Marketing API)
  - Instagram (via Graph API)
  - Facebook (via Graph API)
  - Threads (via API)
  - TikTok (via Content Publishing API)
  - YouTube Community (via Data API)
  - Custom webhook (any platform)

Scheduling:
  - Best-time suggestions per platform
  - Time zone aware
  - Queue system with retry on failure
  - Bulk scheduling (week/month at once)
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.social")


# ── Platform Configuration ──

PLATFORMS = {
    "twitter": {
        "label": "Twitter / X",
        "icon": "𝕏",
        "max_chars": 280,
        "supports_images": True,
        "supports_video": True,
        "supports_links": True,
        "best_times": ["09:00", "12:00", "17:00"],
        "api_type": "oauth2",
    },
    "linkedin": {
        "label": "LinkedIn",
        "icon": "in",
        "max_chars": 3000,
        "supports_images": True,
        "supports_video": True,
        "supports_links": True,
        "best_times": ["08:00", "10:00", "12:00"],
        "api_type": "oauth2",
    },
    "instagram": {
        "label": "Instagram",
        "icon": "📷",
        "max_chars": 2200,
        "supports_images": True,
        "supports_video": True,
        "supports_links": False,
        "best_times": ["11:00", "14:00", "19:00"],
        "api_type": "graph_api",
    },
    "facebook": {
        "label": "Facebook",
        "icon": "f",
        "max_chars": 63206,
        "supports_images": True,
        "supports_video": True,
        "supports_links": True,
        "best_times": ["09:00", "13:00", "16:00"],
        "api_type": "graph_api",
    },
    "threads": {
        "label": "Threads",
        "icon": "@",
        "max_chars": 500,
        "supports_images": True,
        "supports_video": False,
        "supports_links": True,
        "best_times": ["10:00", "15:00", "20:00"],
        "api_type": "graph_api",
    },
    "tiktok": {
        "label": "TikTok",
        "icon": "♪",
        "max_chars": 2200,
        "supports_images": False,
        "supports_video": True,
        "supports_links": True,
        "best_times": ["12:00", "19:00", "21:00"],
        "api_type": "oauth2",
    },
    "webhook": {
        "label": "Custom Webhook",
        "icon": "🔗",
        "max_chars": 100000,
        "supports_images": True,
        "supports_video": True,
        "supports_links": True,
        "best_times": [],
        "api_type": "webhook",
    },
}


class SocialMediaManager:
    """Campaign management with scheduling and publishing."""

    def get_platforms(self) -> dict:
        return PLATFORMS

    # ── Platform Connections ──

    def connect_platform(self, user_id: str, platform: str,
                          access_token: str, refresh_token: str = "",
                          account_name: str = "",
                          account_id: str = "") -> dict:
        """Connect a social media account."""
        if platform not in PLATFORMS:
            return {"error": f"Unsupported platform. Options: {list(PLATFORMS.keys())}"}

        cid = f"conn_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO social_connections
                    (id, user_id, platform, account_name, account_id,
                     access_token, refresh_token, status)
                VALUES (?,?,?,?,?,?,?,?)
            """, (cid, user_id, platform, account_name, account_id,
                  access_token, refresh_token, "active"))
        return {"connected": True, "platform": platform,
                "account": account_name, "id": cid}

    def get_connections(self, user_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT id, platform, account_name, account_id, status, created_at "
                "FROM social_connections WHERE user_id=? ORDER BY platform",
                (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def disconnect_platform(self, user_id: str, connection_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM social_connections WHERE id=? AND user_id=?",
                      (connection_id, user_id))
        return {"disconnected": True}

    # ── Campaigns ──

    def create_campaign(self, owner_id: str, name: str, objective: str = "",
                         platforms: list = None, target_audience: str = "",
                         start_date: str = "", end_date: str = "",
                         tone: str = "professional",
                         posting_frequency: str = "daily") -> dict:
        """Create a social media campaign."""
        cid = f"camp_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO social_campaigns
                    (id, owner_id, name, objective, platforms, target_audience,
                     start_date, end_date, tone, posting_frequency, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (cid, owner_id, name, objective,
                  json.dumps(platforms or ["twitter", "linkedin"]),
                  target_audience, start_date, end_date, tone,
                  posting_frequency, "draft"))

        return {"id": cid, "name": name, "status": "draft",
                "platforms": platforms or ["twitter", "linkedin"]}

    def get_campaigns(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM social_campaigns WHERE owner_id=? ORDER BY created_at DESC",
                (owner_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["platforms"] = json.loads(d.get("platforms", "[]"))
            # Count posts
            posts = db.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN status='published' THEN 1 ELSE 0 END) as published, "
                "SUM(CASE WHEN status='scheduled' THEN 1 ELSE 0 END) as scheduled "
                "FROM social_posts WHERE campaign_id=?", (d["id"],)).fetchone()
            d["post_counts"] = dict(posts) if posts else {}
            result.append(d)
        return result

    def get_campaign(self, campaign_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM social_campaigns WHERE id=?",
                            (campaign_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["platforms"] = json.loads(d.get("platforms", "[]"))
        return d

    def update_campaign(self, campaign_id: str, **updates) -> dict:
        if "platforms" in updates:
            updates["platforms"] = json.dumps(updates["platforms"])
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [campaign_id]
        with get_db() as db:
            db.execute(f"UPDATE social_campaigns SET {sets} WHERE id=?", vals)
        return {"updated": True}

    # ── Posts ──

    def create_post(self, campaign_id: str, platform: str, content: str,
                     scheduled_at: str = "", media_url: str = "",
                     link_url: str = "", hashtags: list = None) -> dict:
        """Create a single post in a campaign."""
        pid = f"post_{uuid.uuid4().hex[:12]}"
        plat_cfg = PLATFORMS.get(platform, {})

        # Validate character limit
        if len(content) > plat_cfg.get("max_chars", 100000):
            return {"error": f"Content exceeds {platform} character limit "
                             f"({plat_cfg['max_chars']} chars)"}

        with get_db() as db:
            db.execute("""
                INSERT INTO social_posts
                    (id, campaign_id, platform, content, scheduled_at,
                     media_url, link_url, hashtags, status)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (pid, campaign_id, platform, content, scheduled_at,
                  media_url, link_url, json.dumps(hashtags or []),
                  "scheduled" if scheduled_at else "draft"))

        return {"id": pid, "platform": platform, "status": "scheduled" if scheduled_at else "draft",
                "scheduled_at": scheduled_at, "char_count": len(content),
                "char_limit": plat_cfg.get("max_chars")}

    def get_posts(self, campaign_id: str, platform: str = None,
                   status: str = None) -> list:
        """Get posts for a campaign, optionally filtered."""
        where = ["campaign_id=?"]
        params = [campaign_id]
        if platform:
            where.append("platform=?")
            params.append(platform)
        if status:
            where.append("status=?")
            params.append(status)

        with get_db() as db:
            rows = db.execute(
                f"SELECT * FROM social_posts WHERE {' AND '.join(where)} "
                "ORDER BY scheduled_at, created_at", params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["hashtags"] = json.loads(d.get("hashtags", "[]"))
            result.append(d)
        return result

    def update_post(self, post_id: str, content: str = None,
                     scheduled_at: str = None, status: str = None) -> dict:
        updates, vals = [], []
        if content is not None:
            updates.append("content=?")
            vals.append(content)
        if scheduled_at is not None:
            updates.append("scheduled_at=?")
            vals.append(scheduled_at)
        if status is not None:
            updates.append("status=?")
            vals.append(status)
        if not updates:
            return {"error": "Nothing to update"}
        vals.append(post_id)
        with get_db() as db:
            db.execute(f"UPDATE social_posts SET {','.join(updates)} WHERE id=?", vals)
        return {"updated": True}

    def delete_post(self, post_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM social_posts WHERE id=?", (post_id,))
        return {"deleted": True}

    # ── Bulk Schedule ──

    def bulk_schedule(self, campaign_id: str, posts: list) -> dict:
        """Schedule multiple posts at once. Each post: {platform, content, scheduled_at}."""
        created = []
        errors = []
        for p in posts:
            result = self.create_post(
                campaign_id, p.get("platform", "twitter"),
                p.get("content", ""), scheduled_at=p.get("scheduled_at", ""),
                media_url=p.get("media_url", ""), link_url=p.get("link_url", ""),
                hashtags=p.get("hashtags"))
            if "error" in result:
                errors.append(result)
            else:
                created.append(result)
        return {"created": len(created), "errors": len(errors),
                "posts": created, "error_details": errors}

    # ── Publishing Queue ──

    def get_queue(self, user_id: str) -> list:
        """Get all scheduled posts ready to publish (scheduled_at <= now)."""
        now = datetime.now().isoformat()
        with get_db() as db:
            rows = db.execute("""
                SELECT p.*, c.name as campaign_name, c.owner_id
                FROM social_posts p
                JOIN social_campaigns c ON p.campaign_id = c.id
                WHERE c.owner_id=? AND p.status='scheduled' AND p.scheduled_at<=?
                ORDER BY p.scheduled_at
            """, (user_id, now)).fetchall()
        return [dict(r) for r in rows]

    def publish_post(self, post_id: str, user_id: str) -> dict:
        """Mark a post as published (actual API call handled by integration layer)."""
        with get_db() as db:
            db.execute(
                "UPDATE social_posts SET status='published', published_at=? WHERE id=?",
                (datetime.now().isoformat(), post_id))
        return {"published": True, "post_id": post_id,
                "published_at": datetime.now().isoformat()}

    def mark_failed(self, post_id: str, error: str = "") -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE social_posts SET status='failed', error_message=? WHERE id=?",
                (error, post_id))
        return {"failed": True}

    # ── Content Calendar View ──

    def get_calendar(self, user_id: str, start_date: str, end_date: str) -> dict:
        """Get all posts in a date range grouped by date — the content calendar."""
        with get_db() as db:
            rows = db.execute("""
                SELECT p.*, c.name as campaign_name
                FROM social_posts p
                JOIN social_campaigns c ON p.campaign_id = c.id
                WHERE c.owner_id=? AND p.scheduled_at>=? AND p.scheduled_at<=?
                ORDER BY p.scheduled_at
            """, (user_id, start_date, end_date)).fetchall()

        calendar = {}
        for r in rows:
            d = dict(r)
            date = d.get("scheduled_at", "")[:10]
            if date not in calendar:
                calendar[date] = []
            d["hashtags"] = json.loads(d.get("hashtags", "[]"))
            calendar[date].append(d)

        return {"start": start_date, "end": end_date,
                "total_posts": len(rows), "days": calendar}

    # ── Analytics ──

    def get_campaign_analytics(self, campaign_id: str) -> dict:
        with get_db() as db:
            total = db.execute(
                "SELECT COUNT(*) as c FROM social_posts WHERE campaign_id=?",
                (campaign_id,)).fetchone()
            by_status = db.execute(
                "SELECT status, COUNT(*) as c FROM social_posts WHERE campaign_id=? GROUP BY status",
                (campaign_id,)).fetchall()
            by_platform = db.execute(
                "SELECT platform, COUNT(*) as c FROM social_posts WHERE campaign_id=? GROUP BY platform",
                (campaign_id,)).fetchall()
        return {
            "total_posts": dict(total)["c"],
            "by_status": {dict(r)["status"]: dict(r)["c"] for r in by_status},
            "by_platform": {dict(r)["platform"]: dict(r)["c"] for r in by_platform},
        }

    # ── AI Content Generation Prompt ──

    def build_generation_prompt(self, campaign: dict, platform: str,
                                 post_count: int = 7) -> str:
        """Build a prompt for AI to generate a week of content."""
        plat = PLATFORMS.get(platform, {})
        return (
            f"Generate {post_count} social media posts for {plat.get('label', platform)}.\n\n"
            f"Campaign: {campaign.get('name', '')}\n"
            f"Objective: {campaign.get('objective', '')}\n"
            f"Target audience: {campaign.get('target_audience', '')}\n"
            f"Tone: {campaign.get('tone', 'professional')}\n"
            f"Character limit: {plat.get('max_chars', 280)}\n"
            f"Platform supports images: {plat.get('supports_images', False)}\n"
            f"Platform supports links: {plat.get('supports_links', True)}\n\n"
            f"Format each post as:\n"
            f"POST 1:\n[content]\nHASHTAGS: #tag1 #tag2\nBEST_TIME: {plat.get('best_times', ['12:00'])[0] if plat.get('best_times') else '12:00'}\n\n"
            f"Make each post unique. Vary the format (questions, tips, stories, stats, quotes). "
            f"Include relevant hashtags. Stay within the character limit."
        )
