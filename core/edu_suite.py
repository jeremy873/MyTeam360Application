# MyTeam360 — Education Suite
# Copyright 2026 Praxis Holdings LLC. All rights reserved.
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET

"""
Education Suite — Parent Dashboard, Curriculum, Progress Reports, Gamification.
"""

import json, uuid, logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.edu_suite")

# ── PARENT DASHBOARD ──

class ParentDashboard:
    def link_parent(self, student_id, parent_email, parent_name="", relationship="parent"):
        lid = f"plink_{uuid.uuid4().hex[:10]}"
        code = uuid.uuid4().hex[:8]
        with get_db() as db:
            db.execute("INSERT INTO parent_links (id,student_id,parent_email,parent_name,relationship,status,invite_code) VALUES (?,?,?,?,?,?,?)",
                (lid, student_id, parent_email, parent_name, relationship, "pending", code))
        return {"id": lid, "status": "pending", "invite_code": code}

    def accept_link(self, invite_code, parent_user_id):
        with get_db() as db:
            row = db.execute("SELECT * FROM parent_links WHERE invite_code=? AND status='pending'", (invite_code,)).fetchone()
            if not row: return {"error": "Invalid invite code"}
            db.execute("UPDATE parent_links SET parent_user_id=?, status='active' WHERE id=?", (parent_user_id, dict(row)["id"]))
        return {"linked": True, "student_id": dict(row)["student_id"]}

    def get_children(self, parent_user_id):
        with get_db() as db:
            rows = db.execute("SELECT pl.*, u.display_name as student_name FROM parent_links pl LEFT JOIN users u ON pl.student_id=u.id WHERE pl.parent_user_id=? AND pl.status='active'", (parent_user_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_overview(self, student_id):
        with get_db() as db:
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            sessions = db.execute("SELECT COUNT(*) as c FROM conversations WHERE user_id=?", (student_id,)).fetchone()
            sessions_week = db.execute("SELECT COUNT(*) as c FROM conversations WHERE user_id=? AND created_at>=?", (student_id, week_ago)).fetchone()
            subjects = db.execute("SELECT a.name as subject, COUNT(c.id) as count, MAX(c.updated_at) as last_studied FROM conversations c JOIN agents a ON c.agent_id=a.id WHERE c.user_id=? GROUP BY a.name ORDER BY count DESC LIMIT 10", (student_id,)).fetchall()
            violations = db.execute("SELECT COUNT(*) as c FROM user_strikes WHERE user_id=?", (student_id,)).fetchone()
            gamer = db.execute("SELECT * FROM student_gamification WHERE student_id=?", (student_id,)).fetchone()
        return {
            "student_id": student_id,
            "total_sessions": dict(sessions)["c"],
            "sessions_this_week": dict(sessions_week)["c"],
            "subjects": [dict(s) for s in subjects],
            "safety": {"violations": dict(violations)["c"], "status": "clean" if dict(violations)["c"]==0 else "review_needed", "content_filtered": True},
            "gamification": dict(gamer) if gamer else {"xp":0,"level":1,"streak_days":0},
        }

    def set_time_limit(self, student_id, parent_user_id, daily_minutes):
        with get_db() as db:
            db.execute("INSERT OR REPLACE INTO student_time_limits (student_id,parent_user_id,daily_minutes) VALUES (?,?,?)",
                (student_id, parent_user_id, daily_minutes))
        return {"set": True, "daily_minutes": daily_minutes}

    def get_time_limit(self, student_id):
        with get_db() as db:
            row = db.execute("SELECT * FROM student_time_limits WHERE student_id=?", (student_id,)).fetchone()
        return dict(row) if row else {"daily_minutes": 0, "unlimited": True}


# ── CURRICULUM ALIGNMENT ──

class CurriculumManager:
    STANDARDS = {
        "common_core_math": {"name": "Common Core — Mathematics", "grades": "K-12",
            "domains": {"K": ["Counting & Cardinality","Operations & Algebraic Thinking","Number & Operations in Base Ten","Measurement & Data","Geometry"],
                "1-2": ["Operations & Algebraic Thinking","Number & Operations in Base Ten","Measurement & Data","Geometry"],
                "3-5": ["Operations & Algebraic Thinking","Number & Operations in Base Ten","Number & Operations—Fractions","Measurement & Data","Geometry"],
                "6-8": ["Ratios & Proportional Relationships","The Number System","Expressions & Equations","Geometry","Statistics & Probability"],
                "9-12": ["Number & Quantity","Algebra","Functions","Geometry","Statistics & Probability","Modeling"]}},
        "common_core_ela": {"name": "Common Core — ELA", "grades": "K-12",
            "domains": {"K-5": ["Reading Literature","Reading Informational Text","Foundational Skills","Writing","Speaking & Listening","Language"],
                "6-12": ["Reading Literature","Reading Informational Text","Writing","Speaking & Listening","Language"]}},
        "ngss": {"name": "Next Generation Science Standards", "grades": "K-12",
            "domains": {"K-5": ["Physical Science","Life Science","Earth & Space Science","Engineering Design"],
                "6-8": ["Physical Science","Life Science","Earth & Space Science","Engineering Design"],
                "9-12": ["Physical Science","Life Science","Earth & Space Science","Engineering Design"]}},
        "ap": {"name": "Advanced Placement", "grades": "9-12",
            "subjects": ["AP Art History","AP Biology","AP Calculus AB","AP Calculus BC","AP Chemistry",
                "AP Computer Science A","AP Computer Science Principles","AP English Language","AP English Literature",
                "AP Environmental Science","AP European History","AP Government & Politics","AP Human Geography",
                "AP Macroeconomics","AP Microeconomics","AP Physics 1","AP Physics 2","AP Physics C: E&M",
                "AP Physics C: Mechanics","AP Psychology","AP Spanish Language","AP Statistics","AP US History","AP World History"]},
        "ib": {"name": "International Baccalaureate", "grades": "11-12",
            "groups": ["Studies in Language and Literature","Language Acquisition","Individuals and Societies","Sciences","Mathematics","The Arts","Theory of Knowledge","Extended Essay","CAS"]},
    }

    def get_standards(self):
        return {k: {"name": v["name"], "grades": v["grades"]} for k, v in self.STANDARDS.items()}

    def get_standard_detail(self, standard_id):
        return self.STANDARDS.get(standard_id, {"error": "Not found"})

    def get_domains_for_grade(self, standard_id, grade):
        std = self.STANDARDS.get(standard_id, {})
        domains = std.get("domains", std.get("subjects", std.get("groups", {})))
        if isinstance(domains, list): return domains
        for k, v in (domains if isinstance(domains, dict) else {}).items():
            if grade in k or k in grade: return v
        return []

    def tag_interaction(self, student_id, conversation_id, standard_id, domain, topic="", mastery_level="practicing"):
        tid = f"tag_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("INSERT INTO curriculum_tags (id,student_id,conversation_id,standard_id,domain,topic,mastery_level) VALUES (?,?,?,?,?,?,?)",
                (tid, student_id, conversation_id, standard_id, domain, topic, mastery_level))
        return {"tagged": True}

    def get_mastery_map(self, student_id, standard_id=""):
        with get_db() as db:
            where, params = ["student_id=?"], [student_id]
            if standard_id: where.append("standard_id=?"); params.append(standard_id)
            rows = db.execute(f"SELECT standard_id, domain, mastery_level, COUNT(*) as interactions, MAX(created_at) as last_practiced FROM curriculum_tags WHERE {' AND '.join(where)} GROUP BY standard_id, domain ORDER BY standard_id, domain", params).fetchall()
        return {"student_id": student_id, "domains": [dict(r) for r in rows]}


# ── PROGRESS REPORTS ──

class ProgressReportGenerator:
    def generate(self, student_id, period="weekly"):
        days = {"weekly":7,"biweekly":14,"monthly":30,"quarterly":90}
        lookback = days.get(period, 7)
        since = (datetime.now() - timedelta(days=lookback)).isoformat()
        with get_db() as db:
            sessions = db.execute("SELECT COUNT(*) as c FROM conversations WHERE user_id=? AND created_at>=?", (student_id, since)).fetchone()
            by_subject = db.execute("SELECT a.name as subject, COUNT(c.id) as sessions, COUNT(DISTINCT DATE(c.created_at)) as days_studied FROM conversations c JOIN agents a ON c.agent_id=a.id WHERE c.user_id=? AND c.created_at>=? GROUP BY a.name ORDER BY sessions DESC", (student_id, since)).fetchall()
            mastery = db.execute("SELECT standard_id, domain, mastery_level, COUNT(*) as count FROM curriculum_tags WHERE student_id=? AND created_at>=? GROUP BY standard_id, domain, mastery_level", (student_id, since)).fetchall()
            gamer = db.execute("SELECT * FROM student_gamification WHERE student_id=?", (student_id,)).fetchone()
        subjects = [dict(s) for s in by_subject]
        gd = dict(gamer) if gamer else {"streak_days":0,"xp":0,"level":1}
        prompt = f"Write an encouraging progress report.\nPeriod: Last {lookback} days\nSessions: {dict(sessions)['c']}\nSubjects: {', '.join(s['subject'] for s in subjects)}\nStreak: {gd['streak_days']} days\nLevel: {gd.get('level',1)}\nTone: Warm, supportive, specific. 3-4 sentences."
        return {
            "student_id": student_id, "period": period, "generated_at": datetime.now().isoformat(),
            "summary": {"total_sessions": dict(sessions)["c"], "subjects_count": len(subjects), "streak": gd["streak_days"]},
            "by_subject": subjects, "mastery": [dict(m) for m in mastery],
            "strengths": [s["subject"] for s in subjects[:3]],
            "gamification": gd, "narrative_prompt": prompt,
        }


# ── STUDY GAMIFICATION ──

LEVELS = [
    {"level":1,"title":"Curious Beginner","xp_required":0},
    {"level":2,"title":"Quick Learner","xp_required":100},
    {"level":3,"title":"Eager Student","xp_required":250},
    {"level":4,"title":"Rising Star","xp_required":500},
    {"level":5,"title":"Knowledge Seeker","xp_required":800},
    {"level":6,"title":"Study Champion","xp_required":1200},
    {"level":7,"title":"Brain Builder","xp_required":1800},
    {"level":8,"title":"Wisdom Warrior","xp_required":2500},
    {"level":9,"title":"Master Scholar","xp_required":3500},
    {"level":10,"title":"Genius Explorer","xp_required":5000},
    {"level":15,"title":"Academic Hero","xp_required":10000},
    {"level":20,"title":"Knowledge Legend","xp_required":20000},
    {"level":25,"title":"Supreme Scholar","xp_required":35000},
    {"level":30,"title":"Enlightened Mind","xp_required":50000},
    {"level":50,"title":"Grandmaster","xp_required":100000},
]

BADGES = {
    "first_question": {"name":"First Question","icon":"🎯","description":"Asked your first question","xp":10},
    "study_streak_3": {"name":"3-Day Streak","icon":"🔥","description":"Studied 3 days in a row","xp":25},
    "study_streak_7": {"name":"Week Warrior","icon":"⚡","description":"7-day study streak","xp":50},
    "study_streak_30": {"name":"Monthly Master","icon":"🏆","description":"30-day study streak","xp":200},
    "math_bronze": {"name":"Math Bronze","icon":"🥉","description":"10 math sessions","xp":30},
    "math_silver": {"name":"Math Silver","icon":"🥈","description":"50 math sessions","xp":75},
    "math_gold": {"name":"Math Gold","icon":"🥇","description":"100 math sessions","xp":150},
    "science_bronze": {"name":"Science Bronze","icon":"🥉","description":"10 science sessions","xp":30},
    "reading_bronze": {"name":"Reading Bronze","icon":"🥉","description":"10 reading sessions","xp":30},
    "writing_champ": {"name":"Writing Champion","icon":"✍️","description":"25 writing sessions","xp":60},
    "night_owl": {"name":"Night Owl","icon":"🦉","description":"Studied after 8 PM","xp":10},
    "early_bird": {"name":"Early Bird","icon":"🐦","description":"Studied before 8 AM","xp":10},
    "explorer": {"name":"Explorer","icon":"🗺️","description":"Studied 5 different subjects","xp":40},
    "marathon": {"name":"Study Marathon","icon":"🏃","description":"2+ hours in one day","xp":50},
    "comeback": {"name":"Comeback Kid","icon":"💪","description":"Returned after 7+ days","xp":20},
}


class StudyGamification:
    def get_profile(self, student_id):
        with get_db() as db:
            row = db.execute("SELECT * FROM student_gamification WHERE student_id=?", (student_id,)).fetchone()
            badges = db.execute("SELECT * FROM student_badges WHERE student_id=? ORDER BY earned_at DESC", (student_id,)).fetchall()
        if not row:
            self._init(student_id)
            return self.get_profile(student_id)
        d = dict(row)
        li = self._level_info(d.get("xp",0))
        return {"student_id": student_id, "xp": d.get("xp",0), "level": li["level"], "title": li["title"],
            "xp_to_next": li["xp_to_next"], "progress_pct": li["progress_pct"],
            "streak_days": d.get("streak_days",0), "longest_streak": d.get("longest_streak",0),
            "total_sessions": d.get("total_sessions",0), "badges": [dict(b) for b in badges], "badge_count": len(badges)}

    def award_xp(self, student_id, amount, reason=""):
        with get_db() as db:
            row = db.execute("SELECT xp,streak_days,longest_streak,last_study_date FROM student_gamification WHERE student_id=?", (student_id,)).fetchone()
            if not row: self._init(student_id); return self.award_xp(student_id, amount, reason)
            d = dict(row)
            old_xp, new_xp = d["xp"], d["xp"] + amount
            today = datetime.now().strftime("%Y-%m-%d")
            last = d.get("last_study_date","")
            streak = d.get("streak_days",0)
            longest = d.get("longest_streak",0)
            if last == today: pass
            elif last == (datetime.now()-timedelta(days=1)).strftime("%Y-%m-%d"): streak += 1
            else: streak = 1
            if streak > longest: longest = streak
            old_lvl = self._level_info(old_xp)["level"]
            new_lvl = self._level_info(new_xp)["level"]
            db.execute("UPDATE student_gamification SET xp=?,streak_days=?,longest_streak=?,last_study_date=?,total_sessions=total_sessions+1 WHERE student_id=?",
                (new_xp, streak, longest, today, student_id))
        result = {"xp_earned": amount, "total_xp": new_xp, "streak": streak}
        if new_lvl > old_lvl:
            li = self._level_info(new_xp)
            result["level_up"] = {"new_level": li["level"], "title": li["title"]}
        self._check_streak_badges(student_id, streak)
        return result

    def award_badge(self, student_id, badge_id):
        if badge_id not in BADGES: return {"error": "Badge not found"}
        badge = BADGES[badge_id]
        with get_db() as db:
            if db.execute("SELECT id FROM student_badges WHERE student_id=? AND badge_id=?", (student_id, badge_id)).fetchone():
                return {"already_earned": True}
            db.execute("INSERT INTO student_badges (id,student_id,badge_id,badge_name,badge_icon,xp_awarded) VALUES (?,?,?,?,?,?)",
                (f"sb_{uuid.uuid4().hex[:8]}", student_id, badge_id, badge["name"], badge["icon"], badge["xp"]))
        return {"badge": badge_id, "name": badge["name"], "icon": badge["icon"], "xp_bonus": badge["xp"]}

    def get_leaderboard(self, limit=20):
        with get_db() as db:
            rows = db.execute("SELECT sg.student_id, u.display_name, sg.xp, sg.streak_days FROM student_gamification sg LEFT JOIN users u ON sg.student_id=u.id ORDER BY sg.xp DESC LIMIT ?", (limit,)).fetchall()
        result = []
        for i, r in enumerate(rows, 1):
            d = dict(r); li = self._level_info(d["xp"])
            result.append({"rank":i,"display_name":d.get("display_name","Student"),"xp":d["xp"],"level":li["level"],"title":li["title"],"streak":d["streak_days"]})
        return result

    def get_available_badges(self): return BADGES

    def _init(self, sid):
        with get_db() as db:
            db.execute("INSERT OR IGNORE INTO student_gamification (student_id,xp,streak_days,longest_streak,total_sessions) VALUES (?,0,0,0,0)", (sid,))

    def _level_info(self, xp):
        current, nxt = LEVELS[0], LEVELS[1] if len(LEVELS)>1 else None
        for i, l in enumerate(LEVELS):
            if xp >= l["xp_required"]: current = l; nxt = LEVELS[i+1] if i+1<len(LEVELS) else None
        to_next = (nxt["xp_required"]-xp) if nxt else 0
        in_lvl = xp - current["xp_required"]
        rng = (nxt["xp_required"]-current["xp_required"]) if nxt else 1
        pct = round(in_lvl/rng*100, 1) if rng>0 else 100
        return {"level":current["level"],"title":current["title"],"xp_to_next":max(to_next,0),"progress_pct":min(pct,100)}

    def _check_streak_badges(self, sid, streak):
        if streak >= 3: self.award_badge(sid, "study_streak_3")
        if streak >= 7: self.award_badge(sid, "study_streak_7")
        if streak >= 30: self.award_badge(sid, "study_streak_30")
