# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Education Upgrades — Comprehensive K-12 and higher ed enhancements.

1. TEACHING METHODS — Multiple pedagogical approaches per student
2. CURRICULUM STANDARDS — Common Core, NGSS, state standards alignment
3. PARENT DASHBOARD — Full progress visibility, report cards, alerts
4. PROGRESS REPORTS — Printable, exportable report cards
5. TEST PREP ENGINE — Structured SAT/ACT/AP/State test preparation
6. LEARNING ANALYTICS — Time on task, mastery levels, weak areas
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.edu_upgrades")


# ══════════════════════════════════════════════════════════════
# 1. TEACHING METHODS
# ══════════════════════════════════════════════════════════════

TEACHING_METHODS = {
    "socratic": {
        "label": "Socratic Method",
        "description": "Guide through questions — never give answers directly",
        "best_for": "Critical thinking, philosophy, literature analysis",
        "ai_instruction": (
            "Use the Socratic method. NEVER give the answer directly. Instead, ask "
            "guiding questions that lead the student to discover the answer themselves. "
            "Start with what they already know, then ask questions that build on that. "
            "If they're stuck, ask a simpler question. Celebrate when they figure it out."
        ),
    },
    "direct_instruction": {
        "label": "Direct Instruction",
        "description": "Explain clearly, demonstrate, then practice together",
        "best_for": "Math procedures, grammar rules, vocabulary, new concepts",
        "ai_instruction": (
            "Use direct instruction. Explain the concept clearly and simply. "
            "Show a worked example step by step. Then give a similar practice problem. "
            "Check their work and provide immediate feedback. If they struggle, "
            "re-explain with a different example."
        ),
    },
    "scaffolded": {
        "label": "Scaffolded Learning",
        "description": "Build skills step by step, removing support as mastery grows",
        "best_for": "Complex multi-step problems, writing, research",
        "ai_instruction": (
            "Use scaffolded learning. Break the task into small, manageable steps. "
            "Start with heavy support (fill-in-the-blank, multiple choice). "
            "As the student succeeds, gradually reduce support until they can do it "
            "independently. Always know what step they're on and what comes next."
        ),
    },
    "project_based": {
        "label": "Project-Based Learning",
        "description": "Learn through building real-world projects",
        "best_for": "Science, technology, engineering, social studies",
        "ai_instruction": (
            "Use project-based learning. Frame everything as a real-world project. "
            "Instead of 'learn about ecosystems,' say 'you're designing a nature preserve.' "
            "Guide them through research, planning, building, and presenting. "
            "Integrate multiple subjects naturally through the project."
        ),
    },
    "inquiry_based": {
        "label": "Inquiry-Based Learning",
        "description": "Start with curiosity — students form hypotheses and investigate",
        "best_for": "Science, history, critical analysis",
        "ai_instruction": (
            "Use inquiry-based learning. Start with a provocative question or phenomenon. "
            "Ask the student what they think and why. Help them form a hypothesis. "
            "Guide them to find evidence. Let them revise their thinking. "
            "Value the process of investigation over the 'right' answer."
        ),
    },
    "montessori": {
        "label": "Montessori Approach",
        "description": "Self-directed, hands-on, follow the child's interest",
        "best_for": "Early elementary, multi-subject exploration, self-paced",
        "ai_instruction": (
            "Use a Montessori-inspired approach. Follow the student's natural curiosity. "
            "Offer choices: 'Would you like to explore counting, shapes, or animals today?' "
            "Use concrete examples and hands-on descriptions. Let them go at their own pace. "
            "Connect subjects naturally — math through cooking, science through nature."
        ),
    },
    "flipped_classroom": {
        "label": "Flipped Classroom",
        "description": "Student reads/watches first, then practices with AI support",
        "best_for": "High school, college prep, AP/IB courses",
        "ai_instruction": (
            "Use the flipped classroom model. Assume the student has already read the material. "
            "Start by asking what they learned and what confused them. "
            "Focus on applying concepts, not re-explaining them. "
            "Go deeper than the textbook. Challenge them with analysis questions."
        ),
    },
    "gamified": {
        "label": "Gamified Learning",
        "description": "Points, levels, challenges — learn through play",
        "best_for": "Elementary, reluctant learners, math facts, vocabulary",
        "ai_instruction": (
            "Use gamified learning. Frame everything as a game or challenge. "
            "'Level 1: Can you solve 5 addition problems to unlock Level 2?' "
            "Use points, streaks, and leaderboard language. Make mistakes feel like "
            "'losing a life' not failure. Celebrate every level-up."
        ),
    },
    "common_core_aligned": {
        "label": "Common Core Aligned",
        "description": "Teaches to Common Core State Standards with explicit standard references",
        "best_for": "Standards-aligned homework help, state test prep",
        "ai_instruction": (
            "Align all instruction to Common Core State Standards. When teaching a concept, "
            "reference the specific standard (e.g., 'CCSS.MATH.CONTENT.3.NF.A.1'). "
            "Focus on conceptual understanding AND procedural fluency. "
            "For ELA, emphasize evidence-based reading and writing. "
            "For math, require students to explain their reasoning, not just get the answer."
        ),
    },
}


# ══════════════════════════════════════════════════════════════
# 2. CURRICULUM STANDARDS
# ══════════════════════════════════════════════════════════════

CURRICULUM_STANDARDS = {
    "ccss_math": {
        "label": "Common Core — Mathematics",
        "organization": "National Governors Association / CCSSO",
        "grades": "K-12",
        "domains": {
            "K": ["Counting & Cardinality", "Operations & Algebraic Thinking",
                  "Number & Operations in Base 10", "Measurement & Data", "Geometry"],
            "1-2": ["Operations & Algebraic Thinking", "Number & Operations in Base 10",
                    "Measurement & Data", "Geometry"],
            "3-5": ["Operations & Algebraic Thinking", "Number & Operations in Base 10",
                    "Number & Operations — Fractions", "Measurement & Data", "Geometry"],
            "6-8": ["Ratios & Proportional Relationships", "The Number System",
                    "Expressions & Equations", "Functions", "Geometry",
                    "Statistics & Probability"],
            "9-12": ["Number & Quantity", "Algebra", "Functions",
                     "Modeling", "Geometry", "Statistics & Probability"],
        },
    },
    "ccss_ela": {
        "label": "Common Core — English Language Arts",
        "organization": "National Governors Association / CCSSO",
        "grades": "K-12",
        "domains": {
            "K-5": ["Reading: Literature", "Reading: Informational Text",
                    "Reading: Foundational Skills", "Writing",
                    "Speaking & Listening", "Language"],
            "6-12": ["Reading: Literature", "Reading: Informational Text",
                     "Writing", "Speaking & Listening", "Language"],
        },
    },
    "ngss": {
        "label": "Next Generation Science Standards",
        "organization": "Achieve Inc.",
        "grades": "K-12",
        "domains": {
            "K-2": ["Physical Science", "Life Science", "Earth & Space Science",
                    "Engineering Design"],
            "3-5": ["Physical Science", "Life Science", "Earth & Space Science",
                    "Engineering Design"],
            "6-8": ["Physical Science", "Life Science", "Earth & Space Science",
                    "Engineering Design"],
            "9-12": ["Physical Science", "Life Science", "Earth & Space Science",
                     "Engineering Design"],
        },
    },
    "c3_social_studies": {
        "label": "C3 Framework — Social Studies",
        "organization": "National Council for Social Studies",
        "grades": "K-12",
        "domains": {
            "all": ["Civics", "Economics", "Geography", "History"],
        },
    },
    "ap": {
        "label": "Advanced Placement (AP)",
        "organization": "College Board",
        "grades": "9-12",
        "courses": [
            "AP Biology", "AP Chemistry", "AP Physics 1", "AP Physics 2",
            "AP Physics C: Mechanics", "AP Physics C: E&M",
            "AP Calculus AB", "AP Calculus BC", "AP Statistics",
            "AP Computer Science A", "AP Computer Science Principles",
            "AP English Language", "AP English Literature",
            "AP US History", "AP World History", "AP European History",
            "AP US Government", "AP Comparative Government",
            "AP Macroeconomics", "AP Microeconomics",
            "AP Psychology", "AP Human Geography",
            "AP Environmental Science", "AP Art History",
            "AP Spanish", "AP French", "AP Chinese", "AP Japanese",
        ],
    },
    "ib": {
        "label": "International Baccalaureate (IB)",
        "organization": "International Baccalaureate Organization",
        "grades": "11-12",
        "groups": [
            "Studies in Language & Literature", "Language Acquisition",
            "Individuals & Societies", "Sciences", "Mathematics",
            "The Arts", "Theory of Knowledge", "Extended Essay",
        ],
    },
}


class CurriculumManager:
    """Manage curriculum standard alignment for students."""

    def get_standards(self) -> dict:
        return CURRICULUM_STANDARDS

    def get_standard(self, standard_id: str) -> dict:
        return CURRICULUM_STANDARDS.get(standard_id)

    def set_student_standards(self, student_id: str, standards: list) -> dict:
        """Assign curriculum standards to a student."""
        with get_db() as db:
            db.execute("""
                UPDATE students SET curriculum_standards=? WHERE id=?
            """, (json.dumps(standards), student_id))
        return {"updated": True, "standards": standards}

    def get_student_standards(self, student_id: str) -> list:
        with get_db() as db:
            row = db.execute(
                "SELECT curriculum_standards FROM students WHERE id=?",
                (student_id,)).fetchone()
        if not row:
            return []
        return json.loads(dict(row).get("curriculum_standards", "[]") or "[]")

    def build_standard_prompt(self, standards: list, grade: str, subject: str) -> str:
        """Build AI instruction to align with specific standards."""
        parts = [f"Align instruction to the following curriculum standards for grade {grade}, subject {subject}:\n"]
        for sid in standards:
            s = CURRICULUM_STANDARDS.get(sid)
            if s:
                parts.append(f"- {s['label']} ({s['organization']})")
        parts.append(
            "\nWhen teaching, reference specific standards by code when possible. "
            "Ensure all content aligns with grade-level expectations defined by these standards."
        )
        return "\n".join(parts)


# ══════════════════════════════════════════════════════════════
# 3. ENHANCED PARENT DASHBOARD
# ══════════════════════════════════════════════════════════════

class ParentDashboard:
    """Comprehensive parent visibility into student learning."""

    def get_full_dashboard(self, parent_id: str) -> dict:
        """Everything a parent needs to see."""
        from .education import EducationTutor
        tutor = EducationTutor()
        students = tutor.list_students(parent_id)
        dashboard = []

        for student in students:
            sid = student["id"]
            progress = tutor.get_progress(sid)
            analytics = self._get_learning_analytics(sid)
            alerts = self._get_alerts(sid)

            dashboard.append({
                "student": {
                    "id": sid,
                    "name": student["name"],
                    "grade": student["grade"],
                    "learning_style": student.get("learning_style", ""),
                    "teaching_method": student.get("teaching_method", "socratic"),
                },
                "summary": {
                    "total_sessions": progress["total_sessions"],
                    "subjects_studied": list(progress.get("subjects", {}).keys()),
                    "total_time_minutes": analytics.get("total_time", 0),
                    "sessions_this_week": analytics.get("sessions_this_week", 0),
                    "current_streak": analytics.get("streak", 0),
                    "last_active": progress["recent_activity"][0]["created_at"]
                        if progress.get("recent_activity") else None,
                },
                "subject_mastery": analytics.get("subject_mastery", {}),
                "recent_activity": [
                    {"subject": r.get("subject", ""),
                     "topic": r.get("subtopic", ""),
                     "date": r.get("created_at", "")[:10]}
                    for r in progress.get("recent_activity", [])[:10]
                ],
                "alerts": alerts,
            })

        return {"students": dashboard, "parent_id": parent_id}

    def _get_learning_analytics(self, student_id: str) -> dict:
        with get_db() as db:
            total = db.execute(
                "SELECT COUNT(*) as c FROM education_sessions WHERE student_id=?",
                (student_id,)).fetchone()
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            weekly = db.execute(
                "SELECT COUNT(*) as c FROM education_sessions WHERE student_id=? AND created_at>=?",
                (student_id, week_ago)).fetchone()
            by_subject = db.execute(
                "SELECT subject, COUNT(*) as sessions, "
                "AVG(CASE WHEN outcome='correct' THEN 100 WHEN outcome='partial' THEN 50 ELSE 0 END) as mastery "
                "FROM education_sessions WHERE student_id=? GROUP BY subject",
                (student_id,)).fetchall()
        mastery = {}
        for r in by_subject:
            d = dict(r)
            pct = round(d.get("mastery", 0) or 0)
            level = "advanced" if pct >= 85 else "proficient" if pct >= 70 else "developing" if pct >= 50 else "needs_support"
            mastery[d["subject"]] = {"sessions": d["sessions"], "mastery_pct": pct, "level": level}

        return {
            "total_sessions": dict(total)["c"],
            "sessions_this_week": dict(weekly)["c"],
            "total_time": 0,
            "streak": 0,
            "subject_mastery": mastery,
        }

    def _get_alerts(self, student_id: str) -> list:
        alerts = []
        with get_db() as db:
            # No activity in 3+ days
            three_days = (datetime.now() - timedelta(days=3)).isoformat()
            recent = db.execute(
                "SELECT COUNT(*) as c FROM education_sessions WHERE student_id=? AND created_at>=?",
                (student_id, three_days)).fetchone()
            if dict(recent)["c"] == 0:
                alerts.append({"type": "inactivity", "level": "warning",
                              "message": "No study activity in the last 3 days"})

            # Struggling subjects (mastery < 50%)
            struggling = db.execute(
                "SELECT subject, AVG(CASE WHEN outcome='correct' THEN 100 ELSE 0 END) as m "
                "FROM education_sessions WHERE student_id=? "
                "GROUP BY subject HAVING m < 50",
                (student_id,)).fetchall()
            for r in struggling:
                d = dict(r)
                alerts.append({"type": "struggling", "level": "attention",
                              "message": f"Struggling with {d['subject']} (mastery: {round(d['m'])}%)"})
        return alerts

    def get_progress_report(self, student_id: str, period: str = "month") -> dict:
        """Generate a printable progress report / report card."""
        with get_db() as db:
            student = db.execute("SELECT * FROM students WHERE id=?",
                                (student_id,)).fetchone()
        if not student:
            return {"error": "Student not found"}
        s = dict(student)
        s["subjects"] = json.loads(s.get("subjects", "[]") or "[]")

        days = 30 if period == "month" else 90 if period == "quarter" else 365
        start = (datetime.now() - timedelta(days=days)).isoformat()

        with get_db() as db:
            by_subject = db.execute("""
                SELECT subject, COUNT(*) as sessions,
                    SUM(CASE WHEN outcome='correct' THEN 1 ELSE 0 END) as correct,
                    SUM(CASE WHEN outcome='incorrect' THEN 1 ELSE 0 END) as incorrect
                FROM education_sessions WHERE student_id=? AND created_at>=?
                GROUP BY subject
            """, (student_id, start)).fetchall()

        report = []
        for r in by_subject:
            d = dict(r)
            total = d["correct"] + d["incorrect"]
            pct = round(d["correct"] / total * 100) if total else 0
            if pct >= 90: grade = "A"
            elif pct >= 80: grade = "B"
            elif pct >= 70: grade = "C"
            elif pct >= 60: grade = "D"
            else: grade = "F"
            report.append({
                "subject": d["subject"],
                "sessions": d["sessions"],
                "accuracy": pct,
                "grade": grade,
                "correct": d["correct"],
                "incorrect": d["incorrect"],
            })

        return {
            "student_name": s["name"],
            "grade_level": s["grade"],
            "period": period,
            "report_date": datetime.now().strftime("%B %d, %Y"),
            "subjects": report,
            "overall_gpa": self._calc_gpa(report),
            "disclaimer": "This progress report reflects AI tutoring session performance "
                         "and does not replace official school assessments.",
        }

    def _calc_gpa(self, report: list) -> float:
        grade_points = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}
        if not report:
            return 0.0
        total = sum(grade_points.get(r["grade"], 0) for r in report)
        return round(total / len(report), 2)


# ══════════════════════════════════════════════════════════════
# 4. TEST PREP ENGINE
# ══════════════════════════════════════════════════════════════

TEST_PREP_PROGRAMS = {
    "sat": {
        "label": "SAT Preparation",
        "sections": [
            {"id": "sat_reading", "label": "Reading & Writing", "time_minutes": 64,
             "question_count": 54, "topics": [
                "Words in Context", "Command of Evidence", "Central Ideas",
                "Rhetorical Synthesis", "Standard English Conventions",
                "Expression of Ideas", "Information and Ideas",
             ]},
            {"id": "sat_math", "label": "Mathematics", "time_minutes": 70,
             "question_count": 44, "topics": [
                "Algebra", "Advanced Math", "Problem Solving & Data Analysis",
                "Geometry & Trigonometry",
             ]},
        ],
        "total_time": 134,
        "total_questions": 98,
        "score_range": "400-1600",
    },
    "act": {
        "label": "ACT Preparation",
        "sections": [
            {"id": "act_english", "label": "English", "time_minutes": 45,
             "question_count": 75, "topics": [
                "Production of Writing", "Knowledge of Language",
                "Conventions of Standard English",
             ]},
            {"id": "act_math", "label": "Mathematics", "time_minutes": 60,
             "question_count": 60, "topics": [
                "Pre-Algebra", "Elementary Algebra", "Intermediate Algebra",
                "Coordinate Geometry", "Plane Geometry", "Trigonometry",
             ]},
            {"id": "act_reading", "label": "Reading", "time_minutes": 35,
             "question_count": 40, "topics": [
                "Prose Fiction", "Social Science", "Humanities", "Natural Science",
             ]},
            {"id": "act_science", "label": "Science", "time_minutes": 35,
             "question_count": 40, "topics": [
                "Data Representation", "Research Summaries", "Conflicting Viewpoints",
             ]},
        ],
        "total_time": 175,
        "total_questions": 215,
        "score_range": "1-36",
    },
    "state_testing": {
        "label": "State Standardized Tests",
        "sections": [
            {"id": "state_ela", "label": "English Language Arts", "topics": [
                "Reading Comprehension", "Writing", "Language Conventions",
            ]},
            {"id": "state_math", "label": "Mathematics", "topics": [
                "Number Sense", "Algebra", "Geometry", "Data Analysis",
            ]},
            {"id": "state_science", "label": "Science (if applicable)", "topics": [
                "Life Science", "Physical Science", "Earth Science",
            ]},
        ],
        "score_range": "Varies by state",
        "note": "Aligned to Common Core State Standards where applicable",
    },
}


class TestPrepEngine:
    """Structured test preparation with practice tests and score tracking."""

    def get_programs(self) -> dict:
        return TEST_PREP_PROGRAMS

    def get_program(self, program_id: str) -> dict:
        return TEST_PREP_PROGRAMS.get(program_id)

    def start_practice_session(self, student_id: str, program: str,
                                 section: str, question_count: int = 10) -> dict:
        """Start a timed practice session."""
        sid = f"prep_{uuid.uuid4().hex[:10]}"
        prog = TEST_PREP_PROGRAMS.get(program, {})
        sec = next((s for s in prog.get("sections", []) if s["id"] == section), None)

        with get_db() as db:
            db.execute("""
                INSERT INTO test_prep_sessions
                    (id, student_id, program, section, question_count, status)
                VALUES (?,?,?,?,?,?)
            """, (sid, student_id, program, section, question_count, "active"))

        return {
            "session_id": sid,
            "program": prog.get("label", program),
            "section": sec.get("label", section) if sec else section,
            "question_count": question_count,
            "topics": sec.get("topics", []) if sec else [],
            "prompt": self._build_practice_prompt(prog, sec, question_count),
        }

    def record_result(self, session_id: str, correct: int, total: int,
                       time_seconds: int = 0) -> dict:
        """Record results from a practice session."""
        pct = round(correct / total * 100) if total else 0
        with get_db() as db:
            db.execute("""
                UPDATE test_prep_sessions SET correct=?, total=?,
                    score_pct=?, time_seconds=?, status='completed', completed_at=?
                WHERE id=?
            """, (correct, total, pct, time_seconds,
                  datetime.now().isoformat(), session_id))
        return {"score": pct, "correct": correct, "total": total}

    def get_score_history(self, student_id: str, program: str = None) -> list:
        with get_db() as db:
            if program:
                rows = db.execute(
                    "SELECT * FROM test_prep_sessions WHERE student_id=? AND program=? AND status='completed' ORDER BY completed_at DESC",
                    (student_id, program)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM test_prep_sessions WHERE student_id=? AND status='completed' ORDER BY completed_at DESC",
                    (student_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_predicted_score(self, student_id: str, program: str) -> dict:
        """Predict test score based on practice performance."""
        history = self.get_score_history(student_id, program)
        if not history:
            return {"predicted": False, "message": "Need more practice sessions for a prediction"}
        recent = history[:10]
        avg_pct = sum(h.get("score_pct", 0) for h in recent) / len(recent)
        prog = TEST_PREP_PROGRAMS.get(program, {})
        score_range = prog.get("score_range", "")

        if program == "sat":
            predicted = round(400 + (avg_pct / 100) * 1200)
            return {"predicted_score": predicted, "score_range": score_range,
                    "based_on": len(recent), "avg_accuracy": round(avg_pct)}
        elif program == "act":
            predicted = round(1 + (avg_pct / 100) * 35)
            return {"predicted_score": predicted, "score_range": score_range,
                    "based_on": len(recent), "avg_accuracy": round(avg_pct)}
        return {"avg_accuracy": round(avg_pct), "based_on": len(recent)}

    def _build_practice_prompt(self, prog: dict, section: dict, count: int) -> str:
        if not section:
            return ""
        return (
            f"Generate a {count}-question practice test for {prog.get('label', '')} — "
            f"{section.get('label', '')}.\n\n"
            f"Topics to cover: {', '.join(section.get('topics', []))}\n\n"
            f"Format each question as:\n"
            f"Q1. [Question text]\n"
            f"A) [Option]\nB) [Option]\nC) [Option]\nD) [Option]\n"
            f"Correct: [Letter]\n"
            f"Explanation: [Why the correct answer is right]\n\n"
            f"Mix difficulty levels. Include some that require critical thinking, "
            f"not just recall. Make answer choices plausible — no obvious wrong answers."
        )


# ══════════════════════════════════════════════════════════════
# 5. TEACHING METHOD MANAGER
# ══════════════════════════════════════════════════════════════

class TeachingMethodManager:
    """Assign and manage teaching methods per student."""

    def get_methods(self) -> dict:
        return TEACHING_METHODS

    def set_student_method(self, student_id: str, method: str) -> dict:
        if method not in TEACHING_METHODS:
            return {"error": f"Unknown method. Options: {list(TEACHING_METHODS.keys())}"}
        with get_db() as db:
            db.execute("UPDATE students SET teaching_method=? WHERE id=?",
                      (method, student_id))
        return {"updated": True, "method": method,
                "label": TEACHING_METHODS[method]["label"]}

    def get_student_method(self, student_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT teaching_method FROM students WHERE id=?",
                            (student_id,)).fetchone()
        method = dict(row).get("teaching_method", "socratic") if row else "socratic"
        return TEACHING_METHODS.get(method, TEACHING_METHODS["socratic"])

    def build_method_prompt(self, student_id: str) -> str:
        method = self.get_student_method(student_id)
        return method.get("ai_instruction", "")

    def recommend_method(self, grade: str, subject: str,
                          learning_style: str = "") -> dict:
        """AI-recommend best teaching method based on student profile."""
        recommendations = []
        if grade in ("K", "1", "2"):
            recommendations = ["montessori", "gamified", "direct_instruction"]
        elif grade in ("3", "4", "5"):
            recommendations = ["scaffolded", "gamified", "direct_instruction"]
        elif grade in ("6", "7", "8"):
            recommendations = ["socratic", "inquiry_based", "scaffolded"]
        else:
            recommendations = ["socratic", "flipped_classroom", "inquiry_based"]

        if subject in ("math", "algebra", "geometry", "calculus"):
            if "direct_instruction" not in recommendations:
                recommendations.insert(1, "direct_instruction")
        elif subject in ("science", "biology", "chemistry", "physics"):
            if "inquiry_based" not in recommendations:
                recommendations.insert(0, "inquiry_based")
        elif subject in ("history", "english", "literature"):
            if "socratic" not in recommendations:
                recommendations.insert(0, "socratic")

        if learning_style == "visual":
            if "project_based" not in recommendations:
                recommendations.append("project_based")

        return {
            "recommended": recommendations[:3],
            "details": {m: TEACHING_METHODS[m] for m in recommendations[:3]},
        }
