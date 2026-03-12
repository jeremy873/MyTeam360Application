# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — Test Suite
# Run: python3 -m pytest tests.py -v
# ═══════════════════════════════════════════════════════════════════

import os
import json
import sys
import pytest

# Ensure app can import
sys.path.insert(0, os.path.dirname(__file__))
os.environ["DATABASE_URL"] = "sqlite://"  # In-memory DB for tests
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"


@pytest.fixture(scope="session")
def app():
    """Create test app."""
    import app as main_app
    main_app.app.config["TESTING"] = True
    main_app.app.config["WTF_CSRF_ENABLED"] = False
    with main_app.app.app_context():
        yield main_app.app


@pytest.fixture
def client(app):
    """Test client with auth."""
    with app.test_client() as c:
        # Create test user and login
        with app.app_context():
            from core.database import get_db
            with get_db() as db:
                db.execute(
                    "INSERT OR IGNORE INTO users (id, email, display_name, password_hash, role) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("test_user", "test@test.com", "Test User",
                     "$2b$12$test_hash", "owner"))
            # Set session
            with c.session_transaction() as sess:
                sess["user_id"] = "test_user"
        yield c


# ══════════════════════════════════════════════════════════════
# 1. COMPILATION & ROUTES
# ══════════════════════════════════════════════════════════════

class TestCompilation:
    def test_app_compiles(self, app):
        assert app is not None

    def test_route_count(self, app):
        routes = [r for r in app.url_map.iter_rules() if r.rule.startswith('/api/')]
        assert len(routes) > 500, f"Expected 500+ routes, got {len(routes)}"

    def test_status_endpoint(self, client):
        # May fail without full auth but shouldn't 500
        r = client.get("/api/status")
        assert r.status_code in (200, 401, 403)

    def test_landing_page(self, client):
        r = client.get("/")
        assert r.status_code in (200, 302)  # 302 if logged in (redirects to /app)

    def test_app_page(self, client):
        r = client.get("/app")
        assert r.status_code == 200

    def test_terms_page(self, client):
        r = client.get("/terms")
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════
# 2. SECURITY
# ══════════════════════════════════════════════════════════════

class TestSecurity:
    def test_aes256_encrypt_decrypt(self):
        from core.security_hardening import FieldEncryptor
        enc = FieldEncryptor()
        original = "sk-ant-api03-super-secret-key"
        encrypted = enc.encrypt(original)
        assert encrypted.startswith("enc2:")
        assert enc.decrypt(encrypted) == original

    def test_aes256_different_ciphertext(self):
        from core.security_hardening import FieldEncryptor
        enc = FieldEncryptor()
        text = "same-text"
        e1 = enc.encrypt(text)
        e2 = enc.encrypt(text)
        assert e1 != e2  # Different nonce = different ciphertext

    def test_password_validation(self):
        from core.security_fortress import PasswordFortress
        pf = PasswordFortress()
        assert not pf.validate_password("123")["valid"]
        assert not pf.validate_password("password")["valid"]
        assert pf.validate_password("MyStr0ngPass!")["valid"]

    def test_password_common_rejection(self):
        from core.security_fortress import PasswordFortress
        pf = PasswordFortress()
        result = pf.validate_password("SecureP@ss99")
        # Should pass complexity but check common list
        assert result["valid"]
        result2 = pf.validate_password("password")
        assert not result2["valid"]

    def test_account_lockout(self):
        from core.security_fortress import AccountLockoutManager
        al = AccountLockoutManager()
        for _ in range(5):
            al.record_failure("bad@actor.com")
        assert al.is_locked("bad@actor.com")["locked"]
        al.unlock("bad@actor.com")
        assert not al.is_locked("bad@actor.com")["locked"]

    def test_error_sanitization(self):
        from core.security_fortress import ErrorSanitizer
        es = ErrorSanitizer()
        dangerous = "sqlite3.OperationalError: /home/claude/db.py line 45"
        assert es.is_safe(dangerous) == False
        assert "sqlite3" not in es.clean(dangerous)
        assert "/home" not in es.clean(dangerous)

    def test_log_sanitization(self):
        from core.security_fortress import LogSanitizer
        ls = LogSanitizer()
        msg = "API key: sk-ant-api03-xxxxxxxxxxxxxxxxxxxx used for request"
        clean = ls.sanitize(msg)
        assert "sk-ant-api03-xx" not in clean
        assert "REDACTED" in clean

    def test_security_headers(self):
        from core.security_fortress import SecurityHeaders
        sh = SecurityHeaders()
        headers = sh.get_headers()
        assert "Content-Security-Policy" in headers
        assert "X-Frame-Options" in headers
        assert headers["X-Frame-Options"] == "DENY"

    def test_csp_blocks_unsafe_eval(self):
        from core.security_fortress import SecurityHeaders
        sh = SecurityHeaders()
        csp = sh.get_headers()["Content-Security-Policy"]
        assert "unsafe-eval" not in csp

    def test_gdpr_preview(self):
        from core.security_fortress import GDPRErasure
        ge = GDPRErasure()
        preview = ge.get_erasure_preview("nonexistent")
        assert "total_records" in preview


# ══════════════════════════════════════════════════════════════
# 3. MFA
# ══════════════════════════════════════════════════════════════

class TestMFA:
    def test_mfa_enforcement_levels(self):
        from core.security_hardening import MFAEnforcement
        ef = MFAEnforcement()
        assert len(ef.LEVELS) == 4

    def test_mfa_enforcement_check(self):
        from core.security_hardening import MFAEnforcement
        ef = MFAEnforcement()
        # Check enforcement (policy may vary)
        check = ef.check_enforcement("u1", "member", True)  # member with MFA = always compliant
        assert check["compliant"]

    def test_trusted_device_token(self):
        from core.security_hardening import TrustedDeviceManager
        td = TrustedDeviceManager()
        token = td.create_device_token("user1", "1.2.3.4", "Mozilla/5.0")
        assert td.validate_device_token(token, "user1", "1.2.3.4", "Mozilla/5.0")
        assert not td.validate_device_token(token, "user1", "5.6.7.8", "Chrome")

    def test_sensitive_ops_guard(self):
        from core.security_hardening import SensitiveOperationGuard
        sg = SensitiveOperationGuard()
        assert sg.is_sensitive("/api/me/password")
        assert sg.is_sensitive("/api/security/gdpr/erase")
        assert not sg.is_sensitive("/api/agents")


# ══════════════════════════════════════════════════════════════
# 4. SOUL — Positivity Guard + Wellbeing
# ══════════════════════════════════════════════════════════════

class TestSoul:
    def test_positivity_detects_pessimism(self):
        from core.soul import DNAPositivityGuard
        pg = DNAPositivityGuard()
        r = pg.analyze_tone("Nothing ever works. Why bother trying.")
        assert r["is_negative"]

    def test_positivity_passes_neutral(self):
        from core.soul import DNAPositivityGuard
        pg = DNAPositivityGuard()
        r = pg.analyze_tone("Please review the attached document by Friday.")
        assert not r["is_negative"]

    def test_dna_filter_blocks_negativity(self):
        from core.soul import DNAPositivityGuard
        pg = DNAPositivityGuard()
        analysis = pg.analyze_tone("I hate everything, this is hopeless garbage.")
        f = pg.filter_for_dna("test", analysis)
        assert f["learn_topics"]  # Always learn topics
        assert not f["learn_tone"]  # Never learn negative tone

    def test_wellbeing_detects_burnout(self):
        from core.soul import WellbeingAwareness
        wb = WellbeingAwareness()
        r = wb.assess_message("test", "I am so burned out, I cannot keep up anymore.")
        assert r["needs_care"]

    def test_wellbeing_ignores_normal(self):
        from core.soul import WellbeingAwareness
        wb = WellbeingAwareness()
        r = wb.assess_message("test", "Can you help me draft this email?")
        assert not r["needs_care"]

    def test_zero_knowledge_encrypt_decrypt(self):
        from core.soul import ZeroKnowledgeVault
        zk = ZeroKnowledgeVault()
        key, salt = zk.derive_key("my-password")
        secret = "Confidential business data"
        encrypted = zk.encrypt(secret, key)
        assert encrypted != secret
        decrypted = zk.decrypt(encrypted, key)
        assert decrypted == secret

    def test_zero_knowledge_wrong_key_fails(self):
        from core.soul import ZeroKnowledgeVault
        zk = ZeroKnowledgeVault()
        key, salt = zk.derive_key("correct-password")
        encrypted = zk.encrypt("secret", key)
        wrong_key, _ = zk.derive_key("wrong-password", salt)
        with pytest.raises(Exception):
            zk.decrypt(encrypted, wrong_key)


# ══════════════════════════════════════════════════════════════
# 5. TEAM BUILDER
# ══════════════════════════════════════════════════════════════

class TestTeamBuilder:
    def test_stats(self):
        from core.team_builder import SmartTeamBuilder
        tb = SmartTeamBuilder()
        s = tb.get_stats()
        assert s["built_in_roles"] >= 290
        assert s["industries"] >= 25

    def test_search(self):
        from core.team_builder import SmartTeamBuilder
        tb = SmartTeamBuilder()
        results = tb.search_roles("software developer")
        assert len(results) > 0
        assert results[0]["score"] > 50

    def test_built_in_recommendation(self):
        from core.team_builder import SmartTeamBuilder
        tb = SmartTeamBuilder()
        rec = tb.get_recommendation("stock_trader")
        assert rec["source"] == "built_in"
        assert rec["space_count"] >= 3

    def test_unknown_role(self):
        from core.team_builder import SmartTeamBuilder
        tb = SmartTeamBuilder()
        rec = tb.get_recommendation("unicorn_trainer")
        assert rec.get("error") == "not_found"
        assert rec.get("action") == "generate"

    def test_fallback_keyword_matching(self):
        from core.team_builder import SmartTeamBuilder
        tb = SmartTeamBuilder()
        rec = tb._fallback_recommendation("auto_mechanic", "Auto Mechanic")
        assert rec["archetype"] == "trades_professional"


# ══════════════════════════════════════════════════════════════
# 6. ACCESSIBILITY
# ══════════════════════════════════════════════════════════════

class TestAccessibility:
    def test_modes_available(self):
        from core.foundations import AccessibilityEngine
        ae = AccessibilityEngine()
        modes = ae.get_modes()
        assert len(modes) >= 7

    def test_ai_instruction_dyslexia(self):
        from core.foundations import AccessibilityEngine
        ae = AccessibilityEngine()
        instr = ae.build_ai_instruction("dyslexia_friendly")
        assert "short sentences" in instr.lower()

    def test_ai_instruction_default(self):
        from core.foundations import AccessibilityEngine
        ae = AccessibilityEngine()
        instr = ae.build_ai_instruction("default")
        assert instr == ""


# ══════════════════════════════════════════════════════════════
# 7. ETHICAL REASONING
# ══════════════════════════════════════════════════════════════

class TestEthics:
    def test_detects_layoffs(self):
        from core.foundations import EthicalReasoningLayer
        er = EthicalReasoningLayer()
        r = er.analyze("We need to lay off 200 employees to cut costs")
        assert r["has_ethical_dimension"]
        assert any(f["category"] == "human_impact" for f in r["flags"])

    def test_ignores_normal(self):
        from core.foundations import EthicalReasoningLayer
        er = EthicalReasoningLayer()
        r = er.analyze("Help me write a blog post about AI trends")
        assert not r["has_ethical_dimension"]


# ══════════════════════════════════════════════════════════════
# 8. PLATFORM INTELLIGENCE
# ══════════════════════════════════════════════════════════════

class TestPlatformIntelligence:
    def test_health_monitor(self):
        from core.platform_intelligence import PlatformHealthMonitor
        hm = PlatformHealthMonitor()
        hm.record_error("/api/test", 500, "test error")
        dashboard = hm.get_health_dashboard()
        assert "uptime_seconds" in dashboard

    def test_feedback_classification(self):
        from core.platform_intelligence import CollectiveFeedbackEngine
        fe = CollectiveFeedbackEngine()
        cls = fe.classify_feedback("This is way too slow, I waited forever")
        assert any(c["theme"] == "slow_response" for c in cls)

    def test_admin_briefing(self):
        from core.platform_intelligence import (PlatformHealthMonitor,
            CollectiveFeedbackEngine, AdminCollaborationChannel)
        hm = PlatformHealthMonitor()
        fe = CollectiveFeedbackEngine()
        ac = AdminCollaborationChannel(hm, fe)
        briefing = ac.generate_briefing()
        assert "greeting" in briefing


# ══════════════════════════════════════════════════════════════
# 9. EMAIL
# ══════════════════════════════════════════════════════════════

class TestEmail:
    def test_email_provider_detection(self):
        from core.email_service import EmailService
        es = EmailService()
        # No env vars set = console mode
        assert es.provider == "console"

    def test_welcome_template(self):
        from core.email_service import EmailService, EmailTemplates
        es = EmailService()
        et = EmailTemplates(es)
        result = et.send_welcome("test@test.com", name="Test")
        assert result["sent"]
        assert result["provider"] == "console"


# ══════════════════════════════════════════════════════════════
# COMPLIANCE
# ══════════════════════════════════════════════════════════════

class TestCompliance:
    def test_watchdog_rules(self):
        from core.enterprise import ComplianceWatchdog
        cw = ComplianceWatchdog()
        assert len(cw.rules) >= 18

    def test_content_filter(self):
        from core.guardrails import ContentFilter
        cf = ContentFilter()
        result = cf.filter_output("This is a normal response about business strategy.")
        assert not result["was_filtered"]


# ══════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
