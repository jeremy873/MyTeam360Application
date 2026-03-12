# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Pedagogy Engine — Teaching methods from around the world.

The way a child learns math in Tokyo is fundamentally different from
how they learn it in Houston — even if the math is the same.

KEY INSIGHT:
  A Japanese family in Las Vegas → US curriculum + Japanese pedagogy blend
  A Japanese family in Tokyo → Japanese curriculum + Japanese pedagogy (pure)
  An American family in Tokyo → Japanese curriculum + American pedagogy blend

This module defines:
  1. Teaching methodologies by country/tradition
  2. Curriculum standards by country
  3. Blending rules (location vs cultural background)
  4. AI instruction injection (how to teach, not just what to teach)

PEDAGOGIES:
  - Japan: Lesson Study, productive struggle, process > answer, bansho
  - China: Mastery repetition, structured progression, teacher-guided discovery
  - Singapore: Concrete-Pictorial-Abstract (CPA), bar modeling, visualization
  - Finland: Play-based (young), student autonomy, minimal testing, equity
  - South Korea: Intense practice, hierarchical respect, collaborative review
  - Montessori: Self-directed, multi-age, hands-on materials, follow the child
  - US Traditional: Standards-based, growth mindset, differentiated, project-based
  - UK: National Curriculum stages, phonics-first reading, form-based learning
  - India: Rote + analytical blend, exam-focused, NCERT framework
"""

import json
import logging

logger = logging.getLogger("MyTeam360.pedagogy")


# ══════════════════════════════════════════════════════════════
# TEACHING METHODOLOGIES
# ══════════════════════════════════════════════════════════════

PEDAGOGIES = {
    "japanese": {
        "name": "Japanese (授業研究)",
        "country": "Japan",
        "philosophy": "The struggle IS the learning. Students discover through guided exploration.",
        "core_principles": [
            "Productive struggle — let students sit with difficulty before helping",
            "Process over answer — HOW you solved it matters more than getting it right",
            "Bansho (板書) — organized board work that shows thinking progression",
            "Lesson Study — carefully structured lessons with predictable flow",
            "Whole-class discussion — students present different approaches to same problem",
            "Hatsumon (発問) — the art of asking the right question at the right time",
            "Neriage (練り上げ) — polishing ideas through class discussion",
        ],
        "math_approach": (
            "Present one carefully chosen problem. Let students work independently for 10-15 minutes. "
            "Do NOT give hints too early — struggle is expected and valued. Then have students share "
            "multiple solution strategies. Compare approaches. Summarize the mathematical principle. "
            "The goal is deep understanding of ONE concept, not coverage of many."
        ),
        "reading_approach": (
            "Close reading with attention to author's craft. Students annotate and discuss in groups. "
            "Emphasis on understanding context and cultural significance."
        ),
        "error_handling": (
            "Mistakes are celebrated as learning opportunities. When a student gets something wrong, "
            "ask the class 'What can we learn from this approach?' Never say 'wrong' — say "
            "'interesting approach — let's examine it together.' Display incorrect solutions "
            "alongside correct ones to build understanding."
        ),
        "ai_instruction": (
            "Use Japanese pedagogy (Lesson Study approach):\n"
            "- Present ONE well-chosen problem, not many\n"
            "- Allow productive struggle — wait at least 2 exchanges before offering hints\n"
            "- When the student tries, ask 'Can you explain your thinking?' before saying if it's correct\n"
            "- If wrong, say 'That's an interesting approach. Let's examine it together.'\n"
            "- Show multiple ways to solve the same problem\n"
            "- Summarize the underlying principle at the end\n"
            "- Process matters more than the answer\n"
            "- Praise effort and reasoning, not just correctness"
        ),
    },

    "chinese": {
        "name": "Chinese (教学法)",
        "country": "China",
        "philosophy": "Mastery through structured practice. Understanding built layer by layer.",
        "core_principles": [
            "Mastery-based progression — don't move forward until current concept is solid",
            "Variation theory — same concept presented with systematic variations",
            "Teacher-guided discovery — structured path to 'aha' moment",
            "Repetition with variation — practice is never mindless, each problem adds complexity",
            "Respect for knowledge — education is honored, effort is expected",
            "Interconnected knowledge — show how concepts connect to what was learned before",
        ],
        "math_approach": (
            "Start with a concrete example. Demonstrate the method step by step. "
            "Give a nearly identical problem for the student to try. Then gradually increase "
            "complexity. Use variation: change one element at a time so the student sees what "
            "each part does. Provide many practice problems grouped by difficulty level. "
            "Connect every new concept to previously learned material."
        ),
        "reading_approach": (
            "Careful text analysis with attention to structure and rhetoric. "
            "Memorization of key passages valued as foundation for understanding. "
            "Writing exercises model exemplary texts."
        ),
        "error_handling": (
            "Errors indicate incomplete understanding. Go back to the foundation. "
            "Re-teach the prerequisite concept, then rebuild. "
            "'Let's make sure our foundation is strong before we continue.'"
        ),
        "ai_instruction": (
            "Use Chinese pedagogy (mastery-based approach):\n"
            "- Check prerequisite understanding before introducing new concepts\n"
            "- Demonstrate the method clearly with a worked example first\n"
            "- Give a nearly identical problem for the student to try\n"
            "- Gradually increase complexity — change one variable at a time\n"
            "- Connect every concept to what they've already learned\n"
            "- If the student struggles, go back to foundations — don't skip ahead\n"
            "- Provide multiple practice problems at each difficulty level\n"
            "- Emphasize precision and completeness in solutions"
        ),
    },

    "singaporean": {
        "name": "Singapore Math (CPA)",
        "country": "Singapore",
        "philosophy": "Concrete → Pictorial → Abstract. See it, draw it, then calculate it.",
        "core_principles": [
            "Concrete-Pictorial-Abstract (CPA) — always start with physical/visual",
            "Bar modeling — visual representation of word problems",
            "Number bonds — decompose numbers to understand relationships",
            "Mastery over speed — understand deeply before moving on",
            "Model drawing — translate words into pictures before equations",
            "Spiral curriculum — revisit concepts with increasing depth",
        ],
        "math_approach": (
            "For every problem: (1) Concrete — use physical objects or examples. "
            "(2) Pictorial — draw a bar model or diagram. (3) Abstract — write the equation. "
            "NEVER skip to the equation. Always start with 'Can you draw this?' "
            "Use bar models for word problems: draw a bar, label the parts, find the unknown. "
            "Number bonds for arithmetic: show how numbers break apart and recombine."
        ),
        "reading_approach": (
            "Structured comprehension with graphic organizers. "
            "Emphasis on extracting information and making inferences from text."
        ),
        "error_handling": (
            "Go back to the pictorial stage. 'Let's draw it out and see what we can find.' "
            "Most errors come from jumping to abstract too quickly."
        ),
        "ai_instruction": (
            "Use Singapore Math pedagogy (CPA approach):\n"
            "- ALWAYS start with a concrete example or visual representation\n"
            "- For math: draw bar models before writing equations\n"
            "- For word problems: 'Let's draw this out first'\n"
            "- Show number bonds for arithmetic (how numbers break apart)\n"
            "- Move to equations ONLY after the student understands the visual\n"
            "- If stuck, go back to pictures — 'Let's see what this looks like'\n"
            "- Emphasize understanding WHY the method works, not just HOW"
        ),
    },

    "finnish": {
        "name": "Finnish (Suomalainen pedagogiikka)",
        "country": "Finland",
        "philosophy": "Trust the child. Less testing, more learning. Play is work for young minds.",
        "core_principles": [
            "Play-based learning for ages 5-8 — learning through exploration and play",
            "Student autonomy — students choose topics and pace when possible",
            "No standardized testing until age 16",
            "Minimal homework — learning happens at school",
            "Equity over excellence — every student supported, no one left behind",
            "Teacher trust — teachers are highly trained professionals given freedom",
            "Outdoor learning — nature as classroom",
            "Wellbeing first — happy students learn better",
        ],
        "math_approach": (
            "For young students: learn through games, physical activities, and exploration. "
            "No worksheets before age 8. Use stories, building, cooking to teach math concepts. "
            "For older students: real-world applications, collaborative problem-solving, "
            "student-led investigation. 'What questions do YOU have about this?'"
        ),
        "reading_approach": (
            "Phonics-based early reading with strong storytelling tradition. "
            "Free reading time valued. Student choice in reading material. "
            "Discussion-based comprehension rather than testing."
        ),
        "error_handling": (
            "Errors are natural and expected. No grades, no judgment. "
            "'That's one way to think about it. What else could we try?' "
            "Focus on the learning process, not the outcome."
        ),
        "ai_instruction": (
            "Use Finnish pedagogy (student-centered approach):\n"
            "- For ages 5-8: use games, stories, and play — NO worksheets or drills\n"
            "- Ask the student what they're curious about\n"
            "- Let them explore before guiding\n"
            "- Never test or quiz — instead ask 'What do you think?' and 'Why?'\n"
            "- Focus on wellbeing: 'Are you having fun learning this?'\n"
            "- Use real-world connections: cooking, building, nature\n"
            "- Celebrate curiosity over correctness\n"
            "- Minimal pressure — learning should feel safe and enjoyable"
        ),
    },

    "south_korean": {
        "name": "South Korean (한국 교육)",
        "country": "South Korea",
        "philosophy": "Diligence and discipline create excellence. Practice perfects understanding.",
        "core_principles": [
            "Rigorous practice — extensive problem sets build mastery",
            "Hierarchical respect — honor the teacher-student relationship",
            "Collaborative review — peer study groups (스터디 그룹)",
            "Test preparation as skill — learning to perform under pressure",
            "Parental involvement — education is a family commitment",
            "Competition as motivation — rankings drive effort",
        ],
        "math_approach": (
            "Thorough concept explanation followed by extensive practice sets. "
            "Problems increase in difficulty systematically. Timed practice for fluency. "
            "Review sessions consolidate learning. Peer discussion of difficult problems."
        ),
        "error_handling": (
            "Analyze mistakes carefully. Keep an error log — track which types of "
            "problems cause difficulty. Revisit weak areas with targeted practice."
        ),
        "ai_instruction": (
            "Use Korean pedagogy (disciplined mastery approach):\n"
            "- Explain concepts thoroughly and precisely\n"
            "- Provide extensive practice — more problems, increasing difficulty\n"
            "- Track which problem types cause errors and revisit them\n"
            "- Encourage the student to keep an error journal\n"
            "- Use timed challenges for fluency building (when appropriate)\n"
            "- Be respectful but direct about areas needing improvement\n"
            "- Connect effort to results: 'Your practice is paying off'"
        ),
    },

    "montessori": {
        "name": "Montessori",
        "country": "International",
        "philosophy": "Follow the child. Hands-on, self-directed, intrinsically motivated.",
        "core_principles": [
            "Follow the child — let interest guide learning",
            "Prepared environment — materials available for discovery",
            "Hands-on materials — concrete before abstract, always",
            "Self-correction — materials designed so student discovers own errors",
            "Multi-age interaction — learning from peers",
            "Uninterrupted work periods — deep focus time",
            "Intrinsic motivation — no grades, no rewards, no punishments",
        ],
        "math_approach": (
            "Use manipulatives: bead chains for multiplication, golden beads for place value, "
            "fraction circles for fractions. Let the student explore the materials. "
            "Ask 'What do you notice?' before teaching. Guide only when asked. "
            "Never interrupt deep concentration."
        ),
        "error_handling": (
            "The materials reveal the error, not the teacher. 'Does that look right to you?' "
            "Let the student self-correct. Only intervene if they're frustrated."
        ),
        "ai_instruction": (
            "Use Montessori pedagogy (child-led approach):\n"
            "- Let the student choose what to explore\n"
            "- Ask 'What do you notice?' and 'What are you curious about?'\n"
            "- Describe hands-on activities: 'Imagine you have 12 blocks...'\n"
            "- When they make errors, ask 'Does that look right to you?'\n"
            "- Don't rush — deep understanding takes time\n"
            "- No grades, no scores — focus on the joy of discovery\n"
            "- Offer choices: 'Would you like to explore X or Y?'\n"
            "- Connect learning to real life and sensory experience"
        ),
    },

    "us_traditional": {
        "name": "US Standards-Based",
        "country": "United States",
        "philosophy": "Growth mindset. Differentiated instruction. Standards-aligned mastery.",
        "core_principles": [
            "Standards-based (Common Core / state standards)",
            "Growth mindset — effort matters more than innate ability",
            "Differentiated instruction — adapt to each learner's level",
            "Formative assessment — check understanding frequently",
            "Project-based learning — apply knowledge to real situations",
            "Social-emotional learning (SEL) integration",
            "Multiple representations — verbal, visual, symbolic, numeric",
        ],
        "math_approach": (
            "Align to grade-level standards. Use multiple representations for every concept. "
            "Emphasize 'productive struggle' but with scaffolding available. "
            "Use formative assessment to check understanding. Differentiate: "
            "provide easier entry points for struggling students, extensions for advanced."
        ),
        "reading_approach": (
            "Balanced literacy: phonics + whole language. Close reading with text evidence. "
            "Reading levels and guided reading groups. Writing across the curriculum."
        ),
        "error_handling": (
            "Growth mindset framing: 'You haven't got it YET.' "
            "Mistakes are proof you're trying. Provide scaffolding — "
            "break the problem into smaller steps."
        ),
        "ai_instruction": (
            "Use US Standards-Based pedagogy:\n"
            "- Align to grade-level expectations (Common Core or state standards)\n"
            "- Use growth mindset language: 'not yet' instead of 'wrong'\n"
            "- Show multiple ways to solve problems (visual, verbal, symbolic)\n"
            "- Provide scaffolding: break hard problems into steps\n"
            "- Check for understanding: 'Can you explain that in your own words?'\n"
            "- Encourage real-world connections and applications\n"
            "- Celebrate effort and perseverance, not just accuracy"
        ),
    },

    "british": {
        "name": "British National Curriculum",
        "country": "United Kingdom",
        "philosophy": "Systematic phonics, key stages, structured progression.",
        "core_principles": [
            "Key Stage progression (KS1-KS4)",
            "Systematic synthetic phonics for early reading",
            "Mastery approach to mathematics",
            "Assessment without levels (since 2014)",
            "Cross-curricular connections",
        ],
        "math_approach": (
            "Mastery-based: whole class moves together, depth before breadth. "
            "Use concrete manipulatives, pictorial representations, then abstract notation. "
            "Variation in practice to deepen understanding."
        ),
        "ai_instruction": (
            "Use British National Curriculum approach:\n"
            "- Systematic phonics for early reading\n"
            "- Mastery mathematics: depth over breadth\n"
            "- Concrete-pictorial-abstract progression\n"
            "- Structured progression through Key Stages\n"
            "- Formal but encouraging tone"
        ),
    },

    "indian": {
        "name": "Indian (NCERT/CBSE)",
        "country": "India",
        "philosophy": "Strong analytical foundation through structured learning and examination.",
        "core_principles": [
            "NCERT framework — structured, comprehensive curriculum",
            "Board examination preparation (CBSE/ICSE/State boards)",
            "Analytical and computational strength emphasis",
            "Rote learning as foundation, analysis as extension",
            "Competitive examination culture (JEE, NEET preparation)",
        ],
        "math_approach": (
            "Thorough concept explanation with derivations and proofs. "
            "Extensive problem practice with worked examples. "
            "Build toward competitive exam difficulty gradually. "
            "Strong emphasis on mental math and calculation speed."
        ),
        "ai_instruction": (
            "Use Indian NCERT pedagogy:\n"
            "- Explain concepts with formal definitions and derivations\n"
            "- Provide worked examples before practice problems\n"
            "- Build calculation speed and mental math skills\n"
            "- Connect to exam patterns and question types when relevant\n"
            "- Thorough, structured, and comprehensive explanations"
        ),
    },
}


# ══════════════════════════════════════════════════════════════
# CURRICULUM STANDARDS BY COUNTRY
# ══════════════════════════════════════════════════════════════

CURRICULUM_STANDARDS = {
    "US": {
        "name": "US Standards",
        "math": "Common Core State Standards (CCSS) / State Standards",
        "reading": "Common Core ELA / State Standards",
        "science": "Next Generation Science Standards (NGSS)",
        "grade_system": "K-12",
        "advanced": ["AP", "IB", "Honors"],
    },
    "JP": {
        "name": "Japanese Curriculum",
        "math": "MEXT Course of Study (学習指導要領)",
        "reading": "Kokugo (国語) National Language",
        "science": "Rika (理科) Science",
        "grade_system": "1-12 (6-3-3 system)",
        "advanced": ["University Entrance Exam preparation"],
    },
    "CN": {
        "name": "Chinese Curriculum",
        "math": "Ministry of Education Mathematics Standards",
        "reading": "Yuwen (语文) Chinese Language",
        "science": "Kexue (科学) Science",
        "grade_system": "1-12 (6-3-3 system)",
        "advanced": ["Gaokao (高考) preparation"],
    },
    "SG": {
        "name": "Singapore Curriculum",
        "math": "Singapore Mathematics Curriculum Framework",
        "reading": "English Language Syllabus",
        "science": "Science Syllabus",
        "grade_system": "Primary 1-6, Secondary 1-5, JC 1-2",
        "advanced": ["GCE A-Level", "IB"],
    },
    "FI": {
        "name": "Finnish National Core Curriculum",
        "math": "Perusopetuksen opetussuunnitelma — Mathematics",
        "reading": "Äidinkieli ja kirjallisuus (Mother tongue and literature)",
        "science": "Ympäristöoppi (Environmental studies) / Fysiikka, Kemia, Biologia",
        "grade_system": "1-9 comprehensive, Upper secondary 1-3",
        "advanced": ["Ylioppilastutkinto (Matriculation examination)"],
    },
    "KR": {
        "name": "Korean National Curriculum",
        "math": "Suhak (수학) Mathematics",
        "reading": "Gukeo (국어) Korean Language",
        "science": "Gwahak (과학) Science",
        "grade_system": "1-12 (6-3-3 system)",
        "advanced": ["Suneung (수능) CSAT preparation"],
    },
    "GB": {
        "name": "UK National Curriculum",
        "math": "Mathematics Programme of Study",
        "reading": "English Programme of Study",
        "science": "Science Programme of Study",
        "grade_system": "Key Stages 1-4, Sixth Form",
        "advanced": ["GCSE", "A-Level", "IB"],
    },
    "IN": {
        "name": "Indian NCERT/CBSE",
        "math": "NCERT Mathematics",
        "reading": "English / Hindi Language",
        "science": "NCERT Science",
        "grade_system": "1-12 (5+3+2+2)",
        "advanced": ["JEE", "NEET", "Board Examinations"],
    },
}


# ══════════════════════════════════════════════════════════════
# BLENDING ENGINE
# ══════════════════════════════════════════════════════════════

class PedagogyEngine:
    """Blend teaching methods based on student's location + cultural background.

    Examples:
      Japanese family in Las Vegas:
        curriculum = US (they're in a US school)
        pedagogy = japanese (70%) + us_traditional (30%)
        → US math standards taught with Japanese productive-struggle method

      American family in Tokyo:
        curriculum = JP (they're in a Japanese school, likely international)
        pedagogy = us_traditional (60%) + japanese (40%)
        → Japanese curriculum taught with growth-mindset scaffolding

      Singaporean family in Singapore:
        curriculum = SG
        pedagogy = singaporean (100%)
        → Pure Singapore Math

      Indian family in London:
        curriculum = GB (UK schools)
        pedagogy = indian (50%) + british (50%)
        → UK curriculum with Indian analytical rigor
    """

    # Map countries to default pedagogy
    COUNTRY_PEDAGOGY = {
        "US": "us_traditional", "JP": "japanese", "CN": "chinese",
        "SG": "singaporean", "FI": "finnish", "KR": "south_korean",
        "GB": "british", "IN": "indian",
    }

    def get_profile(self, location_country: str, cultural_background: str = "",
                     preferred_method: str = "", age: int = 10) -> dict:
        """Build a complete pedagogical profile for a student.

        Args:
            location_country: Where the student lives (2-letter code)
            cultural_background: Family's cultural origin (2-letter code, optional)
            preferred_method: Override with a specific method (optional)
            age: Student's age
        """
        # Determine curriculum (based on where they ARE)
        curriculum = CURRICULUM_STANDARDS.get(location_country,
                     CURRICULUM_STANDARDS.get("US"))

        # Determine pedagogy blend
        if preferred_method and preferred_method in PEDAGOGIES:
            # User explicitly chose a method
            primary = PEDAGOGIES[preferred_method]
            blend = [{"method": preferred_method, "weight": 100}]
        elif cultural_background and cultural_background != location_country:
            # Different culture than location — blend both
            cultural_method = self.COUNTRY_PEDAGOGY.get(cultural_background, "us_traditional")
            local_method = self.COUNTRY_PEDAGOGY.get(location_country, "us_traditional")
            primary = PEDAGOGIES.get(cultural_method, PEDAGOGIES["us_traditional"])
            secondary = PEDAGOGIES.get(local_method, PEDAGOGIES["us_traditional"])
            blend = [
                {"method": cultural_method, "weight": 60},
                {"method": local_method, "weight": 40},
            ]
        else:
            # Same culture as location or no culture specified
            method = self.COUNTRY_PEDAGOGY.get(location_country, "us_traditional")
            primary = PEDAGOGIES.get(method, PEDAGOGIES["us_traditional"])
            blend = [{"method": method, "weight": 100}]

        # Age adjustments
        if age <= 7 and "finnish" not in [b["method"] for b in blend]:
            # Young kids benefit from Finnish play-based elements regardless
            blend.append({"method": "finnish_elements", "weight": 10,
                         "note": "Play-based elements for young learners"})

        return {
            "location": location_country,
            "cultural_background": cultural_background or location_country,
            "curriculum": curriculum,
            "pedagogy_blend": blend,
            "primary_pedagogy": primary,
            "age": age,
        }

    def build_ai_instruction(self, location_country: str,
                               cultural_background: str = "",
                               preferred_method: str = "",
                               age: int = 10) -> str:
        """Build the complete AI teaching instruction for this student."""
        profile = self.get_profile(location_country, cultural_background,
                                    preferred_method, age)
        curriculum = profile["curriculum"]
        blend = profile["pedagogy_blend"]

        parts = [
            f"CURRICULUM: Follow {curriculum['name']} standards for this student's grade level.",
        ]

        if curriculum.get("math"):
            parts.append(f"Math standards: {curriculum['math']}")
        if curriculum.get("science"):
            parts.append(f"Science standards: {curriculum['science']}")

        parts.append("")

        # Add pedagogy instructions
        if len(blend) == 1 or (len(blend) == 2 and blend[-1].get("note")):
            # Single method (or single + young-child supplement)
            method_key = blend[0]["method"]
            method = PEDAGOGIES.get(method_key, {})
            parts.append(f"TEACHING METHOD: {method.get('name', method_key)}")
            parts.append(method.get("ai_instruction", ""))
        else:
            # Blended method
            for b in blend:
                method_key = b["method"]
                if method_key == "finnish_elements":
                    parts.append("\nADDITIONAL: For this young student, incorporate play-based "
                               "elements — games, stories, and exploration — alongside the primary method.")
                    continue
                method = PEDAGOGIES.get(method_key, {})
                weight = b["weight"]
                parts.append(f"\nTEACHING METHOD ({weight}% emphasis): {method.get('name', method_key)}")
                parts.append(method.get("ai_instruction", ""))

        # Error handling from primary method
        primary = profile["primary_pedagogy"]
        if primary.get("error_handling"):
            parts.append(f"\nWHEN STUDENT MAKES ERRORS:\n{primary['error_handling']}")

        return "\n".join(parts)

    def get_available_methods(self) -> list:
        """List all available teaching methods for the settings UI."""
        return [
            {
                "id": k,
                "name": v["name"],
                "country": v["country"],
                "philosophy": v["philosophy"],
                "principles_count": len(v.get("core_principles", [])),
            }
            for k, v in PEDAGOGIES.items()
        ]

    def get_method_detail(self, method_id: str) -> dict:
        """Get full detail on a teaching method."""
        m = PEDAGOGIES.get(method_id)
        if not m:
            return {"error": f"Method not found. Options: {list(PEDAGOGIES.keys())}"}
        return {"id": method_id, **m}

    def get_curriculum(self, country_code: str) -> dict:
        """Get curriculum standards for a country."""
        return CURRICULUM_STANDARDS.get(country_code, CURRICULUM_STANDARDS.get("US"))

    def get_all_curricula(self) -> dict:
        return CURRICULUM_STANDARDS
