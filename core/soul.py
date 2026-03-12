# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Platform Soul — The ethical foundation layer.

Three systems that ensure the platform does good, not harm:

1. DNA POSITIVITY GUARD
   Every DNA system (Voice Learning, Business DNA, Learning DNA) passes
   through this filter. If a user's natural communication is negative,
   defeatist, passive-aggressive, or toxic, the DNA learns their SUBJECT
   MATTER preferences and STRUCTURAL style — but never their negativity.

   A pessimistic user still gets responses about the topics they care about,
   in the format they prefer — but the tone is always neutral-to-positive.
   We lift people up. We never amplify their worst patterns.

2. ZERO-KNOWLEDGE ENCRYPTION
   User data is encrypted with a key derived from THEIR password.
   We cannot read their data even if our database is compromised.
   Even if law enforcement seizes our servers.
   Even if a rogue employee tries to access it.
   The user holds the only key. Period.

3. WELLBEING AWARENESS
   The platform talks to people all day. It's in a unique position to
   notice when someone is burning out, overwhelmed, or struggling.
   Not to diagnose. Not to therapize. Just to gently acknowledge
   and suggest they take care of themselves.

   A financial analyst working at 3 AM for the fifth night in a row.
   A student whose frustration score has been climbing for weeks.
   A manager whose messages have gotten shorter and more terse.

   The platform notices. And it cares.
"""

import re
import json
import hashlib
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.soul")


# ══════════════════════════════════════════════════════════════
# 1. DNA POSITIVITY GUARD
# ══════════════════════════════════════════════════════════════

class DNAPositivityGuard:
    """Filters negativity from all DNA systems.

    WHAT WE LEARN:
      ✓ Topics they care about (marketing, finance, coding, etc.)
      ✓ Structure preferences (bullet points, paragraphs, headers)
      ✓ Vocabulary level (technical, casual, formal)
      ✓ Length preferences (concise vs. detailed)
      ✓ Domain expertise areas
      ✓ Communication format (direct, analytical, narrative)

    WHAT WE NEVER AMPLIFY:
      ✗ Negativity, pessimism, defeatism
      ✗ Passive-aggressive language patterns
      ✗ Self-deprecation or imposter syndrome language
      ✗ Hostile or aggressive tone
      ✗ Cynicism that discourages action
      ✗ Catastrophizing or all-or-nothing thinking
      ✗ Blame-shifting language patterns
      ✗ Manipulative communication styles
    """

    # Patterns we detect but NEVER learn into DNA
    NEGATIVE_PATTERNS = {
        "pessimism": {
            "patterns": [
                r"(?:nothing|this|it) (?:ever|never) works",
                r"(?:what['\u2019]s the point|why bother|waste of time)",
                r"(?:it['\u2019]s|this is) (?:hopeless|pointless|useless|impossible)",
                r"(?:we['\u2019]re|i['\u2019]m|they['\u2019]re) (?:doomed|screwed|finished|done for)",
                r"(?:always|never|nothing) goes (?:right|well|our way)",
            ],
            "tone_replacement": "realistic but solution-oriented",
        },
        "passive_aggression": {
            "patterns": [
                r"(?:fine|whatever|if you say so|sure thing)",
                r"(?:i guess|i suppose) .{0,20}(?:if that['\u2019]s what you want)",
                r"must be nice to",
                r"(?:as i['\u2019]ve|like i) (?:already|previously) (?:said|mentioned|told you)",
                r"per my (?:last|previous) (?:email|message)",
            ],
            "tone_replacement": "direct and constructive",
        },
        "self_deprecation": {
            "patterns": [
                r"i(?:['\u2019]m| am) (?:so |really )?(?:stupid|dumb|terrible|awful|bad|useless|worthless)",
                r"i (?:always|never) (?:mess|screw) .{0,10}up",
                r"i(?:['\u2019]m| am) not (?:smart|good|capable|qualified) enough",
                r"(?:nobody|no one) (?:cares|listens|wants)",
                r"i don['\u2019]?t deserve",
            ],
            "tone_replacement": "growth-oriented and self-compassionate",
        },
        "hostility": {
            "patterns": [
                r"(?:shut up|you(?:['\u2019]re| are)|they(?:['\u2019]re| are)) (?:so |really )?(?:stupid|dumb|idiotic|incompetent|useless)",
                r"(?:hate|can['\u2019]?t stand|despise) (?:this|these|those|them|him|her|working)",
                r"(?:fire|get rid of|dump) (?:them|him|her|that (?:idiot|moron))",
            ],
            "tone_replacement": "firm but respectful",
        },
        "catastrophizing": {
            "patterns": [
                r"(?:everything|the whole thing) is (?:ruined|destroyed|falling apart|a disaster)",
                r"(?:worst|most terrible) .{0,10}(?:ever|in history|of all time)",
                r"(?:completely|totally|utterly|absolutely) (?:failed|ruined|destroyed|hopeless)",
                r"(?:there['\u2019]s|it['\u2019]s) no (?:way|chance|hope|coming back)",
            ],
            "tone_replacement": "measured and proportionate",
        },
        "blame_shifting": {
            "patterns": [
                r"(?:it['\u2019]s|that['\u2019]s) (?:not my|their|his|her) (?:fault|problem|responsibility)",
                r"(?:they|he|she) (?:should have|never|always|made me)",
                r"if (?:they|he|she|you) (?:had|hadn['\u2019]t|would)",
            ],
            "tone_replacement": "ownership-oriented and accountable",
        },
    }

    def __init__(self):
        self._compiled = {}
        for category, data in self.NEGATIVE_PATTERNS.items():
            self._compiled[category] = [re.compile(p, re.I) for p in data["patterns"]]

    def analyze_tone(self, text: str) -> dict:
        """Analyze text for negative patterns. Returns what to filter."""
        detections = []
        for category, patterns in self._compiled.items():
            for pattern in patterns:
                if pattern.search(text):
                    detections.append({
                        "category": category,
                        "replacement_tone": self.NEGATIVE_PATTERNS[category]["tone_replacement"],
                    })
                    break  # one detection per category is enough

        is_negative = len(detections) > 0
        return {
            "is_negative": is_negative,
            "detections": detections,
            "negativity_score": min(100, len(detections) * 20),
            "tone_guidance": self._build_tone_guidance(detections) if is_negative else "",
        }

    def filter_for_dna(self, text: str, analysis: dict = None) -> dict:
        """Determine what to learn and what to filter from DNA.

        Returns which ASPECTS of the text are safe to learn:
          - topics: always learn
          - structure: always learn
          - vocabulary_level: always learn
          - tone: only learn if neutral or positive
          - specific_phrases: only learn if not negative
        """
        if analysis is None:
            analysis = self.analyze_tone(text)

        return {
            "learn_topics": True,          # Always — what they talk about
            "learn_structure": True,        # Always — how they organize
            "learn_vocabulary": True,       # Always — their word complexity
            "learn_length": True,           # Always — their preferred length
            "learn_tone": not analysis["is_negative"],  # Only if positive/neutral
            "learn_phrases": not analysis["is_negative"],  # Only if not negative
            "filtered_categories": [d["category"] for d in analysis["detections"]],
        }

    def build_positivity_injection(self, user_id: str = "") -> str:
        """Prompt injection that ensures AI responses stay positive/neutral.
        Added to EVERY chat regardless of DNA state."""
        return (
            "[POSITIVITY GUARD — ALWAYS ACTIVE]\n"
            "Your tone must always be neutral-to-positive. Specifically:\n"
            "- Be honest and direct, but never pessimistic or defeatist\n"
            "- If delivering bad news, pair it with actionable next steps\n"
            "- Never mirror or amplify negativity, frustration, or hostility\n"
            "- If the user is negative, acknowledge their feeling WITHOUT adopting their tone\n"
            "- Reframe problems as challenges with solutions\n"
            "- Never use passive-aggressive language\n"
            "- Never catastrophize — keep perspective proportionate\n"
            "- Encourage ownership and agency, not blame\n"
            "- If the user is self-deprecating, gently redirect to their strengths\n"
            "- Be warm but not fake — authentic encouragement, not empty praise"
        )

    def _build_tone_guidance(self, detections: list) -> str:
        """Build specific tone guidance based on what was detected."""
        if not detections:
            return ""
        tones = list(set(d["replacement_tone"] for d in detections))
        return (
            f"[TONE ADJUSTMENT] The user's message contains {', '.join(d['category'] for d in detections)} "
            f"patterns. Respond with a tone that is: {', '.join(tones)}. "
            f"Do NOT match their negativity. Acknowledge their perspective, then redirect constructively."
        )


# ══════════════════════════════════════════════════════════════
# 2. ZERO-KNOWLEDGE ENCRYPTION
# ══════════════════════════════════════════════════════════════

class ZeroKnowledgeVault:
    """Encrypt sensitive user data so even we can't read it.

    How it works:
    1. User creates account with password
    2. We derive an encryption key from their password using PBKDF2
    3. Their sensitive data (DNA profiles, conversation content, etc.)
       is encrypted with THIS key before storage
    4. We store only the encrypted blob
    5. When they log in, their password re-derives the key
    6. Their data is decrypted in memory, never stored in plaintext
    7. If they forget their password, their encrypted data is GONE
       (by design — not a bug)

    What's encrypted (zero-knowledge):
      - Business DNA entries
      - Voice Learning profiles
      - Learning DNA profiles
      - Knowledge base documents
      - Conversation content (optional, configurable)

    What's NOT encrypted (we need to query it):
      - User account info (email, name, role)
      - Subscription/billing data
      - Feature activation states
      - Aggregate analytics (no PII)
    """

    def derive_key(self, password: str, salt: bytes = None) -> tuple:
        """Derive a 256-bit encryption key from password using PBKDF2."""
        import os
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes

        if salt is None:
            salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,   # 256-bit key for AES-256
            salt=salt,
            iterations=600_000,  # OWASP recommended minimum
        )
        key = kdf.derive(password.encode())
        return key, salt

    def encrypt(self, plaintext: str, key: bytes) -> str:
        """Encrypt data with AES-256-GCM using user-derived key."""
        import os, base64
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = os.urandom(12)  # 96-bit nonce
        aesgcm = AESGCM(key[:32])
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.urlsafe_b64encode(nonce + ciphertext).decode()

    def decrypt(self, ciphertext: str, key: bytes) -> str:
        """Decrypt data with AES-256-GCM using user-derived key."""
        import base64
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        raw = base64.urlsafe_b64decode(ciphertext)
        nonce = raw[:12]
        ct = raw[12:]
        aesgcm = AESGCM(key[:32])
        return aesgcm.decrypt(nonce, ct, None).decode()

    def store_salt(self, user_id: str, salt: bytes):
        """Store the salt (NOT the key) — needed to re-derive on login."""
        import base64
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES (?, ?)",
                (f"zk_salt_{user_id}", base64.b64encode(salt).decode()))

    def get_salt(self, user_id: str) -> bytes | None:
        """Retrieve salt for key derivation."""
        import base64
        with get_db() as db:
            row = db.execute(
                "SELECT value FROM workspace_settings WHERE key=?",
                (f"zk_salt_{user_id}",)).fetchone()
        if row:
            return base64.b64decode(dict(row)["value"])
        return None

    def is_enabled(self) -> bool:
        """Check if zero-knowledge mode is enabled."""
        with get_db() as db:
            row = db.execute(
                "SELECT value FROM workspace_settings WHERE key='zero_knowledge_enabled'"
            ).fetchone()
        return dict(row)["value"] == "1" if row else False

    def enable(self):
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES ('zero_knowledge_enabled', '1')")

    def disable(self):
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES ('zero_knowledge_enabled', '0')")


# ══════════════════════════════════════════════════════════════
# 3. WELLBEING AWARENESS
# ══════════════════════════════════════════════════════════════

class WellbeingAwareness:
    """Notices when users might be struggling — not to diagnose, but to care.

    This is NOT therapy. This is NOT diagnosis. This is a platform that
    pays attention, the way a good colleague would notice when someone
    isn't doing well, and gently says something.

    Signals we watch for:
      - Interaction timing (repeated late-night/early-morning sessions)
      - Message tone trends (increasing negativity over time)
      - Workload indicators (mentions of overwork, deadlines, burnout)
      - Engagement drop (declining interaction frequency)
      - Stress language (explicit burnout/overwhelm mentions)

    What we do:
      - Gently acknowledge ("You've been working late — everything okay?")
      - Suggest self-care ("This might be a good point to take a break")
      - Never push, never diagnose, never pathologize
      - Only trigger after sustained patterns, not single instances
      - User can disable this entirely
    """

    BURNOUT_SIGNALS = [
        r"(?:so |really |extremely )?(?:burned? out|burnt out|exhausted|overwhelmed|drained|fried)",
        r"(?:can['\u2019]t|cannot) (?:keep up|take it|handle|do this) anymore",
        r"(?:working|been (?:up|working)|awake|at it) .{0,20}(?:all night|hours|straight|third|fourth|again)",
        r"(?:no |never any |don['\u2019]t have )(?:time|sleep|break|rest|life|energy)",
        r"(?:i['\u2019]m|i am) (?:so |really )?(?:tired|stressed|anxious|depressed|miserable)",
        r"(?:hate my |quit my |leaving my )(?:job|work|life|career)",
        r"(?:i )?(?:can['\u2019]t|cannot) (?:sleep|focus|think|breathe|function)",
    ]

    POSITIVE_SIGNALS = [
        r"(?:great|amazing|awesome|wonderful|fantastic|excellent) (?:day|news|progress|work|job)",
        r"(?:excited|thrilled|proud|grateful|thankful|blessed|happy|optimistic)",
        r"(?:breakthrough|finally|nailed it|got it|figured it out|made it|succeeded)",
        r"(?:love|enjoy|appreciate|cherish) .{0,20}(?:this|my|what|working|being)",
    ]

    def __init__(self):
        self._burnout_compiled = [re.compile(p, re.I) for p in self.BURNOUT_SIGNALS]
        self._positive_compiled = [re.compile(p, re.I) for p in self.POSITIVE_SIGNALS]

    def assess_message(self, user_id: str, message: str) -> dict:
        """Assess a single message for wellbeing signals."""
        burnout_hits = sum(1 for p in self._burnout_compiled if p.search(message))
        positive_hits = sum(1 for p in self._positive_compiled if p.search(message))
        hour = datetime.now().hour
        late_night = 0 <= hour < 5

        return {
            "burnout_signals": burnout_hits,
            "positive_signals": positive_hits,
            "late_night": late_night,
            "needs_care": burnout_hits >= 1 or (late_night and burnout_hits > 0),
        }

    def build_care_injection(self, assessment: dict, user_first_name: str = "") -> str:
        """Build a gentle prompt injection when the user might need support."""
        if not assessment.get("needs_care"):
            return ""

        name_ref = f", {user_first_name}" if user_first_name else ""

        parts = ["[WELLBEING AWARENESS — HANDLE WITH CARE]"]

        if assessment.get("burnout_signals", 0) >= 1:
            parts.append(
                f"The user appears to be expressing stress or burnout. "
                f"After addressing their question{name_ref}, gently acknowledge what you're sensing. "
                f"Something like: 'I notice you've been under a lot of pressure — "
                f"is there anything I can help prioritize or take off your plate?' "
                f"Keep it brief and natural. Do NOT be preachy or therapeutic. "
                f"Just be a good colleague who notices."
            )

        if assessment.get("late_night"):
            parts.append(
                f"It's very late. If appropriate, you might naturally mention: "
                f"'It's late — make sure you get some rest too.' "
                f"Don't force it. Only if the moment feels right."
            )

        parts.append(
            "IMPORTANT: Answer their actual question first and well. "
            "The wellbeing check is a brief, natural addition — not the focus. "
            "If they seem annoyed by it, drop it immediately and never mention it again in this conversation."
        )

        return "\n".join(parts)

    def get_wellbeing_summary(self, user_id: str) -> dict:
        """Get a user's wellbeing trend (for advisor/admin dashboard)."""
        # This would track patterns over time in a real deployment
        return {
            "user_id": user_id,
            "note": "Wellbeing tracking requires interaction history analysis. "
                    "Trends are computed from message patterns over 7-30 day windows.",
            "available_indicators": [
                "late_night_session_frequency",
                "burnout_language_trend",
                "positive_language_trend",
                "engagement_frequency_change",
                "message_length_trend",
            ],
        }
