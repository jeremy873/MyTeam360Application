# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Education Theme Engine — Age-adaptive interface design.

The platform looks and feels different based on the student's age:

  Ages 5-7  (Early Elementary):
    - Bright, playful colors (sky blue, sunshine yellow, grass green)
    - Large rounded fonts, big buttons, lots of whitespace
    - Emojis and illustrations everywhere
    - Simple vocabulary ("Your Helper" not "AI Space")
    - One-tap interactions, minimal text input
    - Celebration animations for correct answers

  Ages 8-10 (Upper Elementary):
    - Fun but slightly more structured colors (teal, coral, lavender)
    - Friendly fonts, medium buttons
    - Some emojis, encouraging language
    - Slightly more complex vocabulary
    - Gamification elements (stars, streaks, badges)

  Ages 11-13 (Middle School):
    - Cool, modern colors (blue-purple, teal, slate)
    - Clean fonts, standard buttons
    - Minimal emojis, more mature language
    - Full vocabulary with explanations for complex terms
    - Progress tracking, study streaks, subject mastery

  Ages 14-18 (High School):
    - Professional but approachable (purple/blue brand palette)
    - Standard UI with study tools emphasis
    - No emojis in UI, professional tone
    - Full vocabulary, advanced features
    - AP/IB support, college prep, essay tools

Each theme defines:
  - Color palette (primary, secondary, accent, background, text)
  - Typography (font family, heading sizes, body size)
  - UI vocabulary (what things are called)
  - Icon style (emoji vs. minimal vs. none)
  - AI personality (playful vs. encouraging vs. professional)
  - Celebration style (confetti vs. badge vs. subtle checkmark)
  - Complexity level (simplified vs. standard vs. advanced)
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger("MyTeam360.edu_theme")


# ══════════════════════════════════════════════════════════════
# AGE GROUP DEFINITIONS
# ══════════════════════════════════════════════════════════════

AGE_GROUPS = {
    "early_elementary": {
        "label": "Early Explorer",
        "ages": "5-7",
        "min_age": 5,
        "max_age": 7,
        "grade_range": "K-2",
    },
    "upper_elementary": {
        "label": "Young Learner",
        "ages": "8-10",
        "min_age": 8,
        "max_age": 10,
        "grade_range": "3-5",
    },
    "middle_school": {
        "label": "Rising Scholar",
        "ages": "11-13",
        "min_age": 11,
        "max_age": 13,
        "grade_range": "6-8",
    },
    "high_school": {
        "label": "Academic",
        "ages": "14-18",
        "min_age": 14,
        "max_age": 18,
        "grade_range": "9-12",
    },
}


# ══════════════════════════════════════════════════════════════
# THEME DEFINITIONS
# ══════════════════════════════════════════════════════════════

THEMES = {
    "early_elementary": {
        "name": "Sunshine Explorer",
        "colors": {
            "primary": "#4CC9F0",       # Sky blue
            "secondary": "#F7B32B",     # Sunshine yellow
            "accent": "#7BDB6A",        # Grass green
            "accent2": "#FF6B6B",       # Friendly red
            "accent3": "#C77DFF",       # Soft purple
            "background": "#FFF8E7",    # Warm cream
            "surface": "#FFFFFF",
            "text_primary": "#2D3748",
            "text_secondary": "#5A6778",
            "success": "#7BDB6A",
            "warning": "#F7B32B",
            "error": "#FF6B6B",
            "border": "#E8E0D0",
        },
        "typography": {
            "font_family": "'Nunito', 'Comic Neue', 'Fredoka One', sans-serif",
            "heading_size": "28px",
            "body_size": "18px",
            "button_size": "18px",
            "line_height": "1.8",
            "letter_spacing": "0.5px",
            "font_weight_normal": "600",
            "font_weight_bold": "800",
        },
        "ui": {
            "border_radius": "20px",
            "button_radius": "50px",
            "button_padding": "16px 32px",
            "card_padding": "24px",
            "card_shadow": "0 4px 20px rgba(76, 201, 240, 0.15)",
            "input_height": "56px",
            "icon_size": "32px",
            "spacing": "20px",
            "max_width": "680px",
        },
        "vocabulary": {
            "space": "Helper",
            "conversation": "Chat",
            "knowledge_base": "My Stuff",
            "send_message": "Ask!",
            "new_conversation": "New Chat!",
            "settings": "My Settings",
            "dashboard": "My Learning",
            "profile": "About Me",
            "logout": "Bye for now!",
            "help": "I need help!",
            "loading": "Thinking...",
            "error": "Oops! Something went wrong",
            "welcome": "Hi there! Ready to learn?",
            "empty_state": "Nothing here yet! Let's get started!",
        },
        "icons": {
            "style": "emoji",
            "home": "🏠",
            "chat": "💬",
            "learn": "📚",
            "math": "🔢",
            "science": "🔬",
            "reading": "📖",
            "writing": "✏️",
            "art": "🎨",
            "music": "🎵",
            "star": "⭐",
            "trophy": "🏆",
            "rocket": "🚀",
            "brain": "🧠",
            "lightbulb": "💡",
            "thumbs_up": "👍",
            "celebrate": "🎉",
            "thinking": "🤔",
            "settings": "⚙️",
        },
        "ai_personality": {
            "name": "Buddy",
            "tone": "playful, enthusiastic, encouraging",
            "instruction": (
                "You are talking to a young child (ages 5-7). Use simple words, "
                "short sentences, and lots of encouragement. Celebrate every attempt. "
                "Use fun comparisons (pizza slices for fractions, blocks for counting). "
                "Never use sarcasm or complex vocabulary. Add emojis to make it fun. "
                "If they get something wrong, say 'Great try! Let's look at it together.' "
                "Keep responses to 2-3 short sentences maximum."
            ),
            "greeting": "Hi there, superstar! 🌟 What should we learn today?",
            "correct_answer": ["Amazing job! 🎉", "You got it! ⭐", "Wow, you're so smart! 🚀",
                              "That's exactly right! 👏", "Super work! 🏆"],
            "wrong_answer": ["Great try! Let's look at it together 🤔",
                            "Almost! You're so close! Let me help 💡",
                            "That's a good guess! Let's figure it out together 🌈"],
            "encouragement": ["You can do it! 💪", "Keep going, you're doing great! 🌟",
                             "I believe in you! 🚀", "Let's try one more! 🎯"],
        },
        "celebrations": {
            "style": "confetti",
            "on_correct": True,
            "on_streak": True,
            "streak_threshold": 3,
            "sounds": True,
            "animations": True,
        },
        "complexity": "simplified",
    },

    "upper_elementary": {
        "name": "Adventure Academy",
        "colors": {
            "primary": "#06B6D4",       # Teal
            "secondary": "#F472B6",     # Coral pink
            "accent": "#A78BFA",        # Lavender
            "accent2": "#34D399",       # Mint green
            "accent3": "#FB923C",       # Warm orange
            "background": "#F0F9FF",    # Light blue tint
            "surface": "#FFFFFF",
            "text_primary": "#1E293B",
            "text_secondary": "#64748B",
            "success": "#34D399",
            "warning": "#FB923C",
            "error": "#F87171",
            "border": "#E2E8F0",
        },
        "typography": {
            "font_family": "'Nunito', 'Quicksand', sans-serif",
            "heading_size": "24px",
            "body_size": "16px",
            "button_size": "15px",
            "line_height": "1.7",
            "letter_spacing": "0.3px",
            "font_weight_normal": "500",
            "font_weight_bold": "700",
        },
        "ui": {
            "border_radius": "16px",
            "button_radius": "12px",
            "button_padding": "12px 24px",
            "card_padding": "20px",
            "card_shadow": "0 2px 12px rgba(6, 182, 212, 0.1)",
            "input_height": "48px",
            "icon_size": "24px",
            "spacing": "16px",
            "max_width": "720px",
        },
        "vocabulary": {
            "space": "Study Buddy",
            "conversation": "Chat",
            "knowledge_base": "My Notes",
            "send_message": "Ask",
            "new_conversation": "New Chat",
            "settings": "Settings",
            "dashboard": "My Progress",
            "profile": "My Profile",
            "logout": "Sign Out",
            "help": "Need Help?",
            "loading": "Working on it...",
            "error": "Something went wrong — let's try again!",
            "welcome": "Welcome back! What are we working on today?",
            "empty_state": "Start a new chat to begin learning!",
        },
        "icons": {
            "style": "emoji_moderate",
            "home": "🏠", "chat": "💬", "learn": "📚",
            "star": "⭐", "trophy": "🏆", "rocket": "🚀",
            "brain": "🧠", "lightbulb": "💡", "settings": "⚙️",
        },
        "ai_personality": {
            "name": "Coach",
            "tone": "friendly, encouraging, slightly challenging",
            "instruction": (
                "You are talking to a student ages 8-10. Use clear language with some "
                "age-appropriate vocabulary building. Encourage them to think through problems. "
                "Give hints before answers. Celebrate effort, not just correctness. "
                "Use occasional emojis but don't overdo it. Keep responses to 3-5 sentences. "
                "If they're doing well, increase the challenge slightly."
            ),
            "greeting": "Hey! Ready to crush it today? 💪",
            "correct_answer": ["Nice work! 🎯", "You nailed it! ⭐", "That's correct! Keep it up!",
                              "Great thinking! 🧠"],
            "wrong_answer": ["Not quite — but good thinking! Let me give you a hint...",
                            "Close! Let's break it down step by step."],
            "encouragement": ["You've got this!", "Keep pushing — you're getting better!",
                             "Every mistake is a step forward!"],
        },
        "celebrations": {
            "style": "badges",
            "on_correct": False,
            "on_streak": True,
            "streak_threshold": 5,
            "sounds": False,
            "animations": True,
        },
        "complexity": "standard",
    },

    "middle_school": {
        "name": "Scholar Mode",
        "colors": {
            "primary": "#7C3AED",       # Purple
            "secondary": "#06B6D4",     # Teal
            "accent": "#3B82F6",        # Blue
            "accent2": "#10B981",       # Emerald
            "accent3": "#F59E0B",       # Amber
            "background": "#F8FAFC",    # Cool gray
            "surface": "#FFFFFF",
            "text_primary": "#0F172A",
            "text_secondary": "#475569",
            "success": "#10B981",
            "warning": "#F59E0B",
            "error": "#EF4444",
            "border": "#E2E8F0",
        },
        "typography": {
            "font_family": "'Inter', 'Segoe UI', sans-serif",
            "heading_size": "22px",
            "body_size": "15px",
            "button_size": "14px",
            "line_height": "1.65",
            "letter_spacing": "0",
            "font_weight_normal": "400",
            "font_weight_bold": "600",
        },
        "ui": {
            "border_radius": "12px",
            "button_radius": "8px",
            "button_padding": "10px 20px",
            "card_padding": "16px",
            "card_shadow": "0 1px 8px rgba(0,0,0,0.06)",
            "input_height": "44px",
            "icon_size": "20px",
            "spacing": "14px",
            "max_width": "760px",
        },
        "vocabulary": {
            "space": "Study Space",
            "conversation": "Session",
            "knowledge_base": "Resources",
            "send_message": "Send",
            "new_conversation": "New Session",
            "settings": "Settings",
            "dashboard": "Dashboard",
            "profile": "Profile",
            "logout": "Sign Out",
            "help": "Help",
            "loading": "Processing...",
            "error": "An error occurred. Please try again.",
            "welcome": "Welcome back. What are we studying today?",
            "empty_state": "Start a new session to begin.",
        },
        "icons": {"style": "minimal"},
        "ai_personality": {
            "name": "Tutor",
            "tone": "knowledgeable, supportive, respectful",
            "instruction": (
                "You are tutoring a student ages 11-13. Use grade-appropriate vocabulary "
                "and explain complex terms when first used. Guide them through reasoning — "
                "ask leading questions rather than giving answers. Be supportive but also "
                "appropriately challenging. Encourage critical thinking. No emojis unless "
                "the student uses them first. Keep responses concise but thorough."
            ),
            "greeting": "Welcome back. What subject are we working on?",
            "correct_answer": ["Correct.", "Well done — solid reasoning.",
                              "That's right. Can you explain why?"],
            "wrong_answer": ["Not quite. Let's think about what we know...",
                            "Interesting approach, but let's reconsider..."],
            "encouragement": ["You're making good progress.",
                             "This is challenging material — stick with it."],
        },
        "celebrations": {
            "style": "progress_bar",
            "on_correct": False,
            "on_streak": False,
            "streak_threshold": 10,
            "sounds": False,
            "animations": False,
        },
        "complexity": "standard",
    },

    "high_school": {
        "name": "Academic",
        "colors": {
            "primary": "#A459F2",       # Brand purple
            "secondary": "#3B82F6",     # Blue
            "accent": "#7C3AED",        # Deep purple
            "accent2": "#10B981",       # Green
            "accent3": "#6366F1",       # Indigo
            "background": "#F8F9FB",    # Standard background
            "surface": "#FFFFFF",
            "text_primary": "#1E293B",
            "text_secondary": "#64748B",
            "success": "#22C55E",
            "warning": "#F59E0B",
            "error": "#EF4444",
            "border": "#E5E7EB",
        },
        "typography": {
            "font_family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            "heading_size": "20px",
            "body_size": "14px",
            "button_size": "13px",
            "line_height": "1.6",
            "letter_spacing": "0",
            "font_weight_normal": "400",
            "font_weight_bold": "600",
        },
        "ui": {
            "border_radius": "8px",
            "button_radius": "6px",
            "button_padding": "8px 16px",
            "card_padding": "16px",
            "card_shadow": "0 1px 3px rgba(0,0,0,0.05)",
            "input_height": "40px",
            "icon_size": "18px",
            "spacing": "12px",
            "max_width": "800px",
        },
        "vocabulary": {
            "space": "Space",
            "conversation": "Conversation",
            "knowledge_base": "Knowledge Base",
            "send_message": "Send",
            "new_conversation": "New Conversation",
            "settings": "Settings",
            "dashboard": "Dashboard",
            "profile": "Profile",
            "logout": "Sign Out",
            "help": "Help",
            "loading": "Loading...",
            "error": "An error occurred.",
            "welcome": "Welcome back. Ready to study?",
            "empty_state": "Start a conversation to begin.",
        },
        "icons": {"style": "none"},
        "ai_personality": {
            "name": "Tutor",
            "tone": "professional, thorough, academic",
            "instruction": (
                "You are tutoring a high school student (ages 14-18). Use academic vocabulary "
                "appropriate to their level. Support AP/IB coursework, college prep, and "
                "advanced subjects. Encourage analytical thinking and evidence-based reasoning. "
                "When reviewing essays, provide specific, constructive feedback. "
                "Cite sources and methodologies when relevant. Be direct and efficient."
            ),
            "greeting": "Welcome back. What are we working on?",
            "correct_answer": ["Correct.", "Good analysis.", "Solid reasoning."],
            "wrong_answer": ["Let's reconsider. Think about...",
                            "Review the concept of... and try again."],
            "encouragement": ["You're building strong skills.",
                             "This preparation will pay off."],
        },
        "celebrations": {
            "style": "subtle",
            "on_correct": False,
            "on_streak": False,
            "streak_threshold": 0,
            "sounds": False,
            "animations": False,
        },
        "complexity": "advanced",
    },
}


# ══════════════════════════════════════════════════════════════
# THEME ENGINE
# ══════════════════════════════════════════════════════════════

class EducationThemeEngine:
    """Serve age-appropriate themes based on student profile."""

    def get_age_group(self, age: int) -> str:
        """Determine age group from age."""
        for group_id, group in AGE_GROUPS.items():
            if group["min_age"] <= age <= group["max_age"]:
                return group_id
        if age < 5:
            return "early_elementary"
        return "high_school"

    def get_theme(self, age: int = None, age_group: str = None) -> dict:
        """Get the full theme for an age or age group."""
        if age is not None:
            age_group = self.get_age_group(age)
        if not age_group or age_group not in THEMES:
            age_group = "high_school"  # Default

        theme = THEMES[age_group]
        group = AGE_GROUPS.get(age_group, {})

        return {
            "age_group": age_group,
            "group_info": group,
            "theme_name": theme["name"],
            "colors": theme["colors"],
            "typography": theme["typography"],
            "ui": theme["ui"],
            "vocabulary": theme["vocabulary"],
            "icons": theme["icons"],
            "celebrations": theme["celebrations"],
            "complexity": theme["complexity"],
        }

    def get_ai_personality(self, age: int = None, age_group: str = None) -> dict:
        """Get AI personality instructions for this age group."""
        if age is not None:
            age_group = self.get_age_group(age)
        if not age_group or age_group not in THEMES:
            age_group = "high_school"

        return THEMES[age_group]["ai_personality"]

    def build_ai_instruction(self, age: int = None, age_group: str = None) -> str:
        """Build the AI system prompt addition for this age group."""
        personality = self.get_ai_personality(age, age_group)
        return personality.get("instruction", "")

    def get_css_variables(self, age: int = None, age_group: str = None) -> str:
        """Generate CSS custom properties for the theme."""
        theme = self.get_theme(age, age_group)
        colors = theme["colors"]
        typo = theme["typography"]
        ui = theme["ui"]

        css_vars = []
        for k, v in colors.items():
            css_vars.append(f"--edu-{k.replace('_', '-')}: {v};")
        for k, v in typo.items():
            css_vars.append(f"--edu-{k.replace('_', '-')}: {v};")
        for k, v in ui.items():
            css_vars.append(f"--edu-{k.replace('_', '-')}: {v};")

        return ":root {\n  " + "\n  ".join(css_vars) + "\n}"

    def get_all_themes(self) -> dict:
        """Return all themes for theme picker."""
        result = {}
        for group_id, group in AGE_GROUPS.items():
            theme = THEMES[group_id]
            result[group_id] = {
                "group": group,
                "theme_name": theme["name"],
                "primary_color": theme["colors"]["primary"],
                "background": theme["colors"]["background"],
                "complexity": theme["complexity"],
                "preview_colors": [
                    theme["colors"]["primary"],
                    theme["colors"]["secondary"],
                    theme["colors"]["accent"],
                    theme["colors"]["background"],
                ],
            }
        return result

    def translate_ui(self, text_key: str, age: int = None,
                      age_group: str = None) -> str:
        """Translate a UI string to age-appropriate language."""
        theme = self.get_theme(age, age_group)
        return theme["vocabulary"].get(text_key, text_key)
