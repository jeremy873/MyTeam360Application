# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Lifestyle Intelligence Engine — The platform that knows YOU.

This isn't a business tool with preferences. It's an AI that learns:
  - Your WEEKLY RHYTHM (Monday is pipeline review, Wednesday is client day)
  - Your DAILY PATTERNS (morning = deep work, afternoon = meetings)
  - Your PREFERENCES (Italian for client dinners, window seat, early flights)
  - Your LIFE CONTEXT (kids picked up at 3:30, gym at 6am MWF)

Then it PROACTIVELY adapts:
  - Monday briefing focuses on pipeline and weekly planning
  - Wednesday briefing focuses on client prep and dinner reservations
  - Friday briefing focuses on week wrap-up and next week preview
  - It checks your flight status before you think to
  - It suggests restaurants near your afternoon meeting
  - It reminds you to leave early if traffic is bad

DNA Learning Loop:
  1. User does things on the platform (implicit learning)
  2. User gives explicit preferences ("I like Italian for client dinners")
  3. Platform detects patterns over time ("You always review deals on Monday")
  4. Feedback loop: user rates suggestions, system adjusts

The more they use it, the smarter it gets. The smarter it gets,
the harder it is to leave.
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.lifestyle")


# ══════════════════════════════════════════════════════════════
# WEEKLY RHYTHM PROFILES
# ══════════════════════════════════════════════════════════════

DEFAULT_WEEK_RHYTHM = {
    "monday": {
        "label": "Week Kickoff",
        "focus": "planning",
        "briefing_emphasis": ["pipeline_review", "weekly_goals", "overdue_from_weekend"],
        "default_blocks": [
            {"time": "09:00", "activity": "Weekly pipeline review", "duration": 60},
            {"time": "10:00", "activity": "Team standup / priority setting", "duration": 30},
            {"time": "14:00", "activity": "Client follow-ups", "duration": 90},
        ],
    },
    "tuesday": {
        "label": "Execution Day",
        "focus": "deep_work",
        "briefing_emphasis": ["tasks_due", "content_creation", "deal_progression"],
        "default_blocks": [
            {"time": "09:00", "activity": "Deep work block", "duration": 120},
            {"time": "14:00", "activity": "Client meetings", "duration": 120},
        ],
    },
    "wednesday": {
        "label": "Client Day",
        "focus": "relationships",
        "briefing_emphasis": ["meetings_today", "client_prep", "dinner_suggestions"],
        "default_blocks": [
            {"time": "09:00", "activity": "Meeting prep", "duration": 60},
            {"time": "10:00", "activity": "Client meetings", "duration": 180},
            {"time": "18:00", "activity": "Client dinner", "duration": 120},
        ],
    },
    "thursday": {
        "label": "Content Day",
        "focus": "marketing",
        "briefing_emphasis": ["social_performance", "content_schedule", "marketing_metrics"],
        "default_blocks": [
            {"time": "09:00", "activity": "Content creation", "duration": 120},
            {"time": "14:00", "activity": "Social media review", "duration": 60},
            {"time": "15:00", "activity": "Campaign optimization", "duration": 60},
        ],
    },
    "friday": {
        "label": "Wrap-Up",
        "focus": "review",
        "briefing_emphasis": ["week_summary", "next_week_preview", "invoicing", "loose_ends"],
        "default_blocks": [
            {"time": "09:00", "activity": "Week review & metrics", "duration": 60},
            {"time": "10:00", "activity": "Invoice & expense reconciliation", "duration": 60},
            {"time": "14:00", "activity": "Next week planning", "duration": 60},
            {"time": "15:00", "activity": "Early wrap-up", "duration": 60},
        ],
    },
    "saturday": {
        "label": "Light Touch",
        "focus": "minimal",
        "briefing_emphasis": ["urgent_only", "weekend_personal"],
        "default_blocks": [],
    },
    "sunday": {
        "label": "Week Prep",
        "focus": "preview",
        "briefing_emphasis": ["monday_preview", "week_ahead", "goals_check"],
        "default_blocks": [
            {"time": "19:00", "activity": "Week ahead preview", "duration": 30},
        ],
    },
}


# ══════════════════════════════════════════════════════════════
# PERSONAL PREFERENCES
# ══════════════════════════════════════════════════════════════

PREFERENCE_CATEGORIES = {
    "dining": {
        "label": "Dining Preferences",
        "fields": {
            "cuisine_favorites": {"type": "multi_select", "options": [
                "Italian", "Japanese", "Mexican", "American", "French",
                "Chinese", "Thai", "Indian", "Mediterranean", "Korean",
                "Steakhouse", "Seafood", "Vegetarian", "Vegan"]},
            "price_range": {"type": "select", "options": ["$", "$$", "$$$", "$$$$"]},
            "ambiance": {"type": "multi_select", "options": [
                "Quiet/intimate", "Lively", "Outdoor seating", "Private dining",
                "Bar scene", "Family friendly", "Business appropriate"]},
            "dietary_restrictions": {"type": "multi_select", "options": [
                "None", "Gluten-free", "Dairy-free", "Nut allergy",
                "Halal", "Kosher", "Vegetarian", "Vegan"]},
            "client_dinner_style": {"type": "text",
                "placeholder": "e.g., Upscale Italian, quiet enough to talk business"},
        },
    },
    "travel": {
        "label": "Travel Preferences",
        "fields": {
            "seat_preference": {"type": "select", "options": ["Window", "Aisle", "No preference"]},
            "flight_time": {"type": "select", "options": ["Early morning", "Mid-morning",
                "Afternoon", "Evening", "Red-eye", "No preference"]},
            "airline_preference": {"type": "text", "placeholder": "e.g., Southwest, United"},
            "hotel_preference": {"type": "text", "placeholder": "e.g., Marriott, Hilton"},
            "rental_car": {"type": "select", "options": ["Compact", "Midsize", "Full-size",
                "SUV", "Luxury", "No preference"]},
            "frequent_destinations": {"type": "text", "placeholder": "e.g., Phoenix, NYC, Dallas"},
            "tsa_precheck": {"type": "boolean"},
        },
    },
    "work_style": {
        "label": "Work Style",
        "fields": {
            "peak_hours": {"type": "select", "options": [
                "Early morning (5-8am)", "Morning (8-11am)",
                "Midday (11am-2pm)", "Afternoon (2-5pm)", "Evening (5-8pm)"]},
            "deep_work_preference": {"type": "select", "options": [
                "Morning block", "Afternoon block", "Varies by day"]},
            "meeting_preference": {"type": "select", "options": [
                "Morning meetings", "Afternoon meetings",
                "Batched on specific days", "As needed"]},
            "communication_style": {"type": "select", "options": [
                "Email first", "Call first", "Text first", "Depends on person"]},
            "briefing_time": {"type": "select", "options": [
                "6:00 AM", "7:00 AM", "8:00 AM", "9:00 AM"]},
            "end_of_day": {"type": "select", "options": [
                "3:00 PM", "4:00 PM", "5:00 PM", "6:00 PM", "7:00 PM"]},
        },
    },
    "personal": {
        "label": "Personal Context",
        "fields": {
            "family_commitments": {"type": "text",
                "placeholder": "e.g., Kids pickup at 3:30, soccer practice Tuesdays"},
            "fitness_schedule": {"type": "text",
                "placeholder": "e.g., Gym MWF 6am, yoga Saturday 9am"},
            "commute": {"type": "text",
                "placeholder": "e.g., 25 min drive, take I-215"},
            "timezone": {"type": "text", "placeholder": "e.g., America/Los_Angeles"},
            "do_not_disturb": {"type": "text",
                "placeholder": "e.g., After 8pm, Sunday mornings"},
        },
    },
}


# ══════════════════════════════════════════════════════════════
# LIFESTYLE INTELLIGENCE ENGINE
# ══════════════════════════════════════════════════════════════

class LifestyleIntelligence:
    """The AI that knows your life and adapts to it."""

    # ── Preferences ──

    def set_preferences(self, owner_id: str, category: str,
                         preferences: dict) -> dict:
        """Save user preferences for a category."""
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO lifestyle_preferences
                    (owner_id, category, preferences, updated_at)
                VALUES (?,?,?,?)
            """, (owner_id, category, json.dumps(preferences),
                  datetime.now().isoformat()))
        return {"saved": True, "category": category}

    def get_preferences(self, owner_id: str, category: str = None) -> dict:
        """Get preferences, optionally filtered by category."""
        with get_db() as db:
            if category:
                row = db.execute(
                    "SELECT preferences FROM lifestyle_preferences WHERE owner_id=? AND category=?",
                    (owner_id, category)).fetchone()
                if row:
                    return json.loads(dict(row)["preferences"])
                return {}
            else:
                rows = db.execute(
                    "SELECT category, preferences FROM lifestyle_preferences WHERE owner_id=?",
                    (owner_id,)).fetchall()
                return {dict(r)["category"]: json.loads(dict(r)["preferences"]) for r in rows}

    def get_preference_schema(self) -> dict:
        return PREFERENCE_CATEGORIES

    # ── Weekly Rhythm ──

    def set_day_rhythm(self, owner_id: str, day: str, rhythm: dict) -> dict:
        """Customize the rhythm for a specific day."""
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO weekly_rhythms
                    (owner_id, day_of_week, rhythm)
                VALUES (?,?,?)
            """, (owner_id, day.lower(), json.dumps(rhythm)))
        return {"saved": True, "day": day}

    def get_week_rhythm(self, owner_id: str) -> dict:
        """Get the full week rhythm (custom + defaults)."""
        with get_db() as db:
            rows = db.execute(
                "SELECT day_of_week, rhythm FROM weekly_rhythms WHERE owner_id=?",
                (owner_id,)).fetchall()
        custom = {dict(r)["day_of_week"]: json.loads(dict(r)["rhythm"]) for r in rows}

        # Merge custom over defaults
        full_week = {}
        for day, default in DEFAULT_WEEK_RHYTHM.items():
            if day in custom:
                full_week[day] = {**default, **custom[day]}
            else:
                full_week[day] = default
        return full_week

    def get_today_rhythm(self, owner_id: str) -> dict:
        """Get today's rhythm."""
        day_name = datetime.now().strftime("%A").lower()
        week = self.get_week_rhythm(owner_id)
        return {"day": day_name, "rhythm": week.get(day_name, {})}

    # ── Pattern Learning ──

    def log_activity_pattern(self, owner_id: str, activity_type: str,
                              day_of_week: str = "", hour: int = -1,
                              context: dict = None) -> dict:
        """Log when a user does things — builds pattern data over time."""
        if not day_of_week:
            day_of_week = datetime.now().strftime("%A").lower()
        if hour < 0:
            hour = datetime.now().hour

        pid = f"pat_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO activity_patterns
                    (id, owner_id, activity_type, day_of_week, hour, context)
                VALUES (?,?,?,?,?,?)
            """, (pid, owner_id, activity_type, day_of_week, hour,
                  json.dumps(context or {})))
        return {"logged": True}

    def get_patterns(self, owner_id: str) -> dict:
        """Analyze accumulated patterns — what does this person do when?"""
        with get_db() as db:
            # Activity by day of week
            by_day = db.execute("""
                SELECT day_of_week, activity_type, COUNT(*) as freq
                FROM activity_patterns WHERE owner_id=?
                GROUP BY day_of_week, activity_type
                ORDER BY freq DESC
            """, (owner_id,)).fetchall()

            # Activity by hour
            by_hour = db.execute("""
                SELECT hour, activity_type, COUNT(*) as freq
                FROM activity_patterns WHERE owner_id=?
                GROUP BY hour, activity_type
                ORDER BY freq DESC
            """, (owner_id,)).fetchall()

            # Most common activities
            top_activities = db.execute("""
                SELECT activity_type, COUNT(*) as freq
                FROM activity_patterns WHERE owner_id=?
                GROUP BY activity_type ORDER BY freq DESC LIMIT 10
            """, (owner_id,)).fetchall()

        return {
            "by_day": [dict(r) for r in by_day],
            "by_hour": [dict(r) for r in by_hour],
            "top_activities": [dict(r) for r in top_activities],
        }

    # ── Contextual Briefing ──

    def build_contextual_briefing(self, owner_id: str) -> dict:
        """Build a briefing that adapts to the day, time, and person."""
        now = datetime.now()
        day_name = now.strftime("%A").lower()
        hour = now.hour
        today_rhythm = self.get_today_rhythm(owner_id)
        prefs = self.get_preferences(owner_id)
        work_prefs = prefs.get("work_style", {})
        personal = prefs.get("personal", {})

        # Determine briefing context
        context = {
            "day": day_name,
            "day_label": today_rhythm["rhythm"].get("label", day_name.title()),
            "focus": today_rhythm["rhythm"].get("focus", "general"),
            "emphasis": today_rhythm["rhythm"].get("briefing_emphasis", []),
            "time_of_day": "morning" if hour < 12 else "afternoon" if hour < 17 else "evening",
            "blocks": today_rhythm["rhythm"].get("default_blocks", []),
        }

        # Add personal context
        if personal.get("family_commitments"):
            context["personal_reminders"] = personal["family_commitments"]
        if personal.get("fitness_schedule"):
            context["fitness"] = personal["fitness_schedule"]
        if personal.get("commute"):
            context["commute"] = personal["commute"]

        # Build AI instruction overlay
        ai_overlay = self._build_ai_overlay(context, prefs)

        return {
            "context": context,
            "ai_overlay": ai_overlay,
            "preferences_set": list(prefs.keys()),
        }

    def _build_ai_overlay(self, context: dict, prefs: dict) -> str:
        """Build additional AI instructions based on lifestyle context."""
        parts = [
            f"Today is {context['day'].title()} — {context.get('day_label', '')}.",
            f"Today's focus: {context.get('focus', 'general')}.",
        ]

        emphasis = context.get("emphasis", [])
        if "pipeline_review" in emphasis:
            parts.append("Emphasize deal pipeline, stale deals, and follow-ups in the briefing.")
        if "client_prep" in emphasis:
            parts.append("Focus on upcoming meetings and client preparation.")
        if "dinner_suggestions" in emphasis:
            dining = prefs.get("dining", {})
            if dining:
                parts.append(f"User prefers {dining.get('cuisine_favorites', 'no preference')} "
                           f"restaurants, {dining.get('price_range', '$$')} range, "
                           f"for client dinners: {dining.get('client_dinner_style', 'business appropriate')}.")
        if "week_summary" in emphasis:
            parts.append("Provide a week-in-review summary and highlight wins.")
        if "next_week_preview" in emphasis:
            parts.append("Preview next week's key events, deadlines, and priorities.")
        if "invoicing" in emphasis:
            parts.append("Remind about any unpaid invoices or expenses to log.")
        if "urgent_only" in emphasis:
            parts.append("Weekend mode — only surface truly urgent items.")

        if context.get("personal_reminders"):
            parts.append(f"Personal commitments: {context['personal_reminders']}")

        if context.get("blocks"):
            block_str = ", ".join(f"{b['time']} {b['activity']}" for b in context["blocks"][:3])
            parts.append(f"Suggested schedule: {block_str}")

        return "\n".join(parts)

    # ── Feedback Loop ──

    def rate_suggestion(self, owner_id: str, suggestion_type: str,
                         suggestion_id: str, rating: int,
                         feedback: str = "") -> dict:
        """Rate a suggestion (1-5) — feeds back into personalization."""
        with get_db() as db:
            db.execute("""
                INSERT INTO lifestyle_feedback
                    (id, owner_id, suggestion_type, suggestion_id, rating, feedback)
                VALUES (?,?,?,?,?,?)
            """, (f"fb_{uuid.uuid4().hex[:8]}", owner_id, suggestion_type,
                  suggestion_id, rating, feedback))
        return {"rated": True, "rating": rating}

    def get_feedback_summary(self, owner_id: str) -> dict:
        """Summarize what the user likes and doesn't like."""
        with get_db() as db:
            # Average rating by type
            by_type = db.execute("""
                SELECT suggestion_type, AVG(rating) as avg_rating, COUNT(*) as count
                FROM lifestyle_feedback WHERE owner_id=?
                GROUP BY suggestion_type ORDER BY avg_rating DESC
            """, (owner_id,)).fetchall()

            # Recent low ratings (things to improve)
            low_rated = db.execute("""
                SELECT suggestion_type, feedback, rating, created_at
                FROM lifestyle_feedback WHERE owner_id=? AND rating <= 2
                ORDER BY created_at DESC LIMIT 10
            """, (owner_id,)).fetchall()

        return {
            "by_type": [dict(r) for r in by_type],
            "needs_improvement": [dict(r) for r in low_rated],
        }

    # ── Proactive Life Suggestions ──

    def get_proactive_suggestions(self, owner_id: str) -> list:
        """Generate proactive suggestions based on context + preferences."""
        suggestions = []
        now = datetime.now()
        day = now.strftime("%A").lower()
        prefs = self.get_preferences(owner_id)
        dining = prefs.get("dining", {})
        travel = prefs.get("travel", {})
        personal = prefs.get("personal", {})

        # Wednesday dinner suggestion
        if day == "wednesday" and dining:
            style = dining.get("client_dinner_style", "")
            cuisines = dining.get("cuisine_favorites", [])
            if cuisines:
                suggestions.append({
                    "type": "dinner_suggestion",
                    "icon": "🍽️",
                    "message": f"Client dinner tonight? Based on your preferences, "
                              f"you enjoy {', '.join(cuisines[:2])} restaurants"
                              + (f" — {style}" if style else "") + ".",
                    "action": "Would you like restaurant suggestions near your meeting?",
                })

        # Friday wrap-up
        if day == "friday":
            suggestions.append({
                "type": "week_wrap",
                "icon": "📊",
                "message": "It's Friday — time for your weekly wrap-up. "
                          "Should I generate your week-in-review report?",
                "action": "Generate week summary",
            })

        # Sunday prep
        if day == "sunday" and now.hour >= 17:
            suggestions.append({
                "type": "week_prep",
                "icon": "📅",
                "message": "Ready to preview your week? I can pull together "
                          "Monday's pipeline, this week's meetings, and key deadlines.",
                "action": "Preview next week",
            })

        # Travel day awareness
        if travel.get("frequent_destinations"):
            suggestions.append({
                "type": "travel_prep",
                "icon": "✈️",
                "message": f"Frequent destinations: {travel['frequent_destinations']}. "
                          f"Preferences: {travel.get('seat_preference', 'no preference')} seat, "
                          f"{travel.get('flight_time', 'no preference')} flights.",
                "action": "Check upcoming travel",
            })

        # Personal reminders
        if personal.get("family_commitments"):
            suggestions.append({
                "type": "personal_reminder",
                "icon": "👨‍👧‍👦",
                "message": f"Don't forget: {personal['family_commitments']}",
            })

        if personal.get("fitness_schedule"):
            fitness = personal["fitness_schedule"].lower()
            day_short = day[:3]
            if day_short in fitness.lower():
                suggestions.append({
                    "type": "fitness_reminder",
                    "icon": "💪",
                    "message": f"Workout day: {personal['fitness_schedule']}",
                })

        return suggestions
