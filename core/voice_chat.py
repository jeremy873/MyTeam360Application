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
Voice Chat — Interactive voice conversation with AI agents.
Browser STT (SpeechRecognition) → Chat API → Streaming TTS response.
Supports OpenAI TTS, ElevenLabs, Google Cloud TTS, and browser-native fallback.
"""

import os
import io
import json
import uuid
import time
import logging
import base64
import re
import urllib.request
import urllib.parse
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.voice_chat")


# ══════════════════════════════════════════════════════════════
# TTS PROVIDER REGISTRY
# ══════════════════════════════════════════════════════════════

TTS_PROVIDERS = {
    "openai": {
        "display_name": "OpenAI TTS",
        "voices": [
            {"id": "alloy", "name": "Alloy", "gender": "neutral", "style": "balanced"},
            {"id": "echo", "name": "Echo", "gender": "male", "style": "warm"},
            {"id": "fable", "name": "Fable", "gender": "male", "style": "storytelling"},
            {"id": "onyx", "name": "Onyx", "gender": "male", "style": "deep, authoritative"},
            {"id": "nova", "name": "Nova", "gender": "female", "style": "warm, professional"},
            {"id": "shimmer", "name": "Shimmer", "gender": "female", "style": "clear, expressive"},
        ],
        "models": ["tts-1", "tts-1-hd"],
        "default_voice": "nova",
        "default_model": "tts-1",
        "formats": ["mp3", "opus", "aac", "flac"],
        "max_chars": 4096,
        "env_var": "OPENAI_API_KEY",
        "cost_per_1m_chars": 15.00,
    },
    "elevenlabs": {
        "display_name": "ElevenLabs",
        "voices": [
            {"id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel", "gender": "female", "style": "calm, professional"},
            {"id": "AZnzlk1XvdvUeBnXmlld", "name": "Domi", "gender": "female", "style": "confident, clear"},
            {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella", "gender": "female", "style": "soft, warm"},
            {"id": "ErXwobaYiN019PkySvjV", "name": "Antoni", "gender": "male", "style": "mature, professional"},
            {"id": "MF3mGyEYCl7XYWbV9V6O", "name": "Elli", "gender": "female", "style": "young, pleasant"},
            {"id": "TxGEqnHWrfWFTfGW9XjX", "name": "Josh", "gender": "male", "style": "deep, narrative"},
            {"id": "VR6AewLTigWG4xSOukaG", "name": "Arnold", "gender": "male", "style": "commanding"},
            {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "gender": "male", "style": "natural, clear"},
        ],
        "models": ["eleven_monolingual_v1", "eleven_multilingual_v2", "eleven_turbo_v2"],
        "default_voice": "pNInz6obpgDQGcFmaJgB",
        "default_model": "eleven_turbo_v2",
        "formats": ["mp3_44100_128"],
        "max_chars": 5000,
        "env_var": "ELEVENLABS_API_KEY",
        "cost_per_1m_chars": 30.00,
    },
    "google": {
        "display_name": "Google Cloud TTS",
        "voices": [
            {"id": "en-US-Neural2-A", "name": "US Female A", "gender": "female", "style": "natural"},
            {"id": "en-US-Neural2-C", "name": "US Female C", "gender": "female", "style": "warm"},
            {"id": "en-US-Neural2-D", "name": "US Male D", "gender": "male", "style": "professional"},
            {"id": "en-US-Neural2-J", "name": "US Male J", "gender": "male", "style": "clear"},
            {"id": "en-GB-Neural2-A", "name": "UK Female A", "gender": "female", "style": "british"},
            {"id": "en-GB-Neural2-B", "name": "UK Male B", "gender": "male", "style": "british"},
        ],
        "models": ["neural2"],
        "default_voice": "en-US-Neural2-C",
        "default_model": "neural2",
        "formats": ["mp3", "wav", "ogg"],
        "max_chars": 5000,
        "env_var": "GOOGLE_TTS_API_KEY",
        "cost_per_1m_chars": 16.00,
    },
    "browser": {
        "display_name": "Browser Native (Free)",
        "voices": [],  # Populated client-side
        "models": [],
        "default_voice": "default",
        "default_model": "native",
        "formats": [],
        "max_chars": 0,
        "cost_per_1m_chars": 0,
    },
}


# ══════════════════════════════════════════════════════════════
# SENTENCE CHUNKER — split streaming text into speakable chunks
# ══════════════════════════════════════════════════════════════

class SentenceChunker:
    """Accumulates streaming text and yields complete sentences for TTS."""

    SENTENCE_END = re.compile(r'(?<=[.!?])\s+|(?<=[.!?])$')
    MIN_CHUNK = 20  # Don't send tiny fragments

    def __init__(self):
        self.buffer = ""

    def feed(self, text: str):
        """Feed text chunk, yields complete sentences."""
        self.buffer += text
        while True:
            match = self.SENTENCE_END.search(self.buffer)
            if match and match.start() >= self.MIN_CHUNK:
                sentence = self.buffer[:match.end()].strip()
                self.buffer = self.buffer[match.end():]
                if sentence:
                    yield sentence
            else:
                break

    def flush(self):
        """Flush remaining buffer as final chunk."""
        if self.buffer.strip():
            result = self.buffer.strip()
            self.buffer = ""
            return result
        return None


# ══════════════════════════════════════════════════════════════
# TTS SYNTHESIZER
# ══════════════════════════════════════════════════════════════

class TTSSynthesizer:
    """Generate speech audio from text using configured TTS provider."""

    def synthesize(self, text, provider="openai", voice=None, model=None, speed=1.0):
        """Synthesize text to audio. Returns {"audio": base64, "format": str, "duration_estimate": float}."""
        if provider == "browser" or provider not in TTS_PROVIDERS:
            return {"provider": "browser", "text": text}

        if provider == "openai":
            return self._openai_tts(text, voice, model, speed)
        elif provider == "elevenlabs":
            return self._elevenlabs_tts(text, voice, model)
        elif provider == "google":
            return self._google_tts(text, voice)
        else:
            return {"provider": "browser", "text": text}

    def _openai_tts(self, text, voice=None, model=None, speed=1.0):
        api_key = self._get_key("openai")
        if not api_key:
            return {"provider": "browser", "text": text, "fallback": True}

        voice = voice or "nova"
        model = model or "tts-1"
        try:
            payload = json.dumps({
                "model": model,
                "input": text[:4096],
                "voice": voice,
                "response_format": "mp3",
                "speed": max(0.25, min(4.0, speed)),
            }).encode()

            req = urllib.request.Request(
                "https://api.openai.com/v1/audio/speech",
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                })
            resp = urllib.request.urlopen(req, timeout=30)
            audio_bytes = resp.read()
            audio_b64 = base64.b64encode(audio_bytes).decode()

            # Rough duration estimate: ~150 words/min at speed 1.0
            word_count = len(text.split())
            duration = (word_count / 150) * 60 / speed

            return {
                "provider": "openai",
                "audio": audio_b64,
                "format": "mp3",
                "mime": "audio/mpeg",
                "size_bytes": len(audio_bytes),
                "duration_estimate": round(duration, 1),
                "voice": voice,
                "model": model,
            }
        except Exception as e:
            logger.error(f"OpenAI TTS error: {e}")
            return {"provider": "browser", "text": text, "fallback": True, "error": str(e)}

    def _elevenlabs_tts(self, text, voice=None, model=None):
        api_key = self._get_key("elevenlabs")
        if not api_key:
            return {"provider": "browser", "text": text, "fallback": True}

        voice = voice or "pNInz6obpgDQGcFmaJgB"
        model = model or "eleven_turbo_v2"
        try:
            payload = json.dumps({
                "text": text[:5000],
                "model_id": model,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.5,
                    "use_speaker_boost": True,
                },
            }).encode()

            req = urllib.request.Request(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                data=payload,
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                })
            resp = urllib.request.urlopen(req, timeout=30)
            audio_bytes = resp.read()
            audio_b64 = base64.b64encode(audio_bytes).decode()

            word_count = len(text.split())
            duration = (word_count / 150) * 60

            return {
                "provider": "elevenlabs",
                "audio": audio_b64,
                "format": "mp3",
                "mime": "audio/mpeg",
                "size_bytes": len(audio_bytes),
                "duration_estimate": round(duration, 1),
                "voice": voice,
                "model": model,
            }
        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {e}")
            return {"provider": "browser", "text": text, "fallback": True, "error": str(e)}

    def _google_tts(self, text, voice=None):
        api_key = self._get_key("google_tts")
        if not api_key:
            return {"provider": "browser", "text": text, "fallback": True}

        voice = voice or "en-US-Neural2-C"
        try:
            lang_code = voice.rsplit("-", 1)[0] if "-" in voice else "en-US"
            payload = json.dumps({
                "input": {"text": text[:5000]},
                "voice": {
                    "languageCode": lang_code,
                    "name": voice,
                },
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "speakingRate": 1.0,
                    "pitch": 0,
                },
            }).encode()

            req = urllib.request.Request(
                f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}",
                data=payload,
                headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=30)
            data = json.loads(resp.read().decode())
            audio_b64 = data.get("audioContent", "")

            word_count = len(text.split())
            duration = (word_count / 150) * 60

            return {
                "provider": "google",
                "audio": audio_b64,
                "format": "mp3",
                "mime": "audio/mpeg",
                "size_bytes": len(base64.b64decode(audio_b64)) if audio_b64 else 0,
                "duration_estimate": round(duration, 1),
                "voice": voice,
            }
        except Exception as e:
            logger.error(f"Google TTS error: {e}")
            return {"provider": "browser", "text": text, "fallback": True, "error": str(e)}

    def _get_key(self, provider):
        """Get API key from provider_auth DB or env var."""
        try:
            from .provider_auth import ProviderAuthManager
            mgr = ProviderAuthManager()
            creds = mgr.get_credentials(provider)
            if creds and creds.get("api_key"):
                return creds["api_key"]
        except Exception:
            pass

        env_map = {
            "openai": "OPENAI_API_KEY",
            "elevenlabs": "ELEVENLABS_API_KEY",
            "google_tts": "GOOGLE_TTS_API_KEY",
        }
        return os.getenv(env_map.get(provider, ""), "")


# ══════════════════════════════════════════════════════════════
# VOICE SETTINGS MANAGER
# ══════════════════════════════════════════════════════════════

class VoiceSettingsManager:
    """Per-user voice chat preferences stored in user_preferences."""

    DEFAULT_SETTINGS = {
        "tts_provider": "browser",
        "tts_voice": "default",
        "tts_model": "default",
        "tts_speed": 1.0,
        "stt_language": "en-US",
        "stt_continuous": True,
        "auto_send": True,         # Auto-send when user stops speaking
        "silence_threshold": 1500,  # ms of silence before auto-send
        "voice_activation": False,  # Always-on listening (push-to-talk if false)
        "sound_effects": True,      # Play beeps for state changes
    }

    def get_settings(self, user_id):
        with get_db() as db:
            row = db.execute(
                "SELECT value FROM user_preferences WHERE user_id=? AND key='voice_settings'",
                (user_id,)).fetchone()
            if row:
                try:
                    saved = json.loads(row["value"])
                    return {**self.DEFAULT_SETTINGS, **saved}
                except Exception:
                    pass
        return dict(self.DEFAULT_SETTINGS)

    def update_settings(self, user_id, updates):
        current = self.get_settings(user_id)
        for k, v in updates.items():
            if k in self.DEFAULT_SETTINGS:
                current[k] = v

        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO user_preferences (user_id, key, value)"
                " VALUES (?, 'voice_settings', ?)",
                (user_id, json.dumps(current)))
        return current

    def get_available_providers(self):
        """Check which TTS providers have keys configured."""
        available = [{"id": "browser", **TTS_PROVIDERS["browser"], "configured": True}]
        synth = TTSSynthesizer()
        for pid in ["openai", "elevenlabs", "google"]:
            tmpl = TTS_PROVIDERS[pid]
            has_key = bool(synth._get_key(pid if pid != "google" else "google_tts"))
            available.append({
                "id": pid,
                "display_name": tmpl["display_name"],
                "voices": tmpl["voices"],
                "models": tmpl.get("models", []),
                "default_voice": tmpl["default_voice"],
                "default_model": tmpl.get("default_model", ""),
                "cost_per_1m_chars": tmpl["cost_per_1m_chars"],
                "configured": has_key,
            })
        return available


# ══════════════════════════════════════════════════════════════
# VOICE SESSION TRACKER
# ══════════════════════════════════════════════════════════════

class VoiceSessionTracker:
    """Track active voice sessions for analytics."""

    def __init__(self):
        self.active_sessions = {}

    def start_session(self, user_id, agent_id=None, tts_provider="browser",
                      user_name=""):
        session_id = f"vs_{uuid.uuid4().hex[:12]}"
        first_name = (user_name or "").split()[0] if user_name else ""
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "agent_id": agent_id,
            "tts_provider": tts_provider,
            "user_name": user_name,
            "first_name": first_name,
            "started_at": datetime.utcnow().isoformat(),
            "message_count": 0,
            "total_tts_chars": 0,
            "total_stt_chars": 0,
        }
        return session_id

    def get_greeting(self, session_id: str, agent_name: str = "") -> str:
        """Generate a spoken greeting for voice session."""
        session = self.active_sessions.get(session_id, {})
        first = session.get("first_name", "")
        hour = datetime.utcnow().hour

        if hour < 12:
            time_g = "Good morning"
        elif hour < 17:
            time_g = "Good afternoon"
        else:
            time_g = "Good evening"

        if first and agent_name:
            return f"{time_g}, {first}. I'm {agent_name}. How can I help you?"
        elif first:
            return f"{time_g}, {first}. How can I help you today?"
        elif agent_name:
            return f"{time_g}. I'm {agent_name}. How can I help you?"
        else:
            return f"{time_g}. How can I help you today?"

    def record_exchange(self, session_id, stt_text="", tts_text=""):
        if session_id in self.active_sessions:
            s = self.active_sessions[session_id]
            s["message_count"] += 1
            s["total_stt_chars"] += len(stt_text)
            s["total_tts_chars"] += len(tts_text)

    def end_session(self, session_id):
        session = self.active_sessions.pop(session_id, None)
        if session:
            session["ended_at"] = datetime.utcnow().isoformat()
            # Log to audit
            try:
                with get_db() as db:
                    db.execute(
                        "INSERT INTO audit_log (id, user_id, action, resource_type, detail, severity)"
                        " VALUES (?, ?, 'voice_session_end', 'voice', ?, 'info')",
                        (f"aud_{uuid.uuid4().hex[:8]}", session["user_id"],
                         f"Messages: {session['message_count']}, TTS chars: {session['total_tts_chars']}, Provider: {session['tts_provider']}"))
            except Exception:
                pass
        return session

    def get_active(self):
        return dict(self.active_sessions)
