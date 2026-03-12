# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Education Pedagogy Engine — World teaching methods, localized to the student.

KEY INSIGHT: A Japanese student in the US has different needs than
a Japanese student in Tokyo.

  Japanese student in US:
    - Curriculum: US Common Core (must pass US state tests)
    - Teaching methods: Can blend Kumon mastery + US problem-solving
    - Cultural context: May prefer structured, sequential approach
    - Language: Bilingual support (English + Japanese)

  Japanese student in Japan:
    - Curriculum: Japanese Ministry of Education (文部科学省)
    - Teaching methods: Full Kumon, Lesson Study, Soroban
    - Cultural context: Exam-focused (entrance exams matter)
    - Language: Japanese primary

This module defines:
  1. TEACHING METHODOLOGIES — from 8 countries
  2. CURRICULUM STANDARDS — what students need to know, by country
  3. BLENDING ENGINE — combines methods based on background + location
  4. AI INSTRUCTION BUILDER — generates teaching prompts per student
"""

import json
import logging

logger = logging.getLogger("MyTeam360.pedagogy")


# ══════════════════════════════════════════════════════════════
# 1. TEACHING METHODOLOGIES
# ══════════════════════════════════════════════════════════════

TEACHING_METHODS = {
    "kumon": {
        "origin": "Japan",
        "name": "Kumon Method",
        "name_native": "公文式",
        "philosophy": "Self-learning through incremental mastery. Students work at their own level, not their age level. Daily practice builds fluency and confidence.",
        "key_principles": [
            "Start at the student's actual ability level, not grade level",
            "Small incremental steps — never jump difficulty",
            "Daily practice (consistency over intensity)",
            "Self-correction — student checks own work first",
            "Master before progressing — 100% accuracy before advancing",
            "Speed AND accuracy matter (timed worksheets)",
        ],
        "best_for": ["math_fluency", "reading_fluency", "building_discipline", "catching_up", "getting_ahead"],
        "subjects": ["math", "reading"],
        "ai_instruction": (
            "Apply Kumon-style teaching: Start with problems the student can solve easily to build confidence. "
            "Increase difficulty in tiny increments. If they struggle, go back one step. "
            "Emphasize daily practice. When they get an answer right, move to a slightly harder version. "
            "Focus on computational fluency — speed and accuracy both matter. "
            "Never skip steps. Mastery at each level before advancing."
        ),
    },

    "singapore_math": {
        "origin": "Singapore",
        "name": "Singapore Math (CPA)",
        "name_native": "Singapore Math",
        "philosophy": "Concrete → Pictorial → Abstract. Master fewer concepts deeply rather than many concepts shallowly. Bar models make abstract problems visual.",
        "key_principles": [
            "Concrete-Pictorial-Abstract (CPA) progression",
            "Bar modeling for word problems (visual representation)",
            "Number bonds (part-whole relationships)",
            "Mastery-based — depth over breadth",
            "Mental math strategies explicitly taught",
            "Fewer topics per year, but complete understanding",
        ],
        "best_for": ["math_conceptual", "word_problems", "visual_learners", "number_sense"],
        "subjects": ["math"],
        "ai_instruction": (
            "Apply Singapore Math CPA approach: For new concepts, start with CONCRETE examples "
            "(real objects, counting blocks). Then move to PICTORIAL (draw bar models, number bonds). "
            "Finally go ABSTRACT (numbers and symbols). Always use bar models for word problems. "
            "Teach number bonds for addition/subtraction. Emphasize mental math strategies. "
            "Don't move to abstract until the student demonstrates pictorial understanding."
        ),
    },

    "chinese_intensive": {
        "origin": "China",
        "name": "Chinese Mathematics Education",
        "name_native": "中国数学教育",
        "philosophy": "Understanding through intensive practice. Concepts are taught conceptually first, then reinforced through structured, varied practice. Emphasis on logical reasoning and proof.",
        "key_principles": [
            "Concept explanation before practice (理解 before 练习)",
            "Varied practice — same concept, many problem formats",
            "Two basics: basic knowledge + basic skills (双基)",
            "Teacher-led conceptual instruction with student practice",
            "Error analysis — understand WHY mistakes happen",
            "Competitive but collaborative (study groups)",
        ],
        "best_for": ["math_advanced", "logical_reasoning", "exam_preparation", "problem_variety"],
        "subjects": ["math", "science"],
        "ai_instruction": (
            "Apply Chinese math education approach: First explain the concept clearly with a "
            "worked example. Then provide varied practice — the same concept in different formats "
            "(fill in blank, true/false, word problem, proof). When the student makes an error, "
            "analyze WHY — don't just correct it. Include challenging extension problems for "
            "students who master the basics. Emphasize logical reasoning and showing work."
        ),
    },

    "finnish": {
        "origin": "Finland",
        "name": "Finnish Approach",
        "name_native": "Suomalainen lähestymistapa",
        "philosophy": "Equity, creativity, and joy of learning. Less homework, less testing, more play and exploration. Trust the student. Teacher autonomy over rigid curriculum.",
        "key_principles": [
            "Student-centered, not teacher-centered",
            "Less is more — shorter school days, less homework",
            "Play-based learning especially for younger children",
            "No standardized testing until age 16",
            "Equity — every student supported, no one left behind",
            "Cross-curricular themes (connect subjects together)",
            "Outdoor learning and physical activity integrated",
        ],
        "best_for": ["creative_thinking", "intrinsic_motivation", "struggling_students", "anxiety_reduction", "cross_curricular"],
        "subjects": ["all"],
        "ai_instruction": (
            "Apply Finnish educational approach: Make learning feel like exploration, not work. "
            "Connect the topic to the student's real interests. Ask open-ended questions rather "
            "than drilling facts. Encourage the student's own questions and curiosity. "
            "If they're frustrated, take a break and come at it differently. "
            "Integrate subjects — if studying math, connect it to art or nature. "
            "Celebrate the process of thinking, not just correct answers."
        ),
    },

    "montessori": {
        "origin": "Italy",
        "name": "Montessori Method",
        "name_native": "Metodo Montessori",
        "philosophy": "Follow the child. Self-directed learning with prepared materials. Multi-sensory, hands-on. The teacher guides, not instructs.",
        "key_principles": [
            "Follow the child's interest and readiness",
            "Hands-on, multi-sensory materials",
            "Self-directed learning with teacher as guide",
            "Mixed-age learning environments",
            "Uninterrupted work periods",
            "Intrinsic motivation over external rewards",
            "Concrete to abstract (similar to CPA)",
        ],
        "best_for": ["self_directed", "hands_on_learners", "creative_thinking", "young_children", "independence"],
        "subjects": ["all"],
        "ai_instruction": (
            "Apply Montessori principles: Follow the student's curiosity. If they're interested "
            "in a topic, go deeper rather than redirecting. Use concrete examples before abstract ones. "
            "Ask them to discover patterns rather than telling them rules. "
            "Encourage them to explain their thinking process. "
            "Offer choices — 'Would you like to practice with fractions or geometry?' "
            "Let mistakes be learning opportunities, not failures."
        ),
    },

    "vedic_math": {
        "origin": "India",
        "name": "Vedic Mathematics",
        "name_native": "वैदिक गणित",
        "philosophy": "Ancient Indian mathematical techniques for rapid mental calculation. 16 sutras (formulas) that simplify complex operations.",
        "key_principles": [
            "16 sutras (concise mental math formulas)",
            "Mental calculation speed and accuracy",
            "Pattern recognition in numbers",
            "Multiple methods for the same problem",
            "Simplification before computation",
            "Cross-checking through complementary methods",
        ],
        "best_for": ["mental_math", "speed_calculation", "math_competitions", "pattern_recognition"],
        "subjects": ["math"],
        "ai_instruction": (
            "Incorporate Vedic Math techniques where appropriate: Teach mental math shortcuts. "
            "For multiplication, show the Nikhilam (complement) method. "
            "For squaring numbers near bases (like 98²), show the base method. "
            "Encourage finding patterns in numbers. Show that there are often faster ways "
            "to solve a problem than the textbook method. Make mental math feel like a superpower."
        ),
    },

    "german_dual": {
        "origin": "Germany",
        "name": "German Didaktik",
        "name_native": "Deutsche Didaktik",
        "philosophy": "Bildung — education as formation of the whole person. Theory and practice intertwined. Emphasis on deep understanding through structured discourse.",
        "key_principles": [
            "Bildung — holistic personal development",
            "Structured classroom discourse",
            "Theory connected to practical application",
            "Guided reinvention (students reconstruct knowledge)",
            "Multiple representations of concepts",
            "Formative assessment through dialogue",
        ],
        "best_for": ["deep_understanding", "structured_learners", "theory_practice_connection", "stem"],
        "subjects": ["math", "science", "philosophy"],
        "ai_instruction": (
            "Apply German Didaktik approach: Connect every concept to both theory and practice. "
            "Use structured questions to guide the student to reconstruct understanding themselves. "
            "Present multiple representations (verbal, visual, symbolic, real-world). "
            "Engage in dialogue — ask the student to explain their reasoning, then build on it. "
            "Treat education as developing the whole person, not just passing tests."
        ),
    },

    "us_common_core": {
        "origin": "United States",
        "name": "US Standards-Based",
        "name_native": "Common Core / State Standards",
        "philosophy": "Standards-based education with emphasis on critical thinking and real-world application. Multiple approaches to problem-solving valued.",
        "key_principles": [
            "Grade-level standards (what every student should know)",
            "Multiple strategies for solving problems",
            "Real-world application and modeling",
            "Mathematical practices (reasoning, precision, structure)",
            "Argumentative writing and evidence-based reasoning",
            "Formative and summative assessment balance",
        ],
        "best_for": ["test_preparation", "college_readiness", "real_world_application", "critical_thinking"],
        "subjects": ["all"],
        "ai_instruction": (
            "Follow US Common Core approach: Ensure grade-level standards are met. "
            "Encourage multiple strategies for solving problems — there's not just one right way. "
            "Connect math to real-world situations. For ELA, emphasize evidence-based reasoning. "
            "Use the mathematical practices: make sense of problems, reason abstractly, "
            "construct arguments, model with mathematics, use tools strategically, "
            "attend to precision, look for structure, express regularity in repeated reasoning."
        ),
    },
}


# ══════════════════════════════════════════════════════════════
# 2. CURRICULUM STANDARDS BY COUNTRY
# ══════════════════════════════════════════════════════════════

CURRICULUM_SYSTEMS = {
    "US": {
        "name": "United States",
        "system": "Common Core State Standards / State Standards",
        "structure": "K-12 (ages 5-18)",
        "key_exams": ["SAT", "ACT", "AP Exams", "State Assessments"],
        "grading": "A-F letter grades, GPA system",
        "school_year": "August/September to May/June",
        "default_method": "us_common_core",
        "compatible_methods": ["singapore_math", "montessori", "kumon", "finnish", "vedic_math"],
    },
    "JP": {
        "name": "Japan",
        "system": "文部科学省 (MEXT) Curriculum",
        "structure": "6-3-3 (Elementary 6yr, Junior High 3yr, High School 3yr)",
        "key_exams": ["Center Test / Common Test (大学入学共通テスト)", "School Entrance Exams"],
        "grading": "5-point scale (5=excellent, 1=poor)",
        "school_year": "April to March",
        "default_method": "kumon",
        "compatible_methods": ["chinese_intensive", "singapore_math"],
    },
    "CN": {
        "name": "China",
        "system": "Ministry of Education Curriculum (课程标准)",
        "structure": "6-3-3 (Primary 6yr, Junior High 3yr, Senior High 3yr)",
        "key_exams": ["Zhongkao (中考)", "Gaokao (高考)"],
        "grading": "Percentage-based (100 point scale)",
        "school_year": "September to June/July",
        "default_method": "chinese_intensive",
        "compatible_methods": ["kumon", "singapore_math"],
    },
    "SG": {
        "name": "Singapore",
        "system": "Singapore MOE Curriculum",
        "structure": "6-4-2 (Primary 6yr, Secondary 4yr, JC 2yr)",
        "key_exams": ["PSLE", "O-Levels", "A-Levels"],
        "grading": "A*-F for national exams",
        "school_year": "January to November",
        "default_method": "singapore_math",
        "compatible_methods": ["chinese_intensive", "kumon"],
    },
    "FI": {
        "name": "Finland",
        "system": "Finnish National Core Curriculum",
        "structure": "9-year comprehensive + upper secondary",
        "key_exams": ["Matriculation Examination (Ylioppilastutkinto)"],
        "grading": "4-10 scale (10=excellent)",
        "school_year": "August to June",
        "default_method": "finnish",
        "compatible_methods": ["montessori"],
    },
    "DE": {
        "name": "Germany",
        "system": "Bildungsstandards + State Curricula (Lehrplan)",
        "structure": "4yr Primary + Gymnasium/Realschule/Hauptschule",
        "key_exams": ["Abitur"],
        "grading": "1-6 scale (1=best, 6=worst)",
        "school_year": "August/September to June/July",
        "default_method": "german_dual",
        "compatible_methods": ["finnish", "montessori"],
    },
    "IN": {
        "name": "India",
        "system": "CBSE / ICSE / State Boards",
        "structure": "5+3+2+2 (New Education Policy 2020)",
        "key_exams": ["Board Exams (Class 10, 12)", "JEE", "NEET"],
        "grading": "Percentage and CGPA",
        "school_year": "April to March",
        "default_method": "vedic_math",
        "compatible_methods": ["kumon", "chinese_intensive", "singapore_math"],
    },
    "BR": {
        "name": "Brazil",
        "system": "BNCC (Base Nacional Comum Curricular)",
        "structure": "9yr Fundamental + 3yr Secondary",
        "key_exams": ["ENEM", "Vestibular"],
        "grading": "0-10 scale",
        "school_year": "February to December",
        "default_method": "us_common_core",
        "compatible_methods": ["montessori", "finnish"],
    },
    "SA": {
        "name": "Saudi Arabia / Middle East",
        "system": "MOE National Curriculum",
        "structure": "6+3+3",
        "key_exams": ["Qudurat", "Tahsili"],
        "grading": "Percentage-based",
        "school_year": "September to June",
        "default_method": "us_common_core",
        "compatible_methods": ["kumon", "singapore_math", "vedic_math"],
    },
    "FR": {
        "name": "France",
        "system": "Éducation Nationale",
        "structure": "5yr Primary + 4yr Collège + 3yr Lycée",
        "key_exams": ["Baccalauréat", "Brevet"],
        "grading": "20-point scale",
        "school_year": "September to July",
        "default_method": "german_dual",
        "compatible_methods": ["finnish", "montessori"],
    },
}


# ══════════════════════════════════════════════════════════════
# 3. PEDAGOGY ENGINE
# ══════════════════════════════════════════════════════════════

class PedagogyEngine:
    """Blend teaching methods based on student's background and location."""

    def get_student_pedagogy(self, current_country: str,
                              cultural_background: str = "",
                              preferred_methods: list = None,
                              age: int = 10,
                              subject: str = "math",
                              learning_style: str = "") -> dict:
        """Build a personalized pedagogy profile.

        Args:
            current_country: Where the student is now (determines curriculum)
            cultural_background: Student's heritage country (influences methods)
            preferred_methods: Explicitly chosen methods
            age: Student's age
            subject: Primary subject
            learning_style: visual, auditory, kinesthetic, reading_writing
        """
        # Determine curriculum
        curriculum = CURRICULUM_SYSTEMS.get(current_country,
                     CURRICULUM_SYSTEMS.get("US"))

        # Determine teaching methods
        methods = []

        # Primary: curriculum's default method
        primary_method = curriculum.get("default_method", "us_common_core")
        methods.append(primary_method)

        # Secondary: cultural background method if different
        if cultural_background and cultural_background != current_country:
            bg_curriculum = CURRICULUM_SYSTEMS.get(cultural_background, {})
            bg_method = bg_curriculum.get("default_method")
            if bg_method and bg_method != primary_method:
                methods.append(bg_method)

        # Tertiary: user-preferred methods
        if preferred_methods:
            for m in preferred_methods:
                if m not in methods and m in TEACHING_METHODS:
                    methods.append(m)

        # Learning style enhancement
        if learning_style == "visual" and "singapore_math" not in methods:
            methods.append("singapore_math")  # CPA is great for visual learners
        if learning_style == "kinesthetic" and "montessori" not in methods:
            methods.append("montessori")  # Hands-on focus

        # Build method details
        method_details = []
        for m in methods[:3]:  # Max 3 methods blended
            detail = TEACHING_METHODS.get(m, {})
            method_details.append({
                "id": m,
                "name": detail.get("name", m),
                "origin": detail.get("origin", ""),
                "philosophy": detail.get("philosophy", ""),
                "key_principles": detail.get("key_principles", []),
            })

        return {
            "student_profile": {
                "current_country": current_country,
                "cultural_background": cultural_background or current_country,
                "age": age,
                "subject": subject,
                "learning_style": learning_style,
            },
            "curriculum": {
                "country": curriculum.get("name", ""),
                "system": curriculum.get("system", ""),
                "key_exams": curriculum.get("key_exams", []),
                "grading": curriculum.get("grading", ""),
            },
            "teaching_methods": method_details,
            "primary_method": methods[0],
            "blended_methods": methods,
        }

    def build_ai_instruction(self, current_country: str,
                              cultural_background: str = "",
                              preferred_methods: list = None,
                              age: int = 10,
                              subject: str = "math",
                              learning_style: str = "") -> str:
        """Build complete AI instruction combining curriculum + methods + age."""
        pedagogy = self.get_student_pedagogy(
            current_country, cultural_background, preferred_methods,
            age, subject, learning_style)

        parts = []

        # Curriculum context
        curr = pedagogy["curriculum"]
        parts.append(
            f"CURRICULUM: This student follows {curr['system']} in {curr['country']}. "
            f"They will be assessed through: {', '.join(curr.get('key_exams', [])[:3])}. "
            f"Ensure your teaching aligns with these standards."
        )

        # Teaching methods
        for method_id in pedagogy["blended_methods"][:3]:
            method = TEACHING_METHODS.get(method_id, {})
            instruction = method.get("ai_instruction", "")
            if instruction:
                parts.append(f"\nMETHOD ({method.get('name', '')}): {instruction}")

        # Cultural context for international students
        if cultural_background and cultural_background != current_country:
            bg_name = CURRICULUM_SYSTEMS.get(cultural_background, {}).get("name", cultural_background)
            curr_name = CURRICULUM_SYSTEMS.get(current_country, {}).get("name", current_country)
            parts.append(
                f"\nCULTURAL CONTEXT: This student has a {bg_name} educational background "
                f"but is currently studying in {curr_name}. They may be familiar with teaching styles "
                f"from their home country. Blend approaches — use {curr_name} curriculum content "
                f"with teaching techniques from {bg_name} when it helps understanding."
            )

        # Learning style
        if learning_style:
            style_tips = {
                "visual": "Use diagrams, charts, bar models, and visual representations. Draw things out.",
                "auditory": "Explain concepts verbally in detail. Use rhythm and repetition for memorization.",
                "kinesthetic": "Use hands-on examples and real-world manipulation. Let them 'do' before 'learn'.",
                "reading_writing": "Provide written explanations. Encourage note-taking and written solutions.",
            }
            if learning_style in style_tips:
                parts.append(f"\nLEARNING STYLE: {style_tips[learning_style]}")

        return "\n".join(parts)

    def get_methods(self) -> dict:
        """Return all available teaching methods."""
        return {k: {
            "name": v["name"],
            "origin": v["origin"],
            "philosophy": v["philosophy"][:150] + "...",
            "best_for": v["best_for"],
        } for k, v in TEACHING_METHODS.items()}

    def get_curricula(self) -> dict:
        """Return all supported curriculum systems."""
        return {k: {
            "name": v["name"],
            "system": v["system"],
            "key_exams": v["key_exams"],
            "default_method": v["default_method"],
        } for k, v in CURRICULUM_SYSTEMS.items()}

    def get_compatible_methods(self, country: str) -> list:
        """Get teaching methods compatible with a country's curriculum."""
        curr = CURRICULUM_SYSTEMS.get(country, CURRICULUM_SYSTEMS.get("US"))
        default = curr.get("default_method", "us_common_core")
        compatible = curr.get("compatible_methods", [])
        all_methods = [default] + compatible
        return [{
            "id": m,
            "name": TEACHING_METHODS.get(m, {}).get("name", m),
            "origin": TEACHING_METHODS.get(m, {}).get("origin", ""),
            "is_default": m == default,
        } for m in all_methods if m in TEACHING_METHODS]
