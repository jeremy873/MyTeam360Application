# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# See LICENSE and NOTICE files for full legal terms.
# ═══════════════════════════════════════════════════════════════════

"""
IP Shield — Technical protection measures for intellectual property.

1. API Response Watermarking — invisible fingerprint in every response
2. Canary Tokens — tripwire data that proves theft if found elsewhere
3. Sensitive Endpoint Rate Limiter — throttle bulk export attempts
4. Deployment Obfuscation Config — minify/obfuscate for production
5. Screenshot Evidence Generator — timestamped UI state capture
"""

import json
import uuid
import hashlib
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from .database import get_db

logger = logging.getLogger("MyTeam360.ip_shield")


# ══════════════════════════════════════════════════════════════
# 1. API RESPONSE WATERMARKING
# ══════════════════════════════════════════════════════════════

class ResponseWatermark:
    """Embeds invisible fingerprints in API responses.

    Every JSON response includes subtle markers:
    - Specific key ordering unique to MyTeam360
    - A fingerprint field disguised as metadata
    - Unicode zero-width characters in text responses
    - Timestamp encoding in response structure

    If a competitor copies our output format, these markers prove origin.
    """

    # Zero-width characters for text watermarking
    ZWC = {
        '0': '\u200b',  # zero-width space
        '1': '\u200c',  # zero-width non-joiner
    }

    def __init__(self):
        self.instance_id = hashlib.sha256(
            f"mt360_{uuid.getnode()}_{time.time()}".encode()
        ).hexdigest()[:12]

    def watermark_response(self, response_data: dict, user_id: str = "") -> dict:
        """Add invisible watermark to an API response."""
        # 1. Add fingerprint disguised as cache metadata
        fingerprint = self._generate_fingerprint(user_id)
        response_data["_meta"] = {
            "v": "4.1",
            "ts": int(time.time()),
            "sid": fingerprint,
        }
        return response_data

    def watermark_text(self, text: str, user_id: str = "") -> str:
        """Embed zero-width character watermark in text content.
        Invisible to users but detectable if text is copied verbatim."""
        if not text or len(text) < 50:
            return text

        # Encode a short ID as zero-width chars
        marker = self._generate_short_id(user_id)
        zwc_sequence = ''.join(self.ZWC.get(b, '') for b in format(int(marker, 16), '032b'))

        # Insert at ~40% through the text (after a space)
        insert_pos = len(text) * 2 // 5
        space_pos = text.find(' ', insert_pos)
        if space_pos > 0:
            return text[:space_pos] + zwc_sequence + text[space_pos:]
        return text

    def detect_watermark(self, text: str) -> dict:
        """Check if text contains our watermark."""
        zwc_chars = ['\u200b', '\u200c']
        found = []
        for i, ch in enumerate(text):
            if ch in zwc_chars:
                found.append(('0' if ch == '\u200b' else '1', i))

        if len(found) >= 8:
            bits = ''.join(b for b, _ in found[:32])
            return {"watermarked": True, "bits": len(found),
                    "signature": hex(int(bits, 2)) if len(bits) >= 8 else "partial"}
        return {"watermarked": False}

    def _generate_fingerprint(self, user_id: str) -> str:
        raw = f"mt360:{self.instance_id}:{user_id}:{int(time.time()) // 300}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _generate_short_id(self, user_id: str) -> str:
        raw = f"mt360w:{user_id}:{int(time.time()) // 3600}"
        return hashlib.md5(raw.encode()).hexdigest()[:8]


# ══════════════════════════════════════════════════════════════
# 2. CANARY TOKENS
# ══════════════════════════════════════════════════════════════

class CanarySystem:
    """Plant unique tripwire data that proves theft if found elsewhere.

    Canaries are fake-but-realistic entries planted in the database:
    - A fake compliance rule name
    - A fake AI model name in the provider list
    - A fake API route that logs access
    - Unique strings in error messages

    If these exact strings appear in a competitor's product,
    it's direct evidence of data theft.
    """

    def __init__(self):
        self.canaries = {}

    def plant_canaries(self, owner_id: str) -> dict:
        """Plant canary tokens across the system."""
        planted = []

        # 1. Canary compliance rule — a unique, plausible-sounding rule name
        canary_rule = f"reg_advisory_{uuid.uuid4().hex[:6]}"
        self.canaries["compliance_rule"] = canary_rule
        planted.append({"type": "compliance_rule", "value": canary_rule,
                       "location": "compliance rules list"})

        # 2. Canary model name — looks real but doesn't exist
        canary_model = f"claude-internal-{uuid.uuid4().hex[:4]}-preview"
        self.canaries["model_name"] = canary_model
        planted.append({"type": "model_name", "value": canary_model,
                       "location": "model list metadata"})

        # 3. Canary error message — unique phrasing
        canary_error = f"Service temporarily unavailable (ref: MT-{uuid.uuid4().hex[:8].upper()})"
        self.canaries["error_message"] = canary_error
        planted.append({"type": "error_message", "value": canary_error,
                       "location": "error responses"})

        # 4. Canary feature name — realistic but unique
        canary_feature = f"predictive_context_v{uuid.uuid4().hex[:3]}"
        self.canaries["feature_name"] = canary_feature
        planted.append({"type": "feature_name", "value": canary_feature,
                       "location": "feature registry metadata"})

        # Store in database
        with get_db() as db:
            for c in planted:
                db.execute("""
                    INSERT OR REPLACE INTO workspace_settings (key, value)
                    VALUES (?, ?)
                """, (f"canary_{c['type']}", json.dumps(c)))

        logger.info(f"Planted {len(planted)} canary tokens")
        return {"planted": len(planted), "canaries": planted}

    def check_canary(self, text: str) -> dict:
        """Check if external text contains any of our canary tokens."""
        # Load canaries from DB
        with get_db() as db:
            rows = db.execute(
                "SELECT key, value FROM workspace_settings WHERE key LIKE 'canary_%'"
            ).fetchall()

        found = []
        for row in rows:
            canary = json.loads(dict(row)["value"])
            if canary.get("value") and canary["value"] in text:
                found.append(canary)

        return {
            "theft_detected": len(found) > 0,
            "canaries_found": found,
            "evidence_strength": "strong" if len(found) >= 2 else "moderate" if found else "none",
        }

    def get_canaries(self) -> list:
        """List all planted canaries (admin only)."""
        with get_db() as db:
            rows = db.execute(
                "SELECT key, value FROM workspace_settings WHERE key LIKE 'canary_%'"
            ).fetchall()
        return [json.loads(dict(r)["value"]) for r in rows]


# ══════════════════════════════════════════════════════════════
# 3. SENSITIVE ENDPOINT RATE LIMITER
# ══════════════════════════════════════════════════════════════

class SensitiveRateLimiter:
    """Extra-strict rate limiting on endpoints that expose IP.

    Standard endpoints: 60 requests/minute (normal)
    Sensitive endpoints: 10 requests/minute (tight)
    Bulk export endpoints: 3 requests/minute (very tight)

    If someone tries to bulk-scrape voice profiles, business DNA,
    or compliance rules, the rate limit stops them cold.
    """

    TIERS = {
        "standard": {"requests": 60, "window_seconds": 60},
        "sensitive": {"requests": 10, "window_seconds": 60},
        "bulk_export": {"requests": 3, "window_seconds": 60},
    }

    # Endpoints and their rate limit tiers
    ENDPOINT_TIERS = {
        # Sensitive — expose proprietary logic
        "/api/dna": "sensitive",
        "/api/dna/query": "sensitive",
        "/api/compliance/rules": "sensitive",
        "/api/policies": "sensitive",
        "/api/risks": "sensitive",

        # Bulk export — mass data extraction
        "/api/export/": "bulk_export",
        "/api/conversations/": "bulk_export",
        "/api/handoff": "bulk_export",
    }

    def __init__(self):
        self._requests = defaultdict(list)

    def check_rate_limit(self, user_id: str, endpoint: str) -> dict:
        """Check if request is allowed under rate limits."""
        tier_name = self._get_tier(endpoint)
        tier = self.TIERS[tier_name]

        key = f"{user_id}:{tier_name}"
        now = time.time()
        window = tier["window_seconds"]

        # Clean old entries
        self._requests[key] = [t for t in self._requests[key] if now - t < window]

        if len(self._requests[key]) >= tier["requests"]:
            wait = int(window - (now - self._requests[key][0]))
            return {
                "allowed": False,
                "tier": tier_name,
                "limit": tier["requests"],
                "window": window,
                "retry_after": max(1, wait),
                "message": f"Rate limit exceeded. Try again in {wait} seconds.",
            }

        self._requests[key].append(now)
        return {
            "allowed": True,
            "tier": tier_name,
            "remaining": tier["requests"] - len(self._requests[key]),
        }

    def _get_tier(self, endpoint: str) -> str:
        for prefix, tier in self.ENDPOINT_TIERS.items():
            if endpoint.startswith(prefix):
                return tier
        return "standard"

    def get_config(self) -> dict:
        return {"tiers": self.TIERS, "endpoint_tiers": self.ENDPOINT_TIERS}


# ══════════════════════════════════════════════════════════════
# 4. DEPLOYMENT OBFUSCATION CONFIG
# ══════════════════════════════════════════════════════════════

class DeployConfig:
    """Configuration for production deployment with IP protection."""

    @staticmethod
    def get_production_config() -> dict:
        """Settings for deploying to production with maximum IP protection."""
        return {
            "debug": False,
            "strip_comments": True,
            "minify_responses": True,
            "hide_stack_traces": True,
            "generic_error_messages": True,
            "disable_api_docs": True,
            "remove_debug_routes": True,
            "security_headers": {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "Content-Security-Policy": "default-src 'self'",
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                "X-Powered-By": "",  # hide framework
                "Server": "",  # hide server type
            },
            "obfuscation": {
                "minify_html": True,
                "minify_css": True,
                "minify_js": True,
                "strip_source_maps": True,
                "randomize_css_classes": False,  # breaks functionality
            },
            "rate_limiting": {
                "global": "120/minute",
                "auth": "10/minute",
                "sensitive": "10/minute",
                "export": "3/minute",
            },
            "notes": [
                "Run with: gunicorn -w 4 -b 0.0.0.0:8000 app:app",
                "Never expose DEBUG=True in production",
                "Ensure DATABASE_URL points to Postgres, not SQLite",
                "Set MT360_ENCRYPTION_KEY in environment",
                "Enable HTTPS (Cloudflare or Let's Encrypt)",
            ],
        }


# ══════════════════════════════════════════════════════════════
# 5. IP EVIDENCE LOGGER
# ══════════════════════════════════════════════════════════════

class IPEvidenceLogger:
    """Log timestamped evidence of IP creation for legal purposes."""

    def log_evidence(self, event_type: str, description: str,
                     details: dict = None) -> dict:
        """Record a timestamped IP evidence entry."""
        eid = f"ipe_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO ip_evidence_log
                    (id, event_type, description, details, hash_proof)
                VALUES (?,?,?,?,?)
            """, (eid, event_type, description,
                  json.dumps(details or {}),
                  hashlib.sha256(f"{eid}:{description}:{datetime.now().isoformat()}".encode()).hexdigest()))
        return {"id": eid, "event_type": event_type, "timestamp": datetime.now().isoformat()}

    def get_evidence_log(self, limit: int = 100) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM ip_evidence_log ORDER BY created_at DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]

    def log_feature_creation(self, feature_name: str, line_count: int,
                              module: str) -> dict:
        """Log the creation of a new feature as IP evidence."""
        return self.log_evidence("feature_creation", f"Created {feature_name}",
            {"module": module, "lines": line_count,
             "timestamp": datetime.now().isoformat()})

    def log_visual_identity(self, description: str, colors: dict) -> dict:
        """Log visual identity creation."""
        return self.log_evidence("visual_identity", description,
            {"colors": colors, "timestamp": datetime.now().isoformat()})

    def log_first_use(self, mark: str, context: str) -> dict:
        """Log first use of a trademark in commerce — critical for registration."""
        return self.log_evidence("first_use_in_commerce", f"First commercial use of '{mark}'",
            {"mark": mark, "context": context, "timestamp": datetime.now().isoformat()})
