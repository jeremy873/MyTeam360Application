# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Education Cultural Themes — Mascots + culture-specific design overlays.

MASCOTS by age group:
  5-7:   Full character with face, personality, expressions (Sparky)
  8-10:  Cool companion — same character, matured, adventure-ready
  11-13: Abstract icon — geometric, no face, feels "smart not cute"
  14-18: Standard brand logo — treated as adults

CULTURAL OVERLAYS by language/region:
  Each culture gets adjustments to:
  - Color meaning (red = error in US, luck in China)
  - Mascot style (kawaii in Japan, geometric in Arabic, warm in LatAm)
  - Layout direction (RTL for Arabic/Hebrew)
  - Celebration style (different cultures celebrate differently)
  - Formality level (French education is more formal than American)
  - Character design cues (eyes, expressions, clothing hints)
"""

import json
import logging

logger = logging.getLogger("MyTeam360.edu_culture")


# ══════════════════════════════════════════════════════════════
# MASCOTS — Age-Adaptive Characters
# ══════════════════════════════════════════════════════════════

MASCOTS = {
    "early_elementary": {
        "name": "Sparky",
        "type": "character",
        "description": (
            "A friendly, glowing golden star with big expressive eyes, "
            "a warm smile, and tiny waving arms. Round, soft, approachable. "
            "Bounces and sparkles when celebrating correct answers."
        ),
        "svg": {
            "shape": "star_character",
            "primary_color": "#F7B32B",
            "secondary_color": "#FDE68A",
            "glow_color": "#FEF3C7",
            "eye_color": "#2D3748",
            "has_face": True,
            "has_arms": True,
            "size_px": 120,
            "border_radius": "50%",
        },
        "expressions": {
            "default": {"eyes": "happy", "mouth": "smile", "animation": "gentle_float"},
            "thinking": {"eyes": "looking_up", "mouth": "hmm", "animation": "slow_spin"},
            "celebrating": {"eyes": "stars", "mouth": "big_grin", "animation": "bounce_sparkle"},
            "encouraging": {"eyes": "warm", "mouth": "smile", "animation": "nod"},
            "wrong_answer": {"eyes": "gentle", "mouth": "small_smile", "animation": "tilt_head"},
        },
        "animations": {
            "entrance": "pop_in_with_sparkles",
            "correct": "jump_and_spin_with_confetti",
            "wrong": "gentle_shake_then_encourage",
            "thinking": "float_with_thought_bubble",
            "idle": "gentle_breathing_glow",
            "farewell": "wave_and_float_away",
        },
        "show_in": ["chat_header", "loading_screen", "celebration", "empty_state", "sidebar"],
    },

    "upper_elementary": {
        "name": "Scout",
        "type": "companion",
        "description": (
            "Same star character but matured — wearing a small backpack, "
            "holding a magnifying glass or book. Teal/coral palette. "
            "Adventure explorer vibe. Confident posture, still friendly "
            "but not babyish. Gives fist bumps instead of sparkles."
        ),
        "svg": {
            "shape": "star_explorer",
            "primary_color": "#06B6D4",
            "secondary_color": "#67E8F9",
            "glow_color": "#ECFEFF",
            "eye_color": "#1E293B",
            "has_face": True,
            "has_arms": True,
            "has_accessory": True,
            "accessory": "backpack_and_magnifier",
            "size_px": 96,
            "border_radius": "40%",
        },
        "expressions": {
            "default": {"eyes": "confident", "mouth": "friendly_grin", "animation": "idle_ready"},
            "thinking": {"eyes": "focused", "mouth": "determined", "animation": "magnifier_examine"},
            "celebrating": {"eyes": "excited", "mouth": "big_grin", "animation": "fist_bump"},
            "encouraging": {"eyes": "warm", "mouth": "thumbs_up", "animation": "nod_forward"},
            "wrong_answer": {"eyes": "supportive", "mouth": "slight_smile", "animation": "point_to_hint"},
        },
        "animations": {
            "entrance": "slide_in_from_side",
            "correct": "fist_bump_with_stars",
            "wrong": "point_to_hint_gently",
            "thinking": "examine_with_magnifier",
            "idle": "subtle_sway",
            "farewell": "wave_and_walk_away",
        },
        "show_in": ["chat_header", "celebration", "empty_state"],
    },

    "middle_school": {
        "name": "Prism",
        "type": "abstract_icon",
        "description": (
            "Clean geometric shape — a stylized brain made of connected "
            "hexagons, or a glowing prism/crystal. No face, no personality. "
            "Purple/blue gradient. Feels intelligent and modern. "
            "Subtle glow animation. Students this age reject 'cute.'"
        ),
        "svg": {
            "shape": "geometric_prism",
            "primary_color": "#7C3AED",
            "secondary_color": "#3B82F6",
            "glow_color": "#EDE9FE",
            "has_face": False,
            "has_arms": False,
            "size_px": 48,
            "border_radius": "12px",
            "gradient": "linear-gradient(135deg, #7C3AED, #3B82F6)",
        },
        "expressions": {
            "default": {"animation": "subtle_glow_pulse"},
            "thinking": {"animation": "rotate_slow"},
            "celebrating": {"animation": "brightness_flash"},
            "encouraging": {"animation": "pulse_once"},
        },
        "animations": {
            "entrance": "fade_in",
            "correct": "brief_glow",
            "wrong": "none",
            "thinking": "slow_rotate",
            "idle": "subtle_pulse",
        },
        "show_in": ["loading_screen"],
    },

    "high_school": {
        "name": "MyTeam360",
        "type": "brand_logo",
        "description": (
            "Standard MyTeam360 logo — the purple circular swirl. "
            "No mascot, no character. Treated as the adult/professional "
            "experience. Respects their maturity."
        ),
        "svg": {
            "shape": "brand_logo",
            "primary_color": "#A459F2",
            "secondary_color": "#3B82F6",
            "size_px": 36,
            "border_radius": "8px",
        },
        "expressions": {},
        "animations": {
            "entrance": "none",
            "correct": "none",
            "thinking": "none",
            "idle": "none",
        },
        "show_in": ["nav_header"],
    },
}


# ══════════════════════════════════════════════════════════════
# CULTURAL OVERLAYS — Country/region-specific adjustments
# ══════════════════════════════════════════════════════════════

CULTURAL_OVERLAYS = {
    "en_us": {
        "region": "United States",
        "layout_direction": "ltr",
        "mascot_style": "western_cartoon",
        "color_overrides": {},  # Default colors work for US
        "celebration_style": "confetti_and_stars",
        "formality": "casual",
        "mascot_adjustments": {
            "early_elementary": {"accessory_hint": "baseball_cap"},
        },
        "color_meanings": {
            "success": "#22C55E",   # Green = good
            "error": "#EF4444",     # Red = bad
            "warning": "#F59E0B",   # Yellow = caution
        },
        "education_context": {
            "grade_system": "K-12",
            "school_year": "September to June",
        },
    },

    "ja": {
        "region": "Japan",
        "layout_direction": "ltr",
        "mascot_style": "kawaii",
        "color_overrides": {
            "early_elementary": {
                "primary": "#FF6B9D",       # Sakura pink
                "secondary": "#FFB3D1",
                "background": "#FFF5F8",
                "accent": "#7DD3FC",        # Soft sky blue
            },
            "upper_elementary": {
                "primary": "#06B6D4",
                "accent": "#FF6B9D",        # Keep pink accent
            },
        },
        "celebration_style": "cherry_blossom_confetti",
        "formality": "respectful",
        "mascot_adjustments": {
            "early_elementary": {
                "style": "kawaii",
                "eyes": "large_round_sparkle",
                "mouth": "small_cat_smile",
                "blush": True,
                "blush_color": "#FFB3D1",
                "proportion": "large_head_small_body",
                "accessory_hint": "hachimaki_headband",
            },
            "upper_elementary": {
                "style": "kawaii_mature",
                "eyes": "determined_sparkle",
                "accessory_hint": "school_randoseru_backpack",
            },
            "middle_school": {
                "style": "anime_minimal",
                "note": "Kawaii still acceptable at this age in Japan",
                "has_face": True,
                "eyes": "confident_anime",
            },
        },
        "color_meanings": {
            "success": "#22C55E",
            "error": "#EF4444",
            "celebration": "#FF6B9D",   # Pink celebrations
        },
        "education_context": {
            "grade_system": "Elementary 1-6, Middle 1-3, High 1-3",
            "school_year": "April to March",
        },
    },

    "zh": {
        "region": "China",
        "layout_direction": "ltr",
        "mascot_style": "rounded_friendly",
        "color_overrides": {
            "early_elementary": {
                "primary": "#EF4444",       # Red = lucky, positive
                "secondary": "#F7B32B",     # Gold = prosperity
                "background": "#FFFBEB",
                "accent": "#F97316",        # Warm orange
            },
            "upper_elementary": {
                "accent": "#EF4444",        # Red accent stays
            },
        },
        "celebration_style": "fireworks_and_lanterns",
        "formality": "respectful",
        "mascot_adjustments": {
            "early_elementary": {
                "style": "rounded_lucky",
                "primary_color": "#EF4444",
                "secondary_color": "#F7B32B",
                "accessory_hint": "lucky_cloud",
                "shape_modifier": "more_round",
            },
            "upper_elementary": {
                "accessory_hint": "scholar_scroll",
            },
        },
        "color_meanings": {
            "success": "#22C55E",
            "lucky": "#EF4444",         # Red = lucky, NOT error
            "error": "#9CA3AF",         # Gray for errors instead of red
            "prosperity": "#F7B32B",    # Gold
            "celebration": "#EF4444",   # Red celebrations
        },
        "education_context": {
            "grade_system": "Primary 1-6, Middle 1-3, High 1-3",
            "school_year": "September to July",
        },
    },

    "es": {
        "region": "Latin America / Spain",
        "layout_direction": "ltr",
        "mascot_style": "warm_vibrant",
        "color_overrides": {
            "early_elementary": {
                "primary": "#F97316",       # Warm orange
                "secondary": "#FBBF24",     # Sunny gold
                "accent": "#06B6D4",        # Teal
                "background": "#FFF7ED",    # Warm cream
            },
        },
        "celebration_style": "fiesta_confetti",
        "formality": "warm_casual",
        "mascot_adjustments": {
            "early_elementary": {
                "style": "warm_expressive",
                "eyes": "large_warm",
                "expression_intensity": "high",
                "primary_color": "#F97316",
                "accessory_hint": "sombrero_hint",
            },
        },
        "color_meanings": {
            "success": "#22C55E",
            "error": "#EF4444",
            "celebration": "#F97316",
        },
        "education_context": {
            "grade_system": "Primaria 1-6, Secundaria 1-3, Preparatoria 1-3",
            "school_year": "August/September to June/July (varies by country)",
        },
    },

    "fr": {
        "region": "France",
        "layout_direction": "ltr",
        "mascot_style": "elegant_minimal",
        "color_overrides": {
            "early_elementary": {
                "primary": "#6366F1",       # Soft indigo (more elegant)
                "secondary": "#A78BFA",     # Lavender
                "background": "#F5F3FF",    # Light lavender
            },
        },
        "celebration_style": "subtle_sparkle",
        "formality": "more_formal",
        "mascot_adjustments": {
            "early_elementary": {
                "style": "elegant_friendly",
                "expression_intensity": "moderate",
                "accessory_hint": "beret_hint",
                "note": "French education is more formal — mascot slightly more refined",
            },
            "middle_school": {
                "note": "French middle school (collège) is quite formal — minimal mascot",
            },
        },
        "color_meanings": {
            "success": "#22C55E",
            "error": "#EF4444",
        },
        "education_context": {
            "grade_system": "CP-CM2 (Primary), 6e-3e (Collège), 2nde-Terminale (Lycée)",
            "school_year": "September to July",
        },
    },

    "pt": {
        "region": "Brazil / Portugal",
        "layout_direction": "ltr",
        "mascot_style": "warm_playful",
        "color_overrides": {
            "early_elementary": {
                "primary": "#22C55E",       # Green (Brazilian flag)
                "secondary": "#FBBF24",     # Gold
                "accent": "#06B6D4",
                "background": "#F0FDF4",
            },
        },
        "celebration_style": "carnival_confetti",
        "formality": "warm_casual",
        "mascot_adjustments": {
            "early_elementary": {
                "style": "playful_tropical",
                "expression_intensity": "high",
                "primary_color": "#22C55E",
                "secondary_color": "#FBBF24",
                "accessory_hint": "tropical_leaf",
            },
        },
        "color_meanings": {
            "success": "#22C55E",
            "error": "#EF4444",
            "celebration": "#FBBF24",
        },
        "education_context": {
            "grade_system": "Fundamental I (1-5), Fundamental II (6-9), Ensino Médio (1-3)",
            "school_year": "February to December",
        },
    },

    "ar": {
        "region": "Arabic-speaking countries",
        "layout_direction": "rtl",
        "mascot_style": "geometric_warm",
        "color_overrides": {
            "early_elementary": {
                "primary": "#059669",       # Emerald green (Islamic culture)
                "secondary": "#F7B32B",     # Gold
                "accent": "#06B6D4",        # Teal
                "background": "#ECFDF5",    # Light green tint
            },
            "middle_school": {
                "primary": "#059669",
                "accent": "#F7B32B",
            },
        },
        "celebration_style": "geometric_pattern_reveal",
        "formality": "respectful_formal",
        "mascot_adjustments": {
            "early_elementary": {
                "style": "geometric_friendly",
                "shape": "octagonal_star",
                "primary_color": "#059669",
                "secondary_color": "#F7B32B",
                "pattern": "islamic_geometric_subtle",
                "eyes": "warm_round",
                "note": "Geometric patterns are culturally significant — incorporate into character design",
            },
            "upper_elementary": {
                "style": "geometric_companion",
                "pattern": "arabesque_subtle",
            },
            "middle_school": {
                "style": "calligraphic_icon",
                "note": "Arabic calligraphy-inspired abstract mark",
            },
        },
        "color_meanings": {
            "success": "#059669",       # Green is very positive in Islamic culture
            "error": "#EF4444",
            "sacred": "#059669",        # Green
            "prosperity": "#F7B32B",    # Gold
        },
        "education_context": {
            "grade_system": "Varies by country — typically Primary 1-6, Preparatory 1-3, Secondary 1-3",
            "school_year": "September to June (most countries)",
            "direction": "RTL — all layouts must mirror",
        },
    },
}


# ══════════════════════════════════════════════════════════════
# CULTURAL THEME ENGINE
# ══════════════════════════════════════════════════════════════

class CulturalThemeEngine:
    """Merge age themes + cultural overlays into a complete theme."""

    def get_mascot(self, age_group: str, language: str = "en") -> dict:
        """Get the mascot definition, adjusted for culture."""
        base_mascot = MASCOTS.get(age_group, MASCOTS["high_school"]).copy()
        culture = self._get_culture(language)
        adjustments = culture.get("mascot_adjustments", {}).get(age_group, {})

        if adjustments:
            # Merge culture-specific mascot adjustments
            base_mascot["cultural_adjustments"] = adjustments
            # Override SVG colors if culture specifies
            if "primary_color" in adjustments:
                base_mascot["svg"]["primary_color"] = adjustments["primary_color"]
            if "secondary_color" in adjustments:
                base_mascot["svg"]["secondary_color"] = adjustments["secondary_color"]
            if "style" in adjustments:
                base_mascot["cultural_style"] = adjustments["style"]
            if adjustments.get("has_face") is not None:
                base_mascot["svg"]["has_face"] = adjustments["has_face"]

        base_mascot["culture"] = language
        base_mascot["mascot_global_style"] = culture.get("mascot_style", "western_cartoon")
        return base_mascot

    def get_cultural_colors(self, age_group: str, language: str = "en") -> dict:
        """Get color palette adjusted for cultural context."""
        from .edu_theme import THEMES
        base_colors = THEMES.get(age_group, THEMES["high_school"])["colors"].copy()
        culture = self._get_culture(language)

        # Apply cultural color overrides
        overrides = culture.get("color_overrides", {}).get(age_group, {})
        for key, value in overrides.items():
            if key in base_colors:
                base_colors[key] = value

        # Apply cultural color meanings
        meanings = culture.get("color_meanings", {})
        if meanings:
            base_colors["cultural_meanings"] = meanings

        return base_colors

    def get_celebration_style(self, age_group: str, language: str = "en") -> dict:
        """Get celebration style adjusted for culture."""
        from .edu_theme import THEMES
        base = THEMES.get(age_group, THEMES["high_school"]).get("celebrations", {}).copy()
        culture = self._get_culture(language)
        base["cultural_style"] = culture.get("celebration_style", "confetti_and_stars")
        return base

    def get_full_cultural_theme(self, age_group: str, language: str = "en") -> dict:
        """Get the complete theme: age + culture merged."""
        from .edu_theme import THEMES, AGE_GROUPS
        base_theme = THEMES.get(age_group, THEMES["high_school"])
        culture = self._get_culture(language)

        return {
            "age_group": age_group,
            "age_info": AGE_GROUPS.get(age_group, {}),
            "language": language,
            "region": culture.get("region", ""),
            "layout_direction": culture.get("layout_direction", "ltr"),
            "formality": culture.get("formality", "casual"),
            "mascot": self.get_mascot(age_group, language),
            "colors": self.get_cultural_colors(age_group, language),
            "celebrations": self.get_celebration_style(age_group, language),
            "education_context": culture.get("education_context", {}),
            "theme_name": base_theme.get("name", ""),
            "typography": base_theme.get("typography", {}),
            "ui": base_theme.get("ui", {}),
            "complexity": base_theme.get("complexity", "standard"),
        }

    def get_all_mascots(self) -> dict:
        """Get all mascot definitions for all age groups."""
        return MASCOTS

    def get_all_cultures(self) -> dict:
        """Get all cultural overlay definitions."""
        return {k: {"region": v["region"], "direction": v["layout_direction"],
                     "mascot_style": v["mascot_style"], "formality": v["formality"],
                     "celebration": v["celebration_style"]}
                for k, v in CULTURAL_OVERLAYS.items()}

    def _get_culture(self, language: str) -> dict:
        """Get culture overlay, falling back to en_us for unknowns."""
        # Try exact match first, then language-only
        if language in CULTURAL_OVERLAYS:
            return CULTURAL_OVERLAYS[language]
        # Map language codes to culture codes
        lang_map = {
            "en": "en_us", "es": "es", "fr": "fr",
            "pt": "pt", "zh": "zh", "ja": "ja", "ar": "ar",
        }
        culture_key = lang_map.get(language, "en_us")
        return CULTURAL_OVERLAYS.get(culture_key, CULTURAL_OVERLAYS["en_us"])
