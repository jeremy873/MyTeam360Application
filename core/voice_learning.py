# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# This software and all associated intellectual property are owned
# exclusively by Praxis Holdings LLC, a Nevada limited-liability company.
# Licensed to MyTeam360 LLC for operation.
#
# UNAUTHORIZED ACCESS, COPYING, MODIFICATION, DISTRIBUTION, OR USE
# OF THIS SOFTWARE IS STRICTLY PROHIBITED AND MAY RESULT IN CIVIL
# LIABILITY AND CRIMINAL PROSECUTION UNDER FEDERAL AND STATE LAW,
# INCLUDING THE DEFEND TRADE SECRETS ACT (18 U.S.C. § 1836),
# THE COMPUTER FRAUD AND ABUSE ACT (18 U.S.C. § 1030), AND THE
# NEVADA UNIFORM TRADE SECRETS ACT (NRS 600A).
#
# See LICENSE and NOTICE files for full legal terms.
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Voice Learning — Your AI learns to write like YOU, not like AI.

Analyzes patterns across conversations to build a personal "voice fingerprint":
  - Vocabulary preferences (words you use often, words you never use)
  - Sentence structure (short/punchy vs long/complex, active vs passive)
  - Tone markers (formal/casual, enthusiastic/reserved, direct/diplomatic)
  - Formatting habits (bullet points vs prose, headers, emoji usage)
  - Punctuation style (Oxford comma, em dashes, ellipses, exclamation marks)

The voice profile is automatically injected into every Space's system prompt.
After ~20 conversations, your AI sounds like you.
"""

import json
import re
import uuid
import logging
from datetime import datetime
from collections import Counter
from .database import get_db

logger = logging.getLogger("MyTeam360.voice_learning")

# ══════════════════════════════════════════════════════════════
# STYLE ANALYZER
# ══════════════════════════════════════════════════════════════

# Words that signal tone
FORMAL_MARKERS = {"furthermore", "moreover", "consequently", "nevertheless", "regarding",
    "pursuant", "hereby", "aforementioned", "thus", "hence", "wherein", "thereof"}
CASUAL_MARKERS = {"hey", "yeah", "cool", "awesome", "gonna", "wanna", "kinda", "sorta",
    "lol", "haha", "btw", "tbh", "imo", "ngl", "yep", "nope", "gotta"}
ENTHUSIASTIC_MARKERS = {"!", "amazing", "incredible", "fantastic", "love", "brilliant",
    "excellent", "wonderful", "exciting", "thrilled", "perfect", "great"}
HEDGING_MARKERS = {"perhaps", "maybe", "might", "could", "possibly", "somewhat",
    "relatively", "arguably", "it seems", "in my opinion", "i think", "i believe"}
DIRECT_MARKERS = {"do this", "stop", "fix", "change", "make", "need", "must", "now",
    "immediately", "don't", "wrong", "no"}

# AI-sounding words to detect if user edits them out
AI_SLOP = {"delve", "tapestry", "multifaceted", "nuanced", "landscape", "paradigm",
    "leverage", "synergy", "holistic", "robust", "streamline", "utilize", "facilitate",
    "in conclusion", "it's important to note", "it's worth noting", "let me break this down"}


class StyleAnalyzer:
    """Analyzes text samples to extract writing style patterns."""

    def analyze_text(self, text: str) -> dict:
        """Extract style features from a single text sample."""
        if not text or len(text.strip()) < 20:
            return {}

        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        word_count = len(words)
        sentence_count = max(len(sentences), 1)

        # Sentence length distribution
        sent_lengths = [len(s.split()) for s in sentences]
        avg_sent_len = sum(sent_lengths) / max(len(sent_lengths), 1)

        # Vocabulary level
        unique_words = len(set(w.lower().strip('.,!?;:') for w in words))
        vocab_richness = unique_words / max(word_count, 1)

        # Punctuation analysis
        text_lower = text.lower()
        exclamation_rate = text.count('!') / max(sentence_count, 1)
        question_rate = text.count('?') / max(sentence_count, 1)
        uses_oxford_comma = bool(re.search(r',\s+\w+,\s+and\s+', text))
        uses_em_dash = '—' in text or ' - ' in text or '--' in text
        uses_ellipsis = '...' in text or '…' in text
        uses_semicolons = ';' in text

        # Formatting
        uses_bullets = bool(re.search(r'^\s*[-•*]\s', text, re.MULTILINE))
        uses_numbering = bool(re.search(r'^\s*\d+[.)]\s', text, re.MULTILINE))
        uses_headers = bool(re.search(r'^#+\s|^[A-Z][A-Z\s]+:$', text, re.MULTILINE))
        uses_bold = '**' in text or '__' in text
        uses_emoji = bool(re.search(r'[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff]', text))
        paragraph_count = len([p for p in text.split('\n\n') if p.strip()])

        # Tone detection
        formal_count = sum(1 for w in FORMAL_MARKERS if w in text_lower)
        casual_count = sum(1 for w in CASUAL_MARKERS if w in text_lower)
        enthusiastic_count = sum(1 for w in ENTHUSIASTIC_MARKERS if w in text_lower)
        hedging_count = sum(1 for w in HEDGING_MARKERS if w in text_lower)
        direct_count = sum(1 for w in DIRECT_MARKERS if w in text_lower)

        # Contraction usage (casual indicator)
        contractions = len(re.findall(r"\b\w+'\w+\b", text))
        contraction_rate = contractions / max(word_count, 1)

        # Active vs passive voice (rough heuristic)
        passive_patterns = len(re.findall(r'\b(is|was|were|are|been|being)\s+\w+ed\b', text_lower))
        passive_rate = passive_patterns / max(sentence_count, 1)

        # First person usage
        first_person = len(re.findall(r'\b(I|I\'m|I\'ve|I\'ll|my|me|mine|myself)\b', text))
        first_person_rate = first_person / max(word_count, 1)

        # Frequent words (excluding common stop words)
        stop_words = {"the","a","an","is","are","was","were","be","been","being","have","has","had",
            "do","does","did","will","would","could","should","may","might","shall","can",
            "to","of","in","for","on","with","at","by","from","up","about","into","through",
            "and","but","or","nor","not","no","so","if","than","that","this","it","its","as"}
        content_words = [w.lower().strip('.,!?;:()[]"\'') for w in words
                        if w.lower().strip('.,!?;:()[]"\'') not in stop_words and len(w) > 2]
        word_freq = Counter(content_words).most_common(20)

        return {
            "word_count": word_count,
            "avg_sentence_length": round(avg_sent_len, 1),
            "vocab_richness": round(vocab_richness, 3),
            "exclamation_rate": round(exclamation_rate, 2),
            "question_rate": round(question_rate, 2),
            "contraction_rate": round(contraction_rate, 3),
            "passive_rate": round(passive_rate, 2),
            "first_person_rate": round(first_person_rate, 3),
            "uses_oxford_comma": uses_oxford_comma,
            "uses_em_dash": uses_em_dash,
            "uses_ellipsis": uses_ellipsis,
            "uses_semicolons": uses_semicolons,
            "uses_bullets": uses_bullets,
            "uses_numbering": uses_numbering,
            "uses_headers": uses_headers,
            "uses_bold": uses_bold,
            "uses_emoji": uses_emoji,
            "paragraph_count": paragraph_count,
            "formal_score": formal_count,
            "casual_score": casual_count,
            "enthusiastic_score": enthusiastic_count,
            "hedging_score": hedging_count,
            "direct_score": direct_count,
            "top_words": word_freq,
        }


# ══════════════════════════════════════════════════════════════
# VOICE PROFILE
# ══════════════════════════════════════════════════════════════

class VoiceProfileManager:
    """Manages per-user writing voice profiles."""

    def __init__(self):
        self.analyzer = StyleAnalyzer()

    def ingest_sample(self, user_id: str, text: str, sample_type: str = "user_message"):
        """Add a writing sample to the user's voice profile."""
        if not text or len(text.strip()) < 30:
            return

        features = self.analyzer.analyze_text(text)
        if not features:
            return

        with get_db() as db:
            # Get existing profile
            row = db.execute(
                "SELECT * FROM user_profiles WHERE user_id=?", (user_id,)
            ).fetchone()

            if row:
                try:
                    existing = json.loads(row.get("voice_profile") or "{}")
                except Exception:
                    existing = {}
            else:
                existing = {}
                db.execute("INSERT OR IGNORE INTO user_profiles (user_id) VALUES (?)", (user_id,))

            # Merge new features into running averages
            profile = self._merge_profile(existing, features, sample_type)

            db.execute(
                "UPDATE user_profiles SET voice_profile=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                (json.dumps(profile), user_id)
            )

    def _merge_profile(self, existing: dict, new_features: dict, sample_type: str) -> dict:
        """Merge new analysis into the running profile using exponential moving average."""
        samples = existing.get("sample_count", 0) + 1
        alpha = min(0.3, 2.0 / (samples + 1))  # EMA smoothing factor

        def ema(key, default=0):
            old = existing.get(key, default)
            new = new_features.get(key, default)
            if isinstance(new, bool):
                # For booleans, track as percentage
                old_pct = existing.get(key + "_pct", 0.5)
                new_pct = old_pct * (1 - alpha) + (1.0 if new else 0.0) * alpha
                existing[key + "_pct"] = round(new_pct, 3)
                return new_pct > 0.5
            return round(old * (1 - alpha) + new * alpha, 3)

        profile = {
            "sample_count": samples,
            "last_updated": datetime.now().isoformat(),
            "avg_sentence_length": ema("avg_sentence_length", 15),
            "vocab_richness": ema("vocab_richness", 0.5),
            "exclamation_rate": ema("exclamation_rate", 0),
            "question_rate": ema("question_rate", 0),
            "contraction_rate": ema("contraction_rate", 0),
            "passive_rate": ema("passive_rate", 0),
            "first_person_rate": ema("first_person_rate", 0),
            "uses_oxford_comma": ema("uses_oxford_comma"),
            "uses_em_dash": ema("uses_em_dash"),
            "uses_ellipsis": ema("uses_ellipsis"),
            "uses_emoji": ema("uses_emoji"),
            "uses_bullets": ema("uses_bullets"),
            "formal_score": ema("formal_score", 0),
            "casual_score": ema("casual_score", 0),
            "enthusiastic_score": ema("enthusiastic_score", 0),
            "hedging_score": ema("hedging_score", 0),
            "direct_score": ema("direct_score", 0),
        }

        # Merge top words
        old_words = dict(existing.get("top_words", []))
        for word, count in new_features.get("top_words", []):
            old_words[word] = old_words.get(word, 0) + count
        profile["top_words"] = sorted(old_words.items(), key=lambda x: -x[1])[:30]

        # Carry over pct fields
        for k, v in existing.items():
            if k.endswith("_pct"):
                profile[k] = v

        return profile

    def get_profile(self, user_id: str) -> dict:
        """Get a user's voice profile."""
        with get_db() as db:
            row = db.execute(
                "SELECT voice_profile FROM user_profiles WHERE user_id=?", (user_id,)
            ).fetchone()
        if not row or not row["voice_profile"]:
            return {"sample_count": 0}
        try:
            return json.loads(row["voice_profile"])
        except Exception:
            return {"sample_count": 0}

    def build_voice_injection(self, user_id: str) -> str:
        """Build a natural-language style instruction from the voice profile.
        This gets injected into every Space's system prompt."""
        profile = self.get_profile(user_id)
        if profile.get("sample_count", 0) < 5:
            return ""  # Not enough data yet

        parts = ["[USER'S WRITING STYLE — Match this voice naturally]"]

        # Tone
        formal = profile.get("formal_score", 0)
        casual = profile.get("casual_score", 0)
        if casual > formal + 1:
            parts.append("Tone: Conversational and casual. Use contractions freely.")
        elif formal > casual + 1:
            parts.append("Tone: Professional and polished. Minimize contractions.")
        else:
            parts.append("Tone: Balanced — professional but approachable.")

        # Enthusiasm
        enth = profile.get("enthusiastic_score", 0)
        if enth > 2:
            parts.append("Energy: Enthusiastic and positive. Exclamation points are okay.")
        elif profile.get("exclamation_rate", 0) < 0.1:
            parts.append("Energy: Measured and calm. Avoid exclamation points.")

        # Directness
        direct = profile.get("direct_score", 0)
        hedging = profile.get("hedging_score", 0)
        if direct > hedging + 1:
            parts.append("Directness: Very direct. Get to the point. No hedging.")
        elif hedging > direct + 1:
            parts.append("Directness: Thoughtful and nuanced. Consider multiple angles.")

        # Sentence length
        avg_len = profile.get("avg_sentence_length", 15)
        if avg_len < 10:
            parts.append("Sentences: Keep them short and punchy. Under 12 words average.")
        elif avg_len > 22:
            parts.append("Sentences: Longer, flowing sentences are fine. Be thorough.")
        else:
            parts.append("Sentences: Mix of short and medium length. Vary rhythm.")

        # Formatting
        fmt_notes = []
        if profile.get("uses_bullets_pct", 0) > 0.5:
            fmt_notes.append("bullet points")
        if profile.get("uses_emoji_pct", 0) > 0.4:
            fmt_notes.append("occasional emoji")
        elif profile.get("uses_emoji_pct", 0) < 0.1:
            fmt_notes.append("no emoji")
        if profile.get("uses_em_dash_pct", 0) > 0.4:
            fmt_notes.append("em dashes (—)")
        if profile.get("uses_ellipsis_pct", 0) > 0.3:
            fmt_notes.append("ellipses (...)")
        if fmt_notes:
            parts.append(f"Formatting preferences: {', '.join(fmt_notes)}.")

        # Vocabulary
        if profile.get("vocab_richness", 0.5) > 0.65:
            parts.append("Vocabulary: Rich and varied. Don't simplify unnecessarily.")
        elif profile.get("vocab_richness", 0.5) < 0.35:
            parts.append("Vocabulary: Simple and clear. Avoid jargon.")

        # Favorite words
        top = profile.get("top_words", [])
        if len(top) >= 5:
            fav_words = [w for w, _ in top[:8] if w not in AI_SLOP]
            if fav_words:
                parts.append(f"Words this user favors: {', '.join(fav_words)}")

        # First person
        if profile.get("first_person_rate", 0) > 0.03:
            parts.append("Perspective: Use first person (I, my, we) naturally.")
        elif profile.get("first_person_rate", 0) < 0.01:
            parts.append("Perspective: Third person or impersonal preferred.")

        # Active voice
        if profile.get("passive_rate", 0) < 0.1:
            parts.append("Voice: Active voice strongly preferred.")

        if len(parts) <= 1:
            return ""

        # POSITIVITY GUARD — never learn negative tone into voice profile
        parts.append(
            "IMPORTANT: Match the user's STRUCTURE, VOCABULARY, and FORMAT above. "
            "But always maintain a neutral-to-positive tone regardless of any "
            "negativity in their writing samples. We learn HOW they write, "
            "not their worst moments."
        )

        return "\n".join(parts)

    def get_readable_summary(self, user_id: str) -> dict:
        """Get a human-readable summary of the voice profile for the UI."""
        profile = self.get_profile(user_id)
        samples = profile.get("sample_count", 0)

        if samples < 5:
            return {
                "ready": False,
                "samples": samples,
                "needed": 5,
                "summary": f"Learning your voice... ({samples}/5 samples collected)"
            }

        # Build plain-English description
        traits = []
        formal = profile.get("formal_score", 0)
        casual = profile.get("casual_score", 0)
        if casual > formal + 1:
            traits.append("casual")
        elif formal > casual + 1:
            traits.append("formal")
        else:
            traits.append("balanced")

        if profile.get("direct_score", 0) > profile.get("hedging_score", 0) + 1:
            traits.append("direct")
        else:
            traits.append("thoughtful")

        if profile.get("enthusiastic_score", 0) > 2:
            traits.append("enthusiastic")

        avg_len = profile.get("avg_sentence_length", 15)
        if avg_len < 10:
            traits.append("concise")
        elif avg_len > 22:
            traits.append("detailed")

        return {
            "ready": True,
            "samples": samples,
            "traits": traits,
            "summary": f"Your voice: {', '.join(traits)}. Based on {samples} writing samples.",
            "confidence": min(100, int(samples / 50 * 100)),
        }

    def reset_profile(self, user_id: str):
        """Reset a user's voice profile."""
        with get_db() as db:
            db.execute(
                "UPDATE user_profiles SET voice_profile='{}' WHERE user_id=?",
                (user_id,)
            )
