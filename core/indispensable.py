# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Indispensable Features — The 6 features that make users unable to leave.

1. DAILY BRIEFING — AI-generated morning summary across ALL platform data
2. QUICK CAPTURE — Voice/text → auto-routes to CRM, tasks, calendar
3. WORKFLOW AUTOMATION — If X happens, do Y automatically
4. CONTENT REPURPOSING — One input → multi-platform outputs
5. SMART REMINDERS — Proactive AI nudges based on business logic
6. CLIENT SNAPSHOT — 360° view of any contact across all features
"""

import json
import uuid
import re
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.indispensable")


# ══════════════════════════════════════════════════════════════
# 1. DAILY BRIEFING
# ══════════════════════════════════════════════════════════════

class DailyBriefing:
    """AI-generated morning briefing across ALL platform data.

    Pulls from: CRM, tasks, invoices, goals, social, expenses, conversations.
    Generates: prioritized summary of what matters TODAY.
    """

    def generate(self, owner_id: str) -> dict:
        """Build the daily briefing from all platform data."""
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        briefing = {
            "generated_at": datetime.now().isoformat(),
            "greeting": self._greeting(),
            "urgent": [],
            "today": [],
            "pipeline": {},
            "performance": {},
            "reminders": [],
            "ai_prompt": "",
        }

        with get_db() as db:
            # ── Overdue tasks ──
            overdue_tasks = db.execute(
                "SELECT title, due_date, priority FROM tasks WHERE owner_id=? AND status='open' "
                "AND due_date!='' AND due_date<? ORDER BY due_date LIMIT 10",
                (owner_id, today)).fetchall()
            for t in overdue_tasks:
                d = dict(t)
                briefing["urgent"].append({
                    "type": "overdue_task",
                    "icon": "🔴",
                    "message": f"Task overdue: {d['title']} (due {d['due_date']})",
                    "priority": d["priority"],
                })

            # ── Overdue invoices ──
            overdue_inv = db.execute(
                "SELECT invoice_number, client_name, total, due_date FROM invoices "
                "WHERE owner_id=? AND status='sent' AND due_date<? LIMIT 5",
                (owner_id, today)).fetchall()
            for inv in overdue_inv:
                d = dict(inv)
                briefing["urgent"].append({
                    "type": "overdue_invoice",
                    "icon": "💰",
                    "message": f"Invoice {d['invoice_number']} overdue: ${d['total']:,.2f} from {d['client_name']} (due {d['due_date']})",
                })

            # ── CRM follow-ups due today ──
            followups = db.execute(
                "SELECT a.subject, c.name as contact_name FROM crm_activities a "
                "LEFT JOIN crm_contacts c ON a.contact_id = c.id "
                "WHERE a.owner_id=? AND a.completed=0 AND a.due_date=? LIMIT 10",
                (owner_id, today)).fetchall()
            for f in followups:
                d = dict(f)
                briefing["today"].append({
                    "type": "follow_up",
                    "icon": "📞",
                    "message": f"Follow up: {d['subject']}" + (f" with {d['contact_name']}" if d.get('contact_name') else ""),
                })

            # ── Tasks due today ──
            today_tasks = db.execute(
                "SELECT title, priority, assigned_to FROM tasks WHERE owner_id=? AND status='open' AND due_date=?",
                (owner_id, today)).fetchall()
            for t in today_tasks:
                d = dict(t)
                briefing["today"].append({
                    "type": "task_due",
                    "icon": "📋",
                    "message": f"Due today: {d['title']}" + (f" ({d['priority']})" if d['priority'] in ('high','urgent') else ""),
                })

            # ── Scheduled social posts today ──
            scheduled = db.execute(
                "SELECT COUNT(*) as c FROM social_posts p JOIN social_campaigns camp ON p.campaign_id=camp.id "
                "WHERE camp.owner_id=? AND p.status='scheduled' AND p.scheduled_at LIKE ?",
                (owner_id, f"{today}%")).fetchone()
            post_count = dict(scheduled)["c"]
            if post_count:
                briefing["today"].append({
                    "type": "social_posts",
                    "icon": "📱",
                    "message": f"{post_count} social media post{'s' if post_count > 1 else ''} scheduled today",
                })

            # ── Pipeline summary ──
            pipeline_value = db.execute(
                "SELECT COALESCE(SUM(value),0) as t FROM crm_deals WHERE owner_id=? AND status='open'",
                (owner_id,)).fetchone()
            deal_count = db.execute(
                "SELECT COUNT(*) as c FROM crm_deals WHERE owner_id=? AND status='open'",
                (owner_id,)).fetchone()
            stale = db.execute(
                "SELECT COUNT(*) as c FROM crm_deals WHERE owner_id=? AND status='open' AND updated_at<?",
                (owner_id, week_ago)).fetchone()

            briefing["pipeline"] = {
                "total_value": round(dict(pipeline_value)["t"], 2),
                "deal_count": dict(deal_count)["c"],
                "stale_deals": dict(stale)["c"],
            }

            # ── Performance (last 7 days) ──
            tasks_completed = db.execute(
                "SELECT COUNT(*) as c FROM tasks WHERE owner_id=? AND status='completed' AND completed_at>=?",
                (owner_id, week_ago)).fetchone()
            deals_won = db.execute(
                "SELECT COUNT(*) as c, COALESCE(SUM(value),0) as v FROM crm_deals "
                "WHERE owner_id=? AND stage='closed_won' AND updated_at>=?",
                (owner_id, week_ago)).fetchone()
            invoices_paid = db.execute(
                "SELECT COALESCE(SUM(total),0) as t FROM invoices WHERE owner_id=? AND status='paid' AND paid_at>=?",
                (owner_id, week_ago)).fetchone()

            briefing["performance"] = {
                "tasks_completed_7d": dict(tasks_completed)["c"],
                "deals_won_7d": dict(deals_won)["c"],
                "revenue_won_7d": round(dict(deals_won)["v"], 2),
                "invoices_paid_7d": round(dict(invoices_paid)["t"], 2),
            }

            # ── Goal progress ──
            goals = db.execute(
                "SELECT title, progress_pct, due_date FROM goals "
                "WHERE owner_id=? AND status='active' AND parent_id='' ORDER BY due_date LIMIT 3",
                (owner_id,)).fetchall()
            briefing["goals"] = [dict(g) for g in goals]

        # ── Build AI prompt for natural language briefing ──
        briefing["ai_prompt"] = self._build_prompt(briefing)

        return briefing

    def _greeting(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning"
        elif hour < 17:
            return "Good afternoon"
        return "Good evening"

    def _build_prompt(self, briefing: dict) -> str:
        """Build a prompt for AI to narrate the briefing naturally."""
        parts = [
            "Generate a concise, energetic daily briefing for a business owner. "
            "Use a warm, professional tone. Keep it under 200 words. "
            "Start with the greeting, then hit the highlights:\n\n"
        ]

        if briefing["urgent"]:
            parts.append(f"URGENT ({len(briefing['urgent'])} items):")
            for item in briefing["urgent"][:3]:
                parts.append(f"  - {item['message']}")

        if briefing["today"]:
            parts.append(f"\nTODAY ({len(briefing['today'])} items):")
            for item in briefing["today"][:5]:
                parts.append(f"  - {item['message']}")

        p = briefing.get("pipeline", {})
        if p.get("deal_count"):
            parts.append(f"\nPIPELINE: {p['deal_count']} deals worth ${p['total_value']:,.0f}"
                        + (f" ({p['stale_deals']} going stale)" if p.get('stale_deals') else ""))

        perf = briefing.get("performance", {})
        if any(perf.values()):
            parts.append(f"\nLAST 7 DAYS: {perf.get('tasks_completed_7d',0)} tasks done, "
                        f"{perf.get('deals_won_7d',0)} deals won, "
                        f"${perf.get('invoices_paid_7d',0):,.0f} collected")

        if briefing.get("goals"):
            parts.append("\nGOALS:")
            for g in briefing["goals"]:
                parts.append(f"  - {g['title']}: {g.get('progress_pct',0):.0f}%")

        parts.append("\nEnd with one motivational sentence based on their data.")
        return "\n".join(parts)


# ══════════════════════════════════════════════════════════════
# 2. QUICK CAPTURE
# ══════════════════════════════════════════════════════════════

class QuickCapture:
    """Voice/text → auto-routes to the right place.

    User says: "Just talked to Sarah Johnson about the Oak Street listing,
    she wants to see it Thursday at 2, budget is 450K"

    Platform creates:
      ✓ CRM activity log on Sarah's contact
      ✓ Updates deal value to $450K
      ✓ Suggests creating a showing reminder for Thursday 2pm
    """

    CAPTURE_TYPES = {
        "crm_note": {
            "triggers": ["talked to", "called", "met with", "spoke with", "emailed",
                         "heard from", "message from", "reached out to"],
            "action": "Log CRM activity + update contact",
        },
        "task": {
            "triggers": ["need to", "have to", "should", "don't forget", "remember to",
                         "todo", "to do", "task"],
            "action": "Create task",
        },
        "expense": {
            "triggers": ["spent", "paid", "bought", "cost", "charged", "invoice for",
                         "receipt for", "expense"],
            "action": "Log expense",
        },
        "idea": {
            "triggers": ["idea", "thought", "what if", "we could", "brainstorm",
                         "inspiration", "concept"],
            "action": "Save to ideas whiteboard",
        },
        "follow_up": {
            "triggers": ["follow up", "call back", "check in", "remind me",
                         "circle back", "get back to"],
            "action": "Create follow-up reminder",
        },
    }

    def capture(self, owner_id: str, text: str) -> dict:
        """Parse freeform text and route to the right system."""
        text_lower = text.lower()

        # Detect type
        detected_type = "crm_note"  # Default
        best_score = 0
        for cap_type, config in self.CAPTURE_TYPES.items():
            score = sum(1 for trigger in config["triggers"] if trigger in text_lower)
            if score > best_score:
                best_score = score
                detected_type = cap_type

        # Extract entities
        entities = self._extract_entities(text)

        # Build the structured capture
        capture_id = f"cap_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO quick_captures
                    (id, owner_id, raw_text, capture_type, entities, processed)
                VALUES (?,?,?,?,?,0)
            """, (capture_id, owner_id, text, detected_type,
                  json.dumps(entities)))

        # Build AI prompt to fully parse
        prompt = self._build_parse_prompt(text, detected_type, entities)

        return {
            "capture_id": capture_id,
            "detected_type": detected_type,
            "action": self.CAPTURE_TYPES[detected_type]["action"],
            "entities": entities,
            "ai_parse_prompt": prompt,
            "raw_text": text,
        }

    def _extract_entities(self, text: str) -> dict:
        """Extract names, amounts, dates from text."""
        entities = {}

        # Dollar amounts
        amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?|[\d,]+(?:\.\d{2})?\s*(?:dollars|k\b|K\b)', text)
        if amounts:
            clean = amounts[0].replace("$", "").replace(",", "").replace("dollars", "").strip()
            if clean.lower().endswith("k"):
                entities["amount"] = float(clean[:-1]) * 1000
            else:
                try:
                    entities["amount"] = float(clean)
                except ValueError:
                    pass

        # Dates
        date_patterns = [
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'(today|tomorrow|next week)',
            r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)',
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                entities["date_reference"] = match.group(0)
                break

        # Times
        time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)|\d{1,2}\s*(?:o.clock|oclock))', text)
        if time_match:
            entities["time_reference"] = time_match.group(0)

        # Phone numbers
        phone = re.search(r'(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})', text)
        if phone:
            entities["phone"] = phone.group(0)

        # Email
        email = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
        if email:
            entities["email"] = email.group(0)

        return entities

    def _build_parse_prompt(self, text: str, capture_type: str, entities: dict) -> str:
        return (
            f"Parse this quick capture and extract structured data:\n\n"
            f"Input: \"{text}\"\n"
            f"Detected type: {capture_type}\n"
            f"Extracted entities: {json.dumps(entities)}\n\n"
            f"Return JSON with:\n"
            f"- contact_name (if mentioned)\n"
            f"- action_taken (call, email, meeting, etc.)\n"
            f"- key_details (what was discussed)\n"
            f"- follow_up_needed (true/false)\n"
            f"- follow_up_date (if mentioned)\n"
            f"- amount (if mentioned)\n"
            f"- suggested_actions (array of what the platform should do)\n"
        )

    def list_captures(self, owner_id: str, limit: int = 20) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM quick_captures WHERE owner_id=? ORDER BY created_at DESC LIMIT ?",
                (owner_id, limit)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["entities"] = json.loads(d.get("entities", "{}"))
            result.append(d)
        return result


# ══════════════════════════════════════════════════════════════
# 3. WORKFLOW AUTOMATION
# ══════════════════════════════════════════════════════════════

class WorkflowAutomation:
    """If X happens → do Y automatically.

    Examples:
      Deal closes → send thank you email + create invoice + post on social
      New contact added → send welcome email + create onboarding task
      Task overdue → send reminder email + notify manager
      Invoice paid → update deal stage + send thank you
    """

    TRIGGER_TYPES = [
        "deal_stage_changed", "deal_won", "deal_lost",
        "contact_created", "contact_tagged",
        "task_completed", "task_overdue",
        "invoice_sent", "invoice_paid", "invoice_overdue",
        "goal_progress", "goal_completed",
        "social_post_published",
    ]

    ACTION_TYPES = [
        "send_email", "create_task", "create_invoice",
        "update_deal_stage", "add_tag", "remove_tag",
        "create_social_post", "log_activity",
        "send_notification", "create_follow_up",
        "update_goal_progress",
    ]

    TEMPLATES = {
        "deal_won_celebration": {
            "name": "Deal Won → Celebrate & Invoice",
            "trigger": "deal_won",
            "actions": [
                {"type": "send_email", "template": "thank_you", "to": "contact"},
                {"type": "create_invoice", "from": "deal_value"},
                {"type": "create_task", "title": "Send welcome package to {contact_name}",
                 "due_days": 3},
                {"type": "create_social_post", "content": "Excited to welcome a new client! 🎉",
                 "platform": "linkedin"},
            ],
        },
        "new_lead_nurture": {
            "name": "New Lead → Welcome & Follow-up",
            "trigger": "contact_created",
            "actions": [
                {"type": "send_email", "template": "welcome"},
                {"type": "create_follow_up", "title": "Check in with {contact_name}",
                 "due_days": 3},
                {"type": "add_tag", "tag": "new_lead"},
            ],
        },
        "invoice_overdue_chase": {
            "name": "Invoice Overdue → Reminder",
            "trigger": "invoice_overdue",
            "actions": [
                {"type": "send_email", "template": "payment_reminder"},
                {"type": "create_task", "title": "Call {client_name} about overdue invoice",
                 "priority": "high"},
            ],
        },
        "task_completed_update": {
            "name": "Task Completed → Notify & Log",
            "trigger": "task_completed",
            "actions": [
                {"type": "send_notification", "message": "Task completed: {task_title}"},
                {"type": "update_goal_progress"},
            ],
        },
    }

    def create_workflow(self, owner_id: str, name: str, trigger: str,
                         conditions: dict = None, actions: list = None,
                         template: str = None) -> dict:
        """Create a custom automation workflow."""
        wid = f"wf_{uuid.uuid4().hex[:10]}"

        if template and template in self.TEMPLATES:
            t = self.TEMPLATES[template]
            trigger = t["trigger"]
            actions = t["actions"]
            name = name or t["name"]

        with get_db() as db:
            db.execute("""
                INSERT INTO automation_workflows
                    (id, owner_id, name, trigger_type, conditions, actions, enabled)
                VALUES (?,?,?,?,?,?,1)
            """, (wid, owner_id, name, trigger,
                  json.dumps(conditions or {}), json.dumps(actions or [])))

        return {"id": wid, "name": name, "trigger": trigger,
                "action_count": len(actions or []), "enabled": True}

    def list_workflows(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM automation_workflows WHERE owner_id=? ORDER BY created_at",
                (owner_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["conditions"] = json.loads(d.get("conditions", "{}"))
            d["actions"] = json.loads(d.get("actions", "[]"))
            result.append(d)
        return result

    def get_templates(self) -> dict:
        return {k: {"name": v["name"], "trigger": v["trigger"],
                     "action_count": len(v["actions"])}
                for k, v in self.TEMPLATES.items()}

    def toggle_workflow(self, workflow_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE automation_workflows SET enabled = CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE id=?",
                (workflow_id,))
            row = db.execute("SELECT enabled FROM automation_workflows WHERE id=?",
                            (workflow_id,)).fetchone()
        return {"toggled": True, "enabled": bool(dict(row)["enabled"])}

    def delete_workflow(self, workflow_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM automation_workflows WHERE id=?", (workflow_id,))
        return {"deleted": True}

    def get_active_for_trigger(self, owner_id: str, trigger_type: str) -> list:
        """Get all active workflows matching a trigger — called by the platform when events occur."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM automation_workflows WHERE owner_id=? AND trigger_type=? AND enabled=1",
                (owner_id, trigger_type)).fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════
# 4. CONTENT REPURPOSING
# ══════════════════════════════════════════════════════════════

class ContentRepurposer:
    """One input → multi-platform outputs.

    Write a blog post → generates:
      - 3-5 Twitter/X posts (different angles, under 280 chars)
      - 1 LinkedIn post (professional, 1500 chars)
      - 1 Instagram caption (with emoji, hashtag suggestions)
      - 1 Email newsletter snippet
      - 3 Instagram/TikTok story talking points
    """

    def build_repurpose_prompt(self, content: str, content_type: str = "blog_post",
                                 platforms: list = None, tone: str = "professional",
                                 audience: str = "") -> dict:
        """Build the AI prompt to repurpose content across platforms."""
        if not platforms:
            platforms = ["twitter", "linkedin", "instagram", "email"]

        platform_instructions = []
        for p in platforms:
            if p == "twitter":
                platform_instructions.append(
                    "TWITTER/X (3-5 posts):\n"
                    "  - Each under 280 characters\n"
                    "  - Different angles (question, stat, tip, quote, CTA)\n"
                    "  - Include 2-3 hashtags per post\n"
                    "  - Make the first post a hook that stops scrolling")
            elif p == "linkedin":
                platform_instructions.append(
                    "LINKEDIN (1 post):\n"
                    "  - 1000-1500 characters\n"
                    "  - Professional but personal tone\n"
                    "  - Start with a hook line\n"
                    "  - Include a call-to-action\n"
                    "  - 3-5 relevant hashtags at the end")
            elif p == "instagram":
                platform_instructions.append(
                    "INSTAGRAM (1 caption + 3 story prompts):\n"
                    "  - Caption: engaging, emoji-rich, under 2200 chars\n"
                    "  - End with a question to drive comments\n"
                    "  - 20-30 hashtags (mix of broad and niche)\n"
                    "  - 3 story talking points (short, punchy, one per slide)")
            elif p == "email":
                platform_instructions.append(
                    "EMAIL NEWSLETTER (1 snippet):\n"
                    "  - Subject line (under 50 chars, curiosity-driven)\n"
                    "  - Preview text (under 100 chars)\n"
                    "  - Body: 150-200 words, conversational\n"
                    "  - Clear CTA button text")
            elif p == "tiktok":
                platform_instructions.append(
                    "TIKTOK SCRIPT (1 script):\n"
                    "  - 30-60 second script\n"
                    "  - Hook in first 3 seconds\n"
                    "  - Conversational, not scripted-sounding\n"
                    "  - End with a question or CTA")

        prompt = (
            f"Repurpose the following {content_type.replace('_', ' ')} into multiple platform-specific pieces.\n\n"
            f"ORIGINAL CONTENT:\n{content}\n\n"
            f"TONE: {tone}\n"
            f"TARGET AUDIENCE: {audience or 'General professional audience'}\n\n"
            f"Generate content for each platform below. Each piece should:\n"
            f"- Stand alone (someone seeing it shouldn't need the original)\n"
            f"- Have a unique angle (don't just shorten the same text)\n"
            f"- Match the platform's native format and culture\n\n"
            + "\n\n".join(platform_instructions)
        )

        return {
            "prompt": prompt,
            "source_type": content_type,
            "platforms": platforms,
            "tone": tone,
        }


# ══════════════════════════════════════════════════════════════
# 5. SMART REMINDERS
# ══════════════════════════════════════════════════════════════

class SmartReminders:
    """AI-driven proactive reminders based on business logic.

    Not calendar alarms. Pattern-based nudges:
    - "You haven't followed up with Sarah in 12 days"
    - "3 invoices are overdue totaling $4,500"
    - "Your Q2 goal is at 45% with 3 weeks left"
    - "You have a showing tomorrow but haven't confirmed with the buyer"
    """

    def generate_reminders(self, owner_id: str) -> list:
        """Scan all platform data and generate smart reminders."""
        reminders = []
        today = datetime.now().strftime("%Y-%m-%d")

        with get_db() as db:
            # ── Stale deals (no activity in 7+ days) ──
            stale = db.execute("""
                SELECT d.title, d.value, d.stage, d.updated_at,
                       c.name as contact_name
                FROM crm_deals d
                LEFT JOIN crm_contacts c ON d.contact_id = c.id
                WHERE d.owner_id=? AND d.status='open'
                AND d.stage NOT IN ('closed_won','closed_lost')
                AND d.updated_at < ?
                ORDER BY d.value DESC LIMIT 5
            """, (owner_id, (datetime.now() - timedelta(days=7)).isoformat())).fetchall()
            for s in stale:
                d = dict(s)
                days_stale = (datetime.now() - datetime.fromisoformat(d["updated_at"])).days
                reminders.append({
                    "type": "stale_deal",
                    "priority": "high" if d.get("value", 0) > 10000 else "medium",
                    "icon": "🔔",
                    "message": f"No activity on \"{d['title']}\" (${d.get('value',0):,.0f}) in {days_stale} days"
                              + (f". Reach out to {d['contact_name']}." if d.get("contact_name") else "."),
                    "entity_type": "deal",
                    "entity_id": "",
                    "days_stale": days_stale,
                })

            # ── Overdue follow-ups ──
            overdue_followups = db.execute("""
                SELECT a.subject, a.due_date, c.name as contact_name
                FROM crm_activities a
                LEFT JOIN crm_contacts c ON a.contact_id = c.id
                WHERE a.owner_id=? AND a.completed=0 AND a.due_date!='' AND a.due_date<?
                LIMIT 5
            """, (owner_id, today)).fetchall()
            for f in overdue_followups:
                d = dict(f)
                reminders.append({
                    "type": "overdue_followup",
                    "priority": "high",
                    "icon": "📞",
                    "message": f"Overdue follow-up: {d['subject']}"
                              + (f" with {d['contact_name']}" if d.get("contact_name") else ""),
                })

            # ── Goals at risk ──
            goals_at_risk = db.execute("""
                SELECT title, progress_pct, due_date, target_value, current_value
                FROM goals WHERE owner_id=? AND status='active' AND parent_id=''
                AND due_date!='' AND progress_pct < 50
                AND due_date < ?
            """, (owner_id, (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"))).fetchall()
            for g in goals_at_risk:
                d = dict(g)
                days_left = max(0, (datetime.fromisoformat(d["due_date"]) - datetime.now()).days)
                reminders.append({
                    "type": "goal_at_risk",
                    "priority": "high" if days_left < 14 else "medium",
                    "icon": "🎯",
                    "message": f"Goal \"{d['title']}\" is at {d.get('progress_pct',0):.0f}% "
                              f"with {days_left} days left.",
                })

            # ── Unresponded proposals ──
            old_proposals = db.execute(
                "SELECT title, client_name, total, created_at FROM proposals "
                "WHERE owner_id=? AND status='sent' AND created_at<?",
                (owner_id, (datetime.now() - timedelta(days=5)).isoformat())).fetchall()
            for p in old_proposals:
                d = dict(p)
                days = (datetime.now() - datetime.fromisoformat(d["created_at"])).days
                reminders.append({
                    "type": "proposal_waiting",
                    "priority": "medium",
                    "icon": "📄",
                    "message": f"Proposal \"{d['title']}\" (${d.get('total',0):,.0f}) sent to "
                              f"{d['client_name']} {days} days ago — no response yet.",
                })

            # ── Recurring expenses due ──
            # (check if any recurring expense hasn't been logged this month)
            month_start = datetime.now().strftime("%Y-%m-01")
            recurring = db.execute(
                "SELECT DISTINCT description, amount, vendor FROM expenses "
                "WHERE owner_id=? AND recurring=1", (owner_id,)).fetchall()
            for r in recurring:
                d = dict(r)
                logged = db.execute(
                    "SELECT COUNT(*) as c FROM expenses WHERE owner_id=? AND description=? AND expense_date>=?",
                    (owner_id, d["description"], month_start)).fetchone()
                if dict(logged)["c"] == 0:
                    reminders.append({
                        "type": "recurring_expense",
                        "priority": "low",
                        "icon": "💳",
                        "message": f"Recurring expense \"{d['description']}\" (${d['amount']:,.2f}) "
                                  f"hasn't been logged this month.",
                    })

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        reminders.sort(key=lambda r: priority_order.get(r["priority"], 99))

        return reminders


# ══════════════════════════════════════════════════════════════
# 6. CLIENT SNAPSHOT — 360° VIEW
# ══════════════════════════════════════════════════════════════

class ClientSnapshot:
    """Everything about a contact in one unified view.

    Pulls from: CRM, conversations, invoices, tasks, proposals,
    activities, deals, email outbox.
    """

    def get_snapshot(self, owner_id: str, contact_id: str) -> dict:
        """Build the complete 360° view of a contact."""
        with get_db() as db:
            # Contact info
            contact = db.execute(
                "SELECT * FROM crm_contacts WHERE id=? AND owner_id=?",
                (contact_id, owner_id)).fetchone()
            if not contact:
                return {"error": "Contact not found"}
            contact = dict(contact)
            contact["tags"] = json.loads(contact.get("tags", "[]"))
            contact["custom_fields"] = json.loads(contact.get("custom_fields", "{}"))

            # Deals
            deals = db.execute(
                "SELECT * FROM crm_deals WHERE contact_id=? ORDER BY updated_at DESC",
                (contact_id,)).fetchall()

            # Activities
            activities = db.execute(
                "SELECT * FROM crm_activities WHERE contact_id=? ORDER BY created_at DESC LIMIT 20",
                (contact_id,)).fetchall()

            # Invoices (match by client name/email)
            invoices = db.execute(
                "SELECT id, invoice_number, total, status, due_date, created_at FROM invoices "
                "WHERE owner_id=? AND (client_email=? OR client_name=?) ORDER BY created_at DESC LIMIT 10",
                (owner_id, contact.get("email", ""), contact.get("name", ""))).fetchall()

            # Proposals
            proposals = db.execute(
                "SELECT id, proposal_number, title, total, status, created_at FROM proposals "
                "WHERE owner_id=? AND (client_email=? OR client_name=?) ORDER BY created_at DESC LIMIT 10",
                (owner_id, contact.get("email", ""), contact.get("name", ""))).fetchall()

            # Emails sent
            emails = db.execute(
                "SELECT id, subject, status, sent_at, created_at FROM email_outbox "
                "WHERE contact_id=? ORDER BY created_at DESC LIMIT 10",
                (contact_id,)).fetchall()

            # Tasks related
            tasks = db.execute(
                "SELECT id, title, status, priority, due_date FROM tasks "
                "WHERE owner_id=? AND (assigned_to LIKE ? OR description LIKE ?) "
                "ORDER BY created_at DESC LIMIT 10",
                (owner_id, f"%{contact.get('name', '')}%",
                 f"%{contact_id}%")).fetchall()

            # Financial summary
            total_invoiced = sum(dict(i).get("total", 0) for i in invoices)
            total_paid = sum(dict(i).get("total", 0) for i in invoices if dict(i).get("status") == "paid")
            total_pipeline = sum(dict(d).get("value", 0) for d in deals if dict(d).get("status") == "open")

        # Timeline — merge and sort all activities
        timeline = []
        for a in activities:
            d = dict(a)
            timeline.append({
                "date": d.get("created_at", ""),
                "type": d.get("activity_type", "note"),
                "title": d.get("subject", ""),
                "detail": d.get("notes", ""),
            })
        for e in emails:
            d = dict(e)
            timeline.append({
                "date": d.get("sent_at") or d.get("created_at", ""),
                "type": "email_sent",
                "title": d.get("subject", ""),
            })
        for inv in invoices:
            d = dict(inv)
            timeline.append({
                "date": d.get("created_at", ""),
                "type": "invoice",
                "title": f"Invoice {d.get('invoice_number', '')} — ${d.get('total', 0):,.2f} ({d.get('status', '')})",
            })
        timeline.sort(key=lambda x: x.get("date", ""), reverse=True)

        return {
            "contact": contact,
            "deals": [dict(d) for d in deals],
            "financial": {
                "total_invoiced": round(total_invoiced, 2),
                "total_paid": round(total_paid, 2),
                "outstanding": round(total_invoiced - total_paid, 2),
                "pipeline_value": round(total_pipeline, 2),
            },
            "proposals": [dict(p) for p in proposals],
            "emails_sent": len(emails),
            "tasks": [dict(t) for t in tasks],
            "activity_count": len(activities),
            "timeline": timeline[:30],
            "relationship_age_days": (datetime.now() - datetime.fromisoformat(
                contact.get("created_at", datetime.now().isoformat()))).days,
        }
