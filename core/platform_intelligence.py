# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Platform Intelligence — The platform that fixes itself.

Two systems working together:

1. SELF-HEALING MONITOR
   - Watches every API call for errors, slow responses, missing routes
   - Tracks which features users TRY to use but can't (gap detection)
   - Monitors provider failures, database issues, and performance degradation
   - Aggregates into a health dashboard with specific recommendations
   - Collaborates with the admin in real-time: "I found 3 issues. Here's
     what I think we should do."

2. COLLECTIVE FEEDBACK ENGINE
   - Aggregates user feedback (thumbs down, comments, reports)
   - Clusters similar feedback into themes using pattern matching
   - Detects when N+ users report the same problem
   - Generates specific, actionable recommendations
   - Prioritizes by impact (how many users × severity)
   - Presents to admin: "47 users reported slow responses on the
     Sales Coach. Root cause: the RFP analysis prompt is 4000 tokens.
     Recommendation: chunk the RFP and summarize first."

Together: the platform watches itself, listens to users, figures out
what's wrong, proposes fixes, and with admin approval, can apply them.
"""

import json
import uuid
import re
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from .database import get_db

logger = logging.getLogger("MyTeam360.platform_intelligence")


# ══════════════════════════════════════════════════════════════
# 1. SELF-HEALING MONITOR
# ══════════════════════════════════════════════════════════════

class PlatformHealthMonitor:
    """Watches everything. Detects gaps. Recommends fixes.

    What it tracks:
      - API errors (500s, 404s, timeouts)
      - Slow endpoints (>3s response time)
      - Provider failures (which AI providers are failing)
      - Feature attempts on disabled features (gap detection)
      - Database connection issues
      - Rate limit hits
      - Search queries with no results (what users want but we don't have)
      - Uncaught exceptions with stack traces
    """

    def __init__(self):
        self._errors = defaultdict(list)       # endpoint → [error records]
        self._slow_endpoints = defaultdict(list)  # endpoint → [response times]
        self._feature_gaps = defaultdict(int)   # feature_name → attempt count
        self._search_misses = defaultdict(int)  # query → miss count
        self._provider_errors = defaultdict(int)  # provider → error count
        self._start_time = time.time()

    def record_error(self, endpoint: str, status_code: int, error: str,
                     user_id: str = "", duration_ms: float = 0):
        """Record an API error."""
        self._errors[endpoint].append({
            "status": status_code,
            "error": error[:200],
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "duration_ms": duration_ms,
        })
        # Keep last 100 per endpoint
        if len(self._errors[endpoint]) > 100:
            self._errors[endpoint] = self._errors[endpoint][-100:]

        # Persist critical errors
        if status_code >= 500:
            self._persist_error(endpoint, status_code, error)

    def record_slow_endpoint(self, endpoint: str, duration_ms: float):
        """Record a slow response."""
        self._slow_endpoints[endpoint].append({
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat(),
        })
        if len(self._slow_endpoints[endpoint]) > 50:
            self._slow_endpoints[endpoint] = self._slow_endpoints[endpoint][-50:]

    def record_feature_gap(self, feature: str, user_id: str = ""):
        """User tried a disabled feature — this is demand signal."""
        self._feature_gaps[feature] += 1
        try:
            with get_db() as db:
                db.execute("""
                    INSERT INTO platform_health_events
                        (id, event_type, detail, count_value)
                    VALUES (?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET count_value=count_value+1
                """, (f"gap_{feature}", "feature_gap", feature, 1))
        except:
            pass

    def record_search_miss(self, query: str):
        """User searched for something we don't have."""
        normalized = query.lower().strip()
        self._search_misses[normalized] += 1
        try:
            with get_db() as db:
                db.execute("""
                    INSERT INTO platform_health_events
                        (id, event_type, detail, count_value)
                    VALUES (?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET count_value=count_value+1
                """, (f"miss_{normalized[:50]}", "search_miss", normalized, 1))
        except:
            pass

    def record_provider_error(self, provider: str, error: str = ""):
        self._provider_errors[provider] += 1

    def get_health_dashboard(self) -> dict:
        """Complete platform health overview."""
        uptime_seconds = int(time.time() - self._start_time)

        # Top errors by frequency
        error_summary = {}
        for endpoint, errors in self._errors.items():
            if errors:
                error_summary[endpoint] = {
                    "count": len(errors),
                    "last_error": errors[-1]["error"],
                    "last_status": errors[-1]["status"],
                }

        # Slow endpoints
        slow_summary = {}
        for endpoint, times in self._slow_endpoints.items():
            if times:
                durations = [t["duration_ms"] for t in times]
                slow_summary[endpoint] = {
                    "count": len(times),
                    "avg_ms": round(sum(durations) / len(durations)),
                    "max_ms": round(max(durations)),
                    "p95_ms": round(sorted(durations)[int(len(durations) * 0.95)] if len(durations) >= 5 else max(durations)),
                }

        # Feature gaps (demand signals)
        gaps = sorted(self._feature_gaps.items(), key=lambda x: -x[1])

        # Search misses
        misses = sorted(self._search_misses.items(), key=lambda x: -x[1])[:20]

        return {
            "uptime_seconds": uptime_seconds,
            "uptime_human": f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m",
            "errors": dict(sorted(error_summary.items(), key=lambda x: -x[1]["count"])[:10]),
            "slow_endpoints": dict(sorted(slow_summary.items(), key=lambda x: -x[1]["avg_ms"])[:10]),
            "feature_gaps": gaps[:10],
            "search_misses": misses,
            "provider_errors": dict(self._provider_errors),
        }

    def generate_recommendations(self) -> list:
        """AI-generated recommendations based on platform health."""
        recs = []
        dashboard = self.get_health_dashboard()

        # Recommend based on errors
        for endpoint, info in dashboard["errors"].items():
            if info["count"] >= 5:
                recs.append({
                    "priority": "critical" if info["last_status"] >= 500 else "high",
                    "category": "error",
                    "title": f"Recurring errors on {endpoint}",
                    "detail": f"{info['count']} errors. Last: {info['last_error'][:100]}",
                    "recommendation": f"Investigate {endpoint}. Check for missing data validation, null pointer issues, or provider failures.",
                })

        # Recommend based on slow endpoints
        for endpoint, info in dashboard["slow_endpoints"].items():
            if info["avg_ms"] > 3000:
                recs.append({
                    "priority": "high",
                    "category": "performance",
                    "title": f"Slow endpoint: {endpoint}",
                    "detail": f"Average {info['avg_ms']}ms (p95: {info['p95_ms']}ms) over {info['count']} calls",
                    "recommendation": "Consider: caching, reducing prompt length, switching to a faster model, or pre-computing results.",
                })

        # Recommend based on feature gaps
        for feature, count in dashboard["feature_gaps"]:
            if count >= 3:
                recs.append({
                    "priority": "medium",
                    "category": "feature_gap",
                    "title": f"Users want '{feature}' ({count} attempts)",
                    "detail": f"{count} users tried to use '{feature}' but it's disabled.",
                    "recommendation": f"Consider enabling '{feature}' or adding it to a lower pricing tier. Users are asking for it.",
                })

        # Recommend based on search misses
        for query, count in dashboard["search_misses"]:
            if count >= 3:
                recs.append({
                    "priority": "low",
                    "category": "content_gap",
                    "title": f"Search miss: '{query}' ({count} searches)",
                    "detail": f"{count} users searched for '{query}' with no results.",
                    "recommendation": f"Consider adding content, a profession profile, or documentation for '{query}'.",
                })

        # Recommend based on provider errors
        for provider, count in dashboard["provider_errors"].items():
            if count >= 5:
                recs.append({
                    "priority": "high",
                    "category": "provider",
                    "title": f"Provider issues: {provider} ({count} failures)",
                    "detail": f"{provider} has failed {count} times. Failover may be needed.",
                    "recommendation": f"Check API key validity, rate limits, and billing for {provider}. Consider adjusting failover chain.",
                })

        recs.sort(key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["priority"], 4))
        return recs

    def _persist_error(self, endpoint: str, status: int, error: str):
        try:
            with get_db() as db:
                db.execute("""
                    INSERT INTO platform_health_events
                        (id, event_type, detail, count_value)
                    VALUES (?,?,?,?)
                """, (f"err_{uuid.uuid4().hex[:8]}", "error",
                      json.dumps({"endpoint": endpoint, "status": status, "error": error[:200]}), 1))
        except:
            pass


# ══════════════════════════════════════════════════════════════
# 2. COLLECTIVE FEEDBACK ENGINE
# ══════════════════════════════════════════════════════════════

class CollectiveFeedbackEngine:
    """Aggregates user feedback into actionable themes.

    When 5+ users report the same thing, it becomes a pattern.
    When 20+ users report it, it becomes a priority.
    When 50+ users report it, it's a fire.

    The engine doesn't just count — it clusters similar feedback,
    identifies root causes, and generates specific fix recommendations.
    """

    # Common complaint patterns and their categories
    COMPLAINT_PATTERNS = {
        "slow_response": {
            "patterns": [r"slow", r"takes? (?:too )?long", r"waiting", r"timeout", r"loading"],
            "category": "performance",
        },
        "wrong_answer": {
            "patterns": [r"wrong", r"incorrect", r"inaccurate", r"hallucin", r"made up", r"false"],
            "category": "accuracy",
        },
        "confusing_ui": {
            "patterns": [r"confus", r"can['\u2019]?t find", r"where is", r"how do i", r"not intuitive"],
            "category": "ux",
        },
        "feature_request": {
            "patterns": [r"wish", r"would be nice", r"please add", r"feature request", r"can you add", r"should have"],
            "category": "feature_request",
        },
        "formatting": {
            "patterns": [r"format", r"layout", r"too long", r"too short", r"bullet", r"structure"],
            "category": "output_quality",
        },
        "tone_issue": {
            "patterns": [r"too formal", r"too casual", r"doesn['\u2019]?t sound like", r"tone", r"voice"],
            "category": "voice_learning",
        },
        "missing_knowledge": {
            "patterns": [r"doesn['\u2019]?t know", r"out of date", r"outdated", r"doesn['\u2019]?t understand"],
            "category": "knowledge",
        },
        "cost_concern": {
            "patterns": [r"expensive", r"too much", r"cost", r"pricing", r"cheaper", r"afford"],
            "category": "pricing",
        },
    }

    def __init__(self):
        self._compiled = {}
        for name, data in self.COMPLAINT_PATTERNS.items():
            self._compiled[name] = [re.compile(p, re.I) for p in data["patterns"]]

    def classify_feedback(self, text: str) -> list:
        """Classify a feedback comment into themes."""
        matches = []
        for name, patterns in self._compiled.items():
            for p in patterns:
                if p.search(text):
                    matches.append({
                        "theme": name,
                        "category": self.COMPLAINT_PATTERNS[name]["category"],
                    })
                    break
        return matches if matches else [{"theme": "general", "category": "other"}]

    def analyze_feedback_trends(self, days: int = 30) -> dict:
        """Analyze all feedback from the last N days and find patterns."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with get_db() as db:
            # Get all negative feedback with comments
            rows = db.execute("""
                SELECT rf.*, a.name as space_name
                FROM response_feedback rf
                LEFT JOIN agents a ON rf.agent_id=a.id
                WHERE rf.created_at > ? AND rf.rating IN ('down','1','2')
                ORDER BY rf.created_at DESC
            """, (cutoff,)).fetchall()

        if not rows:
            return {"period_days": days, "total_negative": 0, "themes": [],
                    "message": "No negative feedback in this period. Great!"}

        # Classify each piece of feedback
        theme_counts = defaultdict(lambda: {"count": 0, "examples": [], "spaces": set(), "models": set()})

        for row in rows:
            r = dict(row)
            comment = r.get("comment", "")
            classifications = self.classify_feedback(comment) if comment else [{"theme": "no_comment", "category": "other"}]

            for cls in classifications:
                theme = cls["theme"]
                tc = theme_counts[theme]
                tc["count"] += 1
                tc["category"] = cls["category"]
                if comment and len(tc["examples"]) < 5:
                    tc["examples"].append(comment[:100])
                if r.get("space_name"):
                    tc["spaces"].add(r["space_name"])
                if r.get("model"):
                    tc["models"].add(r["model"])

        # Convert sets to lists and sort by count
        themes = []
        for theme, data in sorted(theme_counts.items(), key=lambda x: -x[1]["count"]):
            themes.append({
                "theme": theme,
                "category": data["category"],
                "count": data["count"],
                "affected_spaces": list(data["spaces"])[:5],
                "affected_models": list(data["models"])[:3],
                "examples": data["examples"],
                "severity": "critical" if data["count"] >= 50 else "high" if data["count"] >= 20 else "medium" if data["count"] >= 5 else "low",
            })

        return {
            "period_days": days,
            "total_negative": len(rows),
            "themes": themes,
            "action_needed": [t for t in themes if t["severity"] in ("critical", "high")],
        }

    def generate_fix_recommendations(self, days: int = 30) -> list:
        """Generate specific fix recommendations from feedback patterns."""
        trends = self.analyze_feedback_trends(days)
        recs = []

        for theme in trends.get("themes", []):
            if theme["count"] < 3:
                continue

            rec = {
                "theme": theme["theme"],
                "category": theme["category"],
                "affected_users": theme["count"],
                "severity": theme["severity"],
                "affected_spaces": theme["affected_spaces"],
            }

            # Generate specific recommendations per category
            cat = theme["category"]
            if cat == "performance":
                rec["recommendation"] = (
                    f"{theme['count']} users report slow responses. "
                    f"Check: 1) Prompt length in affected Spaces ({', '.join(theme['affected_spaces'][:3])}). "
                    f"2) Model selection — switch heavy prompts to a faster model. "
                    f"3) Add response caching for repeated queries."
                )
            elif cat == "accuracy":
                rec["recommendation"] = (
                    f"{theme['count']} users report inaccurate responses. "
                    f"Check: 1) Space instructions may need more specific guardrails. "
                    f"2) Knowledge base may need updating. "
                    f"3) Consider enabling Confidence Scoring to flag low-confidence responses."
                )
            elif cat == "ux":
                rec["recommendation"] = (
                    f"{theme['count']} users find the interface confusing. "
                    f"Common complaints: {'; '.join(theme['examples'][:3])}. "
                    f"Consider: tooltips, onboarding walkthrough, or simplified navigation."
                )
            elif cat == "voice_learning":
                rec["recommendation"] = (
                    f"{theme['count']} users say the tone doesn't match. "
                    f"Check: Voice Learning may need more samples, or the Space instructions "
                    f"may be overriding the learned voice. Review affected Spaces."
                )
            elif cat == "feature_request":
                rec["recommendation"] = (
                    f"{theme['count']} users requesting features. "
                    f"Top requests: {'; '.join(theme['examples'][:3])}. "
                    f"Evaluate for roadmap inclusion."
                )
            elif cat == "pricing":
                rec["recommendation"] = (
                    f"{theme['count']} users mention pricing concerns. "
                    f"Consider: sponsored tier promotion, annual billing discount emphasis, "
                    f"or reviewing feature allocation across tiers."
                )
            elif cat == "knowledge":
                rec["recommendation"] = (
                    f"{theme['count']} users say the AI lacks knowledge. "
                    f"Consider: enabling web search tool in Spaces, updating knowledge base, "
                    f"or adding domain-specific context to Space instructions."
                )
            else:
                rec["recommendation"] = (
                    f"{theme['count']} users reported issues in this category. "
                    f"Review examples: {'; '.join(theme['examples'][:3])}"
                )

            recs.append(rec)

        recs.sort(key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["severity"], 4))
        return recs


# ══════════════════════════════════════════════════════════════
# 3. ADMIN COLLABORATION CHANNEL
# ══════════════════════════════════════════════════════════════

class AdminCollaborationChannel:
    """The platform talks directly to the admin about what it found.

    This is the "partner" interface — the platform presents:
      - Health issues it detected
      - User feedback patterns it identified
      - Specific recommendations with reasoning
      - Proposed changes (code, configuration, or content)

    The admin reviews, approves or modifies, and the platform applies.
    """

    def __init__(self, health_monitor: PlatformHealthMonitor = None,
                 feedback_engine: CollectiveFeedbackEngine = None):
        self.health = health_monitor
        self.feedback = feedback_engine

    def generate_briefing(self) -> dict:
        """Generate a comprehensive briefing for the admin.
        This is the 'Hey Jeremy, here's what I found' report."""

        briefing = {
            "generated_at": datetime.now().isoformat(),
            "greeting": "",  # filled below
            "sections": [],
        }

        # Health recommendations
        health_recs = []
        if self.health:
            health_recs = self.health.generate_recommendations()
            dashboard = self.health.get_health_dashboard()
            briefing["uptime"] = dashboard.get("uptime_human", "")

        # Feedback recommendations
        feedback_recs = []
        if self.feedback:
            feedback_recs = self.feedback.generate_fix_recommendations(days=7)
            trends = self.feedback.analyze_feedback_trends(days=7)

        # Critical issues first
        critical = [r for r in health_recs if r["priority"] == "critical"]
        if critical:
            briefing["sections"].append({
                "title": "🚨 Critical Issues",
                "items": critical,
            })

        # User feedback patterns
        high_feedback = [r for r in feedback_recs if r["severity"] in ("critical", "high")]
        if high_feedback:
            briefing["sections"].append({
                "title": "📢 User Feedback Patterns",
                "summary": f"{trends.get('total_negative', 0)} negative ratings in the last 7 days",
                "items": high_feedback,
            })

        # Performance issues
        perf = [r for r in health_recs if r["category"] == "performance"]
        if perf:
            briefing["sections"].append({
                "title": "⚡ Performance",
                "items": perf,
            })

        # Feature gaps (what users want)
        gaps = [r for r in health_recs if r["category"] in ("feature_gap", "content_gap")]
        if gaps:
            briefing["sections"].append({
                "title": "💡 What Users Want",
                "items": gaps,
            })

        # Lower priority
        remaining = [r for r in health_recs + feedback_recs
                     if r not in critical and r not in high_feedback
                     and r not in perf and r not in gaps]
        if remaining:
            briefing["sections"].append({
                "title": "📋 Other Items",
                "items": remaining[:10],
            })

        # Generate greeting
        total_issues = len(health_recs) + len(feedback_recs)
        critical_count = len(critical)
        if critical_count > 0:
            briefing["greeting"] = f"Jeremy, we have {critical_count} critical issue(s) that need attention right now, plus {total_issues - critical_count} other items."
        elif total_issues > 0:
            briefing["greeting"] = f"Jeremy, things are looking good overall. I found {total_issues} item(s) worth reviewing when you have a moment."
        else:
            briefing["greeting"] = "Jeremy, everything looks healthy. No issues detected, no user complaints. All systems running well."

        return briefing

    def create_change_proposal(self, title: str, description: str,
                                change_type: str, proposed_changes: dict,
                                source: str = "platform_intelligence") -> dict:
        """Platform proposes a change for admin approval."""
        pid = f"prop_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO change_proposals
                    (id, title, description, change_type, proposed_changes,
                     source, status)
                VALUES (?,?,?,?,?,?,?)
            """, (pid, title, description, change_type,
                  json.dumps(proposed_changes), source, "pending"))
        return {"id": pid, "title": title, "status": "pending"}

    def approve_proposal(self, proposal_id: str, admin_id: str,
                          admin_notes: str = "") -> dict:
        """Admin approves a change proposal."""
        with get_db() as db:
            db.execute("""
                UPDATE change_proposals
                SET status='approved', reviewed_by=?, review_notes=?, reviewed_at=?
                WHERE id=?
            """, (admin_id, admin_notes, datetime.now().isoformat(), proposal_id))
            row = db.execute("SELECT * FROM change_proposals WHERE id=?",
                            (proposal_id,)).fetchone()
        if not row:
            return {"error": "Proposal not found"}
        d = dict(row)
        d["proposed_changes"] = json.loads(d.get("proposed_changes", "{}"))
        return d

    def reject_proposal(self, proposal_id: str, admin_id: str,
                         reason: str = "") -> dict:
        with get_db() as db:
            db.execute("""
                UPDATE change_proposals
                SET status='rejected', reviewed_by=?, review_notes=?, reviewed_at=?
                WHERE id=?
            """, (admin_id, reason, datetime.now().isoformat(), proposal_id))
        return {"id": proposal_id, "status": "rejected"}

    def list_proposals(self, status: str = None) -> list:
        with get_db() as db:
            if status:
                rows = db.execute(
                    "SELECT * FROM change_proposals WHERE status=? ORDER BY created_at DESC",
                    (status,)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM change_proposals ORDER BY created_at DESC LIMIT 50"
                ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["proposed_changes"] = json.loads(d.get("proposed_changes", "{}"))
            result.append(d)
        return result
