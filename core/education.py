# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# See LICENSE and NOTICE files for full legal terms.
# ═══════════════════════════════════════════════════════════════════

"""
Education Module — K-12 Tutoring Support

Affordable AI tutoring that TEACHES, not just answers:
  - Socratic method — guides students to discover answers themselves
  - Grade-level adaptation — adjusts language and complexity
  - Subject-specific tutors — Math, Science, English, History, etc.
  - Homework helper — explains concepts, doesn't just give answers
  - Study guide generator — creates review materials for tests
  - Practice quizzes — generates questions with explanations
  - Progress tracker — what the student has worked on and mastered
  - Reading level detection — adapts to student's actual level
  - Parent dashboard — what their child is studying (no content, just topics)
  - Safety guardrails — age-appropriate content enforcement

$5/month because every kid deserves access to a patient tutor
who never gets tired, never judges, and always has time.
"""

import json
import uuid
import re
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.education")


GRADE_LEVELS = {
    "K": {"label": "Kindergarten", "age_range": "5-6", "reading_level": "beginning"},
    "1": {"label": "1st Grade", "age_range": "6-7", "reading_level": "early"},
    "2": {"label": "2nd Grade", "age_range": "7-8", "reading_level": "developing"},
    "3": {"label": "3rd Grade", "age_range": "8-9", "reading_level": "transitional"},
    "4": {"label": "4th Grade", "age_range": "9-10", "reading_level": "intermediate"},
    "5": {"label": "5th Grade", "age_range": "10-11", "reading_level": "intermediate"},
    "6": {"label": "6th Grade", "age_range": "11-12", "reading_level": "proficient"},
    "7": {"label": "7th Grade", "age_range": "12-13", "reading_level": "proficient"},
    "8": {"label": "8th Grade", "age_range": "13-14", "reading_level": "advanced"},
    "9": {"label": "9th Grade / Freshman", "age_range": "14-15", "reading_level": "advanced"},
    "10": {"label": "10th Grade / Sophomore", "age_range": "15-16", "reading_level": "advanced"},
    "11": {"label": "11th Grade / Junior", "age_range": "16-17", "reading_level": "college_prep"},
    "12": {"label": "12th Grade / Senior", "age_range": "17-18", "reading_level": "college_prep"},
}

SUBJECTS = {
    "math": {"label": "Mathematics", "icon": "🔢", "subtopics": [
        "arithmetic", "fractions", "decimals", "algebra", "geometry",
        "pre-algebra", "algebra_2", "trigonometry", "pre-calculus",
        "calculus", "statistics", "probability",
    ]},
    "science": {"label": "Science", "icon": "🔬", "subtopics": [
        "life_science", "earth_science", "physical_science", "biology",
        "chemistry", "physics", "environmental_science", "anatomy",
    ]},
    "english": {"label": "English Language Arts", "icon": "📚", "subtopics": [
        "reading_comprehension", "grammar", "vocabulary", "writing",
        "essay_writing", "creative_writing", "literary_analysis",
        "research_papers", "rhetoric", "poetry",
    ]},
    "history": {"label": "History & Social Studies", "icon": "🏛️", "subtopics": [
        "world_history", "us_history", "civics", "government",
        "geography", "economics", "current_events", "ap_history",
    ]},
    "languages": {"label": "World Languages", "icon": "🌍", "subtopics": [
        "spanish", "french", "german", "mandarin", "japanese",
        "latin", "italian", "arabic",
    ]},
    "cs": {"label": "Computer Science", "icon": "💻", "subtopics": [
        "intro_programming", "python", "java", "web_development",
        "ap_cs_principles", "ap_cs_a", "data_structures",
    ]},
    "test_prep": {"label": "Test Preparation", "icon": "📝", "subtopics": [
        "sat", "act", "ap_exams", "state_testing", "psat", "gre_prep",
    ]},
}

# Safety: content that the education tutor must never help with
EDUCATION_SAFETY = {
    "blocked_topics": [
        "weapons", "drugs", "alcohol", "violence", "self-harm",
        "explicit_content", "gambling", "hate_speech",
    ],
    "response_policy": (
        "You are a tutor for a K-12 student. You MUST:\n"
        "- Keep all content age-appropriate\n"
        "- Never provide answers directly — guide the student to discover them\n"
        "- Use encouraging, patient language\n"
        "- If the student asks about inappropriate topics, gently redirect to the subject\n"
        "- Never share personal opinions on politics, religion, or controversial topics\n"
        "- If the student seems distressed, encourage them to talk to a trusted adult\n"
        "- Celebrate effort, not just correct answers\n"
    ),
}


class EducationTutor:
    """K-12 AI tutoring platform."""

    def __init__(self, agent_manager=None):
        self.agents = agent_manager

    # ── STUDENT PROFILE ─────────────────────────────────────

    def create_student(self, parent_id: str, name: str, grade: str,
                       subjects: list = None, learning_style: str = "",
                       special_needs: str = "") -> dict:
        sid = f"stu_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO students
                    (id, parent_id, name, grade, subjects, learning_style, special_needs)
                VALUES (?,?,?,?,?,?,?)
            """, (sid, parent_id, name, grade,
                  json.dumps(subjects or list(SUBJECTS.keys())),
                  learning_style, special_needs))
        return {"id": sid, "name": name, "grade": grade}

    def get_student(self, sid: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not row: return None
        d = dict(row)
        d["subjects"] = json.loads(d.get("subjects", "[]") or "[]")
        return d

    def list_students(self, parent_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM students WHERE parent_id=? ORDER BY name",
                (parent_id,)).fetchall()
        return [dict(r, subjects=json.loads(r.get("subjects", "[]") or "[]")) for r in rows]

    def update_student(self, sid: str, updates: dict) -> dict:
        safe = {"name", "grade", "subjects", "learning_style", "special_needs"}
        filtered = {k: v for k, v in updates.items() if k in safe}
        if "subjects" in filtered:
            filtered["subjects"] = json.dumps(filtered["subjects"])
        filtered["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in filtered)
        vals = list(filtered.values()) + [sid]
        with get_db() as db:
            db.execute(f"UPDATE students SET {sets} WHERE id=?", vals)
        return self.get_student(sid)

    # ── TUTORING SESSION ────────────────────────────────────

    def tutor(self, student_id: str, parent_id: str, subject: str,
              question: str, subtopic: str = "") -> dict:
        """The core tutoring function — Socratic method, grade-adapted."""
        student = self.get_student(student_id)
        if not student: return {"error": "Student not found"}

        grade_info = GRADE_LEVELS.get(student["grade"], {})
        subject_info = SUBJECTS.get(subject, {})

        prompt = (
            f"{EDUCATION_SAFETY['response_policy']}\n\n"
            f"STUDENT: {student['name']}\n"
            f"GRADE: {grade_info.get('label', student['grade'])}\n"
            f"AGE RANGE: {grade_info.get('age_range', 'unknown')}\n"
            f"READING LEVEL: {grade_info.get('reading_level', 'intermediate')}\n"
            f"SUBJECT: {subject_info.get('label', subject)}\n"
        )
        if subtopic:
            prompt += f"SUBTOPIC: {subtopic}\n"
        if student.get("learning_style"):
            prompt += f"LEARNING STYLE: {student['learning_style']}\n"
        if student.get("special_needs"):
            prompt += f"ACCOMMODATIONS: {student['special_needs']}\n"

        prompt += (
            f"\nThe student asks: \"{question}\"\n\n"
            "TUTORING APPROACH:\n"
            "1. Do NOT give the answer directly\n"
            "2. Break the problem into smaller steps\n"
            "3. Ask guiding questions that lead the student to the answer\n"
            "4. Use examples and analogies appropriate for their grade level\n"
            "5. If they're stuck, give a hint — not the answer\n"
            "6. Celebrate when they get it right\n"
            "7. If the concept is above their grade level, simplify it\n"
            f"8. Use vocabulary and sentence structure appropriate for {grade_info.get('reading_level', 'intermediate')} reading level\n"
        )

        response = self._run_agent(parent_id, prompt)

        # Log the session
        self._log_session(student_id, subject, subtopic, question, response)

        return {
            "student_id": student_id,
            "subject": subject,
            "response": response,
            "grade": student["grade"],
        }

    # ── STUDY GUIDE ─────────────────────────────────────────

    def generate_study_guide(self, student_id: str, parent_id: str,
                              subject: str, topic: str,
                              exam_date: str = "") -> dict:
        """Generate a personalized study guide."""
        student = self.get_student(student_id)
        if not student: return {"error": "Student not found"}

        grade_info = GRADE_LEVELS.get(student["grade"], {})

        prompt = (
            f"Create a study guide for a {grade_info.get('label', '')} student.\n\n"
            f"Subject: {SUBJECTS.get(subject, {}).get('label', subject)}\n"
            f"Topic: {topic}\n"
            f"Reading level: {grade_info.get('reading_level', 'intermediate')}\n"
        )
        if exam_date:
            prompt += f"Exam date: {exam_date}\n"

        prompt += (
            "\nInclude:\n"
            "1. KEY CONCEPTS — The most important things to know (bullet points)\n"
            "2. VOCABULARY — Important terms with simple definitions\n"
            "3. EXAMPLES — Worked examples showing how to solve/apply concepts\n"
            "4. COMMON MISTAKES — What students often get wrong and how to avoid it\n"
            "5. PRACTICE PROBLEMS — 5 problems from easy to hard (with answers at the end)\n"
            "6. STUDY TIPS — How to prepare effectively\n"
            f"\nKeep language at {grade_info.get('reading_level', 'intermediate')} reading level.\n"
            "Use encouraging tone throughout.\n"
        )

        guide = self._run_agent(parent_id, prompt)
        return {"student_id": student_id, "subject": subject,
                "topic": topic, "study_guide": guide}

    # ── PRACTICE QUIZ ───────────────────────────────────────

    def generate_quiz(self, student_id: str, parent_id: str,
                       subject: str, topic: str,
                       num_questions: int = 5,
                       difficulty: str = "medium") -> dict:
        """Generate a practice quiz with explanations."""
        student = self.get_student(student_id)
        if not student: return {"error": "Student not found"}

        grade_info = GRADE_LEVELS.get(student["grade"], {})

        prompt = (
            f"Create a {num_questions}-question practice quiz for a {grade_info.get('label', '')} student.\n\n"
            f"Subject: {SUBJECTS.get(subject, {}).get('label', subject)}\n"
            f"Topic: {topic}\n"
            f"Difficulty: {difficulty}\n"
            f"Reading level: {grade_info.get('reading_level', 'intermediate')}\n\n"
            "For each question provide:\n"
            "- The question (clear, grade-appropriate language)\n"
            "- Multiple choice options (A, B, C, D) OR short answer\n"
            "- The correct answer\n"
            "- A brief explanation of WHY that's the answer\n"
            "- A hint for students who get stuck\n\n"
            "Mix question types. Start easier, get progressively harder.\n"
            "Use encouraging language in explanations.\n"
        )

        quiz = self._run_agent(parent_id, prompt)
        return {"student_id": student_id, "subject": subject,
                "topic": topic, "difficulty": difficulty, "quiz": quiz}

    # ── PROGRESS TRACKING ───────────────────────────────────

    def get_progress(self, student_id: str) -> dict:
        """Get student's learning progress."""
        with get_db() as db:
            sessions = db.execute("""
                SELECT subject, subtopic, COUNT(*) as session_count,
                    MAX(created_at) as last_session
                FROM tutoring_sessions WHERE student_id=?
                GROUP BY subject, subtopic
                ORDER BY last_session DESC
            """, (student_id,)).fetchall()

            total = db.execute(
                "SELECT COUNT(*) as c FROM tutoring_sessions WHERE student_id=?",
                (student_id,)).fetchone()

            recent = db.execute("""
                SELECT subject, subtopic, question, created_at
                FROM tutoring_sessions WHERE student_id=?
                ORDER BY created_at DESC LIMIT 10
            """, (student_id,)).fetchall()

        # Build subject breakdown
        by_subject = {}
        for s in sessions:
            d = dict(s)
            subj = d["subject"]
            by_subject.setdefault(subj, {"sessions": 0, "subtopics": []})
            by_subject[subj]["sessions"] += d["session_count"]
            if d["subtopic"]:
                by_subject[subj]["subtopics"].append(d["subtopic"])

        return {
            "student_id": student_id,
            "total_sessions": dict(total)["c"] if total else 0,
            "subjects": by_subject,
            "recent_activity": [dict(r) for r in recent],
        }

    # ── PARENT DASHBOARD ────────────────────────────────────

    def parent_dashboard(self, parent_id: str) -> dict:
        """What the parent sees — topics studied, not content."""
        students = self.list_students(parent_id)
        dashboard = []
        for student in students:
            progress = self.get_progress(student["id"])
            dashboard.append({
                "student_name": student["name"],
                "student_id": student["id"],
                "grade": student["grade"],
                "total_sessions": progress["total_sessions"],
                "subjects_studied": list(progress["subjects"].keys()),
                "recent_topics": [r["subtopic"] or r["subject"]
                                  for r in progress.get("recent_activity", [])[:5]],
                "last_active": progress["recent_activity"][0]["created_at"]
                    if progress.get("recent_activity") else None,
            })
        return {"students": dashboard}

    # ── REFERENCE DATA ──────────────────────────────────────

    def get_subjects(self) -> dict:
        return SUBJECTS

    def get_grade_levels(self) -> dict:
        return GRADE_LEVELS

    # ── INTERNAL ────────────────────────────────────────────

    def _run_agent(self, owner_id: str, prompt: str) -> str:
        if not self.agents:
            return "(Agent manager not connected)"
        with get_db() as db:
            agent = db.execute("SELECT id FROM agents WHERE owner_id=? LIMIT 1",
                              (owner_id,)).fetchone()
        if not agent:
            return "(No Spaces configured — create at least one Space)"
        result = self.agents.run_agent(dict(agent)["id"], prompt, user_id=owner_id)
        return result.get("text", "")

    def _log_session(self, student_id: str, subject: str,
                     subtopic: str, question: str, response: str):
        sid = f"ts_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO tutoring_sessions
                    (id, student_id, subject, subtopic, question, response_length)
                VALUES (?,?,?,?,?,?)
            """, (sid, student_id, subject, subtopic,
                  question[:500], len(response)))


# ══════════════════════════════════════════════════════════════
# HIGHER EDUCATION — Bachelor's through PhD Support ($15/month)
# ══════════════════════════════════════════════════════════════

"""
Higher Education tier — completely isolated from business features.

KEY INNOVATION: Learning DNA
  - Builds a profile of how each student learns
  - Detects when a student is struggling
  - Adapts teaching approach in real-time
  - Nobody does this today
"""

EDUCATION_PLANS = {
    "k12_student": {
        "label": "K-12 Student",
        "price_monthly": 5,
        "price_yearly": 48,
        "description": "AI tutoring for K-12 students with parental consent required.",
        "levels": ["elementary", "middle_school", "high_school"],
    },
    "student": {
        "label": "College Student",
        "price_monthly": 15,
        "price_yearly": 120,  # $10/mo yearly
        "description": "Full academic AI support from Bachelor's through PhD.",
        "levels": ["bachelors", "masters", "doctoral", "postdoc"],
        "features_included": [
            "learning_dna", "struggle_detection", "adaptive_tutor",
            "study_planner", "research_assistant", "writing_coach",
            "thesis_support", "concept_mapper", "practice_problems",
            "progress_dashboard", "citation_manager",
        ],
        "features_excluded": [
            "sales_coach", "digital_marketing", "compliance_watchdog",
            "compliance_escalation", "risk_register", "policy_engine",
            "delegation_authority", "knowledge_handoff", "client_deliverables",
            "ai_negotiation", "billing_features", "teams",
            "roundtable", "roundtable_multiuser", "corporate_records",
            "resolutions", "action_items",
        ],
        "limits": {
            "spaces": 5,
            "conversations_per_month": -1,
            "messages_per_conversation": -1,
            "knowledge_base_mb": 500,
        },
    },
    "institution": {
        "label": "Institution",
        "price_monthly": -1,
        "description": "University-wide deployment. Contact sales.",
        "contact_sales": True,
        "includes": [
            "All Student features",
            "LMS integration (Canvas, Blackboard, Moodle)",
            "Institutional analytics dashboard",
            "Faculty advisor portal",
            "Department-level curriculum controls",
            "FERPA compliance tools",
            "SSO / SAML integration",
            "Bulk student onboarding",
            "Dedicated support",
        ],
    },
}


LEARNING_STYLES = {
    "visual": "Learns best with diagrams, charts, mind maps, and visual representations",
    "analytical": "Learns best with logical breakdowns, proofs, and systematic analysis",
    "example_driven": "Learns best through worked examples and case studies",
    "analogy": "Learns best when new concepts are connected to familiar ones",
    "socratic": "Learns best when guided through questions rather than given answers",
    "hands_on": "Learns best through practice problems and interactive exercises",
    "narrative": "Learns best through storytelling and real-world context",
    "formal": "Learns best with precise definitions, theorems, and formal notation",
}


class LearningDNA:
    """Builds a living profile of how each student learns.

    Unlike Business DNA (organizational knowledge), Learning DNA tracks
    LEARNING PATTERNS: preferred styles, strong/weak subjects, what
    approaches worked, frustration signals, and confidence over time.
    """

    def get_profile(self, user_id: str) -> dict:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM learning_dna WHERE user_id=?", (user_id,)).fetchone()
        if row:
            d = dict(row)
            for field in ["strong_subjects", "weak_subjects", "preferred_styles",
                         "effective_approaches", "ineffective_approaches", "subject_history"]:
                if d.get(field):
                    try: d[field] = json.loads(d[field])
                    except: pass
            return d

        pid = f"ldna_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO learning_dna
                    (id, user_id, academic_level, strong_subjects, weak_subjects,
                     preferred_styles, effective_approaches, ineffective_approaches,
                     subject_history, struggle_score, total_interactions)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (pid, user_id, "bachelors", "[]", "[]", "[]", "[]", "[]", "{}", 0, 0))
        return self.get_profile(user_id)

    def update_from_interaction(self, user_id: str, subject: str,
                                 was_helpful: bool, approach_used: str,
                                 confidence_after: float = 0.5) -> dict:
        profile = self.get_profile(user_id)
        if not profile: return {"error": "No profile"}

        history = profile.get("subject_history", {})
        if not isinstance(history, dict): history = {}

        if subject not in history:
            history[subject] = {
                "interactions": 0, "helpful_count": 0,
                "avg_confidence": 0.5, "struggle_count": 0,
                "best_approaches": [], "last_interaction": None,
            }

        h = history[subject]
        h["interactions"] += 1
        h["last_interaction"] = datetime.now().isoformat()
        if was_helpful: h["helpful_count"] += 1
        if confidence_after < 0.4: h["struggle_count"] += 1
        n = h["interactions"]
        h["avg_confidence"] = ((h["avg_confidence"] * (n - 1)) + confidence_after) / n

        if was_helpful and approach_used and approach_used not in h.get("best_approaches", []):
            h.setdefault("best_approaches", []).append(approach_used)

        # Update strong/weak
        strong = profile.get("strong_subjects", [])
        weak = profile.get("weak_subjects", [])
        if not isinstance(strong, list): strong = []
        if not isinstance(weak, list): weak = []

        if h["avg_confidence"] >= 0.7 and h["interactions"] >= 3:
            if subject not in strong: strong.append(subject)
            if subject in weak: weak.remove(subject)
        elif h["avg_confidence"] < 0.4 and h["interactions"] >= 2:
            if subject not in weak: weak.append(subject)
            if subject in strong: strong.remove(subject)

        effective = profile.get("effective_approaches", [])
        ineffective = profile.get("ineffective_approaches", [])
        if not isinstance(effective, list): effective = []
        if not isinstance(ineffective, list): ineffective = []
        if was_helpful and approach_used and approach_used not in effective:
            effective.append(approach_used)
        elif not was_helpful and approach_used and approach_used not in ineffective:
            ineffective.append(approach_used)

        preferred = profile.get("preferred_styles", [])
        if not isinstance(preferred, list): preferred = []
        if was_helpful and approach_used in LEARNING_STYLES and approach_used not in preferred:
            preferred.append(approach_used)

        total_struggle = sum(s.get("struggle_count", 0) for s in history.values())
        total_inter = sum(s.get("interactions", 0) for s in history.values())
        struggle_score = min(100, int((total_struggle / max(total_inter, 1)) * 100))

        with get_db() as db:
            db.execute("""
                UPDATE learning_dna SET
                    strong_subjects=?, weak_subjects=?, preferred_styles=?,
                    effective_approaches=?, ineffective_approaches=?,
                    subject_history=?, struggle_score=?,
                    total_interactions=total_interactions+1, updated_at=?
                WHERE user_id=?
            """, (json.dumps(strong), json.dumps(weak), json.dumps(preferred),
                  json.dumps(effective[-10:]), json.dumps(ineffective[-10:]),
                  json.dumps(history), struggle_score,
                  datetime.now().isoformat(), user_id))

        return {"updated": True, "struggle_score": struggle_score, "subject": subject}

    def build_tutor_injection(self, user_id: str, subject: str = "") -> str:
        """Prompt injection that adapts teaching to THIS student."""
        profile = self.get_profile(user_id)
        if not profile or profile.get("total_interactions", 0) < 2:
            return ""

        parts = ["[LEARNING DNA — ADAPT YOUR TEACHING TO THIS STUDENT]"]

        preferred = profile.get("preferred_styles", [])
        if preferred:
            descs = [LEARNING_STYLES.get(s, s) for s in preferred[:3]]
            parts.append(f"This student learns best with: {'; '.join(descs)}.")

        effective = profile.get("effective_approaches", [])
        if effective:
            parts.append(f"Approaches that worked: {', '.join(effective[:5])}.")

        ineffective = profile.get("ineffective_approaches", [])
        if ineffective:
            parts.append(f"Approaches that did NOT work — avoid: {', '.join(ineffective[:5])}.")

        strong = profile.get("strong_subjects", [])
        weak = profile.get("weak_subjects", [])
        if strong:
            parts.append(f"Strong in: {', '.join(strong[:5])}. Reference these when explaining new concepts.")
        if weak:
            parts.append(f"Finds these challenging: {', '.join(weak[:5])}. Extra patience, smaller steps.")

        if subject:
            history = profile.get("subject_history", {})
            if isinstance(history, str):
                try: history = json.loads(history)
                except: history = {}
            sh = history.get(subject, {})
            if sh:
                conf = sh.get("avg_confidence", 0.5)
                if conf < 0.4:
                    parts.append(f"⚠ STRUGGLING with {subject} (confidence: {conf:.0%}). "
                                "Simpler language, more examples, check understanding often.")
                best = sh.get("best_approaches", [])
                if best:
                    parts.append(f"For {subject}, these worked: {', '.join(best)}.")

        struggle = profile.get("struggle_score", 0)
        if struggle >= 60:
            parts.append("🚨 HIGH STRUGGLE — Be encouraging. Celebrate small wins. "
                        "Break everything into manageable steps. Ask 'Does this make sense?' often.")

        parts.append("Always: encourage questions, normalize not knowing, praise effort over correctness.")
        return "\n".join(parts)


class StruggleDetector:
    """Detects when a student is falling behind."""

    FRUSTRATION_PATTERNS = [
        r"i (?:don['\u2019]t|cant|cannot) (?:understand|get|figure|grasp)",
        r"(?:this|it) (?:makes no sense|is (?:impossible|too hard|confusing))",
        r"(?:i['\u2019]m|i am) (?:so |really )?(?:lost|confused|stuck|frustrated|overwhelmed)",
        r"(?:nothing|none of this) (?:makes sense|is working|clicks)",
        r"(?:i give up|forget it|never mind|i quit)",
        r"(?:i['\u2019]m|i am) (?:going to|gonna) fail",
        r"(?:i['\u2019]m|i am) (?:so )?(?:stupid|dumb|bad at this)",
    ]

    def __init__(self):
        self._compiled = [re.compile(p, re.I) for p in self.FRUSTRATION_PATTERNS]

    def analyze_message(self, user_id: str, message: str, subject: str = "") -> dict:
        signals = []
        for pattern in self._compiled:
            if pattern.search(message):
                signals.append({"type": "frustration_language", "severity": "high",
                    "detail": "Student expressing frustration or self-doubt"})
                break

        try:
            with get_db() as db:
                row = db.execute(
                    "SELECT subject_history, struggle_score FROM learning_dna WHERE user_id=?",
                    (user_id,)).fetchone()
            if row:
                d = dict(row)
                history = json.loads(d.get("subject_history", "{}") or "{}")
                if subject and subject in history:
                    sh = history[subject]
                    if sh.get("struggle_count", 0) >= 3:
                        signals.append({"type": "repeated_struggle", "severity": "high",
                            "detail": f"Struggled with {subject} {sh['struggle_count']} times"})
                    if sh.get("avg_confidence", 1) < 0.3:
                        signals.append({"type": "very_low_confidence", "severity": "critical",
                            "detail": f"Confidence in {subject}: {sh['avg_confidence']:.0%}"})
                if d.get("struggle_score", 0) >= 60:
                    signals.append({"type": "high_overall_struggle", "severity": "critical",
                        "detail": f"Overall struggle score: {d['struggle_score']}/100"})
        except Exception:
            pass

        return {
            "struggling": len(signals) > 0,
            "signals": signals,
            "intervention_needed": any(s["severity"] in ("high", "critical") for s in signals),
        }

    def build_intervention_prompt(self, signals: list) -> str:
        if not signals: return ""
        parts = ["[INTERVENTION — STUDENT NEEDS EXTRA SUPPORT]"]
        if any(s["type"] == "frustration_language" for s in signals):
            parts.append("Student frustrated. Switch approach completely. Acknowledge the difficulty.")
            parts.append("Try: analogy, visual, real-world example, or break into smallest possible step.")
        if any(s["type"] == "repeated_struggle" for s in signals):
            parts.append("Previous approaches failed. Try something totally different.")
        if any(s["type"] == "very_low_confidence" for s in signals):
            parts.append("Confidence very low. Start with what they CAN do. Use 'we' language.")
        return "\n".join(parts)


class StudyPlanner:
    """Course and assignment tracking for college students."""

    def add_course(self, user_id: str, name: str, code: str = "",
                   professor: str = "", credits: int = 3) -> dict:
        cid = f"course_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO student_courses
                    (id, user_id, name, code, professor, credits)
                VALUES (?,?,?,?,?,?)
            """, (cid, user_id, name, code, professor, credits))
        return {"id": cid, "name": name}

    def list_courses(self, user_id: str) -> list:
        with get_db() as db:
            rows = db.execute("SELECT * FROM student_courses WHERE user_id=? ORDER BY name",
                             (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def add_assignment(self, user_id: str, course_id: str, title: str,
                       due_date: str, assignment_type: str = "homework",
                       weight: float = 0) -> dict:
        aid = f"asgn_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO student_assignments
                    (id, user_id, course_id, title, due_date, assignment_type, weight, status)
                VALUES (?,?,?,?,?,?,?,?)
            """, (aid, user_id, course_id, title, due_date, assignment_type, weight, "pending"))
        return {"id": aid, "title": title, "due_date": due_date}

    def list_assignments(self, user_id: str, status: str = None) -> list:
        with get_db() as db:
            if status:
                rows = db.execute(
                    "SELECT a.*, c.name as course_name FROM student_assignments a "
                    "LEFT JOIN student_courses c ON a.course_id=c.id "
                    "WHERE a.user_id=? AND a.status=? ORDER BY a.due_date",
                    (user_id, status)).fetchall()
            else:
                rows = db.execute(
                    "SELECT a.*, c.name as course_name FROM student_assignments a "
                    "LEFT JOIN student_courses c ON a.course_id=c.id "
                    "WHERE a.user_id=? ORDER BY a.due_date",
                    (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_upcoming(self, user_id: str, days: int = 7) -> list:
        cutoff = (datetime.now() + timedelta(days=days)).isoformat()[:10]
        with get_db() as db:
            rows = db.execute(
                "SELECT a.*, c.name as course_name FROM student_assignments a "
                "LEFT JOIN student_courses c ON a.course_id=c.id "
                "WHERE a.user_id=? AND a.status='pending' AND a.due_date<=? ORDER BY a.due_date",
                (user_id, cutoff)).fetchall()
        return [dict(r) for r in rows]

    def update_assignment(self, aid: str, updates: dict) -> dict:
        safe = {"title", "due_date", "status", "grade", "notes", "weight"}
        filtered = {k: v for k, v in updates.items() if k in safe}
        if not filtered: return {}
        sets = ", ".join(f"{k}=?" for k in filtered)
        vals = list(filtered.values()) + [aid]
        with get_db() as db:
            db.execute(f"UPDATE student_assignments SET {sets} WHERE id=?", vals)
            row = db.execute("SELECT * FROM student_assignments WHERE id=?", (aid,)).fetchone()
        return dict(row) if row else {}

    def get_dashboard(self, user_id: str) -> dict:
        courses = self.list_courses(user_id)
        upcoming = self.get_upcoming(user_id, 14)
        with get_db() as db:
            pending = db.execute(
                "SELECT COUNT(*) as c FROM student_assignments WHERE user_id=? AND status='pending'",
                (user_id,)).fetchone()
            overdue = db.execute(
                "SELECT COUNT(*) as c FROM student_assignments WHERE user_id=? AND status='pending' AND due_date<?",
                (user_id, datetime.now().isoformat()[:10])).fetchone()
        return {
            "courses": len(courses),
            "pending_assignments": dict(pending)["c"],
            "overdue": dict(overdue)["c"],
            "upcoming_14_days": upcoming,
        }


class EducationPlanEnforcer:
    """Education-tier users can ONLY access education features."""

    BLOCKED_PREFIXES = [
        "/api/sales/", "/api/marketing/", "/api/compliance/",
        "/api/risks", "/api/policies", "/api/delegations",
        "/api/handoff", "/api/deliverables", "/api/teams",
        "/api/roundtable", "/api/minutes", "/api/records",
        "/api/resolutions", "/api/actions",
    ]

    def is_education_plan(self, owner_id: str) -> bool:
        with get_db() as db:
            row = db.execute(
                "SELECT value FROM workspace_settings WHERE key='plan'"
            ).fetchone()
        return dict(row)["value"] in ("student", "k12_student") if row else False

    def check_access(self, route: str, owner_id: str) -> dict:
        if not self.is_education_plan(owner_id):
            return {"allowed": True}
        for prefix in self.BLOCKED_PREFIXES:
            if route.startswith(prefix):
                return {"allowed": False,
                    "message": "This feature is not available on the Student plan."}
        return {"allowed": True}
