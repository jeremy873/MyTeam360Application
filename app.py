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
MyTeam360 — AI Platform
Main application with API routes, streaming, and integration initialization.
"""

import os
import json
import uuid
import time
import secrets
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, Response, g, session, send_from_directory, send_file, redirect, render_template
from flask_cors import CORS

# ── Native app support: bridge DATA_DIR to DB_PATH ──
_data_dir = os.getenv("DATA_DIR")
if _data_dir and not os.getenv("DB_PATH"):
    os.makedirs(_data_dir, exist_ok=True)
    os.environ["DB_PATH"] = os.path.join(_data_dir, "myteam360.db")

# ── Logging ──
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("MyTeam360")

# ── App Init ──
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"
app.config["PERMANENT_SESSION_LIFETIME"] = 28800  # 8 hours

# CORS — restrictive by default. Set CORS_ORIGINS env var to allow specific origins.
_cors_origins = os.getenv("CORS_ORIGINS", "")
if _cors_origins:
    CORS(app, origins=_cors_origins.split(","), supports_credentials=True)
else:
    # No CORS headers = same-origin only (most secure default)
    pass

# ── Core Imports ──
from core.database import init_database, get_db
from core.providers import ProviderRegistry
from core.users import UserManager
from core.agents import AgentManager
from core.conversations import ConversationManager
from core.knowledge import KnowledgeBase
from core.workflows import WorkflowEngine
from core.messaging_hub import MessagingHub
from core.security import SecurityManager
from core.departments import DepartmentManager
from core.audit import AuditLogger
from core.analytics import AgentAnalytics, AgentTemplateManager, RecommendationEngine
from core.spend import SpendManager
from core.advanced import ModelRouter, PromptChainEngine, DelegationManager, VisionHandler
from core.integrations import EventBus, WebhookManager
from core.chat_advanced import ChatAdvanced
from core.provider_auth import ProviderAuthManager
from core.policies import PolicyManager, DataRetentionManager, IPAllowlistManager
from core.setup_wizard import SetupWizard
from core.voice_chat import TTSSynthesizer, VoiceSettingsManager, VoiceSessionTracker, SentenceChunker, TTS_PROVIDERS
from core.agent_import import AgentImportManager
from core.shared_context import SharedContextManager
from core.smart_routing import SmartRouter
from core.triggers import TriggerManager
from core.features_v2 import PipelineManager, ClientPortalManager, WorkReportManager, OutputScorer, ConversationBrancher
from core.voice_learning import VoiceProfileManager
from core.nextgen import NaturalLanguageConfig, ArtifactExtractor, ProactiveManager, TransparencyLayer
from core.untouchable import ConversationDNA, NegotiationManager, ConfidenceScorer, DecisionTracker, SpaceCloner, CostTicker
from core.roundtable import RoundtableManager, DISCUSSION_MODES
from core.governance import MeetingMinutesGenerator, RecordKeeper, ResolutionTracker, SummarizationEngine
from core.collaboration import TeamManager, CollaborativeRoundtable, PresenceTracker, ActivityFeed
from core.doc_export import DocExporter, LetterheadConfig, LetterheadManager
from core.enterprise import (ActionItemTracker, ComplianceWatchdog, ComplianceEscalation,
    DeliverableGenerator, DelegationOfAuthority, RiskRegister, PolicyEngine, KnowledgeHandoff)
from core.feature_gate import FeatureGate, FEATURE_REGISTRY
from core.onboarding import OnboardingAssistant, PricingManager, USE_CASE_TEMPLATES
from core.ip_shield import ResponseWatermark, CanarySystem, SensitiveRateLimiter, IPEvidenceLogger
from core.sales_coach import SalesCoach
from core.global_context import GlobalContextEngine
from core.marketing import DigitalMarketingEngine
from core.guardrails import ParentalConsentManager, CurriculumGuardrail, ContentFilter, CURRICULUM_TEMPLATES
from core.soul import DNAPositivityGuard, ZeroKnowledgeVault, WellbeingAwareness
from core.team_builder import SmartTeamBuilder
from core.foundations import (AccessibilityEngine, EthicalReasoningLayer,
    DataPortabilityManager, SponsoredTierManager, TransparencyReportGenerator)
from core.resilience import (ProviderFailover, ProactiveEngine, SpaceVersioning,
    ResponseFeedback, WebhookManager, BackupManager)
from core.platform_intelligence import (PlatformHealthMonitor, CollectiveFeedbackEngine,
    AdminCollaborationChannel)
from core.security_fortress import (SessionHardener, PasswordFortress, ErrorSanitizer,
    SecurityHeaders, GDPRErasure, LogSanitizer, AccountLockoutManager)
from core.email_service import EmailService, EmailTemplates
from core.enterprise_features import SSOManager, AuditExporter, RBACManager, AffiliateManager
from core.launch_essentials import ConversationOrchestrator, TOSTracker, PlanRateLimiter
from core.safety_shield import InputShield, PromptShield, OutputShield, AbuseReporter, ThreeStrikesEnforcement, ViolationAcknowledgmentManager
from core.whiteboard import RoundtableWhiteboard
from core.social_media import SocialMediaManager
from core.document_export import DocumentExporter
from core.crm import CRMManager
from core.invoicing import InvoiceManager
from core.tasks import TaskManager
from core.business_tools import (MeetingAssistant, CompetitiveIntel, ClientPortal,
    FinancialDashboard, HRAssistant, ContractTemplateManager)
from core.business_os import GoalTracker, EmailComposer, ExpenseTracker
from core.biz_upgrades import (RecurringInvoiceManager, PaymentTracker,
    TaskTimeTracker, EmailTemplateManager, ScheduledEmailManager,
    CustomExpenseCategoryManager, HashtagManager, PostApprovalWorkflow)
from core.crm_customization import (CustomFieldManager, PipelineManager as CRMPipelineManager,
    ActivityTypeManager, SavedViewManager)
from core.launch_fixes import (PlanChangeManager, CancellationManager,
    ConversationOrganizer, SpendAlertManager, validate_roundtable_participants)
from core.edu_theme import EducationThemeEngine
from core.edu_i18n import EducationI18n
from core.edu_culture import CulturalThemeEngine
from core.setup_concierge import SetupConcierge, detect_intent as detect_setup_intent
from core.prod_security import production_readiness_check, sanitize_update_columns
from core.indispensable import (DailyBriefing, QuickCapture, WorkflowAutomation,
    ContentRepurposer, SmartReminders, ClientSnapshot)
from core.lifestyle import LifestyleIntelligence
from core.safe_integrations import (CalendarReader, EmailReader, FlightTracker,
    WeatherService, CommuteEstimator)
from core.ux_essentials import (GlobalSearch, FavoritesManager, ActivityFeed,
    ScratchPad, BookingLinks, CommandPalette)
from core.business_intel import (WinLossAnalyzer, ClientHealthScorer, RevenueForecast,
    TimeToCloseTracker, ActivityScorer, UndoManager, TextMessageLog)
from core.byok import BYOKManager, SUPPORTED_PROVIDERS
from core.platform_keys import PlatformKeyPolicy
from core.provider_resilience import ProviderResilienceManager, OPEN_SOURCE_PROVIDERS
from core.nice_to_have import (OutboundWebhooks, TaskDependencyManager, RecurringTaskManager,
    LateFeeCalculator, DemoDataGenerator, ThemePreference, HelpSystem, WhatsAppLog)
from core.pedagogy import PedagogyEngine
from core.edu_pedagogy import PedagogyEngine
from core.edu_upgrades import (TeachingMethodManager, CurriculumManager,
    ParentDashboard, TestPrepEngine)
from core.edu_suite import (ProgressReportGenerator, StudyGamification)
from core.edu_suite import CurriculumManager as OldCurriculumManager
from core.edu_suite import ParentDashboard as OldParentDashboard
from core.crisis import CrisisInterventionSystem
from core.education import EducationTutor, LearningDNA, StruggleDetector, StudyPlanner, EducationPlanEnforcer
from core.i18n import I18nManager, get_available_languages, get_translations
from core.security_hardening import (FieldEncryptor, get_encryptor, PasswordPolicyManager,
                                      SessionManager, MFAManager, DLPScanner,
                                      MFAEnforcement, TrustedDeviceManager,
                                      SensitiveOperationGuard, MFARecovery)
from core.oauth import GoogleOAuth
from core.billing import register_billing_routes
from core.features import (ConversationExporter, PromptTemplateLibrary,
                            UsageQuotaManager, BrandingManager)

# ── Initialize ──
init_database()
providers = ProviderRegistry()
users = UserManager()
agents = AgentManager(providers, user_manager=users)
conversations = ConversationManager()
kb = KnowledgeBase()
workflows = WorkflowEngine(agents)
hub = MessagingHub(users, agents, conversations, knowledge_base=kb, workflow_engine=workflows)
security = SecurityManager(app, user_manager=users)
google_oauth = GoogleOAuth(app, security_manager=security, user_manager=users)
register_billing_routes(app, get_db)
departments = DepartmentManager()
audit = AuditLogger()
analytics = AgentAnalytics()
templates = AgentTemplateManager()
recommendations = RecommendationEngine()
spend_mgr = SpendManager()
router = ModelRouter()
chains = PromptChainEngine(agents)
delegation = DelegationManager(agents)
vision = VisionHandler()
event_bus = EventBus()
webhooks = WebhookManager()
chat_adv = ChatAdvanced()
provider_auth = ProviderAuthManager()
policy_mgr = PolicyManager()
retention_mgr = DataRetentionManager()
ip_allowlist = IPAllowlistManager()
setup_wizard = SetupWizard()
tts = TTSSynthesizer()
voice_settings = VoiceSettingsManager()
voice_sessions = VoiceSessionTracker()
agent_import = AgentImportManager(agent_manager=agents)
shared_ctx = SharedContextManager()
smart_router = SmartRouter()
trigger_mgr = TriggerManager(agent_manager=agents)
pipeline_mgr = PipelineManager(agent_manager=agents)
portal_mgr = ClientPortalManager()
report_mgr = WorkReportManager()
scorer = OutputScorer()
brancher = ConversationBrancher()
voice_profile = VoiceProfileManager()
nl_config = NaturalLanguageConfig()
artifacts = ArtifactExtractor()
proactive = ProactiveManager()
transparency = TransparencyLayer()
conversation_dna = ConversationDNA()
negotiation_mgr = NegotiationManager(agent_manager=agents)
confidence_scorer = ConfidenceScorer()
decision_tracker = DecisionTracker()
space_cloner = SpaceCloner(agent_manager=agents, voice_profile_manager=voice_profile)
cost_ticker = CostTicker()
roundtable = RoundtableManager(agent_manager=agents)
minutes_gen = MeetingMinutesGenerator(agent_manager=agents)
record_keeper = RecordKeeper()
resolution_tracker = ResolutionTracker()
summarizer = SummarizationEngine(agent_manager=agents)
team_mgr = TeamManager()
collab_rt = CollaborativeRoundtable(roundtable_manager=roundtable, team_manager=team_mgr)
presence = PresenceTracker()
activity_feed = ActivityFeed()
doc_exporter = DocExporter()
letterhead_mgr = LetterheadManager()
action_tracker = ActionItemTracker()
compliance_watchdog = ComplianceWatchdog()
compliance_escalation = ComplianceEscalation(watchdog=compliance_watchdog)
deliverable_gen = DeliverableGenerator(agent_manager=agents)
delegation_auth = DelegationOfAuthority()
risk_register = RiskRegister()
policy_engine = PolicyEngine()
knowledge_handoff = KnowledgeHandoff()
feature_gate = FeatureGate()
onboarding = OnboardingAssistant(feature_gate=feature_gate, agent_manager=agents)
pricing = PricingManager()
watermark = ResponseWatermark()
canary_system = CanarySystem()
sensitive_limiter = SensitiveRateLimiter()
ip_evidence = IPEvidenceLogger()
sales_coach = SalesCoach(agent_manager=agents)
global_ctx = GlobalContextEngine()
marketing = DigitalMarketingEngine(agent_manager=agents, global_context=global_ctx)
education = EducationTutor(agent_manager=agents)
learning_dna = LearningDNA()
struggle_detector = StruggleDetector()
study_planner = StudyPlanner()
edu_plan_enforcer = EducationPlanEnforcer()
parental_consent = ParentalConsentManager()
curriculum_guard = CurriculumGuardrail()
content_filter = ContentFilter()
crisis_system = CrisisInterventionSystem()  # ALWAYS ON — cannot be disabled
positivity_guard = DNAPositivityGuard()      # ALWAYS ON — DNA never goes negative
zk_vault = ZeroKnowledgeVault()
wellbeing = WellbeingAwareness()             # ALWAYS ON — the platform cares
team_builder = SmartTeamBuilder(agent_manager=agents, feature_gate=feature_gate)
accessibility = AccessibilityEngine()
ethical_layer = EthicalReasoningLayer()
data_portability = DataPortabilityManager()
sponsored_tier = SponsoredTierManager()
transparency = TransparencyReportGenerator()
provider_failover = ProviderFailover()
proactive_engine = ProactiveEngine()
space_versioning = SpaceVersioning()
response_feedback = ResponseFeedback()
webhook_mgr = WebhookManager()
backup_mgr = BackupManager()
health_monitor = PlatformHealthMonitor()
feedback_engine = CollectiveFeedbackEngine()
admin_channel = AdminCollaborationChannel(health_monitor=health_monitor, feedback_engine=feedback_engine)
session_hardener = SessionHardener()
password_fortress = PasswordFortress()
error_sanitizer = ErrorSanitizer()
security_headers_mgr = SecurityHeaders()
gdpr_erasure = GDPRErasure()
log_sanitizer = LogSanitizer()
account_lockout = AccountLockoutManager()
email_svc = EmailService()
email_tpl = EmailTemplates(email_svc)
sso_mgr = SSOManager()
audit_exporter = AuditExporter()
rbac = RBACManager()
affiliate_mgr = AffiliateManager()
tos_tracker = TOSTracker()
plan_limiter = PlanRateLimiter()
input_shield = InputShield()
prompt_shield = PromptShield()
output_shield = OutputShield()
abuse_reporter = AbuseReporter()
three_strikes = ThreeStrikesEnforcement(email_templates=email_tpl)
violation_ack = ViolationAcknowledgmentManager()
whiteboard = RoundtableWhiteboard()
social_mgr = SocialMediaManager()
doc_exporter = DocumentExporter()
crm = CRMManager()
invoice_mgr = InvoiceManager()
task_mgr = TaskManager()
meeting_assistant = MeetingAssistant()
competitive_intel = CompetitiveIntel()
client_portal = ClientPortal()
financial_dashboard = FinancialDashboard()
hr_assistant = HRAssistant()
contract_templates = ContractTemplateManager()
goal_tracker = GoalTracker()
email_composer = EmailComposer()
expense_tracker = ExpenseTracker()
custom_fields = CustomFieldManager()
crm_pipeline_mgr = CRMPipelineManager()
activity_types = ActivityTypeManager()
saved_views = SavedViewManager()
recurring_invoices = RecurringInvoiceManager()
payment_tracker = PaymentTracker()
time_tracker = TaskTimeTracker()
email_templates_mgr = EmailTemplateManager()
scheduled_emails = ScheduledEmailManager()
custom_expense_cats = CustomExpenseCategoryManager()
hashtag_mgr = HashtagManager()
post_approval = PostApprovalWorkflow()
plan_changer = PlanChangeManager()
cancel_mgr = CancellationManager()
conv_organizer = ConversationOrganizer()
spend_alerts = SpendAlertManager()
edu_theme = EducationThemeEngine()
edu_i18n = EducationI18n()
cultural_theme = CulturalThemeEngine()
setup_concierge = SetupConcierge()
daily_briefing = DailyBriefing()
quick_capture = QuickCapture()
workflow_automation = WorkflowAutomation()
content_repurposer = ContentRepurposer()
smart_reminders = SmartReminders()
client_snapshot = ClientSnapshot()
lifestyle = LifestyleIntelligence()
calendar_reader = CalendarReader()
email_reader = EmailReader()
flight_tracker = FlightTracker()
weather_svc = WeatherService()
commute_est = CommuteEstimator()
global_search = GlobalSearch()
favorites_mgr = FavoritesManager()
activity_feed = ActivityFeed()
scratch_pad = ScratchPad()
booking_links = BookingLinks()
cmd_palette = CommandPalette()
win_loss = WinLossAnalyzer()
health_scorer = ClientHealthScorer()
revenue_forecast = RevenueForecast()
ttc_tracker = TimeToCloseTracker()
activity_scorer = ActivityScorer()
undo_mgr = UndoManager()
text_log = TextMessageLog()
byok = BYOKManager()
platform_key_policy = PlatformKeyPolicy()
provider_resilience = ProviderResilienceManager()
outbound_hooks = OutboundWebhooks()
task_deps = TaskDependencyManager()
recurring_tasks = RecurringTaskManager()
late_fees = LateFeeCalculator()
demo_data = DemoDataGenerator()
theme_pref = ThemePreference()
help_system = HelpSystem()
whatsapp_log = WhatsAppLog()
pedagogy = PedagogyEngine()
pedagogy = PedagogyEngine()
teaching_methods = TeachingMethodManager()
curriculum_mgr = CurriculumManager()
parent_dashboard = ParentDashboard()
test_prep = TestPrepEngine()
progress_reports = ProgressReportGenerator()
gamification = StudyGamification()
parent_dash = OldParentDashboard()
curriculum = OldCurriculumManager()
i18n = I18nManager()


def _gated(feature: str):
    """Check if a feature is enabled. Returns 403 JSON if disabled."""
    if not feature_gate.is_enabled(feature):
        label = FEATURE_REGISTRY.get(feature, {}).get("label", feature)
        return jsonify({"error": f"{label} is not activated. An admin must enable it in Settings → Features."}), 403
    return None
password_policy = PasswordPolicyManager()
session_mgr = SessionManager()
mfa_mgr = MFAManager()
mfa_enforcement = MFAEnforcement()
trusted_devices = TrustedDeviceManager()
sensitive_ops = SensitiveOperationGuard()
mfa_recovery = MFARecovery()
dlp = DLPScanner()
conv_exporter = ConversationExporter()
prompt_templates = PromptTemplateLibrary()
usage_quotas = UsageQuotaManager()
branding_mgr = BrandingManager()

# Seed defaults on first boot
try:
    policy_mgr.seed_default_aup()
    retention_mgr.seed_defaults()
except Exception as e:
    logger.debug(f"Default seeding: {e}")

# Seed default agent templates on first boot
try:
    seeded = templates.seed_templates()
    if seeded:
        logger.info(f"Seeded {seeded} agent templates")
except Exception as e:
    logger.warning(f"Template seeding: {e}")

# ── Integrations (optional) ──
slack_handler = None
telegram_handler = None
sms_handler = None

try:
    from interfaces.slack_bot.bot import create_slack_bot, register_slack_routes
    slack_handler = create_slack_bot(hub)
    register_slack_routes(app, slack_handler)
except Exception as e:
    logger.info(f"Slack not loaded: {e}")

try:
    from interfaces.telegram_bot.bot import create_telegram_bot, register_telegram_routes
    telegram_handler = create_telegram_bot(hub)
    register_telegram_routes(app, telegram_handler)
except Exception as e:
    logger.info(f"Telegram not loaded: {e}")

try:
    from interfaces.sms.handler import create_sms_handler, register_sms_routes
    sms_handler = create_sms_handler(hub)
    register_sms_routes(app, sms_handler)
except Exception as e:
    logger.info(f"SMS not loaded: {e}")


# ═══════════════════════════════════════════════════════════════
# SECURITY HEADERS — Defense in depth (works even without nginx)
# ═══════════════════════════════════════════════════════════════

@app.after_request
def security_headers(response):
    headers = security_headers_mgr.get_headers()
    for k, v in headers.items():
        response.headers[k] = v
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.before_request
def _start_timer():
    g._request_start = time.time()

@app.before_request
def _check_pending_acknowledgment():
    """Block ALL platform usage until user acknowledges pending violations.
    This is the enforcement mechanism — no way around it."""
    # Skip for non-API routes, auth routes, and the acknowledge endpoint itself
    exempt = [
        "/api/auth/", "/api/safety/acknowledge", "/api/safety/pending",
        "/api/safety/strikes/my", "/api/tos/", "/api/status",
        "/static/", "/terms", "/app", "/",
    ]
    if any(request.path.startswith(e) for e in exempt):
        return
    if not request.path.startswith("/api/"):
        return
    if not hasattr(g, 'user_id') or not g.user_id:
        return

    try:
        pending = violation_ack.get_pending(g.user_id)
        if pending:
            return jsonify({
                "error": "acknowledgment_required",
                "status": 451,  # "Unavailable for Legal Reasons"
                "message": "You must acknowledge a safety policy violation before continuing.",
                "acknowledgment_id": pending["id"],
                "acknowledgment_text": pending["acknowledgment_text"],
                "violation_label": pending["violation_label"],
                "tos_section": pending["tos_section"],
                "strike_number": pending["strike_number"],
                "query_excerpt": pending["query_excerpt"],
                "violation_timestamp": pending["violation_timestamp"],
                "acknowledge_url": "/api/safety/acknowledge",
            }), 451
    except Exception:
        pass

@app.after_request
def _track_health(response):
    """Track every request for platform health monitoring."""
    try:
        duration_ms = (time.time() - getattr(g, '_request_start', time.time())) * 1000
        endpoint = request.path

        if response.status_code >= 400 and endpoint.startswith('/api/'):
            error_body = response.get_data(as_text=True)[:200]
            health_monitor.record_error(endpoint, response.status_code,
                error_body, user_id=getattr(g, 'user_id', ''), duration_ms=duration_ms)

        if duration_ms > 3000 and endpoint.startswith('/api/'):
            health_monitor.record_slow_endpoint(endpoint, duration_ms)

        # Detect feature gap — 403 with "not activated" message
        if response.status_code == 403 and b'not activated' in response.get_data():
            try:
                data = response.get_json()
                if data and 'error' in str(data):
                    health_monitor.record_feature_gap(endpoint, getattr(g, 'user_id', ''))
            except:
                pass
    except:
        pass
    return response


# ═══════════════════════════════════════════════════════════════
# ROUTES — Dashboard & Status
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """Marketing site if not logged in, redirect to app if logged in."""
    if session.get("user_id"):
        user = users.get_user(session["user_id"])
        if user and user.get("is_active"):
            return redirect("/app")
    return send_from_directory("templates", "site.html")

@app.route("/home")
def marketing_home():
    """Always show marketing site (even if logged in)."""
    return send_from_directory("templates", "site.html")

@app.route("/gate")
def gate_page():
    """Password gate — protects the app during development."""
    if session.get("gate_passed"):
        return redirect("/app/dashboard")
    return render_template("gate.html")

@app.route("/gate", methods=["POST"])
def gate_check():
    """Validate gate password."""
    pw = request.form.get("password", "")
    gate_pw = os.getenv("GATE_PASSWORD", "mt360preview")
    if pw == gate_pw:
        session["gate_passed"] = True
        return redirect("/app/dashboard")
    return render_template("gate.html", error="Invalid password")

def _require_gate():
    """Redirect to gate if not passed."""
    if not session.get("gate_passed"):
        return redirect("/gate")
    return None

@app.route("/app")
def app_redirect():
    return redirect("/app/dashboard")

@app.route("/app/dashboard")
def dashboard_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("dashboard.html")

@app.route("/app/briefing")
def briefing_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("briefing.html")

@app.route("/app/crm")
def crm_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("crm.html")

@app.route("/app/tasks")
def tasks_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("tasks.html")

@app.route("/app/invoicing")
def invoicing_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("invoicing.html")

@app.route("/app/social")
def social_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("social.html")

@app.route("/app/roundtable")
def roundtable_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("roundtable.html")

@app.route("/app/providers")
def providers_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("providers.html")

@app.route("/app/settings")
def settings_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("settings.html")

@app.route("/app/spaces")
def spaces_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("dashboard.html")

@app.route("/app/goals")
def goals_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("dashboard.html")

@app.route("/app/analytics")
def analytics_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("dashboard.html")

@app.route("/app/dna")
def dna_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("dashboard.html")

@app.route("/app/team")
def team_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("settings.html")

@app.route("/app/bookings")
def bookings_page():
    gate = _require_gate()
    if gate: return gate
    return render_template("dashboard.html")

@app.route("/security")
def security_page():
    return send_from_directory("templates", "security.html")

@app.route("/terms")
def terms_page():
    return send_from_directory("templates", "terms.html")

@app.route("/privacy")
def privacy_page():
    return send_from_directory("templates", "privacy.html")

@app.route("/auth/reset-password")
def reset_password_page():
    """Password reset page — token in URL param."""
    return send_from_directory("templates", "site.html")

@app.route("/auth/mfa-recover")
def mfa_recover_page():
    """MFA recovery page — token in URL param."""
    return send_from_directory("templates", "site.html")

@app.route("/api/auth/check", methods=["GET"])
def auth_check():
    """Lightweight auth check — frontend calls this to show login/dashboard state."""
    if session.get("user_id"):
        user = users.get_user(session["user_id"])
        if user and user.get("is_active"):
            first = (user.get("display_name", "") or "").split()[0] if user.get("display_name") else ""
            return jsonify({"authenticated": True, "user_id": user["id"],
                           "name": user.get("display_name", ""), "first_name": first,
                           "role": user.get("role", "member")})
    return jsonify({"authenticated": False})

@app.route("/static/native-bridge.js")
def native_bridge_js():
    return send_from_directory("templates", "native-bridge.js", mimetype="application/javascript")

@app.route("/static/logo.png")
def serve_logo():
    return send_from_directory("templates", "logo.png", mimetype="image/png")

@app.route("/static/logo-nav.png")
def serve_logo_nav():
    return send_from_directory("templates", "logo-nav.png", mimetype="image/png")

@app.route("/static/logo-hero.png")
def serve_logo_hero():
    return send_from_directory("templates", "logo-hero.png", mimetype="image/png")


@app.route("/health")
def health_check():
    """Lightweight healthcheck for Railway / load balancers — no auth required."""
    return jsonify({"status": "ok", "service": "myteam360", "backend": get_db.__module__}), 200


@app.route("/api/status")
def api_status():
    # If no authenticated user, return basic status (healthcheck-safe)
    if not hasattr(g, 'user_id') or not g.user_id:
        return jsonify({"status": "ok", "service": "myteam360"}), 200
    u = users.get_user(g.user_id)
    conv_stats = conversations.get_stats(g.user_id)
    kb_stats = kb.get_stats(g.user_id)
    agent_list = agents.list_agents(user_id=g.user_id)
    wf_list = workflows.list_workflows(user_id=g.user_id)
    return jsonify({
        "conversations": conv_stats.get("conversations", 0),
        "messages": conv_stats.get("messages", 0),
        "agents": len(agent_list),
        "documents": kb_stats.get("documents", 0),
        "workflows": len(wf_list),
        "providers": providers.list_all(),
    })


# ═══════════════════════════════════════════════════════════════
# ROUTES — Users & Team
# ═══════════════════════════════════════════════════════════════

@app.route("/api/users", methods=["GET"])
def list_users():
    if not users.has_permission(g.user_id, "manage_users"):
        return jsonify({"error": "Permission denied"}), 403
    all_users = users.list_users()
    # Add usage stats per user
    for u in all_users:
        u["usage"] = users.get_monthly_usage(u["id"])
        u["budget"] = users.check_budget(u["id"])
    return jsonify({"users": all_users})


@app.route("/api/users", methods=["POST"])
def create_user():
    if not users.has_permission(g.user_id, "manage_users"):
        return jsonify({"error": "Permission denied"}), 403
    data = request.json
    try:
        user = users.create_user(
            email=data["email"], display_name=data.get("display_name", data.get("name", "")),
            password=data.get("password", uuid.uuid4().hex[:12]),
            role=data.get("role", "member"), invited_by=g.user_id
        )
        # Create a token for the new user
        token_info = security.create_token(user["id"], name="default")
        return jsonify({"user": user, "token": token_info["token"]}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/users/<user_id>", methods=["PUT"])
def update_user_route(user_id):
    if g.user_id != user_id and not users.has_permission(g.user_id, "manage_users"):
        return jsonify({"error": "Permission denied"}), 403
    user = users.update_user(user_id, request.json)
    return jsonify({"user": user})


@app.route("/api/users/<user_id>", methods=["DELETE"])
def delete_user_route(user_id):
    if not users.has_permission(g.user_id, "manage_users"):
        return jsonify({"error": "Permission denied"}), 403
    users.delete_user(user_id)
    return jsonify({"success": True})


@app.route("/api/me")
def get_me():
    u = users.get_user(g.user_id)
    first = (u.get("display_name", "") or "").split()[0] if u.get("display_name") else ""
    u["first_name"] = first
    return jsonify({"user": u, "permissions": list(users.get_permissions(g.user_id))})


@app.route("/api/me/greeting")
def get_greeting():
    """Personalized, time-aware greeting."""
    from datetime import datetime
    u = users.get_user(g.user_id)
    first = (u.get("display_name", "") or "").split()[0] if u.get("display_name") else ""
    hour = datetime.now().hour

    if hour < 12:
        time_greeting = "Good morning"
    elif hour < 17:
        time_greeting = "Good afternoon"
    elif hour < 21:
        time_greeting = "Good evening"
    else:
        time_greeting = "Good evening"

    if first:
        greeting = f"{time_greeting}, {first}"
    else:
        greeting = f"{time_greeting}"

    # Add contextual message
    tips = []
    try:
        upcoming = study_planner.get_upcoming(g.user_id, days=2)
        if upcoming:
            tips.append(f"You have {len(upcoming)} assignment{'s' if len(upcoming) != 1 else ''} due in the next 2 days.")
    except Exception:
        pass

    return jsonify({
        "greeting": greeting,
        "first_name": first,
        "full_name": u.get("display_name", ""),
        "time_of_day": "morning" if hour < 12 else "afternoon" if hour < 17 else "evening",
        "tips": tips,
    })


@app.route("/api/me/profile", methods=["GET"])
def get_my_profile():
    return jsonify({"profile": users.get_profile(g.user_id)})


@app.route("/api/me/profile", methods=["PUT"])
def update_my_profile():
    return jsonify({"profile": users.update_profile(g.user_id, request.json)})


@app.route("/api/me/preferences", methods=["GET"])
def get_my_prefs():
    return jsonify({"preferences": users.get_preferences(g.user_id)})


@app.route("/api/me/preferences", methods=["PUT"])
def set_my_prefs():
    for k, v in request.json.items():
        users.set_preference(g.user_id, k, str(v))
    return jsonify({"preferences": users.get_preferences(g.user_id)})


@app.route("/api/me/password", methods=["PUT"])
def change_my_password():
    data = request.json
    user = users.authenticate(users.get_user(g.user_id)["email"], data.get("current", ""))
    if not user:
        return jsonify({"error": "Current password incorrect"}), 400
    users.change_password(g.user_id, data["new"])
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════
# ROUTES — Agents
# ═══════════════════════════════════════════════════════════════

@app.route("/api/agents", methods=["GET"])
def list_agents():
    return jsonify({"agents": agents.list_agents(user_id=g.user_id)})


@app.route("/api/agents/templates", methods=["GET"])
def list_templates():
    return jsonify({"templates": agents.list_templates()})


@app.route("/api/agents", methods=["POST"])
def create_agent():
    if not users.has_permission(g.user_id, "create_agents"):
        return jsonify({"error": "Permission denied"}), 403
    data = request.json
    if data.get("from_template"):
        agent = agents.create_from_template(data["from_template"], owner_id=g.user_id, overrides=data)
    else:
        agent = agents.create_agent(data, owner_id=g.user_id)
    return jsonify({"agent": agent}), 201


@app.route("/api/agents/<agent_id>", methods=["GET"])
def get_agent(agent_id):
    agent = agents.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"agent": agent})


@app.route("/api/agents/<agent_id>", methods=["PUT"])
def update_agent(agent_id):
    agent = agents.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Not found"}), 404
    if agent["owner_id"] != g.user_id and not users.has_permission(g.user_id, "manage_users"):
        return jsonify({"error": "Permission denied"}), 403
    data = request.json or {}
    # Version prompt if instructions are changing
    new_instructions = data.get("instructions")
    if new_instructions and new_instructions != agent.get("instructions", ""):
        agent_import._version_prompt(agent_id, agent.get("instructions", ""))
    return jsonify({"agent": agents.update_agent(agent_id, data)})


@app.route("/api/agents/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id):
    agent = agents.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Not found"}), 404
    if agent["owner_id"] != g.user_id and not users.has_permission(g.user_id, "manage_users"):
        return jsonify({"error": "Permission denied"}), 403
    agents.delete_agent(agent_id)
    return jsonify({"success": True})


@app.route("/api/agents/<agent_id>/duplicate", methods=["POST"])
def duplicate_agent(agent_id):
    dup = agents.duplicate_agent(agent_id, owner_id=g.user_id)
    if not dup:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"agent": dup}), 201


# ═══════════════════════════════════════════════════════════════
# ROUTES — Agent Import & Sync
# ═══════════════════════════════════════════════════════════════

@app.route("/api/import/openai/list", methods=["GET"])
def list_openai_assistants():
    """List all GPTs/Assistants from user's OpenAI account."""
    api_key = _get_openai_key()
    if not api_key:
        return jsonify({"error": "No OpenAI API key configured. Add one in Settings → Providers."}), 400
    try:
        assistants = agent_import.list_openai_assistants(api_key)
        return jsonify({"assistants": assistants, "count": len(assistants)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/import/openai", methods=["POST"])
def import_openai_assistant():
    """Import a single OpenAI assistant."""
    data = request.json or {}
    assistant_id = data.get("assistant_id")
    if not assistant_id:
        return jsonify({"error": "assistant_id required"}), 400
    api_key = _get_openai_key()
    if not api_key:
        return jsonify({"error": "No OpenAI API key configured"}), 400
    try:
        agent = agent_import.import_openai_assistant(
            api_key, assistant_id, g.user_id,
            overrides=data.get("overrides")
        )
        return jsonify({"agent": agent, "message": f"Imported '{agent['name']}'"}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/import/openai/all", methods=["POST"])
def import_all_openai_assistants():
    """Import all OpenAI assistants at once."""
    api_key = _get_openai_key()
    if not api_key:
        return jsonify({"error": "No OpenAI API key configured"}), 400
    try:
        results = agent_import.import_all_openai(api_key, g.user_id)
        return jsonify(results), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/import/openai/<agent_id>/sync", methods=["POST"])
def sync_openai_agent(agent_id):
    """Sync an imported agent with OpenAI (pull or push)."""
    data = request.json or {}
    direction = data.get("direction", "pull")
    api_key = _get_openai_key()
    if not api_key:
        return jsonify({"error": "No OpenAI API key configured"}), 400
    try:
        result = agent_import.sync_openai_assistant(api_key, agent_id, direction)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/import/manual", methods=["POST"])
def import_manual_agent():
    """Import an agent from a manual config (paste instructions)."""
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    try:
        agent = agent_import.import_manual(data, g.user_id)
        return jsonify({"agent": agent}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/import/json", methods=["POST"])
def import_json_agent():
    """Import an agent from a JSON config file."""
    data = request.json or {}
    try:
        agent = agent_import.import_agent_json(data, g.user_id)
        return jsonify({"agent": agent}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/<agent_id>/export", methods=["GET"])
def export_agent_json(agent_id):
    """Export an agent as a portable JSON config."""
    try:
        config = agent_import.export_agent_json(agent_id)
        return jsonify(config)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/agents/<agent_id>/prompt-history", methods=["GET"])
def get_prompt_history(agent_id):
    """Get version history of an agent's instructions."""
    history = agent_import.get_prompt_history(agent_id)
    return jsonify({"agent_id": agent_id, "history": history})


@app.route("/api/agents/<agent_id>/prompt-rollback", methods=["POST"])
def rollback_prompt(agent_id):
    """Rollback agent instructions to a previous version."""
    data = request.json or {}
    version = data.get("version")
    if version is None:
        return jsonify({"error": "version required"}), 400
    try:
        result = agent_import.rollback_prompt(agent_id, int(version))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/import/sync-status", methods=["GET"])
def get_sync_status():
    """Get sync status for all imported agents."""
    status = agent_import.get_sync_status(g.user_id)
    return jsonify({"agents": status})


@app.route("/api/agents/<agent_id>/toggle-sync", methods=["POST"])
def toggle_agent_sync(agent_id):
    """Enable/disable auto-sync for an imported agent."""
    data = request.json or {}
    enabled = data.get("enabled", True)
    result = agent_import.toggle_sync(agent_id, enabled)
    return jsonify(result)


def _get_openai_key() -> str | None:
    """Get the OpenAI API key from provider auth or env."""
    try:
        creds = provider_auth.get_credentials("openai")
        if creds:
            return creds.get("api_key") or creds.get("access_token")
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY")


# ═══════════════════════════════════════════════════════════════
# ROUTES — Conversations & Chat
# ═══════════════════════════════════════════════════════════════

@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    return jsonify({"conversations": conversations.list_conversations(g.user_id)})


@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    data = request.json or {}
    conv = conversations.create_conversation(
        g.user_id, agent_id=data.get("agent_id"), title=data.get("title", "New Conversation"))
    return jsonify({"conversation": conv}), 201


@app.route("/api/conversations/<conv_id>", methods=["GET"])
def get_conversation(conv_id):
    conv = conversations.get_conversation(conv_id)
    if not conv:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"conversation": conv})


@app.route("/api/conversations/<conv_id>", methods=["PUT"])
def update_conversation(conv_id):
    return jsonify({"conversation": conversations.update_conversation(conv_id, request.json)})


@app.route("/api/conversations/<conv_id>", methods=["DELETE"])
def delete_conversation(conv_id):
    conversations.delete_conversation(conv_id)
    return jsonify({"success": True})


@app.route("/api/conversations/<conv_id>/messages", methods=["GET"])
def get_messages(conv_id):
    msgs = conversations.get_messages(conv_id, limit=int(request.args.get("limit", 100)))
    return jsonify({"messages": msgs})


@app.route("/api/conversations/search", methods=["GET"])
def search_conversations():
    q = request.args.get("q", "")
    return jsonify({"results": conversations.search(g.user_id, q)})


@app.route("/api/chat", methods=["POST"])
def chat():
    """Non-streaming chat with vision, routing, and delegation."""
    data = request.json
    conv_id = data.get("conversation_id")
    agent_id = data.get("agent_id")
    message = data.get("message", "")
    images = data.get("images", [])

    budget_check = spend_mgr.check_budget_enforcement(g.user_id)
    if not budget_check["allowed"]:
        return jsonify({"error": "Budget exceeded.", "warnings": budget_check["warnings"]}), 402

    # DLP scan — block or warn if sensitive data detected
    if message:
        dlp_result = dlp.scan(message, context="input")
        if not dlp_result["clean"]:
            dlp.log_detection(g.user_id, message, dlp_result, "input")
            if dlp_result["action"] == "block":
                return jsonify({
                    "error": "dlp_blocked",
                    "message": dlp_result["message"],
                    "findings": dlp_result["findings"],
                }), 422

    # Quota check
    quota_check = usage_quotas.check_quota(g.user_id)
    if not quota_check["allowed"]:
        return jsonify({
            "error": "quota_exceeded",
            "message": "Monthly usage quota exceeded.",
            "warnings": quota_check["warnings"],
        }), 429

    if not conv_id:
        conv = conversations.create_conversation(g.user_id, agent_id=agent_id)
        conv_id = conv["id"]
    if not agent_id:
        conv = conversations.get_conversation(conv_id)
        if conv: agent_id = conv.get("agent_id")
    if conv_id:
        existing = conversations.get_conversation(conv_id)
        if not existing:
            return jsonify({"error": "Conversation not found"}), 404

    # Save images
    image_urls = []
    for img in images:
        path = vision.save_image(img, conv_id)
        if path: image_urls.append(path)

    try:
        conversations.add_message(conv_id, "user", message)
    except Exception as e:
        return jsonify({"error": "Failed to save message: {}".format(str(e))}), 400

    # ── Voice Learning: ingest user's writing style ──
    try:
        voice_profile.ingest_sample(g.user_id, message, "user_message")
    except Exception:
        pass

    agent = agents.get_agent(agent_id) if agent_id else None

    # Multi-model routing
    route_info = None
    if agent and agent.get("routing_mode") == "auto":
        route_info = router.get_route(message)

    # KB context
    kb_context = ""
    if agent and agent.get("use_knowledge_base"):
        folders = agent.get("knowledge_folders", [])
        if isinstance(folders, str):
            try: folders = json.loads(folders)
            except: folders = []
        kb_context = kb.get_context_for_agent(message, g.user_id, folder_ids=folders or None)

    # ── Shared Context: inject cross-Space knowledge ──
    try:
        shared_injection = shared_ctx.build_context_injection(
            g.user_id, message, agent_id=agent_id, max_tokens=500)
        if shared_injection:
            kb_context = (kb_context or "") + "\n\n" + shared_injection
    except Exception:
        pass

    # ── Voice Learning: inject user's writing style ──
    try:
        voice_injection = voice_profile.build_voice_injection(g.user_id)
        if voice_injection:
            kb_context = (kb_context or "") + "\n\n" + voice_injection
    except Exception:
        pass

    # ── Name Personalization: use the user's name naturally ──
    try:
        first = getattr(g, 'first_name', '') or ''
        full = getattr(g, 'user_name', '') or ''
        if first:
            name_injection = (
                f"[USER CONTEXT] The user's name is {full}. Their first name is {first}. "
                f"Use their first name naturally in conversation the way a colleague would — "
                f"when greeting them, when acknowledging a good point, when delivering important "
                f"information, or when the conversation benefits from a personal touch. "
                f"Do NOT overuse it — a name every 3-5 messages feels natural. "
                f"Every single message feels robotic."
            )
            kb_context = (kb_context or "") + "\n\n" + name_injection
    except Exception:
        pass

    # ── SAFETY PROMPT SHIELD: ALWAYS ON — liability protection ──
    try:
        kb_context = (kb_context or "") + "\n\n" + prompt_shield.build_universal_safety_prompt()
        advice_contexts = prompt_shield.detect_advice_context(message)
        if advice_contexts:
            disclaimer = prompt_shield.build_context_disclaimer(advice_contexts)
            if disclaimer:
                kb_context = (kb_context or "") + "\n\n" + disclaimer
    except Exception:
        pass

    # ── Positivity Guard: ALWAYS ON — DNA never goes negative ──
    try:
        kb_context = (kb_context or "") + "\n\n" + positivity_guard.build_positivity_injection()

        tone_analysis = positivity_guard.analyze_tone(message)
        if tone_analysis.get("is_negative"):
            tone_guidance = tone_analysis.get("tone_guidance", "")
            if tone_guidance:
                kb_context = (kb_context or "") + "\n\n" + tone_guidance
    except Exception:
        pass

    # ── Wellbeing Awareness: ALWAYS ON — the platform cares ──
    try:
        wellbeing_check = wellbeing.assess_message(g.user_id, message)
        if wellbeing_check.get("needs_care"):
            care_injection = wellbeing.build_care_injection(
                wellbeing_check, user_first_name=getattr(g, 'first_name', ''))
            if care_injection:
                kb_context = (kb_context or "") + "\n\n" + care_injection
    except Exception:
        pass

    # ── Ethical Reasoning: flag human impact decisions ──
    try:
        ethical_check = ethical_layer.analyze(message)
        if ethical_check.get("has_ethical_dimension"):
            ethical_injection = ethical_layer.build_injection(ethical_check)
            if ethical_injection:
                kb_context = (kb_context or "") + "\n\n" + ethical_injection
    except Exception:
        pass

    # ── Accessibility: adapt AI response format to user's mode ──
    try:
        a11y = accessibility.get_user_mode(g.user_id)
        if a11y.get("mode") and a11y["mode"] != "default":
            a11y_injection = accessibility.build_ai_instruction(a11y["mode"])
            if a11y_injection:
                kb_context = (kb_context or "") + "\n\n" + a11y_injection
    except Exception:
        pass

    # ── Crisis Safety Injection: ALWAYS active, cannot be disabled ──
    kb_context = (kb_context or "") + "\n\n" + crisis_system.build_safety_injection()

    # ── Global Context: inject locale-aware compliance + language ──
    try:
        locale = global_ctx.get_workspace_locale()
        if locale.get("country") and locale["country"] != "US":
            locale_ctx = global_ctx.build_full_context(
                country_code=locale["country"],
                language=locale.get("language"),
                include_compliance=feature_gate.is_enabled("compliance_watchdog"),
                include_governance=feature_gate.is_enabled("corporate_records"))
            if locale_ctx:
                kb_context = (kb_context or "") + "\n\n" + locale_ctx
    except Exception:
        pass

    # ══════════════════════════════════════════════════════════
    # INPUT SHIELD — ALWAYS ON — BLOCKS BEFORE AI — CANNOT BE DISABLED
    # ══════════════════════════════════════════════════════════
    safety_check = input_shield.scan(message, user_id=g.user_id)
    if safety_check.get("blocked"):
        # Record the strike with full violation details
        strike_result = three_strikes.record_violation(
            g.user_id, safety_check.get("category", "unknown"),
            safety_check.get("severity", "high"),
            detail=f"Blocked message in conversation {conv_id}",
            violation_label=safety_check.get("violation_label", ""),
            tos_section=safety_check.get("tos_section", ""),
            query=safety_check.get("query", message[:500]),
            timestamp=safety_check.get("timestamp", ""))

        response_msg = strike_result.get("message", safety_check["message"])

        # Create mandatory acknowledgment (unless terminated)
        ack_data = {}
        if strike_result.get("action") in ("warning", "final_warning") and strike_result.get("strike"):
            ack_data = violation_ack.create_pending(
                g.user_id,
                strike_id=strike_result.get("strike_id", ""),
                strike_number=strike_result["strike"],
                violation_label=safety_check.get("violation_label", ""),
                tos_section=safety_check.get("tos_section", ""),
                query_excerpt=safety_check.get("query", "")[:200],
                violation_timestamp=safety_check.get("timestamp", ""))

        if strike_result.get("action") == "terminated":
            session.clear()

        if conv_id:
            conversations.add_message(conv_id, "user", message, agent_id=agent_id)
            conversations.add_message(conv_id, "assistant", response_msg, agent_id=agent_id)
        return jsonify({
            "response": response_msg,
            "message": {"content": response_msg},
            "conversation_id": conv_id,
            "safety_blocked": True,
            "safety_category": safety_check.get("category"),
            "violation_label": safety_check.get("violation_label"),
            "tos_section": safety_check.get("tos_section"),
            "strike": strike_result.get("strike"),
            "strike_action": strike_result.get("action"),
            "timestamp": safety_check.get("timestamp"),
            "acknowledgment_required": bool(ack_data.get("acknowledgment_required")),
            "acknowledgment_id": ack_data.get("acknowledgment_id"),
            "acknowledgment_text": ack_data.get("acknowledgment_text"),
        })

    # ══════════════════════════════════════════════════════════
    # CRISIS INTERVENTION — ALWAYS ON — FIRST CHECK — CANNOT BE DISABLED
    # ══════════════════════════════════════════════════════════
    crisis_result = crisis_system.scan_message(g.user_id, message)
    if crisis_result.get("crisis_detected") and crisis_result.get("block_ai"):
        # Tier 1 or 2: Do NOT send to AI. Override with crisis response.
        locale = {"country": "US"}
        try:
            locale = global_ctx.get_workspace_locale()
        except Exception:
            pass
        first = getattr(g, 'first_name', '') or ''
        crisis_response = crisis_system.get_crisis_response(
            crisis_result["tier"], country_code=locale.get("country", "US"),
            user_first_name=first)
        # Store in conversation so there's a record
        if conv_id:
            conversations.add_message(conv_id, "user", message, agent_id=agent_id)
            conversations.add_message(conv_id, "assistant", crisis_response, agent_id=agent_id)
        return jsonify({
            "response": crisis_response,
            "message": {"content": crisis_response},
            "conversation_id": conv_id,
            "crisis_intervention": True,
            "crisis_tier": crisis_result["tier"],
        })

    # If Tier 3 (watch), let AI respond but we'll append resources after
    crisis_append = None
    if crisis_result.get("crisis_detected") and not crisis_result.get("block_ai"):
        locale = {"country": "US"}
        try:
            locale = global_ctx.get_workspace_locale()
        except Exception:
            pass
        first = getattr(g, 'first_name', '') or ''
        crisis_append = crisis_system.get_crisis_response(
            crisis_result["tier"], country_code=locale.get("country", "US"),
            user_first_name=first)

    # ── Parental Consent: block minors without consent ──
    try:
        consent_status = parental_consent.check_consent(g.user_id)
        if consent_status.get("is_minor") and not consent_status.get("consent_granted"):
            return jsonify({
                "error": "parental_consent_required",
                "message": consent_status.get("message", "Parental consent required."),
                "needs_consent": True,
            }), 403
    except Exception:
        pass

    # ── Curriculum Guardrails: check message against approved topics ──
    try:
        curriculum_check = curriculum_guard.check_message(message)
        if not curriculum_check.get("allowed", True):
            return jsonify({
                "error": "content_restricted",
                "message": curriculum_check.get("reason", "This topic is not permitted."),
            }), 403
    except Exception:
        pass

    # ── Curriculum Injection: tell AI what topics are allowed ──
    try:
        guardrail_injection = curriculum_guard.build_guardrail_injection()
        if guardrail_injection:
            kb_context = (kb_context or "") + "\n\n" + guardrail_injection
    except Exception:
        pass

    # ── Learning DNA: adapt teaching to this student's learning style ──
    try:
        if edu_plan_enforcer.is_education_plan(g.user_id):
            dna_injection = learning_dna.build_tutor_injection(g.user_id, subject="")
            if dna_injection:
                kb_context = (kb_context or "") + "\n\n" + dna_injection

            # Struggle Detection: check for frustration signals
            struggle_result = struggle_detector.analyze_message(g.user_id, message)
            if struggle_result.get("intervention_needed"):
                intervention = struggle_detector.build_intervention_prompt(
                    struggle_result.get("signals", []))
                if intervention:
                    kb_context = (kb_context or "") + "\n\n" + intervention
    except Exception:
        pass

    # ── Business DNA: inject organizational knowledge (if activated) ──
    had_dna = False
    if feature_gate.is_enabled("business_dna"):
        try:
            dna_injection = conversation_dna.build_dna_injection(g.user_id, message, max_items=3)
            if dna_injection:
                kb_context = (kb_context or "") + "\n\n" + dna_injection
                had_dna = True
        except Exception:
            pass

    # ── Policy Engine: inject company policies (if activated) ──
    if feature_gate.is_enabled("policy_engine"):
        try:
            policy_injection = policy_engine.build_policy_injection(g.user_id, agent_id=agent_id)
            if policy_injection:
                kb_context = (kb_context or "") + "\n\n" + policy_injection
        except Exception:
            pass

    # ── Compliance Watchdog: scan user input (if activated) ──
    compliance_alert = None
    if feature_gate.is_enabled("compliance_watchdog"):
        try:
            comp_result = compliance_watchdog.scan_text(message, context="user_input")
            if not comp_result["clean"]:
                if feature_gate.is_enabled("compliance_escalation"):
                    escalation_results = []
                    for flag in comp_result.get("flags", []):
                        esc = compliance_escalation.process_violation(
                            g.user_id, flag, source_type="chat", source_id=conv_id,
                            user_id=g.user_id, user_name=getattr(g, 'user_name', ''))
                        escalation_results.append(esc)
                    comp_result["escalations"] = escalation_results
                compliance_alert = comp_result
        except Exception:
            pass

    # Track what sources contributed (for confidence scoring)
    _ctx_sources = {
        "had_kb": bool(kb_context and agent and agent.get("use_knowledge_base")),
        "had_shared": bool(shared_injection if 'shared_injection' in dir() else False),
        "had_dna": had_dna,
    }

    # Delegation instructions
    if agent and agent.get("can_delegate"):
        deleg_prompt = delegation.build_delegation_prompt(agent)
        if deleg_prompt: kb_context = (kb_context or "") + deleg_prompt

    context_msgs = conversations.get_context_messages(conv_id)

    # Vision: build multimodal message
    if images and agent:
        model = (route_info or {}).get("model") or agent.get("model") or ""
        if vision.is_vision_model(model):
            content = vision.build_vision_message(message, images)
            if context_msgs and context_msgs[-1].get("role") == "user":
                context_msgs[-1]["content"] = content
            else:
                context_msgs.append({"role": "user", "content": content})

    result = agents.run_agent(agent_id, message, user_id=g.user_id,
                              context=kb_context, conversation_messages=context_msgs)

    reply_text = result.get("text", "")

    # Process delegation blocks
    if agent and agent.get("can_delegate"):
        reply_text = delegation.process_delegations(reply_text, user_id=g.user_id)

    # ── Content Filter: scan AI output before delivery ──
    try:
        filter_result = content_filter.filter_output(reply_text)
        if filter_result.get("was_filtered"):
            reply_text = filter_result["filtered_text"]
    except Exception:
        pass

    # ── Output Shield: catch harmful AI-generated content (ALWAYS ON) ──
    try:
        output_safety = output_shield.scan(reply_text)
        if not output_safety.get("safe"):
            if output_safety.get("action") == "block":
                reply_text = "I'm not able to help with that request. Please try a different question."
            else:
                reply_text = output_shield.redact(reply_text)
    except Exception:
        pass

    # ── Crisis Output Scan: block harmful AI responses (ALWAYS ON) ──
    try:
        output_check = crisis_system.scan_ai_output(reply_text)
        if not output_check.get("safe"):
            # AI generated something harmful — replace entirely
            reply_text = (
                "I want to make sure I'm being helpful and safe. "
                "If you're going through a difficult time, please reach out to "
                "the 988 Suicide & Crisis Lifeline — call or text 988, available 24/7."
            )
    except Exception:
        pass

    # ── Crisis Tier 3: append resources if distress detected ──
    if crisis_append:
        reply_text = reply_text + crisis_append

    sources = result.get("sources", [])
    conversations.add_message(conv_id, "assistant", reply_text,
                              agent_id=agent_id, provider=result.get("provider"),
                              model=result.get("model"),
                              tokens_used=result.get("usage",{}).get("total_tokens",0),
                              sources=sources)

    usage = result.get("usage", {})
    users.log_usage(g.user_id, agent_id, result.get("provider",""), result.get("model",""),
                    usage.get("input_tokens",0), usage.get("output_tokens",0), usage.get("cost",0))

    # ── Transparency: build "show your work" report ──
    transparency_report = None
    try:
        transparency_report = transparency.build_transparency(result, agent=agent,
            routing_decision=route_info)
    except Exception:
        pass

    # ── Cost Ticker: track per-conversation cost (if activated) ──
    cost_data = None
    if feature_gate.is_enabled("cost_ticker"):
        try:
            model_used = result.get("model", "")
            cost_data = cost_ticker.record_message_cost(
                conv_id, model_used,
                usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        except Exception:
            pass

    # ── Confidence Scoring: rate this response (if activated) ──
    confidence = None
    if feature_gate.is_enabled("confidence_scoring"):
      try:
        confidence = confidence_scorer.score_response(
            reply_text,
            had_kb_context=_ctx_sources.get("had_kb", False),
            had_dna_context=_ctx_sources.get("had_dna", False),
            had_shared_context=_ctx_sources.get("had_shared", False),
            model_used=result.get("model", ""))
      except Exception:
        pass

    chat_response = {
        "response": reply_text,
        "message": {"content": reply_text, "sources": json.dumps(sources)},
        "conversation_id": conv_id,
        "route_info": route_info,
        "transparency": transparency_report,
        "confidence": confidence,
        "cost": cost_data,
        "compliance": compliance_alert,
        "image_urls": image_urls,
    }
    return jsonify(watermark.watermark_response(chat_response, user_id=g.user_id))


@app.route("/api/chat/stream", methods=["GET"])
def chat_stream():
    """SSE streaming chat endpoint."""
    conv_id = request.args.get("conversation_id")
    agent_id = request.args.get("agent_id")
    message = request.args.get("message", "")

    # Budget enforcement
    budget_check = spend_mgr.check_budget_enforcement(g.user_id)
    if not budget_check["allowed"]:
        return jsonify({"error": "Budget exceeded. Contact your admin."}), 402

    if not conv_id:
        conv = conversations.create_conversation(g.user_id, agent_id=agent_id)
        conv_id = conv["id"]

    # Validate conversation exists
    existing = conversations.get_conversation(conv_id)
    if not existing:
        return jsonify({"error": "Conversation not found"}), 404

    try:
        conversations.add_message(conv_id, "user", message)
    except Exception as e:
        return jsonify({"error": f"Failed to save message: {str(e)}"}), 400
    context_msgs = conversations.get_context_messages(conv_id)

    kb_context = ""
    agent = agents.get_agent(agent_id) if agent_id else None
    if agent and agent.get("use_knowledge_base"):
        folders = agent.get("knowledge_folders", [])
        kb_context = kb.get_context_for_agent(message, g.user_id, folder_ids=folders or None)

    def stream():
        full_text = ""
        for event in agents.run_agent_stream(agent_id, message, user_id=g.user_id,
                                              context=kb_context, conversation_messages=context_msgs):
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "chunk":
                full_text += event.get("text", "")
            elif event.get("type") == "done":
                full_text = event.get("text", full_text)

        if full_text:
            conversations.add_message(conv_id, "assistant", full_text, agent_id=agent_id)

        yield f"data: {json.dumps({'type':'end','conversation_id':conv_id})}\n\n"

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ═══════════════════════════════════════════════════════════════
# ROUTES — Knowledge Base
# ═══════════════════════════════════════════════════════════════

@app.route("/api/kb/folders", methods=["GET"])
def list_kb_folders():
    return jsonify({"folders": kb.list_folders(g.user_id)})


@app.route("/api/kb/folders", methods=["POST"])
def create_kb_folder():
    data = request.json
    f = kb.create_folder(g.user_id, data["name"], icon=data.get("icon","📁"),
                         shared=data.get("shared",False))
    return jsonify({"folder": f}), 201


@app.route("/api/kb/folders/<folder_id>", methods=["DELETE"])
def delete_kb_folder(folder_id):
    try:
        with get_db() as db:
            db.execute("DELETE FROM kb_folders WHERE id=?", (folder_id,))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/kb/documents", methods=["GET"])
def list_kb_docs():
    folder_id = request.args.get("folder_id")
    return jsonify({"documents": kb.list_documents(g.user_id, folder_id=folder_id)})


@app.route("/api/kb/upload", methods=["POST"])
def upload_kb_doc():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    tags = request.form.get("tags", "").split(",") if request.form.get("tags") else []
    folder_id = request.form.get("folder_id")
    shared = request.form.get("shared", "false").lower() == "true"
    doc = kb.add_document(g.user_id, f.filename, f.read(), folder_id=folder_id,
                          tags=tags, shared=shared)
    return jsonify({"document": doc}), 201


@app.route("/api/kb/documents/<doc_id>", methods=["DELETE"])
def delete_kb_doc(doc_id):
    kb.delete_document(doc_id)
    return jsonify({"success": True})


@app.route("/api/kb/search", methods=["GET"])
def search_kb():
    q = request.args.get("q", "")
    return jsonify({"results": kb.search(q, user_id=g.user_id)})


@app.route("/api/kb/stats", methods=["GET"])
def kb_stats():
    return jsonify({"stats": kb.get_stats(g.user_id)})


# ═══════════════════════════════════════════════════════════════
# ROUTES — Workflows
# ═══════════════════════════════════════════════════════════════

@app.route("/api/workflows", methods=["GET"])
def list_workflows():
    return jsonify({"workflows": workflows.list_workflows(user_id=g.user_id)})


@app.route("/api/workflows", methods=["POST"])
def create_workflow():
    if not users.has_permission(g.user_id, "create_workflows"):
        return jsonify({"error": "Permission denied"}), 403
    wf = workflows.create_workflow(request.json, owner_id=g.user_id)
    return jsonify({"workflow": wf}), 201


@app.route("/api/workflows/<wf_id>", methods=["GET"])
def get_workflow(wf_id):
    wf = workflows.get_workflow(wf_id)
    if not wf:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"workflow": wf})


@app.route("/api/workflows/<wf_id>", methods=["PUT"])
def update_workflow(wf_id):
    return jsonify({"workflow": workflows.update_workflow(wf_id, request.json)})


@app.route("/api/workflows/<wf_id>", methods=["DELETE"])
def delete_workflow(wf_id):
    workflows.delete_workflow(wf_id)
    return jsonify({"success": True})


@app.route("/api/workflows/<wf_id>/run", methods=["POST"])
def run_workflow(wf_id):
    if not users.has_permission(g.user_id, "run_workflows"):
        return jsonify({"error": "Permission denied"}), 403
    data = request.json or {}
    result = workflows.run_workflow(wf_id, g.user_id, data.get("input", ""))
    return jsonify({"run": result})


@app.route("/api/workflows/runs/<run_id>/resume", methods=["POST"])
def resume_workflow(run_id):
    data = request.json
    result = workflows.resume_workflow(run_id, approved=data.get("approved", False),
                                       feedback=data.get("feedback", ""))
    return jsonify({"run": result})


@app.route("/api/approvals", methods=["GET"])
def list_approvals():
    return jsonify({"approvals": workflows.get_pending_approvals(g.user_id)})


# ═══════════════════════════════════════════════════════════════
# ROUTES — Workspace Settings
# ═══════════════════════════════════════════════════════════════

@app.route("/api/workspace/settings", methods=["GET"])
def get_workspace_settings():
    with get_db() as db:
        rows = db.execute("SELECT key, value FROM workspace_settings").fetchall()
        return jsonify({"settings": {r["key"]: r["value"] for r in rows}})


@app.route("/api/workspace/settings", methods=["PUT"])
def update_workspace_settings():
    if not users.has_permission(g.user_id, "manage_workspace"):
        return jsonify({"error": "Permission denied"}), 403
    data = request.json
    with get_db() as db:
        for k, v in data.items():
            db.execute("INSERT OR REPLACE INTO workspace_settings (key, value) VALUES (?,?)", (k, str(v)))
    return jsonify({"success": True})


@app.route("/api/workspace/usage", methods=["GET"])
def workspace_usage():
    return jsonify({"usage": users.get_workspace_usage()})


# ═══════════════════════════════════════════════════════════════
# ROUTES — Webhook trigger (external)
# ═══════════════════════════════════════════════════════════════

@app.route("/webhook/<token>", methods=["POST"])
def webhook_trigger(token):
    with get_db() as db:
        wf = db.execute("SELECT id, owner_id FROM workflows WHERE webhook_token=?", (token,)).fetchone()
        if not wf:
            return jsonify({"error": "Invalid webhook"}), 404
    data = request.json or {}
    result = workflows.run_workflow(wf["id"], wf["owner_id"], data.get("input", json.dumps(data)))
    return jsonify({"run": result})


# ═══════════════════════════════════════════════════════════════
# HELPERS — Role checks
# ═══════════════════════════════════════════════════════════════

def require_admin():
    """Return error response if user is not owner/admin, else None."""
    role = getattr(g, "user", {}).get("role", "member")
    if role not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    return None


def require_owner():
    """Return error response if user is not owner, else None."""
    role = getattr(g, "user", {}).get("role", "member")
    if role != "owner":
        return jsonify({"error": "Owner access required"}), 403
    return None


# ═══════════════════════════════════════════════════════════════
# ROUTES — Departments
# ═══════════════════════════════════════════════════════════════

@app.route("/api/departments", methods=["GET"])
def list_departments():
    user_role = getattr(g, "user", {}).get("role", "member")
    if user_role in ("owner", "admin"):
        depts = departments.list_departments()
    else:
        depts = departments.get_user_departments(g.user_id)
    return jsonify({"departments": depts})


@app.route("/api/departments", methods=["POST"])
def create_department():
    check = require_admin()
    if check:
        return check
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "Department name required"}), 400
    dept = departments.create_department(
        name=data["name"],
        description=data.get("description", ""),
        icon=data.get("icon", "🏢"),
        color=data.get("color", "#3b82f6"),
        created_by=g.user_id
    )
    audit.log("department_created", user_id=g.user_id,
              resource_type="department", resource_id=dept["id"], detail=data["name"])
    return jsonify({"department": dept}), 201


@app.route("/api/departments/<dept_id>", methods=["GET"])
def get_department(dept_id):
    dept = departments.get_department(dept_id)
    if not dept:
        return jsonify({"error": "Department not found"}), 404
    return jsonify({"department": dept})


@app.route("/api/departments/<dept_id>", methods=["PUT"])
def update_department(dept_id):
    check = require_admin()
    if check:
        return check
    data = request.json or {}
    dept = departments.update_department(dept_id, **data)
    if not dept:
        return jsonify({"error": "Department not found"}), 404
    audit.log("department_updated", user_id=g.user_id,
              resource_type="department", resource_id=dept_id)
    return jsonify({"department": dept})


@app.route("/api/departments/<dept_id>", methods=["DELETE"])
def delete_department(dept_id):
    check = require_admin()
    if check:
        return check
    departments.delete_department(dept_id)
    audit.log("department_deleted", user_id=g.user_id,
              resource_type="department", resource_id=dept_id, severity="warning")
    return jsonify({"success": True})


@app.route("/api/departments/<dept_id>/members", methods=["POST"])
def add_dept_member(dept_id):
    check = require_admin()
    if check:
        return check
    data = request.json or {}
    uid = data.get("user_id")
    if not uid:
        return jsonify({"error": "user_id required"}), 400
    departments.add_member(dept_id, uid, data.get("role", "member"))
    audit.log("department_member_added", user_id=g.user_id,
              resource_type="department", resource_id=dept_id, detail=uid)
    return jsonify({"success": True})


@app.route("/api/departments/<dept_id>/members/<uid>", methods=["DELETE"])
def remove_dept_member(dept_id, uid):
    check = require_admin()
    if check:
        return check
    departments.remove_member(dept_id, uid)
    audit.log("department_member_removed", user_id=g.user_id,
              resource_type="department", resource_id=dept_id, detail=uid)
    return jsonify({"success": True})


@app.route("/api/departments/<dept_id>/agents", methods=["POST"])
def assign_dept_agent(dept_id):
    check = require_admin()
    if check:
        return check
    data = request.json or {}
    departments.assign_agent(dept_id, data.get("agent_id"))
    return jsonify({"success": True})


@app.route("/api/departments/<dept_id>/agents/<agent_id>", methods=["DELETE"])
def unassign_dept_agent(dept_id, agent_id):
    check = require_admin()
    if check:
        return check
    departments.unassign_agent(dept_id, agent_id)
    return jsonify({"success": True})


@app.route("/api/departments/<dept_id>/spend", methods=["GET"])
def dept_spend(dept_id):
    period = request.args.get("period", "month")
    spend = departments.get_department_spend(dept_id, period)
    return jsonify({"spend": spend, "disclaimer": "Estimated costs. Check your AI provider dashboard for actual charges."})


# ═══════════════════════════════════════════════════════════════
# ROUTES — Admin Panel
# ═══════════════════════════════════════════════════════════════

@app.route("/api/admin/dashboard", methods=["GET"])
def admin_dashboard():
    check = require_admin()
    if check:
        return check
    with get_db() as db:
        user_count = db.execute("SELECT COUNT(*) as c FROM users WHERE is_active=1").fetchone()["c"]
        agent_count = db.execute("SELECT COUNT(*) as c FROM agents").fetchone()["c"]
        dept_count = db.execute("SELECT COUNT(*) as c FROM departments WHERE is_active=1").fetchone()["c"]
        conv_count = db.execute("SELECT COUNT(*) as c FROM conversations").fetchone()["c"]
        msg_count = db.execute("SELECT COUNT(*) as c FROM messages").fetchone()["c"]
        # Spend this month
        spend_row = db.execute("""
            SELECT COALESCE(SUM(cost_estimate), 0) as total_cost,
                   COALESCE(SUM(tokens_in + tokens_out), 0) as total_tokens
            FROM usage_log WHERE created_at >= date('now', 'start of month')
        """).fetchone()
        # Active users today
        active_today = db.execute("""
            SELECT COUNT(DISTINCT user_id) as c FROM audit_log
            WHERE timestamp >= date('now') AND user_id IS NOT NULL
        """).fetchone()["c"]
    security_summary = audit.get_security_summary()
    return jsonify({
        "users": user_count,
        "agents": agent_count,
        "departments": dept_count,
        "conversations": conv_count,
        "messages": msg_count,
        "spend_this_month": spend_row["total_cost"],
        "spend_disclaimer": "Estimated based on token counts. Check your AI provider for actual charges.",
        "tokens_this_month": spend_row["total_tokens"],
        "active_users_today": active_today,
        "security": security_summary,
    })


@app.route("/api/admin/audit", methods=["GET"])
def admin_audit_log():
    check = require_admin()
    if check:
        return check
    result = audit.get_audit_log(
        limit=int(request.args.get("limit", 100)),
        offset=int(request.args.get("offset", 0)),
        user_id=request.args.get("user_id"),
        action=request.args.get("action"),
        severity=request.args.get("severity"),
        since=request.args.get("since"),
        resource_type=request.args.get("resource_type"),
    )
    return jsonify(result)


@app.route("/api/admin/audit/export", methods=["GET"])
def admin_audit_export():
    check = require_admin()
    if check:
        return check
    csv = audit.export_csv(
        since=request.args.get("since"),
        until=request.args.get("until"),
    )
    return Response(csv, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=audit_log.csv"})


@app.route("/api/admin/auth-log", methods=["GET"])
def admin_auth_log():
    check = require_admin()
    if check:
        return check
    entries = audit.get_auth_log(
        limit=int(request.args.get("limit", 100)),
        ip=request.args.get("ip"),
        status=request.args.get("status"),
    )
    return jsonify({"entries": entries})


@app.route("/api/admin/spend", methods=["GET"])
def admin_spend():
    check = require_admin()
    if check:
        return check
    # Check if spend dashboard is enabled
    with get_db() as db:
        from core.billing import get_user_pref, _init_billing_db
        _init_billing_db(db)
        enabled = get_user_pref(db, g.user_id, "spend_dashboard", "off")
        if enabled != "on":
            return jsonify({
                "enabled": False,
                "message": "Spend dashboard is off. Enable it in Settings → Account → Spend Estimates.",
                "disclaimer": "All cost figures are estimates. Actual charges are determined by your AI provider."
            })
    period = request.args.get("period", "month")
    with get_db() as db:
        if period == "month":
            where = "WHERE created_at >= date('now', 'start of month')"
        elif period == "week":
            where = "WHERE created_at >= date('now', '-7 days')"
        else:
            where = ""
        # Per user
        user_spend = db.execute(f"""
            SELECT u.id, u.display_name, u.email,
                   COALESCE(SUM(ul.cost_estimate), 0) as total_cost,
                   COALESCE(SUM(ul.tokens_in + ul.tokens_out), 0) as total_tokens,
                   COUNT(ul.id) as request_count
            FROM users u LEFT JOIN usage_log ul ON u.id=ul.user_id
            {'AND' if where else 'WHERE'} {'ul.' + where.replace('WHERE ','') if where else '1=1'}
            GROUP BY u.id ORDER BY total_cost DESC
        """).fetchall()
        # Per department
        dept_spend = db.execute(f"""
            SELECT d.id, d.name, d.icon, d.budget_monthly,
                   COALESCE(SUM(ul.cost_estimate), 0) as total_cost,
                   COALESCE(SUM(ul.tokens_in + ul.tokens_out), 0) as total_tokens,
                   COUNT(ul.id) as request_count
            FROM departments d LEFT JOIN usage_log ul ON d.id=ul.department_id
            {'AND' if where else 'WHERE'} {'ul.' + where.replace('WHERE ','') if where else '1=1'}
            GROUP BY d.id ORDER BY total_cost DESC
        """).fetchall()
        # Per agent
        agent_spend = db.execute(f"""
            SELECT a.id, a.name, a.icon,
                   COALESCE(SUM(ul.cost_estimate), 0) as total_cost,
                   COALESCE(SUM(ul.tokens_in + ul.tokens_out), 0) as total_tokens,
                   COUNT(ul.id) as request_count
            FROM agents a LEFT JOIN usage_log ul ON a.id=ul.agent_id
            {'AND' if where else 'WHERE'} {'ul.' + where.replace('WHERE ','') if where else '1=1'}
            GROUP BY a.id ORDER BY total_cost DESC
        """).fetchall()
    return jsonify({
        "by_user": [dict(r) for r in user_spend],
        "by_department": [dict(r) for r in dept_spend],
        "by_agent": [dict(r) for r in agent_spend],
        "disclaimer": "All costs shown are estimates based on token counts and published provider pricing. Actual charges are determined by your AI provider and may differ. Check your provider dashboard for exact billing.",
    })


@app.route("/api/admin/api-keys", methods=["GET"])
def admin_list_api_keys():
    check = require_admin()
    if check:
        return check
    with get_db() as db:
        rows = db.execute("""
            SELECT id, provider, created_at,
                   SUBSTR(encrypted_key, 1, 8) || '...' as key_preview
            FROM user_api_keys WHERE user_id=(SELECT id FROM users WHERE role='owner' LIMIT 1)
            ORDER BY provider
        """).fetchall()
    return jsonify({"keys": [dict(r) for r in rows]})


@app.route("/api/admin/api-keys", methods=["POST"])
def admin_set_api_key():
    check = require_owner()
    if check:
        return check
    data = request.json or {}
    provider = data.get("provider")
    key = data.get("key")
    if not provider or not key:
        return jsonify({"error": "provider and key required"}), 400
    # Store as env var and in DB
    os.environ[f"{provider.upper()}_API_KEY"] = key
    with get_db() as db:
        existing = db.execute("""
            SELECT id FROM user_api_keys WHERE user_id=? AND provider=?
        """, (g.user_id, provider)).fetchone()
        if existing:
            db.execute("UPDATE user_api_keys SET encrypted_key=? WHERE id=?", (key, existing["id"]))
        else:
            key_id = f"key_{uuid.uuid4().hex[:8]}"
            db.execute("""
                INSERT INTO user_api_keys (id, user_id, provider, encrypted_key)
                VALUES (?,?,?,?)
            """, (key_id, g.user_id, provider, key))
    providers.reload()
    audit.log("api_key_updated", user_id=g.user_id,
              resource_type="api_key", detail=provider, severity="warning")
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════
# ROUTES — Branding / White-Label
# ═══════════════════════════════════════════════════════════════

# Branding routes moved to CUSTOM BRANDING section below

@app.route("/api/branding/upload-logo", methods=["POST"])
def upload_logo():
    check = require_admin()
    if check:
        return check
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    os.makedirs("data/branding", exist_ok=True)
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else "png"
    path = f"data/branding/logo.{ext}"
    f.save(path)
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO branding (key, value) VALUES ('logo_path', ?)", (path,))
    audit.log("logo_uploaded", user_id=g.user_id, resource_type="branding")
    return jsonify({"success": True, "path": path})


# ═══════════════════════════════════════════════════════════════
# AGENT TEMPLATES
# ═══════════════════════════════════════════════════════════════

@app.route("/api/agent-templates", methods=["GET"])
def api_list_agent_templates():
    uid = g.user_id
    category = request.args.get("category")
    return jsonify({"templates": templates.list_templates(category)})

@app.route("/api/agent-templates/<tmpl_id>", methods=["GET"])
def api_get_agent_template(tmpl_id):
    uid = g.user_id
    t = templates.get_template(tmpl_id)
    if not t:
        return jsonify({"error": "Template not found"}), 404
    return jsonify(t)

@app.route("/api/agent-templates", methods=["POST"])
def api_create_agent_template():
    uid = g.user_id
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    data = request.json
    result = templates.create_template(data)
    return jsonify({"template": result}), 201

@app.route("/api/agent-templates/<tmpl_id>/deploy", methods=["POST"])
def api_deploy_agent_template(tmpl_id):
    uid = g.user_id
    data = request.json or {}
    dept_id = data.get("department_id")
    result = templates.deploy_template(tmpl_id, uid, dept_id)
    if not result:
        return jsonify({"error": "Template not found"}), 404
    return jsonify(result), 201


# ═══════════════════════════════════════════════════════════════
# AGENT PERFORMANCE & ANALYTICS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/agents/performance", methods=["GET"])
def api_all_agent_performance():
    uid = g.user_id
    return jsonify({"agents": analytics.get_all_agent_performance()})

@app.route("/api/agents/<agent_id>/performance", methods=["GET"])
def api_agent_performance(agent_id):
    uid = g.user_id
    perf = analytics.get_agent_performance(agent_id)
    if not perf:
        return jsonify({"error": "Agent not found"}), 404
    return jsonify(perf)

@app.route("/api/agents/<agent_id>/feedback", methods=["GET"])
def api_agent_feedback(agent_id):
    uid = g.user_id
    limit = int(request.args.get("limit", 50))
    return jsonify({"feedback": analytics.get_feedback_for_agent(agent_id, limit)})


# ═══════════════════════════════════════════════════════════════
# MESSAGE FEEDBACK
# ═══════════════════════════════════════════════════════════════

@app.route("/api/feedback", methods=["POST"])
def api_add_feedback():
    uid = g.user_id
    data = request.json
    msg_id = data.get("message_id")
    rating = data.get("rating")
    comment = data.get("comment", "")
    if not msg_id or rating not in (1, -1):
        return jsonify({"error": "message_id and rating (1 or -1) required"}), 400
    result = analytics.add_feedback(msg_id, uid, rating, comment)
    return jsonify(result), 201


# ═══════════════════════════════════════════════════════════════
# AGENT RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/recommendations", methods=["GET"])
def api_list_recommendations():
    uid = g.user_id
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    status = request.args.get("status")
    return jsonify({"recommendations": recommendations.list_recommendations(status)})

@app.route("/api/recommendations/generate", methods=["POST"])
def api_generate_recommendations():
    uid = g.user_id
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    results = recommendations.analyze_and_recommend()
    return jsonify({"generated": len(results), "recommendations": results})

@app.route("/api/recommendations/<rec_id>/review", methods=["POST"])
def api_review_recommendation(rec_id):
    uid = g.user_id
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    data = request.json
    action = data.get("action")  # "approve" or "reject"
    if action not in ("approve", "reject"):
        return jsonify({"error": "action must be 'approve' or 'reject'"}), 400
    result = recommendations.review_recommendation(rec_id, action, uid)
    if not result:
        return jsonify({"error": "Recommendation not found"}), 404
    return jsonify(result)

@app.route("/api/recommendations/summary", methods=["GET"])
def api_recommendations_summary():
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    return jsonify({"summary": recommendations.get_recommendation_summary()})


# ═══════════════════════════════════════════════════════════════
# ADVANCED AI: ROUTING, CHAINS, DELEGATION, VISION
# ═══════════════════════════════════════════════════════════════

# ── Model Routing ──

@app.route("/api/routing/classify", methods=["POST"])
def api_routing_classify():
    data = request.json or {}
    message = data.get("message", "")
    return jsonify(router.classify_task(message))

@app.route("/api/routing/route", methods=["POST"])
def api_routing_route():
    data = request.json or {}
    message = data.get("message", "")
    rule_id = data.get("rule_id")
    return jsonify(router.get_route(message, rule_id))

@app.route("/api/routing/rules", methods=["GET"])
def api_routing_list():
    return jsonify({"rules": router.list_rules()})

@app.route("/api/routing/rules", methods=["POST"])
def api_routing_create():
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    return jsonify(router.create_rule(data)), 201

@app.route("/api/routing/rules/<rule_id>", methods=["GET"])
def api_routing_get(rule_id):
    rule = router.get_rule(rule_id)
    if not rule:
        return jsonify({"error": "Rule not found"}), 404
    return jsonify(rule)

@app.route("/api/routing/rules/<rule_id>", methods=["PUT"])
def api_routing_update(rule_id):
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    data = request.json or {}
    result = router.update_rule(rule_id, data)
    if not result:
        return jsonify({"error": "Rule not found"}), 404
    return jsonify(result)

# ── Prompt Chains ──

@app.route("/api/chains", methods=["GET"])
def api_chains_list():
    uid = g.user_id
    return jsonify({"chains": chains.list_chains(uid)})

@app.route("/api/chains", methods=["POST"])
def api_chains_create():
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    result = chains.create_chain(data, g.user_id)
    return jsonify(result), 201

@app.route("/api/chains/<chain_id>", methods=["GET"])
def api_chains_get(chain_id):
    chain = chains.get_chain(chain_id)
    if not chain:
        return jsonify({"error": "Chain not found"}), 404
    return jsonify(chain)

@app.route("/api/chains/<chain_id>/run", methods=["POST"])
def api_chains_run(chain_id):
    data = request.json or {}
    result = chains.run_chain(
        chain_id,
        input_text=data.get("input", ""),
        variables=data.get("variables"),
        user_id=g.user_id,
    )
    if result.get("error"):
        return jsonify(result), 400
    return jsonify(result)

@app.route("/api/chains/<chain_id>", methods=["DELETE"])
def api_chains_delete(chain_id):
    chains.delete_chain(chain_id)
    return jsonify({"deleted": True})

# ── Vision ──

@app.route("/api/vision/validate", methods=["POST"])
def api_vision_validate():
    data = request.json or {}
    image = data.get("image", "")
    result = vision.validate_image(image)
    if result:
        return jsonify({"valid": True, "media_type": result[0], "size": len(result[1])})
    return jsonify({"valid": False})

@app.route("/api/vision/models", methods=["GET"])
def api_vision_models():
    """List models that support vision/image input."""
    all_models = []
    for p in providers.list_all():
        for m in p.get("available_models", []):
            all_models.append({
                "provider": p["name"],
                "model": m,
                "supports_vision": vision.is_vision_model(m),
            })
    return jsonify({"models": all_models})


# ═══════════════════════════════════════════════════════════════
# SPEND MANAGEMENT & ANALYTICS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/spend/dashboard", methods=["GET"])
def api_spend_dashboard():
    uid = g.user_id
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    days = int(request.args.get("days", 30))
    return jsonify({
        "forecast": spend_mgr.get_forecast(),
        "daily": spend_mgr.get_daily_spend(days),
        "by_agent": spend_mgr.get_agent_costs(days),
        "by_model": spend_mgr.get_model_breakdown(days),
        "leaderboard": spend_mgr.get_user_leaderboard(days),
    })

@app.route("/api/spend/forecast", methods=["GET"])
def api_spend_forecast():
    uid = g.user_id
    return jsonify(spend_mgr.get_forecast())

@app.route("/api/spend/daily", methods=["GET"])
def api_spend_daily():
    uid = g.user_id
    days = int(request.args.get("days", 30))
    user_id = request.args.get("user_id")
    dept_id = request.args.get("department_id")
    return jsonify({"daily": spend_mgr.get_daily_spend(days, user_id, dept_id)})

@app.route("/api/spend/by-agent", methods=["GET"])
def api_spend_by_agent():
    uid = g.user_id
    days = int(request.args.get("days", 30))
    return jsonify({"by_agent": spend_mgr.get_agent_costs(days)})

@app.route("/api/spend/by-model", methods=["GET"])
def api_spend_by_model():
    uid = g.user_id
    days = int(request.args.get("days", 30))
    return jsonify({"by_model": spend_mgr.get_model_breakdown(days)})

@app.route("/api/spend/leaderboard", methods=["GET"])
def api_spend_leaderboard():
    uid = g.user_id
    days = int(request.args.get("days", 30))
    return jsonify({"leaderboard": spend_mgr.get_user_leaderboard(days)})

@app.route("/api/spend/pricing", methods=["GET"])
def api_spend_pricing():
    from core.spend import MODEL_PRICING
    return jsonify({"pricing": MODEL_PRICING})

@app.route("/api/spend/budgets", methods=["GET"])
def api_spend_budgets():
    uid = g.user_id
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    return jsonify({"budgets": spend_mgr.get_budgets()})

@app.route("/api/spend/budgets", methods=["POST"])
def api_set_budget():
    uid = g.user_id
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    data = request.json or {}
    scope = data.get("scope", "workspace")
    if scope not in ("workspace", "user", "department"):
        return jsonify({"error": "scope must be workspace, user, or department"}), 400
    result = spend_mgr.set_budget(
        scope=scope, scope_id=data.get("scope_id"),
        monthly_limit=float(data.get("monthly_limit", 0)),
        warning_pct=float(data.get("warning_pct", 80)),
        hard_stop=bool(data.get("hard_stop", True))
    )
    return jsonify(result)

@app.route("/api/spend/export", methods=["GET"])
def api_spend_export():
    uid = g.user_id
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    days = int(request.args.get("days", 30))
    csv_data = spend_mgr.export_spend_csv(days)
    from flask import Response
    return Response(csv_data, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=myteam360-spend.csv"})

@app.route("/api/spend/my-usage", methods=["GET"])
def api_my_usage():
    uid = g.user_id
    days = int(request.args.get("days", 30))
    daily = spend_mgr.get_daily_spend(days, user_id=uid)
    budget = users.check_budget(uid)
    monthly = users.get_monthly_usage(uid)
    return jsonify({"daily": daily, "budget": budget, "monthly": monthly})

@app.route("/api/spend/budget-check", methods=["GET"])
def api_budget_check():
    uid = g.user_id
    dept_id = request.args.get("department_id")
    return jsonify(spend_mgr.check_budget_enforcement(uid, dept_id))

@app.route("/api/spend/recalculate", methods=["POST"])
def api_spend_recalculate():
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    count = spend_mgr.recalculate_costs()
    return jsonify({"recalculated": count})




# ===============================================================
# PHASE 7: WEBHOOKS & EVENTS
# ===============================================================

@app.route("/api/webhooks", methods=["GET"])
def api_list_webhooks():
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    return jsonify({"webhooks": webhooks.list_all()})

@app.route("/api/webhooks", methods=["POST"])
def api_create_webhook():
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    data = request.json or {}
    if not data.get("name") or not data.get("url"):
        return jsonify({"error": "name and url required"}), 400
    wh = webhooks.create(name=data["name"], url=data["url"],
        events=data.get("events"), secret=data.get("secret"),
        headers=data.get("headers"), created_by=g.user_id)
    return jsonify(wh), 201

@app.route("/api/webhooks/<wid>", methods=["GET"])
def api_get_webhook(wid):
    wh = webhooks.get(wid)
    if not wh: return jsonify({"error": "Not found"}), 404
    return jsonify(wh)

@app.route("/api/webhooks/<wid>", methods=["PUT"])
def api_update_webhook(wid):
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    wh = webhooks.update(wid, request.json or {})
    if not wh: return jsonify({"error": "Not found"}), 404
    return jsonify(wh)

@app.route("/api/webhooks/<wid>", methods=["DELETE"])
def api_delete_webhook(wid):
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    webhooks.delete(wid)
    return jsonify({"deleted": True})

@app.route("/api/webhooks/<wid>/test", methods=["POST"])
def api_test_webhook(wid):
    return jsonify(webhooks.test(wid))

@app.route("/api/events", methods=["GET"])
def api_list_events():
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    event_type = request.args.get("type")
    limit = int(request.args.get("limit", 100))
    return jsonify({"events": event_bus.get_events(event_type, limit)})

@app.route("/api/events/counts", methods=["GET"])
def api_event_counts():
    hours = int(request.args.get("hours", 24))
    return jsonify({"counts": event_bus.get_event_counts(hours)})

@app.route("/api/events/types", methods=["GET"])
def api_event_types():
    from core.integrations import EVENT_TYPES
    return jsonify({"types": EVENT_TYPES})


# ===============================================================
# PHASE 8: ADVANCED CHAT
# ===============================================================

@app.route("/api/conversations/<cid>/pins", methods=["GET"])
def api_get_pins(cid):
    return jsonify({"pins": chat_adv.get_pins(cid)})

@app.route("/api/conversations/<cid>/pins", methods=["POST"])
def api_pin_message(cid):
    data = request.json or {}
    if not data.get("message_id"): return jsonify({"error": "message_id required"}), 400
    return jsonify(chat_adv.pin_message(cid, data["message_id"], g.user_id, data.get("note")))

@app.route("/api/conversations/<cid>/pins/<mid>", methods=["DELETE"])
def api_unpin_message(cid, mid):
    return jsonify(chat_adv.unpin_message(cid, mid))

@app.route("/api/conversations/<cid>/attachments", methods=["GET"])
def api_get_attachments(cid):
    return jsonify({"attachments": chat_adv.get_attachments(cid)})

@app.route("/api/conversations/<cid>/attachments", methods=["POST"])
def api_upload_attachment(cid):
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    data_bytes = f.read()
    if len(data_bytes) > 10 * 1024 * 1024:
        return jsonify({"error": "File too large (max 10MB)"}), 413
    result = chat_adv.save_attachment(cid, request.form.get("message_id"), f.filename, data_bytes, f.content_type, g.user_id)
    return jsonify(result), 201

@app.route("/api/attachments/<att_id>", methods=["GET"])
def api_download_attachment(att_id):
    att = chat_adv.get_attachment_file(att_id)
    if not att or "data" not in att: return jsonify({"error": "Not found"}), 404
    from flask import Response
    return Response(att["data"], mimetype=att.get("mime_type", "application/octet-stream"),
                    headers={"Content-Disposition": "attachment;filename=" + att["filename"]})

@app.route("/api/conversations/<cid>/share", methods=["POST"])
def api_share_conversation(cid):
    data = request.json or {}
    return jsonify(chat_adv.create_share(cid, g.user_id, data.get("expires_hours", 72))), 201

@app.route("/api/shared/<token>", methods=["GET"])
def api_get_shared_conversation(token):
    result = chat_adv.get_shared(token)
    if not result: return jsonify({"error": "Share not found or expired"}), 404
    return jsonify(result)

# Conversation export moved to CONVERSATION EXPORT section below

@app.route("/api/messages/search", methods=["GET"])
def api_search_messages():
    q = request.args.get("q", "").strip()
    if len(q) < 2: return jsonify({"error": "Query must be at least 2 characters"}), 400
    return jsonify({"results": chat_adv.search_messages(q, user_id=g.user_id), "query": q})


# ═══════════════════════════════════════════════════════════════
# ONBOARDING
# ═══════════════════════════════════════════════════════════════

@app.route("/api/onboarding/status", methods=["GET"])
def api_onboarding_status():
    uid = g.user_id
    with get_db() as db:
        row = db.execute("SELECT value FROM workspace_settings WHERE key='setup_complete'").fetchone()
        return jsonify({"setup_complete": row["value"] == "1" if row else False})

@app.route("/api/onboarding/complete", methods=["POST"])
def api_onboarding_complete():
    uid = g.user_id
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403
    data = request.json or {}

    # Step 1: Apply branding settings
    with get_db() as db:
        if data.get("company_name"):
            db.execute("INSERT OR REPLACE INTO branding (key, value) VALUES ('company_name', ?)", (data["company_name"],))
        if data.get("primary_color"):
            db.execute("INSERT OR REPLACE INTO branding (key, value) VALUES ('primary_color', ?)", (data["primary_color"],))
        if data.get("welcome_message"):
            db.execute("INSERT OR REPLACE INTO branding (key, value) VALUES ('welcome_message', ?)", (data["welcome_message"],))
        db.execute("INSERT OR REPLACE INTO workspace_settings (key, value) VALUES ('setup_complete', '1')")
        db.commit()

    # Step 2: Deploy selected templates (separate DB transactions)
    for tmpl_id in data.get("template_ids", []):
        try:
            templates.deploy_template(tmpl_id, uid, data.get("department_id"))
        except Exception:
            pass

    # Step 3: Create initial department (separate DB transaction)
    if data.get("department_name"):
        try:
            departments.create_department(
                name=data["department_name"],
                icon=data.get("department_icon", "🏢"),
                description=data.get("department_desc", ""),
                created_by=uid,
            )
        except Exception:
            pass

    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════
# AUDIT MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

@app.after_request
def log_api_action(response):
    """Log significant API mutations to audit trail."""
    if request.method in ("POST", "PUT", "DELETE") and request.path.startswith("/api/"):
        try:
            user_id = getattr(g, "user_id", None)
            user_email = getattr(g, "user", {}).get("email")
            ip = getattr(g, "client_ip", request.remote_addr)
            # Determine resource type from path
            parts = request.path.split("/")
            resource_type = parts[2] if len(parts) > 2 else "unknown"
            resource_id = parts[3] if len(parts) > 3 else None
            action = f"{request.method.lower()}_{resource_type}"
            severity = "info"
            if response.status_code >= 400:
                severity = "warning"
            if "delete" in request.path.lower() or request.method == "DELETE":
                severity = "warning"
            audit.log(
                action=action,
                user_id=user_id,
                user_email=user_email,
                ip_address=ip,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=f"{response.status_code}",
                severity=severity,
            )
        except Exception:
            pass  # Never block response for audit failure
    return response


# ═══════════════════════════════════════════════════════════════
# POLICIES — Acceptable Use Policy
# ═══════════════════════════════════════════════════════════════

@app.route("/api/policy/active", methods=["GET"])
def api_policy_active():
    """Get the active AUP (public — no auth required)."""
    policy = policy_mgr.get_active_policy(request.args.get("type", "aup"))
    if not policy:
        return jsonify({"exists": False})
    return jsonify(policy)

@app.route("/api/policy/check", methods=["GET"])
def api_policy_check():
    """Check if current user has accepted the AUP."""
    # Need auth for this but it's whitelisted from AUP enforcement
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"required": False, "accepted": True})
    # Manually validate token to get user_id
    try:
        token = auth_header[7:]
        import hashlib
        salt = os.getenv("TOKEN_SALT", "mt360-salt")
        token_hash = hashlib.sha256(f"{salt}:{token}".encode()).hexdigest()
        with get_db() as db:
            row = db.execute(
                "SELECT t.user_id FROM api_tokens t WHERE t.token_hash=? AND t.enabled=1",
                (token_hash,)).fetchone()
        if row:
            return jsonify(policy_mgr.check_user_acceptance(row["user_id"]))
    except Exception:
        pass
    return jsonify({"required": False, "accepted": True})

@app.route("/api/policy/accept", methods=["POST"])
def api_policy_accept():
    """Accept a policy (whitelisted from AUP enforcement)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Auth required"}), 401
    try:
        token = auth_header[7:]
        import hashlib
        salt = os.getenv("TOKEN_SALT", "mt360-salt")
        token_hash = hashlib.sha256(f"{salt}:{token}".encode()).hexdigest()
        with get_db() as db:
            row = db.execute(
                "SELECT t.user_id FROM api_tokens t WHERE t.token_hash=? AND t.enabled=1",
                (token_hash,)).fetchone()
        if not row:
            return jsonify({"error": "Invalid token"}), 401
        data = request.json or {}
        result = policy_mgr.accept_policy(
            row["user_id"], data.get("policy_id", ""),
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", ""))
        if "error" in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/policies", methods=["GET"])
def api_policies_list():
    return jsonify({"policies": policy_mgr.list_policies(request.args.get("type"))})

@app.route("/api/policies", methods=["POST"])
def api_policies_create():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    if not data.get("title") or not data.get("content"):
        return jsonify({"error": "title and content required"}), 400
    result = policy_mgr.create_policy(
        data.get("type", "aup"), data["title"], data["content"],
        created_by=g.user_id, requires_acceptance=data.get("requires_acceptance", True))
    return jsonify(result), 201

@app.route("/api/policies/<policy_id>", methods=["PUT"])
def api_policies_update(policy_id):
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    return jsonify(policy_mgr.update_policy(policy_id, **data))

@app.route("/api/policies/compliance", methods=["GET"])
def api_policies_compliance():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify({
        "acceptances": policy_mgr.get_acceptance_log(),
        "non_compliant": policy_mgr.get_non_compliant_users(),
    })


# ═══════════════════════════════════════════════════════════════
# SETUP WIZARD — First-Time Configuration
# ═══════════════════════════════════════════════════════════════

@app.route("/api/setup/state", methods=["GET"])
def api_setup_state():
    return jsonify(setup_wizard.get_state())

@app.route("/api/setup/step/<step_id>", methods=["POST"])
def api_setup_step(step_id):
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    return jsonify(setup_wizard.update_step(step_id, data))

@app.route("/api/setup/complete", methods=["POST"])
def api_setup_complete():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    result = setup_wizard.complete_wizard(admin_user_id=g.user_id)
    return jsonify(result)

@app.route("/api/setup/departments", methods=["GET"])
def api_setup_departments():
    return jsonify({"departments": setup_wizard.get_department_templates()})

@app.route("/api/setup/provider-guide/<provider>", methods=["GET"])
def api_setup_provider_guide(provider):
    guide = setup_wizard.get_provider_guide(provider)
    if not guide:
        return jsonify({"error": "Unknown provider"}), 404
    return jsonify(guide)

@app.route("/api/setup/provider-guides", methods=["GET"])
def api_setup_provider_guides():
    return jsonify(setup_wizard.get_all_provider_guides())

@app.route("/api/setup/reset", methods=["POST"])
def api_setup_reset():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify(setup_wizard.reset_wizard())


# ═══════════════════════════════════════════════════════════════
# DATA RETENTION & IP ALLOWLIST
# ═══════════════════════════════════════════════════════════════

@app.route("/api/retention", methods=["GET"])
def api_retention_list():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify({"policies": retention_mgr.list_policies()})

@app.route("/api/retention/<resource_type>", methods=["PUT"])
def api_retention_update(resource_type):
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    return jsonify(retention_mgr.update_policy(
        resource_type, data.get("retention_days", 365),
        auto_delete=data.get("auto_delete", False), configured_by=g.user_id))

@app.route("/api/ip-allowlist", methods=["GET"])
def api_ip_allowlist():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify({"entries": ip_allowlist.list_entries(), "enabled": ip_allowlist.is_enabled()})

@app.route("/api/ip-allowlist", methods=["POST"])
def api_ip_allowlist_add():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    if not data.get("ip_address"):
        return jsonify({"error": "ip_address required"}), 400
    return jsonify(ip_allowlist.add_entry(
        data["ip_address"], data.get("description", ""),
        cidr_range=data.get("cidr_range"), created_by=g.user_id))

@app.route("/api/ip-allowlist/<entry_id>", methods=["DELETE"])
def api_ip_allowlist_remove(entry_id):
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify(ip_allowlist.remove_entry(entry_id))


# ═══════════════════════════════════════════════════════════════
# SHARED CONTEXT (Company Brain)
# ═══════════════════════════════════════════════════════════════

@app.route("/api/context", methods=["GET"])
def list_shared_context():
    category = request.args.get("category")
    return jsonify({"items": shared_ctx.list_context(g.user_id, category=category)})

@app.route("/api/context", methods=["POST"])
def add_shared_context():
    data = request.json or {}
    item = shared_ctx.add_context(g.user_id, data.get("key",""), data.get("value",""),
                                   category=data.get("category","general"),
                                   source_agent_id=data.get("agent_id"),
                                   ttl_days=data.get("ttl_days",0))
    return jsonify(item), 201

@app.route("/api/context/query", methods=["POST"])
def query_shared_context():
    data = request.json or {}
    items = shared_ctx.query_context(g.user_id, data.get("query",""),
                                      category=data.get("category"),
                                      limit=data.get("limit",10))
    return jsonify({"results": items})

@app.route("/api/context/<ctx_id>", methods=["PUT"])
def update_shared_context(ctx_id):
    data = request.json or {}
    return jsonify(shared_ctx.update_context(ctx_id, value=data.get("value"), category=data.get("category")))

@app.route("/api/context/<ctx_id>", methods=["DELETE"])
def delete_shared_context(ctx_id):
    return jsonify({"deleted": shared_ctx.delete_context(ctx_id)})

@app.route("/api/context/categories", methods=["GET"])
def get_context_categories():
    return jsonify({"categories": shared_ctx.get_categories(g.user_id)})


# ═══════════════════════════════════════════════════════════════
# SMART COST ROUTING
# ═══════════════════════════════════════════════════════════════

@app.route("/api/routing/analyze", methods=["POST"])
def analyze_message_complexity():
    data = request.json or {}
    analysis = smart_router.analyze_complexity(data.get("message",""), data.get("conversation_length",0))
    return jsonify(analysis)

@app.route("/api/routing/select", methods=["POST"])
def select_smart_model():
    data = request.json or {}
    result = smart_router.select_model(data.get("message",""), provider=data.get("provider","anthropic"),
                                        conversation_length=data.get("conversation_length",0),
                                        budget_mode=data.get("budget_mode","balanced"))
    return jsonify(result)

@app.route("/api/routing/costs", methods=["GET"])
def get_model_costs():
    return jsonify({"models": smart_router.get_model_costs()})


# ═══════════════════════════════════════════════════════════════
# AGENT TRIGGERS (Automation)
# ═══════════════════════════════════════════════════════════════

@app.route("/api/triggers", methods=["GET"])
def list_triggers():
    agent_id = request.args.get("agent_id")
    return jsonify({"triggers": trigger_mgr.list_triggers(owner_id=g.user_id, agent_id=agent_id)})

@app.route("/api/triggers", methods=["POST"])
def create_trigger():
    data = request.json or {}
    try:
        trigger = trigger_mgr.create_trigger(g.user_id, data["agent_id"], data["name"],
                                              data["trigger_type"], data.get("config",{}),
                                              data.get("input_template",""),
                                              data.get("output_action","store"),
                                              data.get("output_config"))
        return jsonify({"trigger": trigger}), 201
    except (KeyError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/triggers/<tid>", methods=["GET"])
def get_trigger(tid):
    t = trigger_mgr.get_trigger(tid)
    return jsonify({"trigger": t}) if t else (jsonify({"error":"Not found"}), 404)

@app.route("/api/triggers/<tid>", methods=["PUT"])
def update_trigger(tid):
    return jsonify({"trigger": trigger_mgr.update_trigger(tid, request.json or {})})

@app.route("/api/triggers/<tid>", methods=["DELETE"])
def delete_trigger(tid):
    return jsonify({"deleted": trigger_mgr.delete_trigger(tid)})

@app.route("/api/triggers/<tid>/fire", methods=["POST"])
def fire_trigger(tid):
    data = request.json or {}
    try:
        result = trigger_mgr.fire_trigger(tid, input_data=data.get("input"))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/triggers/<tid>/toggle", methods=["POST"])
def toggle_trigger(tid):
    data = request.json or {}
    return jsonify({"trigger": trigger_mgr.toggle_trigger(tid, data.get("active", True))})

@app.route("/api/triggers/<tid>/log", methods=["GET"])
def get_trigger_log(tid):
    return jsonify({"log": trigger_mgr.get_trigger_log(tid)})

@app.route("/api/webhooks/trigger/<tid>", methods=["POST"])
def webhook_trigger_endpoint(tid):
    """Public webhook endpoint (no auth required)."""
    try:
        result = trigger_mgr.fire_webhook(tid, request.json or {})
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# PIPELINES (Agent-to-Agent Assembly Line)
# ═══════════════════════════════════════════════════════════════

@app.route("/api/pipelines", methods=["GET"])
def list_pipelines():
    return jsonify({"pipelines": crm_pipeline_mgr.list_pipelines(g.user_id)})

@app.route("/api/pipelines", methods=["POST"])
def create_pipeline():
    data = request.json or {}
    pipe = crm_pipeline_mgr.create_pipeline(g.user_id, data.get("name",""), data.get("description",""), data.get("steps",[]))
    return jsonify({"pipeline": pipe}), 201

@app.route("/api/pipelines/<pid>", methods=["GET"])
def get_pipeline(pid):
    p = crm_pipeline_mgr.get_pipeline(pid)
    return jsonify({"pipeline": p}) if p else (jsonify({"error":"Not found"}), 404)

@app.route("/api/pipelines/<pid>", methods=["PUT"])
def update_pipeline(pid):
    return jsonify({"pipeline": crm_pipeline_mgr.update_pipeline(pid, request.json or {})})

@app.route("/api/pipelines/<pid>", methods=["DELETE"])
def delete_pipeline(pid):
    return jsonify({"deleted": crm_pipeline_mgr.delete_pipeline(pid)})

@app.route("/api/pipelines/<pid>/run", methods=["POST"])
def run_pipeline(pid):
    data = request.json or {}
    try:
        result = pipeline_mgr.run_pipeline(pid, data.get("input",""), owner_id=g.user_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/pipelines/<pid>/runs", methods=["GET"])
def list_pipeline_runs(pid):
    return jsonify({"runs": pipeline_mgr.list_runs(pid)})

@app.route("/api/pipelines/runs/<run_id>", methods=["GET"])
def get_pipeline_run(run_id):
    r = pipeline_mgr.get_run(run_id)
    return jsonify({"run": r}) if r else (jsonify({"error":"Not found"}), 404)


# ═══════════════════════════════════════════════════════════════
# CLIENT PORTALS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/portals", methods=["GET"])
def list_portals():
    return jsonify({"portals": portal_mgr.list_portals(g.user_id)})

@app.route("/api/portals", methods=["POST"])
def create_portal():
    data = request.json or {}
    try:
        portal = portal_mgr.create_portal(g.user_id, data["name"], data["agent_id"],
                                            slug=data.get("slug"), branding=data.get("branding"),
                                            welcome_message=data.get("welcome_message",""),
                                            require_email=data.get("require_email",False))
        return jsonify({"portal": portal}), 201
    except (KeyError, Exception) as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/portals/<pid>", methods=["GET"])
def get_portal(pid):
    p = portal_mgr.get_portal(pid)
    return jsonify({"portal": p}) if p else (jsonify({"error":"Not found"}), 404)

@app.route("/api/portals/<pid>", methods=["PUT"])
def update_portal(pid):
    return jsonify({"portal": portal_mgr.update_portal(pid, request.json or {})})

@app.route("/api/portals/<pid>", methods=["DELETE"])
def delete_portal(pid):
    return jsonify({"deleted": portal_mgr.delete_portal(pid)})

@app.route("/api/portals/<pid>/analytics", methods=["GET"])
def get_portal_analytics(pid):
    return jsonify(portal_mgr.get_portal_analytics(pid))

@app.route("/api/portals/public/<slug>", methods=["GET"])
def get_public_portal(slug):
    """Public portal access (no auth) — returns portal config for client-facing UI."""
    portal = portal_mgr.get_portal_by_slug(slug)
    if not portal or not portal.get("is_active"):
        return jsonify({"error": "Portal not found"}), 404
    return jsonify({
        "name": portal["name"],
        "branding": portal["branding"],
        "welcome_message": portal["welcome_message"],
        "require_email": portal["require_email"],
    })

@app.route("/api/portals/public/<slug>/session", methods=["POST"])
def create_portal_session(slug):
    """Public session creation for client portals."""
    portal = portal_mgr.get_portal_by_slug(slug)
    if not portal or not portal.get("is_active"):
        return jsonify({"error": "Portal not found"}), 404
    data = request.json or {}
    session = portal_mgr.create_session(portal["id"], data.get("name",""), data.get("email",""),
                                         request.remote_addr or "")
    return jsonify(session), 201


# ═══════════════════════════════════════════════════════════════
# PROOF OF WORK / WORK REPORTS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/reports", methods=["GET"])
def list_reports():
    return jsonify({"reports": report_mgr.list_reports(g.user_id)})

@app.route("/api/reports", methods=["POST"])
def generate_report():
    data = request.json or {}
    try:
        report = report_mgr.generate_report(g.user_id, data["title"],
                                              data["period_start"], data["period_end"],
                                              agent_ids=data.get("agent_ids"))
        return jsonify({"report": report}), 201
    except (KeyError, Exception) as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/reports/<rid>", methods=["GET"])
def get_report(rid):
    r = report_mgr.get_report(rid)
    return jsonify({"report": r}) if r else (jsonify({"error":"Not found"}), 404)

@app.route("/api/reports/<rid>", methods=["DELETE"])
def delete_report(rid):
    return jsonify({"deleted": report_mgr.delete_report(rid)})


# ═══════════════════════════════════════════════════════════════
# OUTPUT SCORING + AUTO-IMPROVE
# ═══════════════════════════════════════════════════════════════

@app.route("/api/feedback", methods=["POST"])
def record_feedback():
    data = request.json or {}
    scorer.record_feedback(data.get("message_id",""), data.get("agent_id",""),
                           data.get("rating",3), data.get("feedback",""),
                           data.get("tags",[]))
    return jsonify({"success": True})

@app.route("/api/agents/<agent_id>/feedback-analysis", methods=["GET"])
def get_feedback_analysis(agent_id):
    return jsonify(scorer.get_agent_feedback_analysis(agent_id))


# ═══════════════════════════════════════════════════════════════
# CONVERSATION BRANCHING
# ═══════════════════════════════════════════════════════════════

@app.route("/api/conversations/<conv_id>/branch", methods=["POST"])
def branch_conversation(conv_id):
    data = request.json or {}
    msg_id = data.get("message_id")
    if not msg_id:
        return jsonify({"error": "message_id required"}), 400
    try:
        result = brancher.branch_conversation(conv_id, msg_id,
                                                branch_name=data.get("branch_name",""),
                                                user_id=g.user_id)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/conversations/<conv_id>/branches", methods=["GET"])
def get_conversation_branches(conv_id):
    return jsonify({"branches": brancher.get_branches(conv_id)})

@app.route("/api/conversations/<conv_id>/branch-tree", methods=["GET"])
def get_branch_tree(conv_id):
    return jsonify(brancher.get_branch_tree(conv_id))


# ═══════════════════════════════════════════════════════════════
# VOICE LEARNING (Your AI writes like YOU)
# ═══════════════════════════════════════════════════════════════

@app.route("/api/voice-profile", methods=["GET"])
def get_voice_profile():
    return jsonify(voice_profile.get_readable_summary(g.user_id))

@app.route("/api/voice-profile/full", methods=["GET"])
def get_voice_profile_full():
    return jsonify(voice_profile.get_profile(g.user_id))

@app.route("/api/voice-profile/reset", methods=["POST"])
def reset_voice_profile():
    voice_profile.reset_profile(g.user_id)
    return jsonify({"success": True, "message": "Voice profile reset"})

@app.route("/api/voice-profile/ingest", methods=["POST"])
def ingest_voice_sample():
    """Manually ingest a writing sample to train the voice profile faster."""
    data = request.json or {}
    text = data.get("text", "")
    if len(text) < 30:
        return jsonify({"error": "Sample too short (min 30 characters)"}), 400
    voice_profile.ingest_sample(g.user_id, text, "manual_sample")
    return jsonify({"success": True, "profile": voice_profile.get_readable_summary(g.user_id)})


# ═══════════════════════════════════════════════════════════════
# NATURAL LANGUAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════

@app.route("/api/spaces/create-natural", methods=["POST"])
def create_space_natural():
    """Create a Space from a plain-English description."""
    data = request.json or {}
    description = data.get("description", "")
    if not description:
        return jsonify({"error": "description required"}), 400

    config = nl_config.parse_description(description)

    # Create the agent with the inferred config
    agent = agents.create_agent({
        "name": config["name"],
        "icon": config["icon"],
        "description": config["description"],
        "instructions": config["instructions"],
        "temperature": config["temperature"],
        "color": config["color"],
    }, owner_id=g.user_id)

    return jsonify({
        "agent": agent,
        "inferred": {
            "intent": config["detected_intent"],
            "tones": config["detected_tones"],
            "audience": config["detected_audience"],
        },
    }), 201

@app.route("/api/spaces/<agent_id>/modify-natural", methods=["POST"])
def modify_space_natural(agent_id):
    """Modify a Space using plain English. e.g. 'make it more casual'"""
    data = request.json or {}
    modification = data.get("modification", "")
    if not modification:
        return jsonify({"error": "modification required"}), 400

    agent = agents.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Space not found"}), 404

    # Version current instructions
    agent_import._version_prompt(agent_id, agent.get("instructions", ""))

    new_instructions = nl_config.modify_from_instruction(
        agent.get("instructions", ""), modification)

    updated = agents.update_agent(agent_id, {"instructions": new_instructions})
    return jsonify({"agent": updated, "modification_applied": modification})


# ═══════════════════════════════════════════════════════════════
# CONVERSATION ARTIFACTS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/conversations/<conv_id>/artifacts", methods=["GET"])
def get_conversation_artifacts(conv_id):
    """Extract decisions, tasks, facts, and key data from a conversation."""
    with get_db() as db:
        msgs_rows = db.execute(
            "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY created_at",
            (conv_id,)
        ).fetchall()
    if not msgs_rows:
        return jsonify({"artifacts": {}})

    messages = [{"role": r["role"], "content": r["content"]} for r in msgs_rows]
    agent = None
    conv = conversations.get_conversation(conv_id)
    if conv and conv.get("agent_id"):
        agent = agents.get_agent(conv["agent_id"])

    extracted = artifacts.extract_from_messages(messages, agent.get("name") if agent else "AI")
    return jsonify({"conversation_id": conv_id, "artifacts": extracted})


# ═══════════════════════════════════════════════════════════════
# PROACTIVE AI (Morning Briefings)
# ═══════════════════════════════════════════════════════════════

@app.route("/api/briefing", methods=["GET"])
def get_morning_briefing():
    return jsonify(proactive.generate_briefing(g.user_id))

@app.route("/api/notifications", methods=["GET"])
def get_notifications():
    return jsonify({"notifications": proactive.get_notifications(g.user_id)})


# ═══════════════════════════════════════════════════════════════
# INTERNATIONALIZATION (i18n)
# ═══════════════════════════════════════════════════════════════

@app.route("/api/i18n/languages", methods=["GET"])
def list_languages():
    return jsonify({"languages": get_available_languages()})

@app.route("/api/i18n/translations", methods=["GET"])
def get_user_translations():
    """Get translations for the current user's language."""
    lang = request.args.get("lang") or i18n.get_user_language(g.user_id)
    return jsonify({"lang": lang, "translations": get_translations(lang)})

@app.route("/api/i18n/translations/<lang_code>", methods=["GET"])
def get_lang_translations(lang_code):
    """Get translations for a specific language (no auth needed for initial load)."""
    return jsonify({"lang": lang_code, "translations": get_translations(lang_code)})

@app.route("/api/i18n/set", methods=["POST"])
def set_user_language():
    data = request.json or {}
    lang = data.get("language", "en")
    try:
        i18n.set_user_language(g.user_id, lang)
        return jsonify({"success": True, "language": lang})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/i18n/detect", methods=["GET"])
def detect_language():
    """Auto-detect language from browser."""
    header = request.headers.get("Accept-Language", "")
    detected = i18n.detect_language(header)
    return jsonify({"detected": detected})


# ═══════════════════════════════════════════════════════════════
# CONVERSATION DNA — Digital Twin of Your Business
# ═══════════════════════════════════════════════════════════════

@app.route("/api/dna", methods=["GET"])
def list_business_dna():
    blocked = _gated("business_dna")
    if blocked: return blocked
    category = request.args.get("category")
    return jsonify({"knowledge": conversation_dna.list_dna(g.user_id, category=category)})

@app.route("/api/dna", methods=["POST"])
def add_business_dna():
    blocked = _gated("business_dna")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("question") or not data.get("answer"):
        return jsonify({"error": "question and answer required"}), 400
    result = conversation_dna.record_knowledge(
        g.user_id, data["question"], data["answer"],
        category=data.get("category", "general"),
        conversation_id=data.get("conversation_id"),
        confidence=data.get("confidence", 0.8))
    return jsonify(result), 201

@app.route("/api/dna/query", methods=["POST"])
def query_business_dna():
    blocked = _gated("business_dna")
    if blocked: return blocked
    data = request.json or {}
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "question required"}), 400
    results = conversation_dna.query_dna(g.user_id, question,
        category=data.get("category"), limit=data.get("limit", 5))
    return jsonify({"results": results, "count": len(results)})

@app.route("/api/dna/categories", methods=["GET"])
def get_dna_categories():
    blocked = _gated("business_dna")
    if blocked: return blocked
    return jsonify({"categories": conversation_dna.get_categories(g.user_id)})

@app.route("/api/dna/<kid>", methods=["PUT"])
def update_dna_item(kid):
    blocked = _gated("business_dna")
    if blocked: return blocked
    data = request.json or {}
    return jsonify(conversation_dna.update_knowledge(kid, **data))

@app.route("/api/dna/<kid>", methods=["DELETE"])
def delete_dna_item(kid):
    blocked = _gated("business_dna")
    if blocked: return blocked
    conversation_dna.delete_knowledge(kid)
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════
# AI-TO-AI NEGOTIATION
# ═══════════════════════════════════════════════════════════════

@app.route("/api/negotiations", methods=["GET"])
def list_negotiations():
    blocked = _gated("ai_negotiation")
    if blocked: return blocked
    return jsonify({"negotiations": negotiation_mgr.list_negotiations(g.user_id)})

@app.route("/api/negotiations", methods=["POST"])
def create_negotiation():
    blocked = _gated("ai_negotiation")
    if blocked: return blocked
    data = request.json or {}
    required = ["party_a_agent", "party_b_user", "party_b_agent", "party_a_params", "party_b_params"]
    for r in required:
        if r not in data:
            return jsonify({"error": f"{r} required"}), 400
    neg = negotiation_mgr.create_negotiation(
        g.user_id, data["party_a_agent"],
        data["party_b_user"], data["party_b_agent"],
        data["party_a_params"], data["party_b_params"],
        max_rounds=data.get("max_rounds", 10))
    return jsonify(neg), 201

@app.route("/api/negotiations/<nid>", methods=["GET"])
def get_negotiation(nid):
    blocked = _gated("ai_negotiation")
    if blocked: return blocked
    neg = negotiation_mgr.get_negotiation(nid)
    if not neg: return jsonify({"error": "Not found"}), 404
    return jsonify(neg)

@app.route("/api/negotiations/<nid>/round", methods=["POST"])
def run_negotiation_round(nid):
    blocked = _gated("ai_negotiation")
    if blocked: return blocked
    try:
        result = negotiation_mgr.run_round(nid)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/negotiations/<nid>/run", methods=["POST"])
def run_full_negotiation(nid):
    blocked = _gated("ai_negotiation")
    if blocked: return blocked
    try:
        result = negotiation_mgr.run_full(nid)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ═══════════════════════════════════════════════════════════════
# DECISIONS — Time-Travel Context
# ═══════════════════════════════════════════════════════════════

@app.route("/api/decisions", methods=["GET"])
def list_decisions():
    blocked = _gated("decision_tracker")
    if blocked: return blocked
    agent_id = request.args.get("agent_id")
    return jsonify({"decisions": decision_tracker.list_decisions(g.user_id, agent_id=agent_id)})

@app.route("/api/decisions", methods=["POST"])
def record_decision():
    blocked = _gated("decision_tracker")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("decision"):
        return jsonify({"error": "decision required"}), 400
    result = decision_tracker.record_decision(
        g.user_id, data["decision"],
        reasoning=data.get("reasoning", ""),
        conversation_id=data.get("conversation_id"),
        agent_id=data.get("agent_id"),
        tags=data.get("tags", []),
        context=data.get("context", ""))
    return jsonify(result), 201

@app.route("/api/decisions/search", methods=["POST"])
def search_decisions():
    blocked = _gated("decision_tracker")
    if blocked: return blocked
    data = request.json or {}
    query = data.get("query", "")
    if not query:
        return jsonify({"error": "query required"}), 400
    results = decision_tracker.search_decisions(g.user_id, query, limit=data.get("limit", 10))
    return jsonify({"results": results, "count": len(results)})

@app.route("/api/decisions/<did>", methods=["GET"])
def get_decision(did):
    blocked = _gated("decision_tracker")
    if blocked: return blocked
    d = decision_tracker.get_decision(did)
    if not d: return jsonify({"error": "Not found"}), 404
    return jsonify(d)

@app.route("/api/decisions/<did>/supersede", methods=["POST"])
def supersede_decision(did):
    blocked = _gated("decision_tracker")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("decision"):
        return jsonify({"error": "new decision required"}), 400
    result = decision_tracker.supersede_decision(
        did, data["decision"], data.get("reasoning", ""),
        owner_id=g.user_id, conversation_id=data.get("conversation_id"),
        agent_id=data.get("agent_id"), tags=data.get("tags", []))
    return jsonify(result), 201

@app.route("/api/decisions/timeline", methods=["GET"])
def decision_timeline():
    blocked = _gated("decision_tracker")
    if blocked: return blocked
    tag = request.args.get("tag")
    return jsonify({"timeline": decision_tracker.get_timeline(g.user_id, tag=tag)})


# ═══════════════════════════════════════════════════════════════
# SPACE CLONING — Clone + Auto-Adapt
# ═══════════════════════════════════════════════════════════════

@app.route("/api/spaces/<agent_id>/clone", methods=["POST"])
def clone_space(agent_id):
    blocked = _gated("space_cloning")
    if blocked: return blocked
    data = request.json or {}
    try:
        result = space_cloner.clone_space(
            agent_id, g.user_id,
            client_name=data.get("client_name", ""),
            adaptations=data.get("adaptations", {}))
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/spaces/clones", methods=["GET"])
def list_space_clones():
    blocked = _gated("space_cloning")
    if blocked: return blocked
    source_id = request.args.get("source_id")
    return jsonify({"clones": space_cloner.list_clones(owner_id=g.user_id, source_id=source_id)})


# ═══════════════════════════════════════════════════════════════
# COST TICKER — Real-Time Per-Conversation Costs
# ═══════════════════════════════════════════════════════════════

@app.route("/api/conversations/<conv_id>/cost", methods=["GET"])
def get_conversation_cost(conv_id):
    blocked = _gated("cost_ticker")
    if blocked: return blocked
    return jsonify(cost_ticker.get_conversation_cost(conv_id))

@app.route("/api/conversations/<conv_id>/budget", methods=["POST"])
def set_conversation_budget(conv_id):
    blocked = _gated("cost_ticker")
    if blocked: return blocked
    data = request.json or {}
    cap = data.get("cap", 0)
    if cap <= 0:
        return jsonify({"error": "cap must be positive"}), 400
    return jsonify(cost_ticker.set_budget_cap(conv_id, cap))

@app.route("/api/costs/total", methods=["GET"])
def get_user_total_cost():
    blocked = _gated("cost_ticker")
    if blocked: return blocked
    days = int(request.args.get("days", 30))
    return jsonify(cost_ticker.get_user_total_cost(g.user_id, days=days))

@app.route("/api/costs/estimate", methods=["POST"])
def estimate_message_cost():
    blocked = _gated("cost_ticker")
    if blocked: return blocked
    data = request.json or {}
    model = data.get("model", "claude-sonnet-4-5-20250929")
    text = data.get("text", "")
    return jsonify(cost_ticker.estimate_cost(model, text))


# ═══════════════════════════════════════════════════════════════
# ROUNDTABLE — Multi-Agent Team Discussions
# ═══════════════════════════════════════════════════════════════

@app.route("/api/roundtable/modes", methods=["GET"])
def get_roundtable_modes():
    """List available discussion modes."""
    blocked = _gated("roundtable")
    if blocked: return blocked
    modes = {k: {"label": v["label"], "description": v["description"]}
             for k, v in DISCUSSION_MODES.items()}
    return jsonify({"modes": modes})

@app.route("/api/roundtable", methods=["GET"])
def list_roundtables():
    blocked = _gated("roundtable")
    if blocked: return blocked
    status = request.args.get("status")
    return jsonify({"roundtables": roundtable.list(g.user_id, status=status)})

@app.route("/api/roundtable", methods=["POST"])
def create_roundtable():
    """User creates a new Roundtable discussion."""
    blocked = _gated("roundtable")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("topic"):
        return jsonify({"error": "topic required"}), 400
    if not data.get("agent_ids") or len(data["agent_ids"]) < 2:
        return jsonify({"error": "Select at least 2 Spaces (agent_ids)"}), 400
    try:
        result = roundtable.create(
            g.user_id, data["topic"], data["agent_ids"],
            mode=data.get("mode", "debate"),
            red_team_agent_id=data.get("red_team_agent_id"),
            max_rounds=data.get("max_rounds", 5),
            context=data.get("context", ""))
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/roundtable/<rid>", methods=["GET"])
def get_roundtable_detail(rid):
    blocked = _gated("roundtable")
    if blocked: return blocked
    rt = roundtable.get(rid)
    if not rt: return jsonify({"error": "Not found"}), 404
    return jsonify(rt)

@app.route("/api/roundtable/<rid>/message", methods=["POST"])
def roundtable_user_message(rid):
    """User interjects in the discussion."""
    blocked = _gated("roundtable")
    if blocked: return blocked
    data = request.json or {}
    message = data.get("message", "")
    if not message:
        return jsonify({"error": "message required"}), 400
    try:
        entry = roundtable.user_message(rid, message)
        return jsonify(entry)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/roundtable/<rid>/round", methods=["POST"])
def run_roundtable_round(rid):
    """User triggers one round of discussion. All Spaces speak."""
    blocked = _gated("roundtable")
    if blocked: return blocked
    data = request.json or {}
    user_prompt = data.get("prompt")  # optional steering message
    try:
        entries = roundtable.run_round(rid, user_prompt=user_prompt)
        return jsonify({"entries": entries, "count": len(entries)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/roundtable/<rid>/summary", methods=["GET"])
def roundtable_summary(rid):
    """Get AI-generated summary of the discussion."""
    blocked = _gated("roundtable")
    if blocked: return blocked
    try:
        return jsonify(roundtable.request_summary(rid))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/roundtable/<rid>/end", methods=["POST"])
def end_roundtable(rid):
    """User ends the Roundtable."""
    blocked = _gated("roundtable")
    if blocked: return blocked
    try:
        return jsonify(roundtable.end(rid))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/roundtable/<rid>", methods=["DELETE"])
def delete_roundtable(rid):
    blocked = _gated("roundtable")
    if blocked: return blocked
    roundtable.delete(rid)
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════
# CONFIDENCE — Score any text
# ═══════════════════════════════════════════════════════════════

@app.route("/api/confidence/score", methods=["POST"])
def score_confidence():
    blocked = _gated("confidence_scoring")
    if blocked: return blocked
    data = request.json or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "text required"}), 400
    result = confidence_scorer.score_response(text,
        had_kb_context=data.get("had_kb", False),
        had_dna_context=data.get("had_dna", False),
        had_shared_context=data.get("had_shared", False),
        model_used=data.get("model", ""))
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════
# COLLABORATION — Teams
# ═══════════════════════════════════════════════════════════════

@app.route("/api/teams", methods=["GET"])
def list_teams():
    blocked = _gated("teams")
    if blocked: return blocked
    return jsonify({"teams": team_mgr.list_teams(g.user_id)})

@app.route("/api/teams", methods=["POST"])
def create_team():
    blocked = _gated("teams")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    result = team_mgr.create_team(g.user_id, data["name"], data.get("description", ""))
    return jsonify(result), 201

@app.route("/api/teams/<tid>", methods=["GET"])
def get_team(tid):
    blocked = _gated("teams")
    if blocked: return blocked
    t = team_mgr.get_team(tid)
    if not t: return jsonify({"error": "Not found"}), 404
    return jsonify(t)

@app.route("/api/teams/<tid>/invite", methods=["POST"])
def invite_team_member(tid):
    blocked = _gated("teams")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("email"):
        return jsonify({"error": "email required"}), 400
    try:
        result = team_mgr.invite_member(tid, g.user_id, data["email"], data.get("role", "member"))
        return jsonify(result), 201
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403

@app.route("/api/teams/invites", methods=["GET"])
def get_my_invites():
    blocked = _gated("teams")
    if blocked: return blocked
    return jsonify({"invites": team_mgr.get_pending_invites(g.user_id)})

@app.route("/api/teams/invites/<invite_id>/accept", methods=["POST"])
def accept_team_invite(invite_id):
    blocked = _gated("teams")
    if blocked: return blocked
    try:
        result = team_mgr.accept_invite(invite_id, g.user_id)
        return jsonify(result)
    except (ValueError, PermissionError) as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/teams/<tid>/members/<user_id>", methods=["DELETE"])
def remove_team_member(tid, user_id):
    blocked = _gated("teams")
    if blocked: return blocked
    try:
        team_mgr.remove_member(tid, g.user_id, user_id)
        return jsonify({"success": True})
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403

@app.route("/api/teams/<tid>/members/<user_id>/role", methods=["PUT"])
def update_team_member_role(tid, user_id):
    blocked = _gated("teams")
    if blocked: return blocked
    data = request.json or {}
    try:
        return jsonify(team_mgr.update_member_role(tid, g.user_id, user_id, data.get("role", "member")))
    except (PermissionError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


# ═══════════════════════════════════════════════════════════════
# COLLABORATION — Multi-User Roundtable
# ═══════════════════════════════════════════════════════════════

@app.route("/api/roundtable/<rid>/invite-users", methods=["POST"])
def invite_users_to_roundtable(rid):
    """Moderator invites human team members to the Roundtable."""
    blocked = _gated("roundtable_multiuser")
    if blocked: return blocked
    data = request.json or {}
    user_ids = data.get("user_ids", [])
    if not user_ids:
        return jsonify({"error": "user_ids required"}), 400
    try:
        result = collab_rt.invite_users_to_roundtable(rid, g.user_id, user_ids)
        return jsonify(result)
    except (ValueError, PermissionError) as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/roundtable/<rid>/human-message", methods=["POST"])
def roundtable_human_message(rid):
    """Any invited human participant posts a message."""
    blocked = _gated("roundtable_multiuser")
    if blocked: return blocked
    data = request.json or {}
    message = data.get("message", "")
    if not message:
        return jsonify({"error": "message required"}), 400
    try:
        entry = collab_rt.human_message(rid, g.user_id, message)
        return jsonify(entry)
    except (ValueError, PermissionError) as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/roundtable/<rid>/participants", methods=["GET"])
def get_roundtable_participants(rid):
    blocked = _gated("roundtable_multiuser")
    if blocked: return blocked
    try:
        return jsonify(collab_rt.get_participants(rid))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ═══════════════════════════════════════════════════════════════
# COLLABORATION — Presence and Activity
# ═══════════════════════════════════════════════════════════════

@app.route("/api/presence/heartbeat", methods=["POST"])
def send_heartbeat():
    blocked = _gated("presence")
    if blocked: return blocked
    data = request.json or {}
    return jsonify(presence.heartbeat(
        g.user_id, data.get("context", "app"), data.get("context_id", "")))

@app.route("/api/presence/online", methods=["GET"])
def get_online_users():
    blocked = _gated("presence")
    if blocked: return blocked
    context = request.args.get("context", "app")
    context_id = request.args.get("context_id", "")
    return jsonify({"online": presence.get_online_users(context, context_id)})

@app.route("/api/roundtable/<rid>/presence", methods=["GET"])
def get_roundtable_presence(rid):
    blocked = _gated("presence")
    if blocked: return blocked
    return jsonify({"online": presence.get_roundtable_presence(rid)})

@app.route("/api/teams/<tid>/activity", methods=["GET"])
def get_team_activity(tid):
    blocked = _gated("activity_feed")
    if blocked: return blocked
    limit = int(request.args.get("limit", 50))
    return jsonify({"activity": activity_feed.get_feed(tid, limit=limit)})



# ═══════════════════════════════════════════════════════════════
# EDUCATION — K-12 Tutoring
# ═══════════════════════════════════════════════════════════════

@app.route("/api/education/subjects", methods=["GET"])
def list_subjects():
    blocked = _gated("education_tutor")
    if blocked: return blocked
    return jsonify({"subjects": education.get_subjects()})

@app.route("/api/education/grades", methods=["GET"])
def list_grade_levels():
    blocked = _gated("education_tutor")
    if blocked: return blocked
    return jsonify({"grades": education.get_grade_levels()})

@app.route("/api/education/students", methods=["GET"])
def list_students():
    blocked = _gated("education_tutor")
    if blocked: return blocked
    return jsonify({"students": education.list_students(g.user_id)})

@app.route("/api/education/students", methods=["POST"])
def create_student():
    blocked = _gated("education_tutor")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("name") or not data.get("grade"):
        return jsonify({"error": "name and grade required"}), 400
    return jsonify(education.create_student(
        g.user_id, data["name"], data["grade"],
        subjects=data.get("subjects"),
        learning_style=data.get("learning_style", ""),
        special_needs=data.get("special_needs", ""))), 201

@app.route("/api/education/students/<sid>", methods=["GET"])
def get_student(sid):
    blocked = _gated("education_tutor")
    if blocked: return blocked
    s = education.get_student(sid)
    if not s: return jsonify({"error": "Not found"}), 404
    return jsonify(s)

@app.route("/api/education/students/<sid>", methods=["PUT"])
def update_student(sid):
    blocked = _gated("education_tutor")
    if blocked: return blocked
    return jsonify(education.update_student(sid, request.json or {}))

@app.route("/api/education/students/<sid>/tutor", methods=["POST"])
def tutor_student(sid):
    """Core tutoring — Socratic method, grade-adapted."""
    blocked = _gated("education_tutor")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("subject") or not data.get("question"):
        return jsonify({"error": "subject and question required"}), 400
    return jsonify(education.tutor(
        sid, g.user_id, data["subject"], data["question"],
        subtopic=data.get("subtopic", "")))

@app.route("/api/education/students/<sid>/study-guide", methods=["POST"])
def generate_student_study_guide(sid):
    """Generate a personalized study guide."""
    blocked = _gated("education_tutor")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("subject") or not data.get("topic"):
        return jsonify({"error": "subject and topic required"}), 400
    return jsonify(education.generate_study_guide(
        sid, g.user_id, data["subject"], data["topic"],
        exam_date=data.get("exam_date", "")))

@app.route("/api/education/students/<sid>/quiz", methods=["POST"])
def generate_student_quiz(sid):
    """Generate a practice quiz with explanations."""
    blocked = _gated("education_tutor")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("subject") or not data.get("topic"):
        return jsonify({"error": "subject and topic required"}), 400
    return jsonify(education.generate_quiz(
        sid, g.user_id, data["subject"], data["topic"],
        num_questions=data.get("num_questions", 5),
        difficulty=data.get("difficulty", "medium")))

@app.route("/api/education/students/<sid>/progress", methods=["GET"])
def get_student_progress(sid):
    """Student learning progress — subjects, sessions, activity."""
    blocked = _gated("education_tutor")
    if blocked: return blocked
    return jsonify(education.get_progress(sid))

@app.route("/api/education/dashboard", methods=["GET"])
def parent_dashboard():
    """Parent dashboard — what their children are studying."""
    blocked = _gated("education_tutor")
    if blocked: return blocked
    return jsonify(education.parent_dashboard(g.user_id))


# ═══════════════════════════════════════════════════════════════
# EDUCATION — Higher Ed: Learning DNA, Study Planner, Struggle Detection
# ═══════════════════════════════════════════════════════════════

@app.route("/api/education/learning-dna", methods=["GET"])
def get_learning_dna():
    """Get student's Learning DNA profile."""
    blocked = _gated("education_tutor")
    if blocked: return blocked
    return jsonify(learning_dna.get_profile(g.user_id))

@app.route("/api/education/learning-dna/update", methods=["POST"])
def update_learning_dna():
    """Update Learning DNA after an interaction."""
    blocked = _gated("education_tutor")
    if blocked: return blocked
    data = request.json or {}
    return jsonify(learning_dna.update_from_interaction(
        g.user_id, data.get("subject", "general"),
        data.get("was_helpful", True), data.get("approach_used", ""),
        confidence_after=data.get("confidence", 0.5)))

@app.route("/api/education/struggle-check", methods=["POST"])
def check_struggle():
    """Analyze a message for struggle signals."""
    blocked = _gated("education_tutor")
    if blocked: return blocked
    data = request.json or {}
    return jsonify(struggle_detector.analyze_message(
        g.user_id, data.get("message", ""), subject=data.get("subject", "")))

@app.route("/api/education/courses", methods=["GET"])
def list_student_courses():
    blocked = _gated("education_tutor")
    if blocked: return blocked
    return jsonify({"courses": study_planner.list_courses(g.user_id)})

@app.route("/api/education/courses", methods=["POST"])
def add_student_course():
    blocked = _gated("education_tutor")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("name"): return jsonify({"error": "name required"}), 400
    return jsonify(study_planner.add_course(
        g.user_id, data["name"], code=data.get("code", ""),
        professor=data.get("professor", ""), credits=data.get("credits", 3)))

@app.route("/api/education/assignments", methods=["GET"])
def list_student_assignments():
    blocked = _gated("education_tutor")
    if blocked: return blocked
    return jsonify({"assignments": study_planner.list_assignments(
        g.user_id, status=request.args.get("status"))})

@app.route("/api/education/assignments", methods=["POST"])
def add_student_assignment():
    blocked = _gated("education_tutor")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("title") or not data.get("course_id"):
        return jsonify({"error": "title and course_id required"}), 400
    return jsonify(study_planner.add_assignment(
        g.user_id, data["course_id"], data["title"],
        due_date=data.get("due_date", ""),
        assignment_type=data.get("type", "homework"),
        weight=data.get("weight", 0)))

@app.route("/api/education/assignments/<aid>", methods=["PUT"])
def update_student_assignment(aid):
    blocked = _gated("education_tutor")
    if blocked: return blocked
    return jsonify(study_planner.update_assignment(aid, request.json or {}))

@app.route("/api/education/assignments/upcoming", methods=["GET"])
def upcoming_assignments():
    blocked = _gated("education_tutor")
    if blocked: return blocked
    days = int(request.args.get("days", 14))
    return jsonify({"upcoming": study_planner.get_upcoming(g.user_id, days)})

@app.route("/api/education/study-dashboard", methods=["GET"])
def study_dashboard():
    """Complete academic dashboard — courses, assignments, Learning DNA."""
    blocked = _gated("education_tutor")
    if blocked: return blocked
    dna = learning_dna.get_profile(g.user_id)
    planner = study_planner.get_dashboard(g.user_id)
    return jsonify({
        "planner": planner,
        "learning_dna": {
            "struggle_score": dna.get("struggle_score", 0),
            "strong_subjects": dna.get("strong_subjects", []),
            "weak_subjects": dna.get("weak_subjects", []),
            "preferred_styles": dna.get("preferred_styles", []),
            "total_interactions": dna.get("total_interactions", 0),
        },
    })

@app.route("/api/education/plans", methods=["GET"])
def list_education_plans():
    """List education pricing plans."""
    from core.education import EDUCATION_PLANS
    return jsonify({"plans": EDUCATION_PLANS})


# ═══════════════════════════════════════════════════════════════
# CRISIS INTERVENTION — Admin Monitoring (Always On, No Feature Gate)
# ═══════════════════════════════════════════════════════════════

@app.route("/api/crisis/events", methods=["GET"])
def list_crisis_events():
    """Admin view of crisis detections. Always available — not feature-gated."""
    limit = int(request.args.get("limit", 50))
    return jsonify({"events": crisis_system.get_crisis_events(limit=limit)})

@app.route("/api/crisis/events/<event_id>/handled", methods=["POST"])
def mark_crisis_handled(event_id):
    """Mark a crisis event as reviewed/handled by admin."""
    return jsonify(crisis_system.mark_handled(
        event_id, handled_by=getattr(g, 'user_name', g.user_id)))


# ═══════════════════════════════════════════════════════════════
# GUARDRAILS — Age Verification, Parental Consent, Curriculum
# ═══════════════════════════════════════════════════════════════

@app.route("/api/guardrails/age-verify", methods=["POST"])
def verify_age():
    """Submit date of birth for age verification."""
    data = request.json or {}
    if not data.get("date_of_birth"):
        return jsonify({"error": "date_of_birth required (YYYY-MM-DD)"}), 400
    return jsonify(parental_consent.submit_age(g.user_id, data["date_of_birth"]))

@app.route("/api/guardrails/consent/status", methods=["GET"])
def check_consent_status():
    """Check if current user has required parental consent."""
    return jsonify(parental_consent.check_consent(g.user_id))

@app.route("/api/guardrails/consent", methods=["POST"])
def submit_consent():
    """Parent/guardian submits TOS consent for a minor."""
    data = request.json or {}
    required = ["parent_name", "parent_email", "relationship", "consent_agreed"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"{field} required"}), 400
    return jsonify(parental_consent.submit_parental_consent(
        data.get("user_id", g.user_id), data["parent_name"],
        data["parent_email"], data["relationship"],
        data["consent_agreed"], tos_version=data.get("tos_version", "1.0")))

@app.route("/api/guardrails/consent/revoke", methods=["POST"])
def revoke_consent():
    """Parent revokes consent — blocks the minor's access."""
    data = request.json or {}
    if not data.get("parent_email"):
        return jsonify({"error": "parent_email required"}), 400
    return jsonify(parental_consent.revoke_consent(
        data.get("user_id", g.user_id), data["parent_email"]))

@app.route("/api/guardrails/curriculum", methods=["GET"])
def get_curriculum():
    """Get current curriculum settings."""
    return jsonify(curriculum_guard.get_curriculum())

@app.route("/api/guardrails/curriculum", methods=["POST"])
def set_curriculum():
    """Admin sets approved curriculum — template and/or custom topics."""
    data = request.json or {}
    return jsonify(curriculum_guard.set_curriculum(
        template_name=data.get("template"),
        custom_allowed=data.get("allowed_topics"),
        custom_blocked=data.get("blocked_topics")))

@app.route("/api/guardrails/curriculum/templates", methods=["GET"])
def list_curriculum_templates():
    """List available curriculum templates."""
    return jsonify({"templates": curriculum_guard.get_templates()})

@app.route("/api/guardrails/curriculum/check", methods=["POST"])
def check_curriculum_compliance():
    """Check if a message passes curriculum guardrails."""
    data = request.json or {}
    if not data.get("message"):
        return jsonify({"error": "message required"}), 400
    return jsonify(curriculum_guard.check_message(data["message"]))

@app.route("/api/guardrails/filter", methods=["POST"])
def filter_content():
    """Check text against content safety filter."""
    data = request.json or {}
    if not data.get("text"):
        return jsonify({"error": "text required"}), 400
    return jsonify(content_filter.filter_output(data["text"]))


# ═══════════════════════════════════════════════════════════════
# DIGITAL MARKETING — Country-Aware Campaign Intelligence
# ═══════════════════════════════════════════════════════════════

@app.route("/api/marketing/campaigns", methods=["GET"])
def list_marketing_campaigns():
    blocked = _gated("digital_marketing")
    if blocked: return blocked
    return jsonify({"campaigns": marketing.list_campaigns(g.user_id, status=request.args.get("status"))})

@app.route("/api/marketing/campaigns", methods=["POST"])
def create_marketing_campaign():
    blocked = _gated("digital_marketing")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("name") or not data.get("objective"):
        return jsonify({"error": "name and objective required"}), 400
    result = marketing.create_campaign(
        g.user_id, data["name"], data["objective"],
        target_country=data.get("target_country", "US"),
        target_audience=data.get("target_audience", ""),
        budget=data.get("budget", 0),
        budget_currency=data.get("budget_currency", "USD"),
        start_date=data.get("start_date"), end_date=data.get("end_date"),
        notes=data.get("notes", ""))
    return jsonify(result), 201

@app.route("/api/marketing/campaigns/<cid>", methods=["GET"])
def get_marketing_campaign(cid):
    blocked = _gated("digital_marketing")
    if blocked: return blocked
    c = marketing.get_campaign(cid)
    if not c: return jsonify({"error": "Not found"}), 404
    return jsonify(c)

@app.route("/api/marketing/campaigns/<cid>", methods=["PUT"])
def update_marketing_campaign(cid):
    blocked = _gated("digital_marketing")
    if blocked: return blocked
    return jsonify(marketing.update_campaign(cid, request.json or {}))

@app.route("/api/marketing/campaigns/<cid>/strategy", methods=["POST"])
def generate_marketing_strategy(cid):
    """AI generates full locale-aware marketing strategy."""
    blocked = _gated("digital_marketing")
    if blocked: return blocked
    return jsonify(marketing.generate_strategy(cid, g.user_id))

@app.route("/api/marketing/campaigns/<cid>/content", methods=["POST"])
def generate_marketing_content(cid):
    """Generate locale-aware content (social, ads, email, blog, video, etc.)."""
    blocked = _gated("digital_marketing")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("content_type"):
        return jsonify({"error": "content_type required (social_post, ad_copy, email, blog_outline, landing_page, video_script, press_release, newsletter)"}), 400
    return jsonify(marketing.generate_content(
        cid, g.user_id, data["content_type"],
        platform=data.get("platform", ""), topic=data.get("topic", ""),
        tone=data.get("tone", ""), additional_instructions=data.get("instructions", "")))

@app.route("/api/marketing/campaigns/<cid>/ad-compliance", methods=["POST"])
def check_ad_compliance(cid):
    """Check ad copy against local advertising regulations."""
    blocked = _gated("digital_marketing")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("ad_text"):
        return jsonify({"error": "ad_text required"}), 400
    return jsonify(marketing.check_ad_compliance(cid, g.user_id, data["ad_text"]))

@app.route("/api/marketing/campaigns/<cid>/seo", methods=["POST"])
def generate_seo_brief(cid):
    """Generate locale-aware SEO brief."""
    blocked = _gated("digital_marketing")
    if blocked: return blocked
    data = request.json or {}
    return jsonify(marketing.get_seo_brief(cid, g.user_id, keywords=data.get("keywords", [])))

@app.route("/api/marketing/platforms/<country>", methods=["GET"])
def get_platform_guide(country):
    """Get platform strategy guide for a country."""
    blocked = _gated("digital_marketing")
    if blocked: return blocked
    result = marketing.get_platform_guide(country)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════
# GLOBAL CONTEXT — Country-Aware Intelligence
# ═══════════════════════════════════════════════════════════════

@app.route("/api/locale", methods=["GET"])
def get_workspace_locale():
    """Get current workspace locale settings."""
    return jsonify(global_ctx.get_workspace_locale())

@app.route("/api/locale", methods=["POST"])
def set_workspace_locale():
    """Set workspace locale — affects language, compliance, and culture context."""
    data = request.json or {}
    if not data.get("country"):
        return jsonify({"error": "country code required (e.g., US, GB, MX, DE, JP)"}), 400
    result = global_ctx.set_workspace_locale(
        data["country"], language=data.get("language"))
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)

@app.route("/api/locale/countries", methods=["GET"])
def list_supported_countries():
    """List all supported countries with languages."""
    return jsonify({"countries": global_ctx.list_countries()})

@app.route("/api/locale/country/<code>", methods=["GET"])
def get_country_profile(code):
    """Get full country profile — laws, customs, governance."""
    profile = global_ctx.get_country_profile(code)
    if not profile:
        return jsonify({"error": f"Country {code} not found"}), 404
    return jsonify(profile)

@app.route("/api/locale/compliance/<code>", methods=["GET"])
def get_country_compliance(code):
    """Get compliance laws for a specific country."""
    ctx = global_ctx.get_compliance_context(code)
    if not ctx:
        return jsonify({"error": "Country not found"}), 404
    return jsonify({"country": code, "compliance": ctx})

@app.route("/api/locale/sales/<code>", methods=["GET"])
def get_country_sales_context(code):
    """Get business culture and sales customs for a country."""
    ctx = global_ctx.get_sales_context(code)
    if not ctx:
        return jsonify({"error": "Country not found"}), 404
    return jsonify({"country": code, "sales_context": ctx})


# ═══════════════════════════════════════════════════════════════
# SALES COACH — RFP Analysis, Interview Prep, Deal Intelligence
# ═══════════════════════════════════════════════════════════════

@app.route("/api/sales/deals", methods=["GET"])
def list_deals():
    blocked = _gated("sales_coach")
    if blocked: return blocked
    stage = request.args.get("stage")
    return jsonify({"deals": sales_coach.list_deals(g.user_id, stage=stage)})

@app.route("/api/sales/deals", methods=["POST"])
def create_deal():
    blocked = _gated("sales_coach")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("title"):
        return jsonify({"error": "title required"}), 400
    result = sales_coach.create_deal(
        g.user_id, data["title"], data.get("client_name", ""),
        deal_value=data.get("deal_value", 0), close_date=data.get("close_date"),
        stage=data.get("stage", "prospect"), notes=data.get("notes", ""),
        rfp_text=data.get("rfp_text", ""), proposal_text=data.get("proposal_text", ""),
        client_requirements=data.get("client_requirements", ""))
    return jsonify(result), 201

@app.route("/api/sales/deals/<did>", methods=["GET"])
def get_deal_detail(did):
    blocked = _gated("sales_coach")
    if blocked: return blocked
    d = sales_coach.get_deal(did)
    if not d: return jsonify({"error": "Not found"}), 404
    return jsonify(d)

@app.route("/api/sales/deals/<did>", methods=["PUT"])
def update_deal(did):
    blocked = _gated("sales_coach")
    if blocked: return blocked
    return jsonify(sales_coach.update_deal(did, request.json or {}))

@app.route("/api/sales/deals/<did>/analyze-rfp", methods=["POST"])
def analyze_rfp(did):
    """AI analyzes the RFP — extracts requirements, criteria, red flags."""
    blocked = _gated("sales_coach")
    if blocked: return blocked
    return jsonify(sales_coach.analyze_rfp(did, g.user_id))

@app.route("/api/sales/deals/<did>/gap-analysis", methods=["POST"])
def deal_gap_analysis(did):
    """Compare proposal vs. RFP — find gaps and strengths."""
    blocked = _gated("sales_coach")
    if blocked: return blocked
    return jsonify(sales_coach.gap_analysis(did, g.user_id))

@app.route("/api/sales/deals/<did>/simulate-interview", methods=["POST"])
def simulate_interview(did):
    """AI plays the client and asks hard questions."""
    blocked = _gated("sales_coach")
    if blocked: return blocked
    data = request.json or {}
    return jsonify(sales_coach.simulate_interview(
        did, g.user_id, difficulty=data.get("difficulty", "tough"),
        focus=data.get("focus", "")))

@app.route("/api/sales/deals/<did>/objections", methods=["POST"])
def prepare_objections(did):
    """Generate likely objections with coached responses."""
    blocked = _gated("sales_coach")
    if blocked: return blocked
    return jsonify(sales_coach.prepare_objections(did, g.user_id))

@app.route("/api/sales/deals/<did>/score-pitch", methods=["POST"])
def score_pitch(did):
    """Score your pitch across 6 dimensions with specific feedback."""
    blocked = _gated("sales_coach")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("pitch_text"):
        return jsonify({"error": "pitch_text required"}), 400
    return jsonify(sales_coach.score_pitch(did, g.user_id, data["pitch_text"]))

@app.route("/api/sales/deals/<did>/brief", methods=["POST"])
def generate_deal_brief(did):
    """One-page deal brief — everything you need before the meeting."""
    blocked = _gated("sales_coach")
    if blocked: return blocked
    return jsonify(sales_coach.generate_brief(did, g.user_id))

@app.route("/api/sales/deals/<did>/coach", methods=["POST"])
def live_coach(did):
    """Real-time: 'The client just asked X, how should I respond?'"""
    blocked = _gated("sales_coach")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("question"):
        return jsonify({"error": "question required"}), 400
    return jsonify(sales_coach.coach_response(did, g.user_id, data["question"]))

@app.route("/api/sales/deals/<did>/outcome", methods=["POST"])
def record_deal_outcome(did):
    """Record win/loss with reason."""
    blocked = _gated("sales_coach")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("outcome"):
        return jsonify({"error": "outcome required (won/lost/no_decision/cancelled)"}), 400
    try:
        return jsonify(sales_coach.record_outcome(
            did, data["outcome"], data.get("loss_reason", ""), data.get("notes", "")))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/sales/pipeline", methods=["GET"])
def sales_pipeline():
    """Pipeline dashboard with win/loss analytics."""
    blocked = _gated("sales_coach")
    if blocked: return blocked
    return jsonify(sales_coach.get_pipeline(g.user_id))


# ═══════════════════════════════════════════════════════════════
# SECURITY FORTRESS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/security/password/validate", methods=["POST"])
def validate_password():
    """Check password strength before submission."""
    data = request.json or {}
    if not data.get("password"): return jsonify({"error": "password required"}), 400
    return jsonify(password_fortress.validate_password(
        data["password"], email=data.get("email", "")))

@app.route("/api/security/gdpr/preview", methods=["GET"])
def gdpr_preview():
    """Preview what data would be deleted."""
    return jsonify(gdpr_erasure.get_erasure_preview(g.user_id))

@app.route("/api/security/gdpr/erase", methods=["POST"])
def gdpr_erase():
    """PERMANENTLY delete all user data. Requires confirmation."""
    data = request.json or {}
    if data.get("confirm") != "DELETE_ALL_MY_DATA":
        return jsonify({"error": "Must send {\"confirm\": \"DELETE_ALL_MY_DATA\"} to proceed"}), 400
    result = gdpr_erasure.erase_user(g.user_id, requester_id=g.user_id)
    session.clear()
    return jsonify(result)

@app.route("/api/admin/accounts/<user_id>/unlock", methods=["POST"])
def admin_unlock_account(user_id):
    """Admin unlocks a locked account."""
    account_lockout.unlock(user_id)
    return jsonify({"unlocked": True, "user_id": user_id})

@app.route("/api/security/headers", methods=["GET"])
def get_security_info():
    """Show current security configuration."""
    return jsonify({
        "encryption": "AES-256-GCM",
        "password_hashing": "bcrypt (12 rounds)",
        "session_timeout": "8 hours idle, 24 hours absolute",
        "cookie_flags": "httponly, samesite=lax, secure (in production)",
        "csp": "Enabled — script-src self + CDN, frame-ancestors none",
        "rate_limiting": "Sensitive endpoints: 10/min, bulk: 3/min",
        "mfa": "TOTP available",
        "zero_knowledge": "Optional AES-256-GCM with user-derived key",
        "compliance": "18-rule watchdog, 3-tier escalation",
        "gdpr": "Full erasure available at /api/security/gdpr/erase",
        "account_lockout": "Progressive: 3→30s, 5→5min, 8→30min, 10→permanent",
    })


# ═══════════════════════════════════════════════════════════════
# PLATFORM INTELLIGENCE — Self-Healing + Collective Feedback
# ═══════════════════════════════════════════════════════════════

@app.route("/api/platform/health", methods=["GET"])
def platform_health_dashboard():
    """Full platform health dashboard."""
    return jsonify(health_monitor.get_health_dashboard())

@app.route("/api/platform/recommendations", methods=["GET"])
def platform_recommendations():
    """AI-generated recommendations based on platform health."""
    return jsonify({"recommendations": health_monitor.generate_recommendations()})

@app.route("/api/platform/feedback-trends", methods=["GET"])
def platform_feedback_trends():
    """Collective user feedback analysis."""
    days = int(request.args.get("days", 30))
    return jsonify(feedback_engine.analyze_feedback_trends(days))

@app.route("/api/platform/feedback-recommendations", methods=["GET"])
def platform_feedback_recs():
    """Fix recommendations from user feedback patterns."""
    days = int(request.args.get("days", 30))
    return jsonify({"recommendations": feedback_engine.generate_fix_recommendations(days)})

@app.route("/api/platform/briefing", methods=["GET"])
def admin_briefing():
    """Complete briefing for the admin — everything the platform found."""
    return jsonify(admin_channel.generate_briefing())

@app.route("/api/platform/proposals", methods=["GET"])
def list_change_proposals():
    """List all change proposals."""
    status = request.args.get("status")
    return jsonify({"proposals": admin_channel.list_proposals(status=status)})

@app.route("/api/platform/proposals", methods=["POST"])
def create_change_proposal():
    """Create a change proposal (platform or admin)."""
    data = request.json or {}
    if not data.get("title"):
        return jsonify({"error": "title required"}), 400
    return jsonify(admin_channel.create_change_proposal(
        data["title"], data.get("description", ""),
        data.get("change_type", "configuration"),
        data.get("proposed_changes", {}),
        source=data.get("source", "admin")))

@app.route("/api/platform/proposals/<pid>/approve", methods=["POST"])
def approve_change_proposal(pid):
    """Admin approves a platform change proposal."""
    data = request.json or {}
    return jsonify(admin_channel.approve_proposal(
        pid, g.user_id, admin_notes=data.get("notes", "")))

@app.route("/api/platform/proposals/<pid>/reject", methods=["POST"])
def reject_change_proposal(pid):
    """Admin rejects a change proposal."""
    data = request.json or {}
    return jsonify(admin_channel.reject_proposal(
        pid, g.user_id, reason=data.get("reason", "")))


# ═══════════════════════════════════════════════════════════════
# PROVIDER FAILOVER
# ═══════════════════════════════════════════════════════════════

@app.route("/api/providers/health", methods=["GET"])
def provider_health():
    return jsonify({"health": provider_failover.get_health()})


# ═══════════════════════════════════════════════════════════════
# PROACTIVE ENGINE — Day-Two Retention
# ═══════════════════════════════════════════════════════════════

@app.route("/api/nudges", methods=["GET"])
def get_nudges():
    """Get relevant nudges for the current user."""
    return jsonify({"nudges": proactive_engine.generate_nudges(g.user_id)})


# ═══════════════════════════════════════════════════════════════
# SPACE VERSIONING — Undo any change
# ═══════════════════════════════════════════════════════════════

@app.route("/api/spaces/<agent_id>/versions", methods=["GET"])
def list_space_versions(agent_id):
    return jsonify({"versions": space_versioning.list_versions(agent_id)})

@app.route("/api/spaces/<agent_id>/versions/<vid>", methods=["GET"])
def get_space_version(agent_id, vid):
    v = space_versioning.get_version(vid)
    if not v: return jsonify({"error": "Version not found"}), 404
    return jsonify(v)

@app.route("/api/spaces/<agent_id>/versions/<vid>/restore", methods=["POST"])
def restore_space_version(agent_id, vid):
    return jsonify(space_versioning.restore_version(vid, agent_manager=agents))


# ═══════════════════════════════════════════════════════════════
# RESPONSE FEEDBACK — Users rate, platform learns
# ═══════════════════════════════════════════════════════════════

@app.route("/api/feedback", methods=["POST"])
def submit_feedback():
    data = request.json or {}
    if not data.get("rating"): return jsonify({"error": "rating required (up/down or 1-5)"}), 400
    return jsonify(response_feedback.submit_feedback(
        g.user_id, data.get("message_id", ""), data["rating"],
        comment=data.get("comment", ""), agent_id=data.get("agent_id", ""),
        model=data.get("model", ""), provider=data.get("provider", "")))

@app.route("/api/feedback/stats", methods=["GET"])
def feedback_stats():
    agent_id = request.args.get("agent_id")
    return jsonify(response_feedback.get_feedback_stats(agent_id=agent_id))

@app.route("/api/feedback/model-rankings", methods=["GET"])
def model_rankings():
    return jsonify({"rankings": response_feedback.get_model_rankings()})


# ═══════════════════════════════════════════════════════════════
# WEBHOOKS — Platform talks to the outside world
# ═══════════════════════════════════════════════════════════════

@app.route("/api/webhooks", methods=["GET"])
def list_webhooks():
    return jsonify({"webhooks": webhook_mgr.list_webhooks(g.user_id)})

@app.route("/api/webhooks", methods=["POST"])
def create_webhook():
    data = request.json or {}
    if not data.get("url") or not data.get("events"):
        return jsonify({"error": "url and events required"}), 400
    return jsonify(webhook_mgr.register_webhook(
        g.user_id, data["url"], data["events"],
        name=data.get("name", ""), secret=data.get("secret", "")))

@app.route("/api/webhooks/<wid>", methods=["DELETE"])
def delete_webhook(wid):
    webhook_mgr.delete_webhook(wid)
    return jsonify({"deleted": True})

@app.route("/api/webhooks/events", methods=["GET"])
def list_webhook_events():
    return jsonify({"events": webhook_mgr.get_available_events()})


# ═══════════════════════════════════════════════════════════════
# BACKUPS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/backups", methods=["GET"])
def list_backups():
    return jsonify({"backups": backup_mgr.list_backups()})

@app.route("/api/backups/create", methods=["POST"])
def create_backup():
    return jsonify(backup_mgr.create_backup())

@app.route("/api/backups/status", methods=["GET"])
def backup_status():
    return jsonify(backup_mgr.get_backup_status())


# ═══════════════════════════════════════════════════════════════
# ACCESSIBILITY
# ═══════════════════════════════════════════════════════════════

@app.route("/api/accessibility/modes", methods=["GET"])
def list_a11y_modes():
    return jsonify({"modes": accessibility.get_modes()})

@app.route("/api/accessibility/current", methods=["GET"])
def get_a11y_mode():
    return jsonify(accessibility.get_user_mode(g.user_id))

@app.route("/api/accessibility/set", methods=["POST"])
def set_a11y_mode():
    data = request.json or {}
    if not data.get("mode"): return jsonify({"error": "mode required"}), 400
    return jsonify(accessibility.set_user_mode(g.user_id, data["mode"]))


# ═══════════════════════════════════════════════════════════════
# ETHICAL REASONING
# ═══════════════════════════════════════════════════════════════

@app.route("/api/ethics/analyze", methods=["POST"])
def analyze_ethics():
    data = request.json or {}
    if not data.get("text"): return jsonify({"error": "text required"}), 400
    return jsonify(ethical_layer.analyze(data["text"]))


# ═══════════════════════════════════════════════════════════════
# DATA PORTABILITY — Your data, your right to leave
# ═══════════════════════════════════════════════════════════════

@app.route("/api/data-export/preview", methods=["GET"])
def preview_export():
    return jsonify(data_portability.get_export_summary(g.user_id))

@app.route("/api/data-export/full", methods=["POST"])
def full_data_export():
    export = data_portability.generate_export(g.user_id)
    return jsonify(export)


# ═══════════════════════════════════════════════════════════════
# SPONSORED TIER — Pay It Forward
# ═══════════════════════════════════════════════════════════════

@app.route("/api/sponsor/create", methods=["POST"])
def create_sponsorship():
    data = request.json or {}
    return jsonify(sponsored_tier.create_sponsorship(
        g.user_id, months=data.get("months", 1),
        amount_per_month=data.get("amount", 7.0)))

@app.route("/api/sponsor/apply", methods=["POST"])
def apply_for_sponsorship():
    data = request.json or {}
    if not data.get("reason"): return jsonify({"error": "reason required"}), 400
    return jsonify(sponsored_tier.apply_for_sponsorship(
        g.user_id, data["reason"],
        organization=data.get("organization", ""),
        role=data.get("role", "")))

@app.route("/api/sponsor/approve/<app_id>", methods=["POST"])
def approve_sponsored(app_id):
    return jsonify(sponsored_tier.approve_application(app_id, g.user_id))

@app.route("/api/sponsor/impact", methods=["GET"])
def sponsor_impact():
    return jsonify(sponsored_tier.get_impact_stats())


# ═══════════════════════════════════════════════════════════════
# TRANSPARENCY REPORT — Public proof
# ═══════════════════════════════════════════════════════════════

@app.route("/api/transparency-report", methods=["GET"])
def get_transparency_report():
    return jsonify(transparency.generate_report())


# ═══════════════════════════════════════════════════════════════
# SMART TEAM BUILDER — "I'm a [profession]" → AI Team
# ═══════════════════════════════════════════════════════════════

@app.route("/api/team-builder/industries", methods=["GET"])
def list_tb_industries():
    return jsonify({"industries": team_builder.get_industries()})

@app.route("/api/team-builder/industries/<industry_id>/roles", methods=["GET"])
def list_tb_roles(industry_id):
    return jsonify({"roles": team_builder.get_industry_roles(industry_id)})

@app.route("/api/team-builder/search", methods=["GET"])
def search_tb_roles():
    q = request.args.get("q", "")
    if not q: return jsonify({"error": "q parameter required"}), 400
    return jsonify({"results": team_builder.search_roles(q)})

@app.route("/api/team-builder/recommend/<role_id>", methods=["GET"])
def get_tb_recommendation(role_id):
    return jsonify(team_builder.get_recommendation(role_id))

@app.route("/api/team-builder/apply", methods=["POST"])
def apply_tb_recommendation():
    data = request.json or {}
    if not data.get("role"):
        return jsonify({"error": "role required"}), 400
    return jsonify(team_builder.apply_recommendation(
        g.user_id, data["role"],
        admin_name=getattr(g, 'user_name', '')))

@app.route("/api/team-builder/generate", methods=["POST"])
def generate_tb_profession():
    """AI generates a team for an unknown profession and LEARNS it for future users."""
    data = request.json or {}
    if not data.get("title"):
        return jsonify({"error": "title required (e.g., 'security guard')"}), 400
    return jsonify(team_builder.generate_for_unknown(
        data["title"], g.user_id,
        description=data.get("description", "")))

@app.route("/api/team-builder/learned", methods=["GET"])
def list_learned_professions():
    """List all AI-learned professions."""
    min_uses = int(request.args.get("min_uses", 0))
    return jsonify({"learned": team_builder.get_learned_professions(min_uses=min_uses)})

@app.route("/api/team-builder/popular", methods=["GET"])
def popular_learned_professions():
    """Most popular AI-generated professions — candidates for promotion to built-in."""
    limit = int(request.args.get("limit", 20))
    return jsonify({"popular": team_builder.get_popular_learned(limit=limit)})

@app.route("/api/team-builder/stats", methods=["GET"])
def get_tb_stats():
    return jsonify(team_builder.get_stats())


# ═══════════════════════════════════════════════════════════════
# SOUL — Positivity Guard, Zero-Knowledge, Wellbeing
# ═══════════════════════════════════════════════════════════════

@app.route("/api/soul/tone-check", methods=["POST"])
def check_tone():
    """Analyze text for negativity patterns."""
    data = request.json or {}
    if not data.get("text"): return jsonify({"error": "text required"}), 400
    return jsonify(positivity_guard.analyze_tone(data["text"]))

@app.route("/api/soul/dna-filter", methods=["POST"])
def check_dna_filter():
    """Check what would be learned vs filtered from a text sample."""
    data = request.json or {}
    if not data.get("text"): return jsonify({"error": "text required"}), 400
    analysis = positivity_guard.analyze_tone(data["text"])
    filter_result = positivity_guard.filter_for_dna(data["text"], analysis)
    return jsonify({"analysis": analysis, "filter": filter_result})

@app.route("/api/soul/wellbeing", methods=["POST"])
def check_wellbeing():
    """Check a message for wellbeing signals."""
    data = request.json or {}
    if not data.get("message"): return jsonify({"error": "message required"}), 400
    return jsonify(wellbeing.assess_message(g.user_id, data["message"]))

@app.route("/api/soul/zk/status", methods=["GET"])
def zk_status():
    """Check if zero-knowledge encryption is enabled."""
    return jsonify({"enabled": zk_vault.is_enabled()})

@app.route("/api/soul/zk/enable", methods=["POST"])
def zk_enable():
    """Enable zero-knowledge encryption."""
    zk_vault.enable()
    return jsonify({"enabled": True, "message": "Zero-knowledge encryption enabled. User data will be encrypted with user-derived keys."})

@app.route("/api/soul/zk/disable", methods=["POST"])
def zk_disable():
    """Disable zero-knowledge encryption."""
    zk_vault.disable()
    return jsonify({"enabled": False})


# ═══════════════════════════════════════════════════════════════
# IP SHIELD — Technical IP Protection
# ═══════════════════════════════════════════════════════════════

@app.route("/api/ip-shield/canaries/plant", methods=["POST"])
def plant_canaries():
    """Plant canary tokens across the system (admin only)."""
    return jsonify(canary_system.plant_canaries(g.user_id))

@app.route("/api/ip-shield/canaries", methods=["GET"])
def list_canaries():
    """List all planted canary tokens (admin only)."""
    return jsonify({"canaries": canary_system.get_canaries()})

@app.route("/api/ip-shield/canaries/check", methods=["POST"])
def check_canaries():
    """Check if external text contains our canary tokens."""
    data = request.json or {}
    text = data.get("text", "")
    if not text: return jsonify({"error": "text required"}), 400
    return jsonify(canary_system.check_canary(text))

@app.route("/api/ip-shield/watermark/detect", methods=["POST"])
def detect_watermark():
    """Check if text contains our zero-width character watermark."""
    data = request.json or {}
    text = data.get("text", "")
    if not text: return jsonify({"error": "text required"}), 400
    return jsonify(watermark.detect_watermark(text))

@app.route("/api/ip-shield/rate-limits", methods=["GET"])
def get_rate_limit_config():
    """View rate limiting configuration."""
    return jsonify(sensitive_limiter.get_config())

@app.route("/api/ip-shield/evidence", methods=["GET"])
def get_ip_evidence():
    """View IP creation evidence log."""
    limit = int(request.args.get("limit", 100))
    return jsonify({"evidence": ip_evidence.get_evidence_log(limit=limit)})

@app.route("/api/ip-shield/evidence", methods=["POST"])
def log_ip_evidence():
    """Log a new IP evidence entry."""
    data = request.json or {}
    if not data.get("event_type") or not data.get("description"):
        return jsonify({"error": "event_type and description required"}), 400
    return jsonify(ip_evidence.log_evidence(
        data["event_type"], data["description"], data.get("details", {})))

@app.route("/api/ip-shield/deploy-config", methods=["GET"])
def get_deploy_config():
    """Get production deployment configuration."""
    from core.ip_shield import DeployConfig
    return jsonify(DeployConfig.get_production_config())


# ═══════════════════════════════════════════════════════════════
# ONBOARDING — Guided Setup
# ═══════════════════════════════════════════════════════════════

@app.route("/api/onboarding/status", methods=["GET"])
def onboarding_status():
    """Check if the user has completed onboarding."""
    return jsonify(onboarding.get_onboarding_status())

@app.route("/api/onboarding/use-cases", methods=["GET"])
def list_use_cases():
    """List available business use case templates."""
    return jsonify({"use_cases": onboarding.get_use_cases()})

@app.route("/api/onboarding/recommend/<use_case>", methods=["GET"])
def get_onboarding_recommendation(use_case):
    """Get full recommendation for a specific use case."""
    result = onboarding.get_recommendation(use_case)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)

@app.route("/api/onboarding/apply", methods=["POST"])
def apply_onboarding():
    """Apply a use case recommendation — activates features and creates Spaces."""
    data = request.json or {}
    use_case = data.get("use_case", "")
    if not use_case:
        return jsonify({"error": "use_case required"}), 400
    try:
        result = onboarding.apply_recommendation(
            g.user_id, use_case, g.user_id,
            admin_name=getattr(g, 'user_name', ''))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/onboarding/reset", methods=["POST"])
def reset_onboarding():
    """Reset onboarding to run the guide again."""
    return jsonify(onboarding.reset_onboarding())


# ═══════════════════════════════════════════════════════════════
# PRICING — Plan Management
# ═══════════════════════════════════════════════════════════════

@app.route("/api/pricing/tiers", methods=["GET"])
def list_pricing_tiers():
    """List all available pricing tiers."""
    return jsonify({"tiers": pricing.get_tiers()})

@app.route("/api/pricing/tiers/<tier>", methods=["GET"])
def get_pricing_tier(tier):
    """Get full details for a specific tier."""
    detail = pricing.get_tier_detail(tier)
    if not detail:
        return jsonify({"error": "Tier not found"}), 404
    return jsonify(detail)

@app.route("/api/pricing/current", methods=["GET"])
def get_current_plan():
    """Get the current subscription plan."""
    return jsonify(pricing.get_current_plan(g.user_id))

@app.route("/api/pricing/upgrade", methods=["POST"])
def upgrade_plan():
    """Upgrade to a new plan."""
    data = request.json or {}
    plan = data.get("plan", "")
    if not plan:
        return jsonify({"error": "plan required"}), 400
    try:
        return jsonify(pricing.set_plan(g.user_id, plan))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/pricing/feature-plan/<feature>", methods=["GET"])
def get_feature_plan_requirement(feature):
    """Check which plan is needed for a specific feature."""
    min_plan = pricing.get_upgrade_needed(feature)
    return jsonify({"feature": feature, "minimum_plan": min_plan})


# ═══════════════════════════════════════════════════════════════
# FEATURE GATES — Admin-Controlled Activation
# ═══════════════════════════════════════════════════════════════

@app.route("/api/features", methods=["GET"])
def list_features():
    """List all features and their activation status."""
    return jsonify({"features": feature_gate.get_all()})

@app.route("/api/features/categories", methods=["GET"])
def list_features_by_category():
    return jsonify({"categories": feature_gate.get_by_category()})

@app.route("/api/features/<feature>/enable", methods=["POST"])
def enable_feature(feature):
    """Admin activates a feature."""
    try:
        result = feature_gate.enable(feature, g.user_id,
            admin_name=getattr(g, 'user_name', ''))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/features/<feature>/disable", methods=["POST"])
def disable_feature(feature):
    """Admin deactivates a feature."""
    try:
        result = feature_gate.disable(feature, g.user_id,
            admin_name=getattr(g, 'user_name', ''))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/features/bulk", methods=["POST"])
def bulk_toggle_features():
    """Enable or disable multiple features at once."""
    data = request.json or {}
    enable = data.get("enable", [])
    disable = data.get("disable", [])
    results = []
    if enable:
        results.extend(feature_gate.bulk_enable(enable, g.user_id,
            admin_name=getattr(g, 'user_name', '')))
    if disable:
        results.extend(feature_gate.bulk_disable(disable, g.user_id,
            admin_name=getattr(g, 'user_name', '')))
    return jsonify({"results": results})

@app.route("/api/features/log", methods=["GET"])
def feature_gate_audit_log():
    limit = int(request.args.get("limit", 50))
    return jsonify({"log": feature_gate.get_audit_log(limit=limit)})


# ═══════════════════════════════════════════════════════════════
# ENTERPRISE — Action Item Tracker
# ═══════════════════════════════════════════════════════════════

@app.route("/api/actions", methods=["GET"])
def list_action_items():
    blocked = _gated("action_items")
    if blocked: return blocked
    return jsonify({"items": action_tracker.list_items(
        g.user_id, assignee=request.args.get("assignee"),
        status=request.args.get("status"), priority=request.args.get("priority"))})

@app.route("/api/actions", methods=["POST"])
def create_action_item():
    blocked = _gated("action_items")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("title"):
        return jsonify({"error": "title required"}), 400
    result = action_tracker.create_item(
        g.user_id, data["title"], data.get("assignee", ""),
        due_date=data.get("due_date"), priority=data.get("priority", "medium"),
        description=data.get("description", ""), tags=data.get("tags", []),
        source_type=data.get("source_type", "manual"), source_id=data.get("source_id", ""))
    return jsonify(result), 201

@app.route("/api/actions/<aid>", methods=["GET"])
def get_action_item(aid):
    blocked = _gated("action_items")
    if blocked: return blocked
    item = action_tracker.get_item(aid)
    if not item: return jsonify({"error": "Not found"}), 404
    return jsonify(item)

@app.route("/api/actions/<aid>", methods=["PUT"])
def update_action_item(aid):
    blocked = _gated("action_items")
    if blocked: return blocked
    return jsonify(action_tracker.update_item(aid, request.json or {}))

@app.route("/api/actions/dashboard", methods=["GET"])
def action_items_dashboard():
    blocked = _gated("action_items")
    if blocked: return blocked
    return jsonify(action_tracker.get_dashboard(g.user_id))


# ═══════════════════════════════════════════════════════════════
# ENTERPRISE — Compliance Watchdog
# ═══════════════════════════════════════════════════════════════

@app.route("/api/compliance/scan", methods=["POST"])
def compliance_scan():
    blocked = _gated("compliance_watchdog")
    if blocked: return blocked
    data = request.json or {}
    text = data.get("text", "")
    if not text: return jsonify({"error": "text required"}), 400
    result = compliance_watchdog.scan_text(text, context=data.get("context", ""))
    # Auto-log critical flags
    for flag in result.get("flags", []):
        if flag["severity"] in ("critical", "high"):
            compliance_watchdog.log_flag(g.user_id, flag,
                source_type=data.get("source_type", ""), source_id=data.get("source_id", ""))
    return jsonify(result)

@app.route("/api/compliance/flags", methods=["GET"])
def list_compliance_flags():
    blocked = _gated("compliance_watchdog")
    if blocked: return blocked
    return jsonify({"flags": compliance_watchdog.get_flags(
        g.user_id, status=request.args.get("status"), severity=request.args.get("severity"))})

@app.route("/api/compliance/flags/<fid>/resolve", methods=["POST"])
def resolve_compliance_flag(fid):
    blocked = _gated("compliance_watchdog")
    if blocked: return blocked
    data = request.json or {}
    return jsonify(compliance_watchdog.resolve_flag(fid, data.get("resolution", "")))

@app.route("/api/compliance/rules", methods=["GET"])
def list_compliance_rules():
    blocked = _gated("compliance_watchdog")
    if blocked: return blocked
    return jsonify({"rules": compliance_watchdog.get_rules()})

@app.route("/api/compliance/rules", methods=["POST"])
def add_compliance_rule():
    blocked = _gated("compliance_watchdog")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("name") or not data.get("patterns"):
        return jsonify({"error": "name and patterns required"}), 400
    return jsonify(compliance_watchdog.add_rule(
        data["name"], data["patterns"], data.get("severity", "medium"),
        data.get("label", ""), owner_id=g.user_id))

@app.route("/api/compliance/rules/custom", methods=["GET"])
def list_custom_compliance_rules():
    blocked = _gated("compliance_watchdog")
    if blocked: return blocked
    return jsonify({"rules": compliance_watchdog.list_custom_rules(g.user_id)})

@app.route("/api/compliance/rules/<rule_name>", methods=["DELETE"])
def remove_custom_compliance_rule(rule_name):
    blocked = _gated("compliance_watchdog")
    if blocked: return blocked
    if compliance_watchdog.remove_custom_rule(rule_name):
        return jsonify({"success": True})
    return jsonify({"error": "Rule not found or is a built-in rule"}), 404


# ═══════════════════════════════════════════════════════════════
# ENTERPRISE — Compliance Escalation Pipeline
# ═══════════════════════════════════════════════════════════════

@app.route("/api/compliance/violations", methods=["GET"])
def list_compliance_violations():
    blocked = _gated("compliance_escalation")
    if blocked: return blocked
    status = request.args.get("status")
    tier = request.args.get("tier")
    return jsonify({"violations": compliance_escalation.get_violations(
        g.user_id, status=status, tier=int(tier) if tier else None)})

@app.route("/api/compliance/violations/<vid>/resolve", methods=["POST"])
def resolve_compliance_violation(vid):
    blocked = _gated("compliance_escalation")
    if blocked: return blocked
    data = request.json or {}
    return jsonify(compliance_escalation.resolve_violation(
        vid, data.get("resolution", ""), resolved_by=data.get("resolved_by", "")))

@app.route("/api/compliance/dashboard", methods=["GET"])
def compliance_dashboard():
    blocked = _gated("compliance_escalation")
    if blocked: return blocked
    return jsonify(compliance_escalation.get_compliance_dashboard(g.user_id))

@app.route("/api/compliance/officer", methods=["GET"])
def get_compliance_officer():
    blocked = _gated("compliance_escalation")
    if blocked: return blocked
    return jsonify(compliance_escalation.get_compliance_officer(g.user_id))

@app.route("/api/compliance/officer", methods=["POST"])
def set_compliance_officer():
    blocked = _gated("compliance_escalation")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("user_id") or not data.get("name"):
        return jsonify({"error": "user_id and name required"}), 400
    return jsonify(compliance_escalation.set_compliance_officer(
        g.user_id, data["user_id"], data["name"], data.get("email", "")))


# ═══════════════════════════════════════════════════════════════
# ENTERPRISE — Client Deliverables
# ═══════════════════════════════════════════════════════════════

@app.route("/api/deliverables/styles", methods=["GET"])
def list_deliverable_styles():
    blocked = _gated("client_deliverables")
    if blocked: return blocked
    return jsonify({"styles": deliverable_gen.get_styles()})

@app.route("/api/deliverables", methods=["GET"])
def list_deliverables():
    blocked = _gated("client_deliverables")
    if blocked: return blocked
    return jsonify({"deliverables": deliverable_gen.list_deliverables(g.user_id)})

@app.route("/api/deliverables", methods=["POST"])
def generate_deliverable():
    blocked = _gated("client_deliverables")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("conversation_id"):
        return jsonify({"error": "conversation_id required"}), 400
    result = deliverable_gen.generate(
        g.user_id, data["conversation_id"],
        style=data.get("style", "report"), client_name=data.get("client_name", ""),
        additional_instructions=data.get("instructions", ""))
    return jsonify(result), 201

@app.route("/api/deliverables/<did>", methods=["GET"])
def get_deliverable(did):
    blocked = _gated("client_deliverables")
    if blocked: return blocked
    d = deliverable_gen.get_deliverable(did)
    if not d: return jsonify({"error": "Not found"}), 404
    return jsonify(d)


# ═══════════════════════════════════════════════════════════════
# ENTERPRISE — Delegation of Authority
# ═══════════════════════════════════════════════════════════════

@app.route("/api/delegations", methods=["GET"])
def list_delegations():
    blocked = _gated("delegation_authority")
    if blocked: return blocked
    return jsonify(delegation_auth.get_active_delegations(g.user_id))

@app.route("/api/delegations", methods=["POST"])
def create_delegation():
    blocked = _gated("delegation_authority")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("delegate_id"):
        return jsonify({"error": "delegate_id required"}), 400
    result = delegation_auth.create_delegation(
        g.user_id, data["delegate_id"], scope=data.get("scope", "all"),
        expires_at=data.get("expires_at"), reason=data.get("reason", ""))
    return jsonify(result), 201

@app.route("/api/delegations/<did>/revoke", methods=["POST"])
def revoke_delegation(did):
    blocked = _gated("delegation_authority")
    if blocked: return blocked
    return jsonify(delegation_auth.revoke_delegation(did))


# ═══════════════════════════════════════════════════════════════
# ENTERPRISE — Risk Register
# ═══════════════════════════════════════════════════════════════

@app.route("/api/risks", methods=["GET"])
def list_risks():
    blocked = _gated("risk_register")
    if blocked: return blocked
    return jsonify({"risks": risk_register.list_risks(
        g.user_id, status=request.args.get("status"), category=request.args.get("category"))})

@app.route("/api/risks", methods=["POST"])
def create_risk():
    blocked = _gated("risk_register")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("title"):
        return jsonify({"error": "title required"}), 400
    result = risk_register.create_risk(
        g.user_id, data["title"], data.get("category", "general"),
        description=data.get("description", ""), severity=data.get("severity", "medium"),
        likelihood=data.get("likelihood", "medium"), mitigation=data.get("mitigation", ""),
        owner_name=data.get("owner_name", ""), source_id=data.get("source_id", ""))
    return jsonify(result), 201

@app.route("/api/risks/<rid>", methods=["PUT"])
def update_risk(rid):
    blocked = _gated("risk_register")
    if blocked: return blocked
    return jsonify(risk_register.update_risk(rid, request.json or {}))

@app.route("/api/risks/matrix", methods=["GET"])
def get_risk_matrix():
    blocked = _gated("risk_register")
    if blocked: return blocked
    return jsonify(risk_register.get_risk_matrix(g.user_id))


# ═══════════════════════════════════════════════════════════════
# ENTERPRISE — Policy Engine
# ═══════════════════════════════════════════════════════════════

@app.route("/api/policies", methods=["GET"])
def list_policies_v2():
    blocked = _gated("policy_engine")
    if blocked: return blocked
    return jsonify({"policies": policy_engine.list_policies(
        g.user_id, category=request.args.get("category"))})

@app.route("/api/policies", methods=["POST"])
def create_policy_v2():
    blocked = _gated("policy_engine")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("name") or not data.get("rule"):
        return jsonify({"error": "name and rule required"}), 400
    result = policy_engine.create_policy(
        g.user_id, data["name"], data["rule"],
        category=data.get("category", "general"),
        enforcement=data.get("enforcement", "warn"),
        applies_to=data.get("applies_to", "all"))
    return jsonify(result), 201

@app.route("/api/policies/<pid>", methods=["PUT"])
def update_policy_v2(pid):
    blocked = _gated("policy_engine")
    if blocked: return blocked
    return jsonify(policy_engine.update_policy(pid, request.json or {}))

@app.route("/api/policies/<pid>", methods=["DELETE"])
def delete_policy_v2(pid):
    blocked = _gated("policy_engine")
    if blocked: return blocked
    policy_engine.delete_policy(pid)
    return jsonify({"success": True})

@app.route("/api/policies/check", methods=["POST"])
def check_policy_compliance():
    blocked = _gated("policy_engine")
    if blocked: return blocked
    data = request.json or {}
    return jsonify(policy_engine.check_compliance(
        g.user_id, data.get("text", ""), agent_id=data.get("agent_id")))


# ═══════════════════════════════════════════════════════════════
# ENTERPRISE — Knowledge Handoff
# ═══════════════════════════════════════════════════════════════

@app.route("/api/handoff", methods=["POST"])
def generate_handoff():
    blocked = _gated("knowledge_handoff")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("user_id") or not data.get("name"):
        return jsonify({"error": "user_id and name required"}), 400
    result = knowledge_handoff.generate_handoff(
        g.user_id, data["user_id"], data["name"])
    return jsonify(result), 201


# ═══════════════════════════════════════════════════════════════
# DOCUMENT EXPORT — .docx with Company Letterhead
# ═══════════════════════════════════════════════════════════════

@app.route("/api/letterhead", methods=["GET"])
def get_letterhead():
    return jsonify(letterhead_mgr.get_letterhead(g.user_id))

@app.route("/api/letterhead", methods=["POST"])
def save_letterhead():
    data = request.json or {}
    return jsonify(letterhead_mgr.save_letterhead(g.user_id, data))

@app.route("/api/export/minutes/<mid>", methods=["GET"])
def export_minutes_docx(mid):
    """Export meeting minutes as .docx with letterhead."""
    blocked = _gated("doc_export")
    if blocked: return blocked
    m = minutes_gen.get_minutes(mid)
    if not m: return jsonify({"error": "Minutes not found"}), 404
    lh = LetterheadConfig().load_from_db(g.user_id)
    filepath = doc_exporter.export_minutes(m, lh)
    return send_file(filepath, as_attachment=True,
                     download_name=os.path.basename(filepath))

@app.route("/api/export/roundtable/<rid>", methods=["GET"])
def export_roundtable_docx(rid):
    """Export Roundtable transcript as .docx with letterhead."""
    blocked = _gated("doc_export")
    if blocked: return blocked
    rt_data = roundtable.get(rid)
    if not rt_data: return jsonify({"error": "Roundtable not found"}), 404
    lh = LetterheadConfig().load_from_db(g.user_id)
    filepath = doc_exporter.export_roundtable(rt_data, lh)
    return send_file(filepath, as_attachment=True,
                     download_name=os.path.basename(filepath))

@app.route("/api/export/record/<rid>", methods=["GET"])
def export_record_docx(rid):
    """Export corporate record as .docx with letterhead."""
    blocked = _gated("doc_export")
    if blocked: return blocked
    r = record_keeper.get_record(rid)
    if not r: return jsonify({"error": "Record not found"}), 404
    lh = LetterheadConfig().load_from_db(g.user_id)
    filepath = doc_exporter.export_record(r, lh)
    return send_file(filepath, as_attachment=True,
                     download_name=os.path.basename(filepath))

@app.route("/api/export/resolution/<rid>", methods=["GET"])
def export_resolution_docx(rid):
    """Export resolution with vote record as .docx with letterhead."""
    blocked = _gated("doc_export")
    if blocked: return blocked
    r = resolution_tracker.get_resolution(rid)
    if not r: return jsonify({"error": "Resolution not found"}), 404
    lh = LetterheadConfig().load_from_db(g.user_id)
    filepath = doc_exporter.export_resolution(r, lh)
    return send_file(filepath, as_attachment=True,
                     download_name=os.path.basename(filepath))

@app.route("/api/export/summary", methods=["POST"])
def export_summary_docx():
    """Export any summary or content as .docx with letterhead."""
    blocked = _gated("doc_export")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("content"):
        return jsonify({"error": "content required"}), 400
    lh = LetterheadConfig()
    if data.get("letterhead"):
        lh.load_from_dict(data["letterhead"])
    else:
        lh.load_from_db(g.user_id)
    filepath = doc_exporter.export_summary(
        data.get("title", "Summary"), data["content"],
        data.get("metadata", {}), lh)
    return send_file(filepath, as_attachment=True,
                     download_name=os.path.basename(filepath))


# ═══════════════════════════════════════════════════════════════
# GOVERNANCE — Meeting Minutes
# ═══════════════════════════════════════════════════════════════

@app.route("/api/minutes", methods=["GET"])
def list_meeting_minutes():
    blocked = _gated("meeting_minutes")
    if blocked: return blocked
    status = request.args.get("status")
    return jsonify({"minutes": minutes_gen.list_minutes(g.user_id, status=status)})

@app.route("/api/minutes/from-roundtable/<rid>", methods=["POST"])
def generate_minutes_from_roundtable(rid):
    """Auto-generate meeting minutes from a Roundtable discussion."""
    blocked = _gated("meeting_minutes")
    if blocked: return blocked
    rt = roundtable.get(rid)
    if not rt: return jsonify({"error": "Roundtable not found"}), 404
    result = minutes_gen.generate_from_roundtable(rt, g.user_id)
    return jsonify(result), 201

@app.route("/api/minutes/from-conversation/<conv_id>", methods=["POST"])
def generate_minutes_from_conversation(conv_id):
    """Auto-generate meeting notes from any conversation."""
    blocked = _gated("meeting_minutes")
    if blocked: return blocked
    result = minutes_gen.generate_from_conversation(conv_id, g.user_id)
    return jsonify(result), 201

@app.route("/api/minutes/<mid>", methods=["GET"])
def get_meeting_minutes(mid):
    blocked = _gated("meeting_minutes")
    if blocked: return blocked
    m = minutes_gen.get_minutes(mid)
    if not m: return jsonify({"error": "Not found"}), 404
    return jsonify(m)

@app.route("/api/minutes/<mid>/approve", methods=["POST"])
def approve_meeting_minutes(mid):
    blocked = _gated("meeting_minutes")
    if blocked: return blocked
    return jsonify(minutes_gen.approve_minutes(mid))

@app.route("/api/minutes/<mid>", methods=["DELETE"])
def delete_meeting_minutes(mid):
    blocked = _gated("meeting_minutes")
    if blocked: return blocked
    if not minutes_gen.delete_minutes(mid):
        return jsonify({"error": "Cannot delete approved minutes"}), 403
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════
# GOVERNANCE — Corporate Records
# ═══════════════════════════════════════════════════════════════

@app.route("/api/records", methods=["GET"])
def list_corporate_records():
    blocked = _gated("corporate_records")
    if blocked: return blocked
    record_type = request.args.get("type")
    tag = request.args.get("tag")
    query = request.args.get("q")
    return jsonify({"records": record_keeper.search_records(
        g.user_id, query=query, record_type=record_type, tag=tag)})

@app.route("/api/records", methods=["POST"])
def create_corporate_record():
    blocked = _gated("corporate_records")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("title"):
        return jsonify({"error": "title required"}), 400
    result = record_keeper.create_record(
        g.user_id, data.get("record_type", "general"),
        data["title"], data.get("content", ""),
        tags=data.get("tags", []),
        retention_days=data.get("retention_days", 0),
        attachments=data.get("attachments", []),
        related_ids=data.get("related_ids", []))
    return jsonify(result), 201

@app.route("/api/records/types", methods=["GET"])
def get_record_types():
    blocked = _gated("corporate_records")
    if blocked: return blocked
    return jsonify({"types": record_keeper.get_record_types()})

@app.route("/api/records/expiring", methods=["GET"])
def get_expiring_records():
    blocked = _gated("corporate_records")
    if blocked: return blocked
    days = int(request.args.get("days", 30))
    return jsonify({"records": record_keeper.get_expiring_records(g.user_id, days)})

@app.route("/api/records/<rid>", methods=["GET"])
def get_corporate_record(rid):
    blocked = _gated("corporate_records")
    if blocked: return blocked
    r = record_keeper.get_record(rid)
    if not r: return jsonify({"error": "Not found"}), 404
    return jsonify(r)

@app.route("/api/records/<rid>", methods=["PUT"])
def update_corporate_record(rid):
    blocked = _gated("corporate_records")
    if blocked: return blocked
    return jsonify(record_keeper.update_record(rid, request.json or {}))

@app.route("/api/records/<rid>", methods=["DELETE"])
def delete_corporate_record(rid):
    blocked = _gated("corporate_records")
    if blocked: return blocked
    record_keeper.delete_record(rid)
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════
# GOVERNANCE — Resolutions and Votes
# ═══════════════════════════════════════════════════════════════

@app.route("/api/resolutions", methods=["GET"])
def list_resolutions():
    blocked = _gated("resolutions")
    if blocked: return blocked
    status = request.args.get("status")
    return jsonify({"resolutions": resolution_tracker.list_resolutions(g.user_id, status=status)})

@app.route("/api/resolutions", methods=["POST"])
def create_resolution():
    blocked = _gated("resolutions")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("title"):
        return jsonify({"error": "title required"}), 400
    result = resolution_tracker.create_resolution(
        g.user_id, data["title"], data.get("description", ""),
        required_approvers=data.get("required_approvers", []),
        threshold=data.get("threshold", "majority"))
    return jsonify(result), 201

@app.route("/api/resolutions/<rid>", methods=["GET"])
def get_resolution(rid):
    blocked = _gated("resolutions")
    if blocked: return blocked
    r = resolution_tracker.get_resolution(rid)
    if not r: return jsonify({"error": "Not found"}), 404
    return jsonify(r)

@app.route("/api/resolutions/<rid>/vote", methods=["POST"])
def vote_on_resolution(rid):
    blocked = _gated("resolutions")
    if blocked: return blocked
    data = request.json or {}
    if not data.get("voter_name") or not data.get("vote"):
        return jsonify({"error": "voter_name and vote required"}), 400
    try:
        result = resolution_tracker.cast_vote(
            rid, data["voter_name"], data["vote"], data.get("comment", ""))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ═══════════════════════════════════════════════════════════════
# GOVERNANCE — Summarization Engine
# ═══════════════════════════════════════════════════════════════

@app.route("/api/summarize/conversations", methods=["POST"])
def summarize_conversations():
    blocked = _gated("summarization")
    if blocked: return blocked
    data = request.json or {}
    result = summarizer.summarize_conversations(
        g.user_id, agent_id=data.get("agent_id"),
        days=data.get("days", 7), style=data.get("style", "executive"))
    return jsonify(result)

@app.route("/api/summarize/digest", methods=["GET"])
def get_governance_digest():
    blocked = _gated("summarization")
    if blocked: return blocked
    return jsonify(summarizer.generate_digest(g.user_id))


# ═══════════════════════════════════════════════════════════════
# VOICE CHAT — Interactive Voice Conversations
# ═══════════════════════════════════════════════════════════════

@app.route("/api/voice/providers", methods=["GET"])
def api_voice_providers():
    """List available TTS providers with configuration status."""
    return jsonify({"providers": voice_settings.get_available_providers()})

@app.route("/api/voice/settings", methods=["GET"])
def api_voice_settings_get():
    return jsonify(voice_settings.get_settings(g.user_id))

@app.route("/api/voice/settings", methods=["PUT"])
def api_voice_settings_update():
    data = request.json or {}
    return jsonify(voice_settings.update_settings(g.user_id, data))

@app.route("/api/voice/synthesize", methods=["POST"])
def api_voice_synthesize():
    """Convert text to speech audio. Returns base64 audio or browser fallback."""
    data = request.json or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "text required"}), 400

    settings = voice_settings.get_settings(g.user_id)
    provider = data.get("provider") or settings.get("tts_provider", "browser")
    voice = data.get("voice") or settings.get("tts_voice")
    model = data.get("model") or settings.get("tts_model")
    speed = data.get("speed") or settings.get("tts_speed", 1.0)

    result = tts.synthesize(text, provider=provider, voice=voice, model=model, speed=speed)
    return jsonify(result)

@app.route("/api/voice/synthesize/agent/<agent_id>", methods=["POST"])
def api_voice_synthesize_agent(agent_id):
    """Synthesize using agent's configured voice."""
    data = request.json or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "text required"}), 400

    # Get agent's voice config
    with get_db() as db:
        agent = db.execute(
            "SELECT voice_provider, voice_id, voice_model, voice_speed FROM agents WHERE id=?",
            (agent_id,)).fetchone()

    if agent and agent["voice_provider"]:
        provider = agent["voice_provider"]
        voice = agent["voice_id"]
        model = agent["voice_model"]
        speed = agent["voice_speed"] or 1.0
    else:
        # Fall back to user settings
        settings = voice_settings.get_settings(g.user_id)
        provider = settings.get("tts_provider", "browser")
        voice = settings.get("tts_voice")
        model = settings.get("tts_model")
        speed = settings.get("tts_speed", 1.0)

    result = tts.synthesize(text, provider=provider, voice=voice, model=model, speed=speed)
    return jsonify(result)

@app.route("/api/voice/session/start", methods=["POST"])
def api_voice_session_start():
    data = request.json or {}
    user_name = getattr(g, 'user_name', '') or ''
    session_id = voice_sessions.start_session(
        g.user_id, agent_id=data.get("agent_id"),
        tts_provider=data.get("tts_provider", "browser"),
        user_name=user_name)
    # Get agent name for greeting
    agent_name = ""
    if data.get("agent_id"):
        agent = agents.get_agent(data["agent_id"])
        if agent:
            agent_name = agent.get("name", "")
    greeting = voice_sessions.get_greeting(session_id, agent_name=agent_name)
    return jsonify({"session_id": session_id, "greeting": greeting})

@app.route("/api/voice/session/<session_id>/end", methods=["POST"])
def api_voice_session_end(session_id):
    result = voice_sessions.end_session(session_id)
    return jsonify({"session": result or {}})

@app.route("/api/voice/session/<session_id>/exchange", methods=["POST"])
def api_voice_session_exchange(session_id):
    data = request.json or {}
    voice_sessions.record_exchange(session_id, data.get("stt_text", ""), data.get("tts_text", ""))
    return jsonify({"recorded": True})

@app.route("/api/voice/sessions/active", methods=["GET"])
def api_voice_sessions_active():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify({"sessions": voice_sessions.get_active()})

@app.route("/api/agents/<agent_id>/voice", methods=["GET"])
def api_agent_voice_get(agent_id):
    """Get agent's voice configuration."""
    with get_db() as db:
        agent = db.execute(
            "SELECT id, name, voice_provider, voice_id, voice_model, voice_speed FROM agents WHERE id=?",
            (agent_id,)).fetchone()
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    return jsonify({
        "agent_id": agent["id"],
        "agent_name": agent["name"],
        "voice_provider": agent["voice_provider"] or "browser",
        "voice_id": agent["voice_id"] or "default",
        "voice_model": agent["voice_model"] or "",
        "voice_speed": agent["voice_speed"] or 1.0,
    })

@app.route("/api/agents/<agent_id>/voice", methods=["PUT"])
def api_agent_voice_set(agent_id):
    """Set agent's voice configuration."""
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    with get_db() as db:
        db.execute(
            "UPDATE agents SET voice_provider=?, voice_id=?, voice_model=?, voice_speed=?,"
            " updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (data.get("voice_provider", ""), data.get("voice_id", ""),
             data.get("voice_model", ""), data.get("voice_speed", 1.0), agent_id))
    return jsonify({"updated": True, "agent_id": agent_id})

@app.route("/voice-chat")
def voice_chat_page():
    """Serve the voice chat UI."""
    return send_from_directory("templates", "voice-chat.html")


# ═══════════════════════════════════════════════════════════════
# CONVERSATION EXPORT — CSV, JSON, Markdown
# ═══════════════════════════════════════════════════════════════

@app.route("/api/conversations/<conv_id>/export/<fmt>", methods=["GET"])
def api_conversation_export(conv_id, fmt):
    """Export a conversation. Format: csv, json, or markdown."""
    if fmt == "csv":
        result = conv_exporter.export_csv(conv_id, g.user_id)
    elif fmt == "markdown":
        result = conv_exporter.export_markdown(conv_id, g.user_id)
    else:
        result = conv_exporter.export_json(conv_id, g.user_id)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)

@app.route("/api/conversations/export-all", methods=["GET"])
def api_conversations_export_all():
    """Export all conversations for current user (GDPR data export)."""
    fmt = request.args.get("format", "json")
    limit = int(request.args.get("limit", 100))
    return jsonify(conv_exporter.bulk_export(g.user_id, format=fmt, limit=limit))


# ═══════════════════════════════════════════════════════════════
# PROMPT TEMPLATE LIBRARY — Create, share, use reusable prompts
# ═══════════════════════════════════════════════════════════════

@app.route("/api/templates", methods=["GET"])
def api_templates_list():
    category = request.args.get("category")
    search = request.args.get("search")
    return jsonify({"templates": prompt_templates.list_templates(g.user_id, category, search)})

@app.route("/api/templates", methods=["POST"])
def api_templates_create():
    data = request.json or {}
    return jsonify(prompt_templates.create_template(g.user_id, data))

@app.route("/api/templates/<tid>", methods=["GET"])
def api_template_get(tid):
    t = prompt_templates.get_template(tid)
    if not t:
        return jsonify({"error": "Not found"}), 404
    return jsonify(t)

@app.route("/api/templates/<tid>", methods=["PUT"])
def api_template_update(tid):
    return jsonify(prompt_templates.update_template(tid, g.user_id, request.json or {}))

@app.route("/api/templates/<tid>", methods=["DELETE"])
def api_template_delete(tid):
    return jsonify(prompt_templates.delete_template(tid, g.user_id))

@app.route("/api/templates/<tid>/use", methods=["POST"])
def api_template_use(tid):
    data = request.json or {}
    return jsonify(prompt_templates.use_template(tid, g.user_id, data.get("variables", {})))

@app.route("/api/templates/categories", methods=["GET"])
def api_template_categories():
    return jsonify({"categories": prompt_templates.get_categories()})

@app.route("/api/templates/popular", methods=["GET"])
def api_templates_popular():
    return jsonify({"templates": prompt_templates.get_popular()})


# ═══════════════════════════════════════════════════════════════
# USAGE QUOTAS — Per-user, per-department, org-wide limits
# ═══════════════════════════════════════════════════════════════

@app.route("/api/quotas", methods=["GET"])
def api_quotas_get():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify(usage_quotas.get_quotas())

@app.route("/api/quotas", methods=["PUT"])
def api_quotas_update():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify(usage_quotas.update_quotas(request.json or {}))

@app.route("/api/quotas/user/<user_id>", methods=["PUT"])
def api_quota_set_user(user_id):
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    return jsonify(usage_quotas.set_user_quota(
        user_id, data.get("monthly_tokens"), data.get("monthly_cost")))

@app.route("/api/quotas/department/<dept_id>", methods=["PUT"])
def api_quota_set_dept(dept_id):
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    return jsonify(usage_quotas.set_department_quota(
        dept_id, data.get("monthly_tokens"), data.get("monthly_cost")))

@app.route("/api/quotas/check", methods=["GET"])
def api_quota_check():
    """Check current user's quota status."""
    return jsonify(usage_quotas.check_quota(g.user_id))

@app.route("/api/quotas/usage", methods=["GET"])
def api_quota_usage():
    """Get usage report for user, department, or org."""
    scope = request.args.get("scope", "user")
    scope_id = request.args.get("scope_id") or g.user_id
    return jsonify(usage_quotas.get_usage_report(scope, scope_id))


# ═══════════════════════════════════════════════════════════════
# CUSTOM BRANDING — Org name, colors, logo, white-label
# ═══════════════════════════════════════════════════════════════

@app.route("/api/branding", methods=["GET"])
def api_branding_get():
    return jsonify(branding_mgr.get_branding())

@app.route("/api/branding", methods=["PUT"])
def api_branding_update():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify(branding_mgr.update_branding(request.json or {}))

@app.route("/api/branding/css", methods=["GET"])
def api_branding_css():
    """Get CSS variables for current branding."""
    css = branding_mgr.generate_css_variables()
    return app.response_class(css, mimetype="text/css")

@app.route("/api/branding/logo", methods=["POST"])
def api_branding_logo_upload():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    if data.get("logo_base64"):
        return jsonify(branding_mgr.save_logo(data["logo_base64"]))
    return jsonify({"error": "No logo data provided"}), 400

@app.route("/api/branding/reset", methods=["POST"])
def api_branding_reset():
    if g.user.get("role") != "owner":
        return jsonify({"error": "Owner only"}), 403
    return jsonify(branding_mgr.reset_branding())


# ═══════════════════════════════════════════════════════════════
# SECURITY HARDENING — MFA, Password Policy, Sessions, DLP, Encryption
# ═══════════════════════════════════════════════════════════════

# ── Password Policy ──

@app.route("/api/security/password-policy", methods=["GET"])
def api_password_policy_get():
    return jsonify(password_policy.get_policy())

@app.route("/api/security/password-policy", methods=["PUT"])
def api_password_policy_update():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify(password_policy.update_policy(request.json or {}))

@app.route("/api/security/validate-password", methods=["POST"])
def api_validate_password():
    data = request.json or {}
    pw = data.get("password", "")
    result = password_policy.validate_password(pw, user_id=data.get("user_id"))
    if data.get("check_breached"):
        result["breach_check"] = password_policy.check_breached(pw)
    return jsonify(result)

@app.route("/api/security/password-expiry", methods=["GET"])
def api_password_expiry():
    return jsonify(password_policy.check_password_expiry(g.user_id))

@app.route("/api/security/lockout/<user_id>", methods=["GET"])
def api_check_lockout(user_id):
    if g.user.get("role") not in ("owner", "admin") and g.user_id != user_id:
        return jsonify({"error": "Not authorized"}), 403
    return jsonify(password_policy.check_lockout(user_id))

@app.route("/api/security/lockout/<user_id>/clear", methods=["POST"])
def api_clear_lockout(user_id):
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    password_policy.clear_failed_attempts(user_id)
    return jsonify({"cleared": True, "user_id": user_id})

# ── MFA / TOTP ──

@app.route("/api/security/mfa/setup", methods=["POST"])
def api_mfa_setup():
    """Generate TOTP secret + QR code for authenticator app."""
    result = mfa_mgr.setup_totp(g.user_id)
    return jsonify(result)

@app.route("/api/security/mfa/verify-setup", methods=["POST"])
def api_mfa_verify_setup():
    """Verify first TOTP code to activate MFA."""
    data = request.json or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "Code required"}), 400
    return jsonify(mfa_mgr.verify_setup(g.user_id, code))

@app.route("/api/security/mfa/verify", methods=["POST"])
def api_mfa_verify():
    """Verify TOTP code during login flow."""
    data = request.json or {}
    user_id = data.get("user_id") or g.user_id
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "Code required"}), 400
    return jsonify(mfa_mgr.verify_code(user_id, code))

@app.route("/api/security/mfa/status", methods=["GET"])
def api_mfa_status():
    return jsonify(mfa_mgr.get_status(g.user_id))

@app.route("/api/security/mfa/disable", methods=["POST"])
def api_mfa_disable():
    data = request.json or {}
    target = data.get("user_id", g.user_id)
    if target != g.user_id and g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify(mfa_mgr.disable(target, admin_id=g.user_id))

@app.route("/api/security/mfa/enforcement", methods=["GET"])
def get_mfa_enforcement():
    """Get MFA enforcement policy."""
    return jsonify(mfa_enforcement.get_policy())

@app.route("/api/security/mfa/enforcement", methods=["POST"])
def set_mfa_enforcement():
    """Set MFA enforcement level (admin only)."""
    data = request.json or {}
    if not data.get("level"): return jsonify({"error": "level required"}), 400
    return jsonify(mfa_enforcement.set_policy(data["level"], admin_id=g.user_id))

@app.route("/api/security/mfa/check-enforcement", methods=["GET"])
def check_mfa_enforcement():
    """Check if current user is MFA compliant."""
    user = users.get_user(g.user_id)
    enabled = mfa_mgr.is_enabled(g.user_id)
    return jsonify(mfa_enforcement.check_enforcement(
        g.user_id, user.get("role", "member"), enabled))

@app.route("/api/security/mfa/trust-device", methods=["POST"])
def trust_device():
    """Trust this device for 30 days — skip MFA on future logins."""
    ip = request.remote_addr or ""
    ua = request.headers.get("User-Agent", "")
    token = trusted_devices.create_device_token(g.user_id, ip, ua)
    trusted_devices.store_trust(g.user_id, token)
    return jsonify({"trusted": True, "token": token, "expires_days": 30})

@app.route("/api/security/mfa/revoke-devices", methods=["POST"])
def revoke_trusted_devices():
    """Revoke all trusted devices — force MFA everywhere."""
    trusted_devices.revoke_all(g.user_id)
    return jsonify({"revoked": True, "message": "All trusted devices revoked. MFA required on next login."})

@app.route("/api/security/mfa/verify-sensitive", methods=["POST"])
def verify_sensitive_op():
    """Verify MFA for sensitive operations (password change, GDPR erase, etc)."""
    data = request.json or {}
    code = data.get("code", "")
    if not code: return jsonify({"error": "MFA code required"}), 400
    result = mfa_mgr.verify_code(g.user_id, code)
    if result.get("verified"):
        sensitive_ops.record_verification(g.user_id)
        return jsonify({"verified": True, "window_seconds": sensitive_ops.WINDOW_SECONDS})
    return jsonify(result), 401

@app.route("/api/security/mfa/recover", methods=["POST"])
def initiate_mfa_recovery():
    """Start MFA recovery process (lost phone + backup codes)."""
    data = request.json or {}
    if not data.get("email"): return jsonify({"error": "email required"}), 400
    return jsonify(mfa_recovery.initiate_recovery(data["email"]))

@app.route("/api/security/mfa/recover/complete", methods=["POST"])
def complete_mfa_recovery():
    """Complete MFA recovery with the recovery token."""
    data = request.json or {}
    if not data.get("recovery_token"): return jsonify({"error": "recovery_token required"}), 400
    return jsonify(mfa_recovery.complete_recovery(data["recovery_token"]))

# ── Session Management ──

@app.route("/api/security/sessions", methods=["GET"])
def api_sessions_list():
    return jsonify({"sessions": session_mgr.list_sessions(g.user_id)})

@app.route("/api/security/sessions/<session_id>/end", methods=["POST"])
def api_session_end(session_id):
    session_mgr.end_session(session_id)
    return jsonify({"ended": True})

@app.route("/api/security/sessions/end-all", methods=["POST"])
def api_sessions_end_all():
    """Kill all sessions except current (password change, security event)."""
    data = request.json or {}
    session_mgr.end_all_sessions(g.user_id, except_session=data.get("current_session"))
    return jsonify({"ended_all": True})

@app.route("/api/security/session-policy", methods=["GET"])
def api_session_policy_get():
    return jsonify(session_mgr.policy)

@app.route("/api/security/session-policy", methods=["PUT"])
def api_session_policy_update():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    for k, v in data.items():
        if k in session_mgr.policy:
            session_mgr.policy[k] = v
    return jsonify(session_mgr.policy)

# ── DLP — Data Loss Prevention ──

@app.route("/api/security/dlp/scan", methods=["POST"])
def api_dlp_scan():
    """Scan text for sensitive data (PII, credentials, etc.)."""
    data = request.json or {}
    text = data.get("text", "")
    context = data.get("context", "input")
    result = dlp.scan(text, context=context)
    if not result["clean"]:
        dlp.log_detection(g.user_id, text, result, context)
    return jsonify(result)

@app.route("/api/security/dlp/redact", methods=["POST"])
def api_dlp_redact():
    """Redact sensitive data from text."""
    data = request.json or {}
    text = data.get("text", "")
    return jsonify({"redacted": dlp.redact_text(text)})

@app.route("/api/security/dlp/policy", methods=["GET"])
def api_dlp_policy_get():
    return jsonify(dlp.get_policy())

@app.route("/api/security/dlp/policy", methods=["PUT"])
def api_dlp_policy_update():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify(dlp.update_policy(request.json or {}))

# ── Encryption Key Management ──

@app.route("/api/security/encryption/status", methods=["GET"])
def api_encryption_status():
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    enc = get_encryptor()
    test = enc.encrypt("test_probe")
    return jsonify({
        "active": True,
        "encrypted_fields": ["api_keys", "oauth_secrets", "oauth_tokens", "mfa_secrets"],
        "test": enc.decrypt(test) == "test_probe",
    })

@app.route("/api/security/encryption/rotate", methods=["POST"])
def api_encryption_rotate():
    """Rotate encryption key and re-encrypt all sensitive fields."""
    if g.user.get("role") != "owner":
        return jsonify({"error": "Owner only"}), 403
    enc = get_encryptor()
    result = enc.rotate_key()
    return jsonify(result)

# ── Security Dashboard ──

@app.route("/api/security/dashboard", methods=["GET"])
def api_security_dashboard():
    """Overview of all security settings and health."""
    if g.user.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403

    with get_db() as db:
        total_users = db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        mfa_enabled = db.execute("SELECT COUNT(*) as c FROM mfa_config WHERE is_enabled=1 AND is_verified=1").fetchone()["c"]
        locked_accounts = db.execute("SELECT COUNT(*) as c FROM account_lockout WHERE locked_until > datetime('now')").fetchone()["c"]
        active_sessions_count = db.execute("SELECT COUNT(*) as c FROM active_sessions WHERE is_active=1").fetchone()["c"]
        recent_dlp = db.execute("SELECT COUNT(*) as c FROM audit_log WHERE action='dlp_detection' AND timestamp > datetime('now', '-24 hours')").fetchone()["c"]

    enc = get_encryptor()
    return jsonify({
        "encryption": {"active": True, "test": enc.decrypt(enc.encrypt("ok")) == "ok"},
        "password_policy": password_policy.get_policy(),
        "session_policy": session_mgr.policy,
        "dlp_policy": dlp.get_policy(),
        "mfa": {"total_users": total_users, "mfa_enabled": mfa_enabled,
                "coverage_pct": round((mfa_enabled / max(total_users, 1)) * 100, 1)},
        "accounts": {"locked": locked_accounts},
        "sessions": {"active": active_sessions_count},
        "dlp_detections_24h": recent_dlp,
    })


# ═══════════════════════════════════════════════════════════════
# LOGO & BRANDING ASSETS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/branding/logo-asset", methods=["GET"])
def api_branding_logo_asset():
    """Serve the platform logo."""
    logo_path = os.path.join(os.path.dirname(__file__), "static", "logo.png")
    if os.path.exists(logo_path):
        return send_file(logo_path, mimetype="image/png")
    return jsonify({"error": "No logo configured"}), 404


# ═══════════════════════════════════════════════════════════════
# PROVIDER AUTH — API Key & OAuth Configuration
# ═══════════════════════════════════════════════════════════════

@app.route("/api/providers", methods=["GET"])
def api_providers_list():
    return jsonify({"providers": provider_auth.list_providers()})

@app.route("/api/providers/templates", methods=["GET"])
def api_providers_templates():
    return jsonify({"templates": provider_auth.get_templates()})

@app.route("/api/providers/<provider>", methods=["GET"])
def api_providers_get(provider):
    conf = provider_auth.get_provider(provider)
    if not conf:
        return jsonify({"error": "Provider not found"}), 404
    return jsonify(conf)

@app.route("/api/providers/<provider>/api-key", methods=["POST"])
def api_providers_set_key(provider):
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    if not data.get("api_key"):
        return jsonify({"error": "api_key required"}), 400
    result = provider_auth.set_api_key(
        provider, data["api_key"],
        configured_by=g.user_id,
        base_url=data.get("base_url"),
        default_model=data.get("default_model"))
    if "error" in result:
        return jsonify(result), 400
    # Reload provider registry to pick up new key
    providers.reload()
    return jsonify(result)

@app.route("/api/providers/<provider>/api-key/validate", methods=["POST"])
def api_providers_validate_key(provider):
    data = request.json or {}
    return jsonify(provider_auth.validate_api_key(provider, data.get("api_key", "")))

@app.route("/api/providers/<provider>/oauth", methods=["POST"])
def api_providers_set_oauth(provider):
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    if not data.get("client_id") or not data.get("client_secret"):
        return jsonify({"error": "client_id and client_secret required"}), 400
    result = provider_auth.set_oauth_credentials(
        provider, data["client_id"], data["client_secret"],
        configured_by=g.user_id, tenant=data.get("tenant"))
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)

@app.route("/api/providers/<provider>/oauth/authorize", methods=["POST"])
def api_providers_oauth_authorize(provider):
    data = request.json or {}
    redirect_uri = data.get("redirect_uri", request.url_root.rstrip("/") + "/api/providers/oauth/callback")
    result = provider_auth.get_oauth_authorize_url(provider, redirect_uri)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)

@app.route("/api/providers/oauth/callback", methods=["GET", "POST"])
def api_providers_oauth_callback():
    code = request.args.get("code") or (request.json or {}).get("code")
    state = request.args.get("state") or (request.json or {}).get("state")
    if not code or not state:
        return jsonify({"error": "Missing code or state"}), 400
    result = provider_auth.exchange_oauth_code(code, state)
    if "error" in result:
        return jsonify(result), 400
    # Reload providers with new token
    providers.reload()
    return jsonify(result)

@app.route("/api/providers/<provider>/oauth/refresh", methods=["POST"])
def api_providers_oauth_refresh(provider):
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    result = provider_auth.refresh_oauth_token(provider)
    if "error" in result:
        return jsonify(result), 400
    providers.reload()
    return jsonify(result)

@app.route("/api/providers/<provider>/toggle", methods=["POST"])
def api_providers_toggle(provider):
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    return jsonify(provider_auth.toggle_provider(provider, data.get("enabled", True)))

@app.route("/api/providers/<provider>/models", methods=["PUT"])
def api_providers_set_models(provider):
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    return jsonify(provider_auth.set_custom_models(provider, data.get("models", [])))

@app.route("/api/providers/<provider>", methods=["DELETE"])
def api_providers_delete(provider):
    u = g.user
    if u.get("role") not in ("owner", "admin"):
        return jsonify({"error": "Admin only"}), 403
    return jsonify(provider_auth.delete_provider_config(provider))


# ═══════════════════════════════════════════════════════════════
# BOOT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    host = os.getenv("BIND_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    logger.info(f"MyTeam360 starting on {host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)


# ═══════════════════════════════════════════════════════════════
# SSO / SAML
# ═══════════════════════════════════════════════════════════════

@app.errorhandler(404)
def page_not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Endpoint not found"}), 404
    return send_from_directory("templates", "site.html")  # SPA fallback

@app.errorhandler(500)
def internal_error(e):
    safe_msg = error_sanitizer.sanitize(e) if hasattr(e, '__class__') else "An error occurred"
    if request.path.startswith("/api/"):
        return jsonify({"error": safe_msg}), 500
    return f"<h1>Something went wrong</h1><p>{safe_msg}</p>", 500


# ── TOS Acceptance ──

@app.route("/api/tos/check", methods=["GET"])
def tos_check():
    return jsonify(tos_tracker.check(g.user_id))

@app.route("/api/tos/accept", methods=["POST"])
def tos_accept():
    return jsonify(tos_tracker.accept(
        g.user_id, ip=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", "")))


# ── Rate Limit Check ──

@app.route("/api/rate-limit/check", methods=["GET"])
def rate_limit_check():
    """Check current rate limit status for the user."""
    user = users.get_user(g.user_id)
    plan = user.get("plan", "starter") if user else "starter"
    return jsonify(plan_limiter.check(g.user_id, plan))

@app.route("/api/rate-limit/limits", methods=["GET"])
def rate_limit_info():
    """Show rate limits for all plans."""
    return jsonify({"plans": plan_limiter.PLAN_LIMITS})


# ── Abuse Reporting ──

@app.route("/api/safety/report", methods=["POST"])
def report_abuse():
    """User reports harmful content or platform misuse."""
    data = request.json or {}
    if not data.get("type"):
        return jsonify({"error": "type required", "options": abuse_reporter.REPORT_TYPES}), 400
    return jsonify(abuse_reporter.submit_report(
        g.user_id, data["type"],
        message_id=data.get("message_id", ""),
        conversation_id=data.get("conversation_id", ""),
        description=data.get("description", "")))

@app.route("/api/safety/reports", methods=["GET"])
def list_abuse_reports():
    """Admin: list all abuse reports."""
    return jsonify({"reports": abuse_reporter.get_reports(
        status=request.args.get("status"))})

@app.route("/api/safety/reports/<rid>/resolve", methods=["POST"])
def resolve_abuse_report(rid):
    """Admin resolves an abuse report."""
    data = request.json or {}
    return jsonify(abuse_reporter.resolve_report(
        rid, g.user_id, action=data.get("action", "reviewed"),
        notes=data.get("notes", "")))

@app.route("/api/safety/violations", methods=["GET"])
def list_safety_violations():
    """Admin: see all safety violations."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM safety_violations ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    return jsonify({"violations": [dict(r) for r in rows]})


# ── Three-Strikes Enforcement ──

@app.route("/api/safety/strikes/<user_id>", methods=["GET"])
def get_user_strikes(user_id):
    """Admin: get a user's strike history."""
    return jsonify(three_strikes.get_user_strikes(user_id))

@app.route("/api/safety/strikes/<user_id>/reset", methods=["POST"])
def reset_user_strikes(user_id):
    """Admin: reset a user's strikes (second chance)."""
    data = request.json or {}
    return jsonify(three_strikes.reset_strikes(
        user_id, g.user_id, reason=data.get("reason", "")))

@app.route("/api/safety/strikes/my", methods=["GET"])
def get_my_strikes():
    """User: see your own strike status."""
    return jsonify(three_strikes.get_user_strikes(g.user_id))


# ── Mandatory Violation Acknowledgment ──

@app.route("/api/safety/pending", methods=["GET"])
def get_pending_acknowledgment():
    """Check if user has a pending violation acknowledgment."""
    pending = violation_ack.get_pending(g.user_id)
    if not pending:
        return jsonify({"acknowledgment_required": False})
    return jsonify({
        "acknowledgment_required": True,
        "acknowledgment_id": pending["id"],
        "acknowledgment_text": pending["acknowledgment_text"],
        "violation_label": pending["violation_label"],
        "tos_section": pending["tos_section"],
        "strike_number": pending["strike_number"],
        "query_excerpt": pending["query_excerpt"],
        "violation_timestamp": pending["violation_timestamp"],
    })

@app.route("/api/safety/acknowledge", methods=["POST"])
def acknowledge_violation():
    """User acknowledges a safety violation — creates legal record."""
    data = request.json or {}
    ack_id = data.get("acknowledgment_id", "")
    if not ack_id:
        return jsonify({"error": "acknowledgment_id required"}), 400
    return jsonify(violation_ack.acknowledge(
        g.user_id, ack_id,
        ip=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", ""),
        session_id=session.get("session_id", "")))

@app.route("/api/safety/acknowledgments", methods=["GET"])
def get_acknowledgment_history():
    """Admin: get user's full acknowledgment record."""
    user_id = request.args.get("user_id", g.user_id)
    return jsonify({"acknowledgments": violation_ack.get_history(user_id)})


# ═══════════════════════════════════════════════════════════════
# SSO / SAML
# ═══════════════════════════════════════════════════════════════

@app.route("/api/sso/providers", methods=["GET"])
def sso_providers():
    return jsonify({"providers": sso_mgr.get_providers()})

@app.route("/api/sso/config", methods=["GET"])
def sso_config_get():
    return jsonify(sso_mgr.get_config())

@app.route("/api/sso/configure", methods=["POST"])
def sso_configure():
    data = request.json or {}
    if not data.get("provider"): return jsonify({"error": "provider required"}), 400
    return jsonify(sso_mgr.configure(data["provider"], data.get("config", {})))

@app.route("/api/auth/sso/login", methods=["GET"])
def sso_login():
    return jsonify(sso_mgr.initiate_login())

@app.route("/api/auth/sso/callback", methods=["POST"])
def sso_callback():
    data = request.json or request.form.to_dict()
    result = sso_mgr.handle_callback(data)
    if result.get("authenticated"):
        session["user_id"] = result["user_id"]
    return jsonify(result)

@app.route("/api/sso/disable", methods=["POST"])
def sso_disable():
    return jsonify(sso_mgr.disable())


# ═══════════════════════════════════════════════════════════════
# AUDIT LOG EXPORT
# ═══════════════════════════════════════════════════════════════

@app.route("/api/audit/export/csv", methods=["GET"])
def audit_export_csv():
    filters = {
        "start_date": request.args.get("start"),
        "end_date": request.args.get("end"),
        "user_id": request.args.get("user_id"),
        "action": request.args.get("action"),
        "severity": request.args.get("severity"),
    }
    filters = {k: v for k, v in filters.items() if v}
    csv_data = audit_exporter.export_csv(filters)
    return Response(csv_data, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=audit-log-{datetime.now().strftime('%Y%m%d')}.csv"})

@app.route("/api/audit/export/json", methods=["GET"])
def audit_export_json():
    filters = {
        "start_date": request.args.get("start"),
        "end_date": request.args.get("end"),
        "user_id": request.args.get("user_id"),
        "action": request.args.get("action"),
        "severity": request.args.get("severity"),
    }
    filters = {k: v for k, v in filters.items() if v}
    return jsonify({"events": audit_exporter.export_json(filters)})

@app.route("/api/audit/summary", methods=["GET"])
def audit_summary():
    days = int(request.args.get("days", 30))
    return jsonify(audit_exporter.get_summary(days))


# ═══════════════════════════════════════════════════════════════
# GRANULAR RBAC
# ═══════════════════════════════════════════════════════════════

@app.route("/api/rbac/permissions", methods=["GET"])
def rbac_permissions():
    return jsonify({"permissions": rbac.get_all_permissions()})

@app.route("/api/rbac/roles", methods=["GET"])
def rbac_roles():
    built_in = rbac.get_built_in_roles()
    custom = rbac.list_custom_roles()
    return jsonify({"built_in": built_in, "custom": custom})

@app.route("/api/rbac/roles", methods=["POST"])
def rbac_create_role():
    data = request.json or {}
    if not data.get("name") or not data.get("permissions"):
        return jsonify({"error": "name and permissions required"}), 400
    return jsonify(rbac.create_custom_role(data["name"], data["permissions"], g.user_id))

@app.route("/api/rbac/roles/<role_id>", methods=["PUT"])
def rbac_update_role(role_id):
    data = request.json or {}
    return jsonify(rbac.update_custom_role(role_id, data.get("permissions"), data.get("name")))

@app.route("/api/rbac/roles/<role_id>", methods=["DELETE"])
def rbac_delete_role(role_id):
    return jsonify(rbac.delete_custom_role(role_id))

@app.route("/api/rbac/users/<user_id>/assign", methods=["POST"])
def rbac_assign_role(user_id):
    data = request.json or {}
    if not data.get("role"): return jsonify({"error": "role required"}), 400
    return jsonify(rbac.assign_role(user_id, data["role"], g.user_id))

@app.route("/api/rbac/check", methods=["POST"])
def rbac_check():
    data = request.json or {}
    user = users.get_user(g.user_id)
    has = rbac.check_permission(g.user_id, user.get("role", "member"), data.get("permission", ""))
    return jsonify({"has_permission": has, "permission": data.get("permission")})


# ═══════════════════════════════════════════════════════════════
# AFFILIATE / INFLUENCER PROGRAM
# ═══════════════════════════════════════════════════════════════

@app.route("/api/affiliates/apply", methods=["POST"])
def affiliate_apply():
    data = request.json or {}
    if not data.get("name") or not data.get("email"):
        return jsonify({"error": "name and email required"}), 400
    return jsonify(affiliate_mgr.apply(
        g.user_id, data["name"], data["email"],
        platform=data.get("platform", ""), followers=data.get("followers", 0),
        audience=data.get("audience", ""), pitch=data.get("pitch", "")))

@app.route("/api/affiliates/<aid>/approve", methods=["POST"])
def affiliate_approve(aid):
    data = request.json or {}
    return jsonify(affiliate_mgr.approve(aid, g.user_id,
        commission_pct=data.get("commission_pct")))

@app.route("/api/affiliates/<aid>/reject", methods=["POST"])
def affiliate_reject(aid):
    data = request.json or {}
    return jsonify(affiliate_mgr.reject(aid, data.get("reason", "")))

@app.route("/api/affiliates/<aid>/dashboard", methods=["GET"])
def affiliate_dashboard(aid):
    return jsonify(affiliate_mgr.get_dashboard(aid))

@app.route("/api/affiliates/<aid>/link", methods=["GET"])
def affiliate_link(aid):
    return jsonify(affiliate_mgr.get_referral_link(aid))

@app.route("/api/affiliates/<aid>/payout", methods=["POST"])
def affiliate_request_payout(aid):
    return jsonify(affiliate_mgr.request_payout(aid))

@app.route("/api/affiliates/track", methods=["POST"])
def affiliate_track_click():
    """Track a referral click (called from landing page JS)."""
    data = request.json or {}
    ref = data.get("ref", request.args.get("ref", ""))
    if not ref: return jsonify({"tracked": False}), 400
    return jsonify(affiliate_mgr.track_click(ref,
        ip=request.remote_addr or "", user_agent=request.headers.get("User-Agent", "")))

@app.route("/api/affiliates/simulate", methods=["GET"])
def affiliate_simulate():
    """Show potential earnings per plan."""
    plan = request.args.get("plan", "pro")
    billing = request.args.get("billing", "monthly")
    return jsonify(affiliate_mgr.simulate_commission(plan, billing))

@app.route("/api/affiliates/admin", methods=["GET"])
def affiliate_admin_overview():
    return jsonify(affiliate_mgr.get_admin_overview())

@app.route("/api/affiliates/admin/payouts/<pid>/process", methods=["POST"])
def affiliate_process_payout(pid):
    return jsonify(affiliate_mgr.process_payout(pid, g.user_id))


# ═══════════════════════════════════════════════════════════════
# PASSWORD RESET + EMAIL NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════

# ── Roundtable Whiteboard ──

@app.route("/api/roundtables/<rid>/whiteboard", methods=["GET"])
def get_whiteboard(rid):
    wb = whiteboard.get_or_create(rid, g.user_id)
    return jsonify(wb)

@app.route("/api/roundtables/<rid>/whiteboard/notes", methods=["POST"])
def add_whiteboard_note(rid):
    data = request.json or {}
    return jsonify(whiteboard.add_note(
        rid, data.get("section_id", "ideas"), data.get("content", ""),
        author=data.get("author", ""), color=data.get("color", ""),
        tags=data.get("tags")))

@app.route("/api/roundtables/<rid>/whiteboard/notes/<note_id>", methods=["PUT"])
def update_whiteboard_note(rid, note_id):
    data = request.json or {}
    return jsonify(whiteboard.update_note(
        rid, note_id, content=data.get("content"),
        section_id=data.get("section_id"), pinned=data.get("pinned"),
        completed=data.get("completed"), color=data.get("color")))

@app.route("/api/roundtables/<rid>/whiteboard/notes/<note_id>", methods=["DELETE"])
def delete_whiteboard_note(rid, note_id):
    return jsonify(whiteboard.delete_note(rid, note_id))

@app.route("/api/roundtables/<rid>/whiteboard/action-items", methods=["GET"])
def get_whiteboard_actions(rid):
    return jsonify({"action_items": whiteboard.get_action_items(rid)})

@app.route("/api/roundtables/<rid>/whiteboard/action-items", methods=["POST"])
def add_whiteboard_action(rid):
    data = request.json or {}
    return jsonify(whiteboard.add_action_item(
        rid, data.get("title", ""), assigned_to=data.get("assigned_to", ""),
        due_date=data.get("due_date", ""), priority=data.get("priority", "medium")))

@app.route("/api/roundtables/<rid>/whiteboard/sections", methods=["POST"])
def add_whiteboard_section(rid):
    data = request.json or {}
    return jsonify(whiteboard.add_section(
        rid, data.get("title", "New Section"),
        color=data.get("color", ""), icon=data.get("icon", "📝")))

@app.route("/api/roundtables/<rid>/whiteboard/export/<fmt>", methods=["GET"])
def export_whiteboard(rid, fmt):
    if fmt == "markdown":
        md = whiteboard.export_markdown(rid)
        return Response(md, mimetype="text/markdown",
                       headers={"Content-Disposition": f"attachment; filename=whiteboard-{rid}.md"})
    elif fmt == "json":
        return jsonify(whiteboard.export_json(rid))
    return jsonify({"error": "Format must be markdown or json"}), 400


# ── Social Media Campaign Manager ──

@app.route("/api/social/platforms", methods=["GET"])
def social_platforms():
    return jsonify({"platforms": social_mgr.get_platforms()})

@app.route("/api/social/connections", methods=["GET"])
def social_connections():
    return jsonify({"connections": social_mgr.get_connections(g.user_id)})

@app.route("/api/social/connections", methods=["POST"])
def social_connect():
    data = request.json or {}
    if not data.get("platform") or not data.get("access_token"):
        return jsonify({"error": "platform and access_token required"}), 400
    return jsonify(social_mgr.connect_platform(
        g.user_id, data["platform"], data["access_token"],
        refresh_token=data.get("refresh_token", ""),
        account_name=data.get("account_name", ""),
        account_id=data.get("account_id", "")))

@app.route("/api/social/connections/<cid>", methods=["DELETE"])
def social_disconnect(cid):
    return jsonify(social_mgr.disconnect_platform(g.user_id, cid))

@app.route("/api/social/campaigns", methods=["GET"])
def social_campaigns_list():
    return jsonify({"campaigns": social_mgr.get_campaigns(g.user_id)})

@app.route("/api/social/campaigns", methods=["POST"])
def social_campaign_create():
    data = request.json or {}
    if not data.get("name"): return jsonify({"error": "name required"}), 400
    return jsonify(social_mgr.create_campaign(
        g.user_id, data["name"], objective=data.get("objective", ""),
        platforms=data.get("platforms"), target_audience=data.get("target_audience", ""),
        start_date=data.get("start_date", ""), end_date=data.get("end_date", ""),
        tone=data.get("tone", "professional"),
        posting_frequency=data.get("posting_frequency", "daily")))

@app.route("/api/social/campaigns/<cid>", methods=["GET"])
def social_campaign_get(cid):
    camp = social_mgr.get_campaign(cid)
    if not camp: return jsonify({"error": "Campaign not found"}), 404
    return jsonify(camp)

@app.route("/api/social/campaigns/<cid>", methods=["PUT"])
def social_campaign_update(cid):
    data = request.json or {}
    return jsonify(social_mgr.update_campaign(cid, **data))

@app.route("/api/social/campaigns/<cid>/posts", methods=["GET"])
def social_posts_list(cid):
    return jsonify({"posts": social_mgr.get_posts(
        cid, platform=request.args.get("platform"),
        status=request.args.get("status"))})

@app.route("/api/social/campaigns/<cid>/posts", methods=["POST"])
def social_post_create(cid):
    data = request.json or {}
    if not data.get("platform") or not data.get("content"):
        return jsonify({"error": "platform and content required"}), 400
    return jsonify(social_mgr.create_post(
        cid, data["platform"], data["content"],
        scheduled_at=data.get("scheduled_at", ""),
        media_url=data.get("media_url", ""), link_url=data.get("link_url", ""),
        hashtags=data.get("hashtags")))

@app.route("/api/social/campaigns/<cid>/bulk", methods=["POST"])
def social_bulk_schedule(cid):
    data = request.json or {}
    return jsonify(social_mgr.bulk_schedule(cid, data.get("posts", [])))

@app.route("/api/social/posts/<pid>", methods=["PUT"])
def social_post_update(pid):
    data = request.json or {}
    return jsonify(social_mgr.update_post(
        pid, content=data.get("content"), scheduled_at=data.get("scheduled_at"),
        status=data.get("status")))

@app.route("/api/social/posts/<pid>", methods=["DELETE"])
def social_post_delete(pid):
    return jsonify(social_mgr.delete_post(pid))

@app.route("/api/social/posts/<pid>/publish", methods=["POST"])
def social_post_publish(pid):
    return jsonify(social_mgr.publish_post(pid, g.user_id))

@app.route("/api/social/queue", methods=["GET"])
def social_queue():
    return jsonify({"queue": social_mgr.get_queue(g.user_id)})

@app.route("/api/social/calendar", methods=["GET"])
def social_calendar():
    start = request.args.get("start", datetime.now().strftime("%Y-%m-%d"))
    end = request.args.get("end", (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"))
    return jsonify(social_mgr.get_calendar(g.user_id, start, end))

@app.route("/api/social/campaigns/<cid>/analytics", methods=["GET"])
def social_campaign_analytics(cid):
    return jsonify(social_mgr.get_campaign_analytics(cid))

@app.route("/api/social/campaigns/<cid>/generate-prompt", methods=["GET"])
def social_generate_prompt(cid):
    camp = social_mgr.get_campaign(cid)
    if not camp: return jsonify({"error": "Campaign not found"}), 404
    platform = request.args.get("platform", "twitter")
    count = int(request.args.get("count", 7))
    return jsonify({"prompt": social_mgr.build_generation_prompt(camp, platform, count)})


# ── Document Export Engine ──

# ═══════════════════════════════════════════════════════════════
# CRM / DEAL TRACKER
# ═══════════════════════════════════════════════════════════════

@app.route("/api/crm/contacts", methods=["GET"])
def crm_contacts_list():
    return jsonify({"contacts": crm.list_contacts(
        g.user_id, search=request.args.get("q", ""),
        tag=request.args.get("tag", ""))})

@app.route("/api/crm/contacts", methods=["POST"])
def crm_contact_create():
    data = request.json or {}
    if not data.get("name"): return jsonify({"error": "name required"}), 400
    return jsonify(crm.create_contact(
        g.user_id, data["name"], email=data.get("email", ""),
        phone=data.get("phone", ""), company=data.get("company", ""),
        title=data.get("title", ""), source=data.get("source", ""),
        tags=data.get("tags"), custom_fields=data.get("custom_fields"),
        notes=data.get("notes", "")))

@app.route("/api/crm/contacts/<cid>", methods=["GET"])
def crm_contact_get(cid):
    c = crm.get_contact(cid)
    if not c: return jsonify({"error": "Not found"}), 404
    return jsonify(c)

@app.route("/api/crm/contacts/<cid>", methods=["PUT"])
def crm_contact_update(cid):
    safe = sanitize_update_columns("crm_contacts", request.json or {})
    return jsonify(crm.update_contact(cid, **safe))

@app.route("/api/crm/contacts/<cid>", methods=["DELETE"])
def crm_contact_delete(cid):
    return jsonify(crm.delete_contact(cid))

@app.route("/api/crm/contacts/<cid>/context", methods=["GET"])
def crm_contact_context(cid):
    """Get AI-ready context for a contact."""
    return jsonify({"context": crm.build_contact_context(cid)})

@app.route("/api/crm/companies", methods=["GET"])
def crm_companies_list():
    return jsonify({"companies": crm.list_companies(g.user_id)})

@app.route("/api/crm/companies", methods=["POST"])
def crm_company_create():
    data = request.json or {}
    if not data.get("name"): return jsonify({"error": "name required"}), 400
    return jsonify(crm.create_company(
        g.user_id, data["name"], domain=data.get("domain", ""),
        industry=data.get("industry", ""), size=data.get("size", ""),
        notes=data.get("notes", "")))

@app.route("/api/crm/companies/<cid>", methods=["GET"])
def crm_company_get(cid):
    c = crm.get_company(cid)
    if not c: return jsonify({"error": "Not found"}), 404
    return jsonify(c)

@app.route("/api/crm/deals", methods=["GET"])
def crm_deals_list():
    return jsonify({"deals": crm.list_deals(
        g.user_id, stage=request.args.get("stage"),
        status=request.args.get("status", "open"))})

@app.route("/api/crm/deals", methods=["POST"])
def crm_deal_create():
    data = request.json or {}
    if not data.get("title"): return jsonify({"error": "title required"}), 400
    return jsonify(crm.create_deal(
        g.user_id, data["title"], value=data.get("value", 0),
        contact_id=data.get("contact_id", ""), company_id=data.get("company_id", ""),
        stage=data.get("stage", "lead"), expected_close=data.get("expected_close", ""),
        notes=data.get("notes", "")))

@app.route("/api/crm/deals/<did>", methods=["PUT"])
def crm_deal_update(did):
    safe = sanitize_update_columns("crm_deals", request.json or {})
    return jsonify(crm.update_deal(did, **safe))

@app.route("/api/crm/deals/<did>/move", methods=["POST"])
def crm_deal_move(did):
    data = request.json or {}
    return jsonify(crm.move_deal(did, data.get("stage", "lead")))

@app.route("/api/crm/deals/<did>", methods=["DELETE"])
def crm_deal_delete(did):
    return jsonify(crm.delete_deal(did))

@app.route("/api/crm/activities", methods=["GET"])
def crm_activities_list():
    return jsonify({"activities": crm.list_activities(
        g.user_id, contact_id=request.args.get("contact_id", ""),
        deal_id=request.args.get("deal_id", ""))})

@app.route("/api/crm/activities", methods=["POST"])
def crm_activity_create():
    data = request.json or {}
    if not data.get("type") or not data.get("subject"):
        return jsonify({"error": "type and subject required"}), 400
    return jsonify(crm.log_activity(
        g.user_id, data["type"], data["subject"],
        contact_id=data.get("contact_id", ""), deal_id=data.get("deal_id", ""),
        notes=data.get("notes", ""), due_date=data.get("due_date", "")))

@app.route("/api/crm/activities/<aid>/complete", methods=["POST"])
def crm_activity_complete(aid):
    return jsonify(crm.complete_activity(aid))

@app.route("/api/crm/follow-ups", methods=["GET"])
def crm_follow_ups():
    return jsonify({"follow_ups": crm.get_follow_ups(g.user_id)})

@app.route("/api/crm/stale-deals", methods=["GET"])
def crm_stale_deals():
    days = int(request.args.get("days", 14))
    return jsonify({"stale_deals": crm.get_stale_deals(g.user_id, days)})

@app.route("/api/crm/pipeline", methods=["GET"])
def crm_pipeline():
    return jsonify(crm.get_pipeline(g.user_id))

# ── CRM Customization ──

@app.route("/api/crm/custom-fields", methods=["GET"])
def crm_custom_fields_list():
    return jsonify({"fields": custom_fields.list_fields(
        g.user_id, entity_type=request.args.get("entity_type"))})

@app.route("/api/crm/custom-fields", methods=["POST"])
def crm_custom_field_create():
    d = request.json or {}
    if not d.get("entity_type") or not d.get("label"):
        return jsonify({"error": "entity_type and label required"}), 400
    return jsonify(custom_fields.create_field(
        g.user_id, d["entity_type"], d["label"],
        field_type=d.get("type", "text"), options=d.get("options"),
        required=d.get("required", False), default_value=d.get("default", ""),
        placeholder=d.get("placeholder", ""), group=d.get("group", ""),
        position=d.get("position", 0)))

@app.route("/api/crm/custom-fields/<fid>", methods=["PUT"])
def crm_custom_field_update(fid):
    return jsonify(custom_fields.update_field(fid, **(request.json or {})))

@app.route("/api/crm/custom-fields/<fid>", methods=["DELETE"])
def crm_custom_field_delete(fid):
    return jsonify(custom_fields.delete_field(fid))

@app.route("/api/crm/custom-fields/types", methods=["GET"])
def crm_field_types():
    return jsonify({"types": custom_fields.FIELD_TYPES,
                    "entity_types": custom_fields.ENTITY_TYPES})

@app.route("/api/crm/pipelines", methods=["GET"])
def crm_pipelines_list():
    return jsonify({"pipelines": crm_pipeline_mgr.list_pipelines(g.user_id)})

@app.route("/api/crm/pipelines", methods=["POST"])
def crm_pipeline_create():
    d = request.json or {}
    if not d.get("name"): return jsonify({"error": "name required"}), 400
    return jsonify(crm_pipeline_mgr.create_pipeline(
        g.user_id, d["name"], stages=d.get("stages")))

@app.route("/api/crm/pipelines/<pid>", methods=["GET"])
def crm_pipeline_get(pid):
    p = crm_pipeline_mgr.get_pipeline(pid)
    return jsonify(p) if p else (jsonify({"error": "Not found"}), 404)

@app.route("/api/crm/pipelines/<pid>", methods=["PUT"])
def crm_pipeline_update(pid):
    d = request.json or {}
    return jsonify(crm_pipeline_mgr.update_pipeline(
        pid, name=d.get("name"), stages=d.get("stages")))

@app.route("/api/crm/pipelines/<pid>", methods=["DELETE"])
def crm_pipeline_delete(pid):
    return jsonify(crm_pipeline_mgr.delete_pipeline(pid))

@app.route("/api/crm/activity-types", methods=["GET"])
def crm_activity_types_list():
    return jsonify({"types": activity_types.get_types(g.user_id)})

@app.route("/api/crm/activity-types", methods=["POST"])
def crm_activity_type_create():
    d = request.json or {}
    if not d.get("label"): return jsonify({"error": "label required"}), 400
    return jsonify(activity_types.create_type(
        g.user_id, d["label"], icon=d.get("icon", "📌"),
        color=d.get("color", "#94a3b8")))

@app.route("/api/crm/activity-types/<tid>", methods=["DELETE"])
def crm_activity_type_delete(tid):
    return jsonify(activity_types.delete_type(g.user_id, tid))

@app.route("/api/crm/views", methods=["GET"])
def crm_views_list():
    return jsonify({"views": saved_views.list_views(
        g.user_id, entity_type=request.args.get("entity_type"))})

@app.route("/api/crm/views", methods=["POST"])
def crm_view_create():
    d = request.json or {}
    if not d.get("name") or not d.get("entity_type"):
        return jsonify({"error": "name and entity_type required"}), 400
    return jsonify(saved_views.create_view(
        g.user_id, d["name"], d["entity_type"],
        filters=d.get("filters"), sort_by=d.get("sort_by", ""),
        sort_order=d.get("sort_order", "desc"), columns=d.get("columns")))

@app.route("/api/crm/views/<vid>", methods=["GET"])
def crm_view_get(vid):
    v = saved_views.get_view(vid)
    return jsonify(v) if v else (jsonify({"error": "Not found"}), 404)

@app.route("/api/crm/views/<vid>", methods=["PUT"])
def crm_view_update(vid):
    return jsonify(saved_views.update_view(vid, **(request.json or {})))

@app.route("/api/crm/views/<vid>", methods=["DELETE"])
def crm_view_delete(vid):
    return jsonify(saved_views.delete_view(vid))

@app.route("/api/crm/views/<vid>/apply", methods=["GET"])
def crm_view_apply(vid):
    return jsonify(saved_views.apply_view(vid, g.user_id))


# ═══════════════════════════════════════════════════════════════
# INVOICES & PROPOSALS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/invoicing/profile", methods=["GET"])
def invoice_profile_get():
    return jsonify(invoice_mgr.get_business_profile(g.user_id))

@app.route("/api/invoicing/profile", methods=["POST"])
def invoice_profile_set():
    data = request.json or {}
    return jsonify(invoice_mgr.set_business_profile(g.user_id, **(data)))

@app.route("/api/invoicing/invoices", methods=["GET"])
def invoices_list():
    return jsonify({"invoices": invoice_mgr.list_invoices(
        g.user_id, status=request.args.get("status"))})

@app.route("/api/invoicing/invoices", methods=["POST"])
def invoice_create():
    data = request.json or {}
    if not data.get("client_name"): return jsonify({"error": "client_name required"}), 400
    return jsonify(invoice_mgr.create_invoice(
        g.user_id, data["client_name"], client_email=data.get("client_email", ""),
        client_address=data.get("client_address", ""),
        line_items=data.get("line_items"), tax_rate=data.get("tax_rate"),
        discount=data.get("discount", 0), notes=data.get("notes", ""),
        due_days=data.get("due_days"), currency=data.get("currency")))

@app.route("/api/invoicing/invoices/<iid>", methods=["GET"])
def invoice_get(iid):
    inv = invoice_mgr.get_invoice(iid)
    if not inv: return jsonify({"error": "Not found"}), 404
    return jsonify(inv)

@app.route("/api/invoicing/invoices/<iid>", methods=["PUT"])
def invoice_update(iid):
    return jsonify(invoice_mgr.update_invoice(iid, **(request.json or {})))

@app.route("/api/invoicing/invoices/<iid>/send", methods=["POST"])
def invoice_send(iid):
    return jsonify(invoice_mgr.mark_sent(iid))

@app.route("/api/invoicing/invoices/<iid>/paid", methods=["POST"])
def invoice_paid(iid):
    data = request.json or {}
    return jsonify(invoice_mgr.mark_paid(
        iid, payment_method=data.get("method", ""),
        payment_date=data.get("date", "")))

@app.route("/api/invoicing/invoices/<iid>/pdf", methods=["GET"])
def invoice_pdf(iid):
    inv = invoice_mgr.get_invoice(iid)
    if not inv: return jsonify({"error": "Not found"}), 404
    profile = invoice_mgr.get_business_profile(inv["owner_id"])
    html = invoice_mgr.invoice_to_html(inv, profile)
    return Response(html, mimetype="text/html",
                   headers={"Content-Disposition": f"attachment; filename=invoice-{inv.get('invoice_number','')}.html"})

@app.route("/api/invoicing/overdue", methods=["GET"])
def invoices_overdue():
    return jsonify({"overdue": invoice_mgr.get_overdue(g.user_id)})

@app.route("/api/invoicing/proposals", methods=["GET"])
def proposals_list():
    return jsonify({"proposals": invoice_mgr.list_proposals(
        g.user_id, status=request.args.get("status"))})

@app.route("/api/invoicing/proposals", methods=["POST"])
def proposal_create():
    data = request.json or {}
    if not data.get("title") or not data.get("client_name"):
        return jsonify({"error": "title and client_name required"}), 400
    return jsonify(invoice_mgr.create_proposal(
        g.user_id, data["title"], data["client_name"],
        client_email=data.get("client_email", ""),
        sections=data.get("sections"), pricing_items=data.get("pricing_items"),
        total=data.get("total", 0), valid_days=data.get("valid_days", 30),
        notes=data.get("notes", ""), terms=data.get("terms", "")))

@app.route("/api/invoicing/proposals/<pid>", methods=["GET"])
def proposal_get(pid):
    prop = invoice_mgr.get_proposal(pid)
    if not prop: return jsonify({"error": "Not found"}), 404
    return jsonify(prop)

@app.route("/api/invoicing/proposals/<pid>/accept", methods=["POST"])
def proposal_accept(pid):
    return jsonify(invoice_mgr.accept_proposal(pid))

@app.route("/api/invoicing/dashboard", methods=["GET"])
def invoice_dashboard():
    return jsonify(invoice_mgr.get_revenue_dashboard(g.user_id))


# ═══════════════════════════════════════════════════════════════
# TASK / PROJECT BOARD
# ═══════════════════════════════════════════════════════════════

@app.route("/api/projects/templates", methods=["GET"])
def project_templates():
    return jsonify({"templates": task_mgr.get_templates()})

@app.route("/api/projects", methods=["GET"])
def projects_list():
    return jsonify({"projects": task_mgr.list_projects(g.user_id)})

@app.route("/api/projects", methods=["POST"])
def project_create():
    data = request.json or {}
    if not data.get("name"): return jsonify({"error": "name required"}), 400
    return jsonify(task_mgr.create_project(
        g.user_id, data["name"], description=data.get("description", ""),
        template=data.get("template"), columns=data.get("columns")))

@app.route("/api/projects/<pid>", methods=["GET"])
def project_get(pid):
    p = task_mgr.get_project(pid)
    if not p: return jsonify({"error": "Not found"}), 404
    return jsonify(p)

@app.route("/api/projects/<pid>", methods=["PUT"])
def project_update(pid):
    return jsonify(task_mgr.update_project(pid, **(request.json or {})))

@app.route("/api/projects/<pid>/archive", methods=["POST"])
def project_archive(pid):
    return jsonify(task_mgr.archive_project(pid))

@app.route("/api/projects/<pid>/board", methods=["GET"])
def project_board(pid):
    return jsonify(task_mgr.get_board(pid))

@app.route("/api/projects/<pid>/tasks", methods=["POST"])
def task_create(pid):
    data = request.json or {}
    if not data.get("title"): return jsonify({"error": "title required"}), 400
    return jsonify(task_mgr.create_task(
        pid, g.user_id, data["title"], description=data.get("description", ""),
        column=data.get("column", "todo"), priority=data.get("priority", "medium"),
        assigned_to=data.get("assigned_to", ""), due_date=data.get("due_date", ""),
        labels=data.get("labels"), source=data.get("source", "manual")))

@app.route("/api/tasks/<tid>", methods=["GET"])
def task_get(tid):
    t = task_mgr.get_task(tid)
    if not t: return jsonify({"error": "Not found"}), 404
    return jsonify(t)

@app.route("/api/tasks/<tid>", methods=["PUT"])
def task_update(tid):
    safe = sanitize_update_columns("tasks", request.json or {})
    return jsonify(task_mgr.update_task(tid, **safe))

@app.route("/api/tasks/<tid>/move", methods=["POST"])
def task_move(tid):
    data = request.json or {}
    return jsonify(task_mgr.move_task(
        tid, data.get("column", "todo"), position=data.get("position")))

@app.route("/api/tasks/<tid>/complete", methods=["POST"])
def task_complete(tid):
    return jsonify(task_mgr.complete_task(tid))

@app.route("/api/tasks/<tid>", methods=["DELETE"])
def task_delete(tid):
    return jsonify(task_mgr.delete_task(tid))

@app.route("/api/tasks/<tid>/subtasks", methods=["POST"])
def subtask_add(tid):
    data = request.json or {}
    return jsonify(task_mgr.add_subtask(tid, data.get("title", "")))

@app.route("/api/tasks/subtasks/<sid>/toggle", methods=["POST"])
def subtask_toggle(sid):
    return jsonify(task_mgr.toggle_subtask(sid))

@app.route("/api/tasks/<tid>/comments", methods=["POST"])
def task_comment(tid):
    data = request.json or {}
    return jsonify(task_mgr.add_comment(tid, g.user_id, data.get("content", "")))

@app.route("/api/projects/<pid>/tasks/from-roundtable", methods=["POST"])
def tasks_from_roundtable(pid):
    """Create tasks from Roundtable whiteboard action items."""
    data = request.json or {}
    return jsonify({"tasks": task_mgr.create_tasks_from_action_items(
        pid, g.user_id, data.get("action_items", []))})

@app.route("/api/tasks/dashboard", methods=["GET"])
def task_dashboard():
    return jsonify(task_mgr.get_dashboard(g.user_id))

# ═══════════════════════════════════════════════════════════════
# COMPLETE BUSINESS OS — All remaining business tools
# ═══════════════════════════════════════════════════════════════

# ── Meeting Prep & Summary ──
@app.route("/api/meetings/prepare", methods=["POST"])
def meeting_prep():
    d = request.json or {}
    return jsonify(meeting_assistant.prepare(g.user_id, d.get("meeting_with",""),
        topic=d.get("topic",""), contact_id=d.get("contact_id",""), deal_id=d.get("deal_id","")))

@app.route("/api/meetings/summarize", methods=["POST"])
def meeting_summary():
    d = request.json or {}
    return jsonify(meeting_assistant.summarize(g.user_id, d.get("meeting_with",""), d.get("notes",""),
        contact_id=d.get("contact_id",""), deal_id=d.get("deal_id","")))

# ── Competitive Intelligence ──
@app.route("/api/competitors", methods=["GET"])
def competitors_list():
    return jsonify({"competitors": competitive_intel.list_competitors(g.user_id)})

@app.route("/api/competitors", methods=["POST"])
def competitor_add():
    d = request.json or {}
    return jsonify(competitive_intel.add_competitor(g.user_id, d.get("name",""),
        website=d.get("website",""), description=d.get("description",""), tags=d.get("tags")))

@app.route("/api/competitors/<cid>", methods=["GET"])
def competitor_get(cid):
    c = competitive_intel.get_competitor(cid)
    return jsonify(c) if c else (jsonify({"error":"Not found"}), 404)

@app.route("/api/competitors/<cid>", methods=["DELETE"])
def competitor_del(cid):
    return jsonify(competitive_intel.delete_competitor(cid))

@app.route("/api/competitors/<cid>/intel", methods=["GET"])
def competitor_intel_get(cid):
    return jsonify({"intel": competitive_intel.get_intel(cid)})

@app.route("/api/competitors/<cid>/intel", methods=["POST"])
def competitor_intel_add(cid):
    d = request.json or {}
    return jsonify(competitive_intel.log_intel(cid, d.get("type","general"), d.get("content",""), source=d.get("source","")))

@app.route("/api/competitors/analysis-prompt", methods=["GET"])
def competitor_analysis_prompt():
    return jsonify({"prompt": competitive_intel.build_analysis_prompt(g.user_id)})

# ── Client Portal ──
@app.route("/api/portal/shares", methods=["GET"])
def portal_shares_list():
    return jsonify({"shares": client_portal.list_shares(g.user_id)})

@app.route("/api/portal/shares", methods=["POST"])
def portal_share_create():
    d = request.json or {}
    return jsonify(client_portal.create_share(g.user_id, d.get("title",""), d.get("content_type",""),
        d.get("content_id",""), client_name=d.get("client_name",""), client_email=d.get("client_email",""),
        expires_days=d.get("expires_days",30), password=d.get("password","")))

@app.route("/api/portal/shares/<sid>/revoke", methods=["POST"])
def portal_share_revoke(sid):
    return jsonify(client_portal.revoke_share(sid))

@app.route("/portal/<token>", methods=["GET", "POST"])
def portal_public_view(token):
    password = (request.json or {}).get("password","") if request.method == "POST" else request.args.get("p","")
    result = client_portal.get_share(token, password)
    if result.get("error") == "password_required":
        return jsonify(result), 401
    if result.get("error"):
        return jsonify(result), 404
    return jsonify(result)

# ── Financial Dashboard ──
@app.route("/api/financial/overview", methods=["GET"])
def financial_overview():
    return jsonify(financial_dashboard.get_overview(g.user_id))

# ── HR Assistant ──
@app.route("/api/hr/job-description", methods=["POST"])
def hr_job_description():
    d = request.json or {}
    return jsonify(hr_assistant.build_job_description_prompt(d.get("title",""),
        department=d.get("department",""), employment_type=d.get("type","Full-time"),
        location=d.get("location",""), company=d.get("company",""), description=d.get("description","")))

@app.route("/api/hr/interview-questions", methods=["POST"])
def hr_interview():
    d = request.json or {}
    return jsonify(hr_assistant.build_interview_prompt(d.get("title",""),
        description=d.get("description",""), stage=d.get("stage","first_round")))

@app.route("/api/hr/onboarding/templates", methods=["GET"])
def hr_onboarding_templates():
    return jsonify({"templates": hr_assistant.get_onboarding_templates()})

@app.route("/api/hr/onboarding/<template>", methods=["GET"])
def hr_onboarding_checklist(template):
    return jsonify(hr_assistant.get_onboarding_checklist(template))

# ── Contract Templates ──
@app.route("/api/contracts/templates", methods=["GET"])
def contract_tmpl_list():
    return jsonify({"templates": contract_templates.get_templates()})

@app.route("/api/contracts/templates/<tid>", methods=["GET"])
def contract_tmpl_get(tid):
    return jsonify(contract_templates.get_template(tid))

@app.route("/api/contracts/generate", methods=["POST"])
def contract_generate():
    d = request.json or {}
    return jsonify(contract_templates.build_prompt(d.get("template",""), d.get("fields",{})))

# ── Goal / KPI Tracker ──
@app.route("/api/goals", methods=["GET"])
def goals_list():
    return jsonify({"goals": goal_tracker.list_goals(g.user_id,
        category=request.args.get("category"), status=request.args.get("status","active"))})

@app.route("/api/goals", methods=["POST"])
def goal_create():
    d = request.json or {}
    return jsonify(goal_tracker.create_goal(g.user_id, d.get("title",""),
        description=d.get("description",""), goal_type=d.get("type","objective"),
        target_value=d.get("target",0), target_unit=d.get("unit",""),
        due_date=d.get("due_date",""), parent_id=d.get("parent_id",""),
        assigned_to=d.get("assigned_to",""), category=d.get("category","business")))

@app.route("/api/goals/<gid>", methods=["GET"])
def goal_get(gid):
    g_data = goal_tracker.get_goal(gid)
    return jsonify(g_data) if g_data else (jsonify({"error":"Not found"}), 404)

@app.route("/api/goals/<gid>/progress", methods=["POST"])
def goal_progress(gid):
    d = request.json or {}
    return jsonify(goal_tracker.update_progress(gid, d.get("value",0), note=d.get("note","")))

@app.route("/api/goals/<gid>/complete", methods=["POST"])
def goal_complete(gid):
    return jsonify(goal_tracker.complete_goal(gid))

@app.route("/api/goals/dashboard", methods=["GET"])
def goals_dashboard():
    return jsonify(goal_tracker.get_dashboard(g.user_id))

# ── Email Composer + Outbox ──
@app.route("/api/email/drafts", methods=["GET"])
def email_drafts_list():
    return jsonify({"drafts": email_composer.list_outbox(g.user_id, status="draft")})

@app.route("/api/email/sent", methods=["GET"])
def email_sent_list():
    return jsonify({"sent": email_composer.list_outbox(g.user_id, status="sent")})

@app.route("/api/email/outbox", methods=["GET"])
def email_outbox_list():
    return jsonify({"emails": email_composer.list_outbox(g.user_id)})

@app.route("/api/email/compose", methods=["POST"])
def email_compose():
    d = request.json or {}
    return jsonify(email_composer.create_draft(g.user_id, d.get("to",""), d.get("subject",""),
        d.get("body",""), cc=d.get("cc",""), bcc=d.get("bcc",""), reply_to=d.get("reply_to",""),
        contact_id=d.get("contact_id",""), deal_id=d.get("deal_id","")))

@app.route("/api/email/<eid>", methods=["GET"])
def email_get(eid):
    e = email_composer.get_email(eid)
    return jsonify(e) if e else (jsonify({"error":"Not found"}), 404)

@app.route("/api/email/<eid>", methods=["PUT"])
def email_update(eid):
    return jsonify(email_composer.update_draft(eid, **(request.json or {})))

@app.route("/api/email/<eid>/send", methods=["POST"])
def email_send(eid):
    return jsonify(email_composer.send_email(eid, email_service=email_svc))

@app.route("/api/email/<eid>", methods=["DELETE"])
def email_delete(eid):
    return jsonify(email_composer.delete_draft(eid))

# ── Expense Tracker ──
@app.route("/api/expenses", methods=["GET"])
def expenses_list():
    return jsonify({"expenses": expense_tracker.list_expenses(g.user_id,
        start_date=request.args.get("start",""), end_date=request.args.get("end",""),
        category=request.args.get("category",""))})

@app.route("/api/expenses", methods=["POST"])
def expense_add():
    d = request.json or {}
    return jsonify(expense_tracker.add_expense(g.user_id, d.get("description",""),
        d.get("amount",0), category=d.get("category","other"), vendor=d.get("vendor",""),
        date=d.get("date",""), receipt_url=d.get("receipt_url",""),
        recurring=d.get("recurring",False), notes=d.get("notes","")))

@app.route("/api/expenses/<eid>", methods=["PUT"])
def expense_update(eid):
    safe = sanitize_update_columns("expenses", request.json or {})
    return jsonify(expense_tracker.update_expense(eid, **safe))

@app.route("/api/expenses/<eid>", methods=["DELETE"])
def expense_delete(eid):
    return jsonify(expense_tracker.delete_expense(eid))

@app.route("/api/expenses/summary", methods=["GET"])
def expense_summary():
    return jsonify(expense_tracker.get_summary(g.user_id,
        start_date=request.args.get("start",""), end_date=request.args.get("end","")))

@app.route("/api/expenses/categories", methods=["GET"])
def expense_categories():
    return jsonify({"categories": custom_expense_cats.list_categories(g.user_id)})

@app.route("/api/expenses/categories/custom", methods=["POST"])
def expense_category_create():
    d = request.json or {}
    return jsonify(custom_expense_cats.create_category(g.user_id, d.get("name",""),
        icon=d.get("icon","📁"), color=d.get("color","#94a3b8"),
        tax_deductible=d.get("tax_deductible", True)))

@app.route("/api/expenses/categories/<cid>", methods=["DELETE"])
def expense_category_delete(cid):
    return jsonify(custom_expense_cats.delete_category(g.user_id, cid))

@app.route("/api/expenses/tax-summary", methods=["GET"])
def expense_tax_summary():
    return jsonify(custom_expense_cats.get_tax_summary(g.user_id, year=request.args.get("year","")))

# ── Recurring Invoices ──
@app.route("/api/invoicing/recurring", methods=["GET"])
def recurring_list():
    return jsonify({"recurring": recurring_invoices.list_recurring(g.user_id)})

@app.route("/api/invoicing/recurring", methods=["POST"])
def recurring_create():
    d = request.json or {}
    return jsonify(recurring_invoices.create_recurring(g.user_id, d.get("client_name",""),
        d.get("client_email",""), d.get("line_items",[]),
        frequency=d.get("frequency","monthly"), auto_send=d.get("auto_send",False)))

@app.route("/api/invoicing/recurring/<rid>/pause", methods=["POST"])
def recurring_pause(rid):
    return jsonify(recurring_invoices.pause(rid))

@app.route("/api/invoicing/recurring/<rid>/resume", methods=["POST"])
def recurring_resume(rid):
    return jsonify(recurring_invoices.resume(rid))

# ── Partial Payments ──
@app.route("/api/invoicing/invoices/<iid>/payments", methods=["GET"])
def invoice_payments_list(iid):
    return jsonify({"payments": payment_tracker.get_payments(iid)})

@app.route("/api/invoicing/invoices/<iid>/payments", methods=["POST"])
def invoice_payment_add(iid):
    d = request.json or {}
    return jsonify(payment_tracker.record_payment(iid, d.get("amount",0),
        method=d.get("method",""), note=d.get("note","")))

@app.route("/api/invoicing/invoices/<iid>/balance", methods=["GET"])
def invoice_balance(iid):
    return jsonify(payment_tracker.get_balance(iid))

# ── Task Time Tracking ──
@app.route("/api/time/start", methods=["POST"])
def time_start():
    d = request.json or {}
    return jsonify(time_tracker.start_timer(d.get("task_id",""), g.user_id))

@app.route("/api/time/stop", methods=["POST"])
def time_stop():
    return jsonify(time_tracker.stop_timer(g.user_id))

@app.route("/api/time/active", methods=["GET"])
def time_active():
    t = time_tracker.get_active_timer(g.user_id)
    return jsonify(t or {"active": False})

@app.route("/api/time/log", methods=["POST"])
def time_log():
    d = request.json or {}
    return jsonify(time_tracker.log_manual(d.get("task_id",""), g.user_id,
        d.get("minutes",0), date=d.get("date",""), note=d.get("note","")))

@app.route("/api/time/task/<tid>", methods=["GET"])
def time_task(tid):
    return jsonify(time_tracker.get_task_time(tid))

@app.route("/api/time/timesheet", methods=["GET"])
def timesheet():
    return jsonify(time_tracker.get_timesheet(g.user_id,
        request.args.get("start",""), request.args.get("end","")))

# ── Email Templates + Signatures ──
@app.route("/api/email/templates", methods=["GET"])
def email_tpl_list():
    return jsonify({"templates": email_templates_mgr.list_templates(g.user_id)})

@app.route("/api/email/templates", methods=["POST"])
def email_tpl_create():
    d = request.json or {}
    return jsonify(email_templates_mgr.create_template(g.user_id, d.get("name",""),
        d.get("subject",""), d.get("body",""), category=d.get("category","general")))

@app.route("/api/email/templates/<tid>", methods=["GET"])
def email_tpl_get(tid):
    t = email_templates_mgr.get_template(tid)
    return jsonify(t) if t else (jsonify({"error":"Not found"}), 404)

@app.route("/api/email/templates/<tid>", methods=["PUT"])
def email_tpl_update(tid):
    return jsonify(email_templates_mgr.update_template(tid, **(request.json or {})))

@app.route("/api/email/templates/<tid>", methods=["DELETE"])
def email_tpl_delete(tid):
    return jsonify(email_templates_mgr.delete_template(tid))

@app.route("/api/email/signature", methods=["GET"])
def email_sig_get():
    return jsonify({"signature": email_templates_mgr.get_signature(g.user_id)})

@app.route("/api/email/signature", methods=["POST"])
def email_sig_set():
    d = request.json or {}
    return jsonify(email_templates_mgr.set_signature(g.user_id, d.get("signature","")))

@app.route("/api/email/<eid>/schedule", methods=["POST"])
def email_schedule(eid):
    d = request.json or {}
    return jsonify(scheduled_emails.schedule(eid, d.get("send_at","")))

@app.route("/api/email/scheduled", methods=["GET"])
def email_scheduled_list():
    return jsonify({"scheduled": scheduled_emails.get_scheduled(g.user_id)})

@app.route("/api/email/<eid>/cancel-schedule", methods=["POST"])
def email_cancel_schedule(eid):
    return jsonify(scheduled_emails.cancel(eid))

# ── Hashtag Groups ──
@app.route("/api/social/hashtag-groups", methods=["GET"])
def hashtag_groups_list():
    return jsonify({"groups": hashtag_mgr.list_groups(g.user_id)})

@app.route("/api/social/hashtag-groups", methods=["POST"])
def hashtag_group_create():
    d = request.json or {}
    return jsonify(hashtag_mgr.create_group(g.user_id, d.get("name",""),
        d.get("hashtags",[]), platform=d.get("platform","all")))

@app.route("/api/social/hashtag-groups/<gid>", methods=["DELETE"])
def hashtag_group_delete(gid):
    return jsonify(hashtag_mgr.delete_group(gid))

# ── Post Approval Workflow ──
@app.route("/api/social/posts/<pid>/submit-approval", methods=["POST"])
def post_submit_approval(pid):
    return jsonify(post_approval.submit_for_approval(pid, g.user_id))

@app.route("/api/social/posts/<pid>/approve", methods=["POST"])
def post_approve(pid):
    return jsonify(post_approval.approve(pid, g.user_id))

@app.route("/api/social/posts/<pid>/reject", methods=["POST"])
def post_reject(pid):
    d = request.json or {}
    return jsonify(post_approval.reject(pid, g.user_id, reason=d.get("reason","")))

@app.route("/api/social/pending-approval", methods=["GET"])
def posts_pending_approval():
    return jsonify({"posts": post_approval.get_pending(g.user_id)})

# ═══════════════════════════════════════════════════════════════
# LAUNCH CRITICAL FIXES
# ═══════════════════════════════════════════════════════════════

# ── Plan Upgrade/Downgrade ──

@app.route("/api/billing/plan/preview", methods=["POST"])
def plan_change_preview():
    d = request.json or {}
    user = users.get_user(g.user_id)
    current = user.get("plan", "starter") if user else "starter"
    return jsonify(plan_changer.preview_change(current, d.get("new_plan", "")))

@app.route("/api/billing/plan/change", methods=["POST"])
def plan_change_execute():
    d = request.json or {}
    user = users.get_user(g.user_id)
    current = user.get("plan", "starter") if user else "starter"
    return jsonify(plan_changer.execute_change(g.user_id, d.get("new_plan", ""), current))

# ── Cancellation Flow ──

@app.route("/api/billing/cancel/preview", methods=["GET"])
def cancel_preview():
    return jsonify(cancel_mgr.preview_cancellation(g.user_id))

@app.route("/api/billing/cancel", methods=["POST"])
def cancel_subscription():
    d = request.json or {}
    if not d.get("reason"):
        return jsonify({"error": "reason required", "options": cancel_mgr.CANCEL_REASONS}), 400
    return jsonify(cancel_mgr.submit_cancellation(
        g.user_id, d["reason"], feedback=d.get("feedback", ""),
        would_return=d.get("would_return", "")))

@app.route("/api/billing/cancel/reactivate", methods=["POST"])
def cancel_reactivate():
    return jsonify(cancel_mgr.reactivate(g.user_id))

@app.route("/api/billing/cancel/analytics", methods=["GET"])
def cancel_analytics():
    return jsonify(cancel_mgr.get_churn_analytics())

# ── Conversation Folders ──

@app.route("/api/conversations/folders", methods=["GET"])
def conv_folders_list():
    return jsonify({"folders": conv_organizer.list_folders(g.user_id)})

@app.route("/api/conversations/folders", methods=["POST"])
def conv_folder_create():
    d = request.json or {}
    if not d.get("name"): return jsonify({"error": "name required"}), 400
    return jsonify(conv_organizer.create_folder(g.user_id, d["name"],
        color=d.get("color", "#94a3b8"), icon=d.get("icon", "📁")))

@app.route("/api/conversations/folders/<fid>", methods=["PUT"])
def conv_folder_rename(fid):
    d = request.json or {}
    return jsonify(conv_organizer.rename_folder(fid, d.get("name", "")))

@app.route("/api/conversations/folders/<fid>", methods=["DELETE"])
def conv_folder_delete(fid):
    return jsonify(conv_organizer.delete_folder(fid))

@app.route("/api/conversations/folders/<fid>/conversations", methods=["GET"])
def conv_folder_contents(fid):
    return jsonify({"conversations": conv_organizer.get_folder_conversations(fid, g.user_id)})

@app.route("/api/conversations/<cid>/move-to-folder", methods=["POST"])
def conv_move_to_folder(cid):
    d = request.json or {}
    return jsonify(conv_organizer.move_to_folder(cid, d.get("folder_id", "")))

@app.route("/api/conversations/<cid>/remove-from-folder", methods=["POST"])
def conv_remove_from_folder(cid):
    return jsonify(conv_organizer.remove_from_folder(cid))

@app.route("/api/conversations/bulk-delete", methods=["POST"])
def conv_bulk_delete():
    d = request.json or {}
    ids = d.get("conversation_ids", [])
    if not ids: return jsonify({"error": "conversation_ids required"}), 400
    return jsonify(conv_organizer.bulk_delete(g.user_id, ids))

@app.route("/api/conversations/bulk-archive", methods=["POST"])
def conv_bulk_archive():
    d = request.json or {}
    ids = d.get("conversation_ids", [])
    if not ids: return jsonify({"error": "conversation_ids required"}), 400
    return jsonify(conv_organizer.bulk_archive(g.user_id, ids))

# ── Spend Budget Alerts ──

@app.route("/api/spend/budget", methods=["GET"])
def spend_budget_get():
    return jsonify(spend_alerts.get_budget(g.user_id))

@app.route("/api/spend/budget", methods=["POST"])
def spend_budget_set():
    d = request.json or {}
    if not d.get("monthly_budget"): return jsonify({"error": "monthly_budget required"}), 400
    return jsonify(spend_alerts.set_budget(g.user_id, d["monthly_budget"],
        alert_at_pct=d.get("alert_at_pct", 80)))

@app.route("/api/spend/budget/check", methods=["GET"])
def spend_budget_check():
    """Check current spend against budget."""
    current = 0
    try:
        with get_db() as db:
            month_start = datetime.now().strftime("%Y-%m-01")
            row = db.execute(
                "SELECT COALESCE(SUM(cost),0) as t FROM cost_tracking WHERE user_id=? AND created_at>=?",
                (g.user_id, month_start)).fetchone()
            current = dict(row)["t"] if row else 0
    except:
        pass
    return jsonify(spend_alerts.check_budget(g.user_id, current))

@app.route("/api/spend/budget", methods=["DELETE"])
def spend_budget_delete():
    return jsonify(spend_alerts.delete_budget(g.user_id))

# ═══════════════════════════════════════════════════════════════
# EDUCATION — Age-Adaptive Theme Engine
# ═══════════════════════════════════════════════════════════════

@app.route("/api/education/themes", methods=["GET"])
def edu_themes_list():
    """Get all available education themes with previews."""
    return jsonify({"themes": edu_theme.get_all_themes()})

@app.route("/api/education/theme", methods=["GET"])
def edu_theme_get():
    """Get theme for a specific age or age group."""
    age = request.args.get("age")
    group = request.args.get("group")
    if age:
        return jsonify(edu_theme.get_theme(age=int(age)))
    elif group:
        return jsonify(edu_theme.get_theme(age_group=group))
    return jsonify({"error": "Provide age or group parameter"}), 400

@app.route("/api/education/theme/css", methods=["GET"])
def edu_theme_css():
    """Get CSS variables for the theme — inject into page."""
    age = request.args.get("age")
    group = request.args.get("group")
    css = edu_theme.get_css_variables(
        age=int(age) if age else None,
        age_group=group)
    return Response(css, mimetype="text/css")

@app.route("/api/education/theme/ai-personality", methods=["GET"])
def edu_ai_personality():
    """Get AI personality instructions for this age group."""
    age = request.args.get("age")
    group = request.args.get("group")
    return jsonify(edu_theme.get_ai_personality(
        age=int(age) if age else None, age_group=group))

@app.route("/api/education/theme/translate", methods=["GET"])
def edu_translate():
    """Translate a UI string to age-appropriate language."""
    key = request.args.get("key", "")
    age = request.args.get("age")
    group = request.args.get("group")
    return jsonify({"key": key,
        "text": edu_theme.translate_ui(key, age=int(age) if age else None, age_group=group)})

@app.route("/api/education/i18n", methods=["GET"])
def edu_i18n_get():
    """Get full translation set for language + age group."""
    lang = request.args.get("lang", "en")
    age = request.args.get("age")
    group = request.args.get("group", "high_school")
    if age:
        group = edu_theme.get_age_group(int(age))
    return jsonify(edu_i18n.get_translation(lang, group))

@app.route("/api/education/i18n/ai-instruction", methods=["GET"])
def edu_i18n_ai():
    """Get AI personality instruction in target language."""
    lang = request.args.get("lang", "en")
    age = request.args.get("age")
    group = request.args.get("group", "high_school")
    if age:
        group = edu_theme.get_age_group(int(age))
    return jsonify({"instruction": edu_i18n.get_ai_instruction(lang, group)})

@app.route("/api/education/i18n/languages", methods=["GET"])
def edu_languages():
    """Get all supported languages for education."""
    return jsonify({"languages": edu_i18n.get_supported_languages()})

@app.route("/api/education/culture/theme", methods=["GET"])
def edu_cultural_theme():
    """Get full cultural theme: age + language merged."""
    age = request.args.get("age")
    group = request.args.get("group", "high_school")
    lang = request.args.get("lang", "en")
    if age:
        group = edu_theme.get_age_group(int(age))
    return jsonify(cultural_theme.get_full_cultural_theme(group, lang))

@app.route("/api/education/culture/mascot", methods=["GET"])
def edu_mascot():
    """Get mascot for age group + culture."""
    age = request.args.get("age")
    group = request.args.get("group", "high_school")
    lang = request.args.get("lang", "en")
    if age:
        group = edu_theme.get_age_group(int(age))
    return jsonify(cultural_theme.get_mascot(group, lang))

@app.route("/api/education/culture/mascots", methods=["GET"])
def edu_all_mascots():
    """Get all mascot definitions."""
    return jsonify({"mascots": cultural_theme.get_all_mascots()})

@app.route("/api/education/culture/regions", methods=["GET"])
def edu_all_cultures():
    """Get all cultural overlay definitions."""
    return jsonify({"cultures": cultural_theme.get_all_cultures()})

# ═══════════════════════════════════════════════════════════════
# VOICE SETUP CONCIERGE
# ═══════════════════════════════════════════════════════════════

@app.route("/api/setup/start", methods=["POST"])
def setup_start():
    """Start a guided setup session. Send a message or specify an intent."""
    d = request.json or {}
    return jsonify(setup_concierge.start_session(
        g.user_id, intent=d.get("intent"), user_message=d.get("message", "")))

@app.route("/api/setup/respond", methods=["POST"])
def setup_respond():
    """Send user's response to advance the setup flow."""
    d = request.json or {}
    if not d.get("session_id") or not d.get("response"):
        return jsonify({"error": "session_id and response required"}), 400
    return jsonify(setup_concierge.respond(d["session_id"], g.user_id, d["response"]))

@app.route("/api/setup/session/<sid>", methods=["GET"])
def setup_session_get(sid):
    """Get current state of a setup session."""
    s = setup_concierge.get_session(sid)
    return jsonify(s) if s else (jsonify({"error": "Not found"}), 404)

@app.route("/api/setup/detect-intent", methods=["POST"])
def setup_detect():
    """Detect what the user wants to set up from their message."""
    d = request.json or {}
    return jsonify(detect_setup_intent(d.get("message", "")))

@app.route("/api/admin/production-readiness", methods=["GET"])
def production_readiness():
    """Check if the platform is ready for production deployment."""
    return jsonify(production_readiness_check())

# ═══════════════════════════════════════════════════════════════
# INDISPENSABLE FEATURES — Daily Briefing, Quick Capture,
# Workflow Automation, Content Repurposing, Smart Reminders,
# Client 360° Snapshot
# ═══════════════════════════════════════════════════════════════

@app.route("/api/briefing", methods=["GET"])
def get_daily_briefing():
    return jsonify(daily_briefing.generate(g.user_id))

@app.route("/api/capture", methods=["POST"])
def quick_capture_submit():
    d = request.json or {}
    if not d.get("text"): return jsonify({"error": "text required"}), 400
    return jsonify(quick_capture.capture(g.user_id, d["text"]))

@app.route("/api/capture/history", methods=["GET"])
def quick_capture_history():
    return jsonify({"captures": quick_capture.list_captures(g.user_id)})

@app.route("/api/automations", methods=["GET"])
def automations_list():
    return jsonify({"workflows": workflow_automation.list_workflows(g.user_id)})

@app.route("/api/automations/templates", methods=["GET"])
def automation_templates():
    return jsonify({"templates": workflow_automation.get_templates()})

@app.route("/api/automations", methods=["POST"])
def automation_create():
    d = request.json or {}
    return jsonify(workflow_automation.create_workflow(
        g.user_id, d.get("name", ""), d.get("trigger", ""),
        conditions=d.get("conditions"), actions=d.get("actions"),
        template=d.get("template")))

@app.route("/api/automations/<wid>/toggle", methods=["POST"])
def automation_toggle(wid):
    return jsonify(workflow_automation.toggle_workflow(wid))

@app.route("/api/automations/<wid>", methods=["DELETE"])
def automation_delete(wid):
    return jsonify(workflow_automation.delete_workflow(wid))

@app.route("/api/content/repurpose", methods=["POST"])
def content_repurpose():
    d = request.json or {}
    if not d.get("content"): return jsonify({"error": "content required"}), 400
    return jsonify(content_repurposer.build_repurpose_prompt(
        d["content"], content_type=d.get("type", "blog_post"),
        platforms=d.get("platforms"), tone=d.get("tone", "professional"),
        audience=d.get("audience", "")))

@app.route("/api/reminders", methods=["GET"])
def smart_reminders_get():
    return jsonify({"reminders": smart_reminders.generate_reminders(g.user_id)})

@app.route("/api/crm/contacts/<cid>/snapshot", methods=["GET"])
def contact_snapshot(cid):
    return jsonify(client_snapshot.get_snapshot(g.user_id, cid))

# ═══════════════════════════════════════════════════════════════
# LIFESTYLE INTELLIGENCE — Weekly rhythms, preferences, patterns
# ═══════════════════════════════════════════════════════════════

@app.route("/api/lifestyle/preferences/schema", methods=["GET"])
def lifestyle_pref_schema():
    return jsonify({"categories": lifestyle.get_preference_schema()})

@app.route("/api/lifestyle/preferences", methods=["GET"])
def lifestyle_prefs_get():
    category = request.args.get("category")
    return jsonify({"preferences": lifestyle.get_preferences(g.user_id, category)})

@app.route("/api/lifestyle/preferences/<category>", methods=["POST"])
def lifestyle_prefs_set(category):
    d = request.json or {}
    return jsonify(lifestyle.set_preferences(g.user_id, category, d))

@app.route("/api/lifestyle/rhythm", methods=["GET"])
def lifestyle_rhythm_get():
    return jsonify({"week": lifestyle.get_week_rhythm(g.user_id)})

@app.route("/api/lifestyle/rhythm/today", methods=["GET"])
def lifestyle_rhythm_today():
    return jsonify(lifestyle.get_today_rhythm(g.user_id))

@app.route("/api/lifestyle/rhythm/<day>", methods=["POST"])
def lifestyle_rhythm_set(day):
    d = request.json or {}
    return jsonify(lifestyle.set_day_rhythm(g.user_id, day, d))

@app.route("/api/lifestyle/briefing", methods=["GET"])
def lifestyle_briefing():
    return jsonify(lifestyle.build_contextual_briefing(g.user_id))

@app.route("/api/lifestyle/patterns", methods=["GET"])
def lifestyle_patterns():
    return jsonify(lifestyle.get_patterns(g.user_id))

@app.route("/api/lifestyle/patterns/log", methods=["POST"])
def lifestyle_pattern_log():
    d = request.json or {}
    return jsonify(lifestyle.log_activity_pattern(g.user_id,
        d.get("activity_type", ""), context=d.get("context")))

@app.route("/api/lifestyle/suggestions", methods=["GET"])
def lifestyle_suggestions():
    return jsonify({"suggestions": lifestyle.get_proactive_suggestions(g.user_id)})

@app.route("/api/lifestyle/feedback", methods=["POST"])
def lifestyle_feedback():
    d = request.json or {}
    return jsonify(lifestyle.rate_suggestion(g.user_id,
        d.get("type", ""), d.get("id", ""), d.get("rating", 3),
        feedback=d.get("feedback", "")))

@app.route("/api/lifestyle/feedback/summary", methods=["GET"])
def lifestyle_feedback_summary():
    return jsonify(lifestyle.get_feedback_summary(g.user_id))

# ═══════════════════════════════════════════════════════════════
# SAFE INTEGRATIONS (Read-Only)
# ═══════════════════════════════════════════════════════════════

@app.route("/api/integrations", methods=["GET"])
def integrations_list():
    return jsonify({"connections": calendar_reader.list_connections(g.user_id)})

@app.route("/api/integrations/google-calendar", methods=["POST"])
def connect_google_cal():
    d = request.json or {}
    return jsonify(calendar_reader.connect_google(g.user_id, d.get("access_token",""), d.get("refresh_token","")))

@app.route("/api/integrations/outlook-calendar", methods=["POST"])
def connect_outlook_cal():
    d = request.json or {}
    return jsonify(calendar_reader.connect_outlook(g.user_id, d.get("access_token",""), d.get("refresh_token","")))

@app.route("/api/integrations/<cid>", methods=["DELETE"])
def disconnect_integration(cid):
    return jsonify(calendar_reader.disconnect(g.user_id, cid))

@app.route("/api/calendar/today", methods=["GET"])
def calendar_today():
    return jsonify(calendar_reader.get_today_events(g.user_id))

@app.route("/api/calendar/upcoming", methods=["GET"])
def calendar_upcoming():
    days = int(request.args.get("days", 7))
    return jsonify(calendar_reader.get_upcoming(g.user_id, days))

@app.route("/api/calendar/next-meeting", methods=["GET"])
def calendar_next():
    return jsonify(calendar_reader.get_next_meeting(g.user_id))

@app.route("/api/email/inbox-summary", methods=["GET"])
def email_inbox_summary():
    return jsonify(email_reader.get_inbox_summary(g.user_id))

@app.route("/api/flights", methods=["GET"])
def flights_list():
    return jsonify({"flights": flight_tracker.get_flights(g.user_id)})

@app.route("/api/flights", methods=["POST"])
def flight_add():
    d = request.json or {}
    return jsonify(flight_tracker.add_flight(g.user_id, d.get("flight_number",""),
        date=d.get("date",""), airline=d.get("airline",""),
        confirmation=d.get("confirmation",""), notes=d.get("notes","")))

@app.route("/api/flights/<fid>", methods=["DELETE"])
def flight_remove(fid):
    return jsonify(flight_tracker.remove_flight(fid))

@app.route("/api/flights/status/<flight_number>", methods=["GET"])
def flight_status(flight_number):
    return jsonify(flight_tracker.check_status(flight_number))

@app.route("/api/weather", methods=["GET"])
def weather_get():
    return jsonify(weather_svc.get_weather(
        location=request.args.get("location",""),
        lat=float(request.args.get("lat",0)) or None,
        lon=float(request.args.get("lon",0)) or None))

@app.route("/api/commute", methods=["GET"])
def commute_get():
    return jsonify(commute_est.estimate(
        request.args.get("origin",""), request.args.get("destination","")))

# ═══════════════════════════════════════════════════════════════
# UX ESSENTIALS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/search", methods=["GET"])
def universal_search():
    return jsonify(global_search.search(g.user_id,
        request.args.get("q",""), entity_filter=request.args.get("type")))

@app.route("/api/favorites", methods=["GET"])
def favorites_list():
    return jsonify({"favorites": favorites_mgr.list(g.user_id)})

@app.route("/api/favorites", methods=["POST"])
def favorite_add():
    d = request.json or {}
    return jsonify(favorites_mgr.add(g.user_id, d.get("type",""), d.get("id",""),
        label=d.get("label",""), icon=d.get("icon","")))

@app.route("/api/favorites", methods=["DELETE"])
def favorite_remove():
    d = request.json or {}
    return jsonify(favorites_mgr.remove(g.user_id, d.get("type",""), d.get("id","")))

@app.route("/api/favorites/reorder", methods=["POST"])
def favorites_reorder():
    d = request.json or {}
    return jsonify(favorites_mgr.reorder(g.user_id, d.get("ids",[])))

@app.route("/api/feed", methods=["GET"])
def activity_feed_get():
    return jsonify({"feed": activity_feed.get_feed(g.user_id,
        entity_type=request.args.get("type"))})

@app.route("/api/notes", methods=["GET"])
def notes_list():
    return jsonify({"notes": scratch_pad.list(g.user_id)})

@app.route("/api/notes", methods=["POST"])
def note_create():
    d = request.json or {}
    return jsonify(scratch_pad.create(g.user_id, title=d.get("title",""),
        content=d.get("content",""), color=d.get("color","#FEF3C7"),
        pinned=d.get("pinned",False)))

@app.route("/api/notes/<nid>", methods=["GET"])
def note_get(nid):
    n = scratch_pad.get(nid)
    return jsonify(n) if n else (jsonify({"error":"Not found"}), 404)

@app.route("/api/notes/<nid>", methods=["PUT"])
def note_update(nid):
    d = request.json or {}
    return jsonify(scratch_pad.update(nid, title=d.get("title"),
        content=d.get("content"), color=d.get("color"), pinned=d.get("pinned")))

@app.route("/api/notes/<nid>", methods=["DELETE"])
def note_delete(nid):
    return jsonify(scratch_pad.delete(nid))

@app.route("/api/booking-links", methods=["GET"])
def booking_links_list():
    return jsonify({"links": booking_links.list_links(g.user_id)})

@app.route("/api/booking-links", methods=["POST"])
def booking_link_create():
    d = request.json or {}
    return jsonify(booking_links.create_link(g.user_id, d.get("name","Meeting"),
        duration_minutes=d.get("duration",30), description=d.get("description",""),
        availability=d.get("availability"), questions=d.get("questions")))

@app.route("/book/<slug>", methods=["GET"])
def booking_page(slug):
    link = booking_links.get_link(slug)
    if not link: return jsonify({"error":"Booking link not found"}), 404
    return jsonify({"booking_page": link})

@app.route("/book/<slug>/submit", methods=["POST"])
def booking_submit(slug):
    d = request.json or {}
    return jsonify(booking_links.submit_booking(slug, d.get("name",""),
        d.get("email",""), d.get("time",""), answers=d.get("answers")))

@app.route("/api/booking-requests", methods=["GET"])
def booking_requests_list():
    return jsonify({"requests": booking_links.get_requests(g.user_id,
        status=request.args.get("status","pending"))})

@app.route("/api/booking-requests/<bid>/confirm", methods=["POST"])
def booking_confirm(bid):
    return jsonify(booking_links.confirm_booking(bid))

@app.route("/api/booking-requests/<bid>/decline", methods=["POST"])
def booking_decline(bid):
    d = request.json or {}
    return jsonify(booking_links.decline_booking(bid, reason=d.get("reason","")))

@app.route("/api/commands", methods=["GET"])
def command_palette():
    return jsonify({"commands": cmd_palette.get_commands(request.args.get("q",""))})

# ═══════════════════════════════════════════════════════════════
# BUSINESS INTELLIGENCE
# ═══════════════════════════════════════════════════════════════

@app.route("/api/bi/win-loss", methods=["GET"])
def bi_win_loss():
    days = int(request.args.get("days", 90))
    return jsonify(win_loss.get_analysis(g.user_id, period_days=days))

@app.route("/api/bi/win-loss/log", methods=["POST"])
def bi_win_loss_log():
    d = request.json or {}
    return jsonify(win_loss.log_outcome(d.get("deal_id",""), d.get("outcome",""),
        reason=d.get("reason",""), competitor=d.get("competitor",""),
        notes=d.get("notes",""), feedback=d.get("feedback","")))

@app.route("/api/bi/health-scores", methods=["GET"])
def bi_health_scores():
    return jsonify(health_scorer.score_all_contacts(g.user_id))

@app.route("/api/bi/health-score/<cid>", methods=["GET"])
def bi_health_score(cid):
    return jsonify(health_scorer.score_contact(cid))

@app.route("/api/bi/forecast", methods=["GET"])
def bi_forecast():
    months = int(request.args.get("months", 3))
    return jsonify(revenue_forecast.forecast(g.user_id, months))

@app.route("/api/bi/time-to-close", methods=["GET"])
def bi_time_to_close():
    return jsonify(ttc_tracker.get_metrics(g.user_id))

@app.route("/api/bi/activity-scores", methods=["GET"])
def bi_activity_scores():
    return jsonify(activity_scorer.score_pipeline(g.user_id))

@app.route("/api/bi/activity-score/<did>", methods=["GET"])
def bi_activity_score(did):
    return jsonify(activity_scorer.score_deal(did))

# ═══════════════════════════════════════════════════════════════
# UNDO SYSTEM
# ═══════════════════════════════════════════════════════════════

@app.route("/api/undo/pending", methods=["GET"])
def undo_pending():
    return jsonify({"pending": undo_mgr.get_pending(g.user_id)})

@app.route("/api/undo/<uid>", methods=["POST"])
def undo_execute(uid):
    return jsonify(undo_mgr.execute_undo(uid, g.user_id))

# ═══════════════════════════════════════════════════════════════
# TEXT / SMS LOG
# ═══════════════════════════════════════════════════════════════

@app.route("/api/texts", methods=["GET"])
def texts_list():
    return jsonify({"texts": text_log.get_log(g.user_id,
        contact_id=request.args.get("contact_id",""))})

@app.route("/api/texts", methods=["POST"])
def text_log_add():
    d = request.json or {}
    return jsonify(text_log.log_text(g.user_id, contact_id=d.get("contact_id",""),
        contact_name=d.get("contact_name",""), phone_number=d.get("phone",""),
        direction=d.get("direction","outbound"), content=d.get("content",""),
        notes=d.get("notes","")))

# ═══════════════════════════════════════════════════════════════
# BYOK — Bring Your Own Key
# ═══════════════════════════════════════════════════════════════

@app.route("/api/keys", methods=["GET"])
def byok_list():
    return jsonify({"keys": byok.list_keys(g.user_id)})

@app.route("/api/keys/providers", methods=["GET"])
def byok_providers():
    return jsonify({"providers": SUPPORTED_PROVIDERS})

@app.route("/api/keys/setup-guide", methods=["GET"])
def byok_guide():
    return jsonify({"guide": byok.get_setup_guide()})

@app.route("/api/keys/<provider>", methods=["POST"])
def byok_add(provider):
    d = request.json or {}
    if not d.get("api_key"): return jsonify({"error": "api_key required"}), 400
    return jsonify(byok.add_key(g.user_id, provider, d["api_key"],
        label=d.get("label",""), preferred_model=d.get("model","")))

@app.route("/api/keys/<provider>", methods=["DELETE"])
def byok_remove(provider):
    return jsonify(byok.remove_key(g.user_id, provider))

@app.route("/api/keys/<provider>/test", methods=["POST"])
def byok_test(provider):
    return jsonify(byok.test_key(g.user_id, provider))

@app.route("/api/keys/<provider>/model", methods=["PUT"])
def byok_model(provider):
    d = request.json or {}
    return jsonify(byok.set_preferred_model(g.user_id, provider, d.get("model","")))

@app.route("/api/keys/preferred", methods=["GET"])
def byok_preferred():
    return jsonify(byok.get_preferred_provider(g.user_id))

@app.route("/api/keys/has-key", methods=["GET"])
def byok_has_key():
    return jsonify({"has_key": byok.has_any_key(g.user_id)})

@app.route("/api/usage", methods=["GET"])
def usage_summary():
    days = int(request.args.get("days", 30))
    return jsonify(byok.get_usage_summary(g.user_id, days))

# ═══════════════════════════════════════════════════════════════
# PLATFORM KEY GOVERNANCE (Owner only)
# ═══════════════════════════════════════════════════════════════

@app.route("/api/admin/platform-keys/policy", methods=["GET"])
def platform_key_policy_get():
    return jsonify(platform_key_policy.get_policy_summary())

@app.route("/api/admin/platform-keys/approvals", methods=["GET"])
def platform_key_approvals():
    return jsonify({"approvals": platform_key_policy.get_approved_use_cases()})

@app.route("/api/admin/platform-keys/approve", methods=["POST"])
def platform_key_approve():
    d = request.json or {}
    return jsonify(platform_key_policy.approve_use_case(
        g.user_id, d.get("use_case",""), d.get("description",""),
        max_calls_per_day=d.get("max_calls",50),
        max_cost_per_day=d.get("max_cost",1.0)))

@app.route("/api/admin/platform-keys/revoke/<aid>", methods=["POST"])
def platform_key_revoke(aid):
    return jsonify(platform_key_policy.revoke_use_case(g.user_id, aid))

@app.route("/api/admin/platform-keys/audit", methods=["GET"])
def platform_key_audit():
    days = int(request.args.get("days", 30))
    return jsonify(platform_key_policy.get_audit_log(g.user_id, days))

# ═══════════════════════════════════════════════════════════════
# PROVIDER RESILIENCE
# ═══════════════════════════════════════════════════════════════

@app.route("/api/providers/all", methods=["GET"])
def providers_all():
    return jsonify(provider_resilience.get_all_providers())

@app.route("/api/providers/open-source", methods=["GET"])
def providers_open_source():
    return jsonify({"providers": OPEN_SOURCE_PROVIDERS})

@app.route("/api/providers/fallback-chain", methods=["GET"])
def providers_fallback():
    return jsonify({"chain": provider_resilience.get_fallback_chain(g.user_id)})

@app.route("/api/providers/independence-report", methods=["GET"])
def providers_independence():
    return jsonify(provider_resilience.get_independence_report())

BETA_CAP = 100  # Maximum beta users

@app.route("/api/waitlist", methods=["POST"])
def waitlist_join():
    d = request.json or {}
    email = d.get("email", "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400
    import uuid
    wid = f"wl_{uuid.uuid4().hex[:8]}"
    ref = d.get("ref", "")
    try:
        from core.database import get_db
        with get_db() as db:
            # Check beta cap
            count = db.execute("SELECT COUNT(*) as c FROM beta_waitlist").fetchone()
            current = dict(count)["c"]
            if current >= BETA_CAP:
                # Still capture email for general waitlist but mark as overflow
                db.execute("INSERT OR IGNORE INTO beta_waitlist (id,email,referral_code,source) VALUES (?,?,?,?)",
                          (wid, email, ref, "waitlist_overflow"))
                return jsonify({"joined": True, "waitlisted": True, "position": current + 1,
                    "message": f"Beta is full ({BETA_CAP} spots taken). You\'re #{current + 1} on the waitlist — we\'ll notify you when spots open."})
            # Check for duplicate
            existing = db.execute("SELECT id FROM beta_waitlist WHERE email=?", (email,)).fetchone()
            if existing:
                return jsonify({"joined": False, "message": "You\'re already on the list!"})
            db.execute("INSERT INTO beta_waitlist (id,email,referral_code,source) VALUES (?,?,?,?)",
                      (wid, email, ref, d.get("source", "website")))
            position = current + 1
            spots_left = BETA_CAP - position
            return jsonify({"joined": True, "position": position, "spots_left": spots_left,
                "message": f"You\'re in! Spot #{position} of {BETA_CAP}. {spots_left} spots remaining."})
    except Exception as e:
        return jsonify({"joined": True, "message": "You\'re on the list!"})

@app.route("/api/waitlist/status", methods=["GET"])
def waitlist_status():
    """Public endpoint — how many spots are left."""
    try:
        from core.database import get_db
        with get_db() as db:
            count = db.execute("SELECT COUNT(*) as c FROM beta_waitlist WHERE source!=\'waitlist_overflow\'").fetchone()
            current = dict(count)["c"]
        return jsonify({"total_spots": BETA_CAP, "taken": current,
            "remaining": max(0, BETA_CAP - current), "full": current >= BETA_CAP})
    except:
        return jsonify({"total_spots": BETA_CAP, "remaining": "unknown"})

# ═══════════════════════════════════════════════════════════════
# NICE-TO-HAVE FEATURES
# ═══════════════════════════════════════════════════════════════

@app.route("/api/webhooks/outbound", methods=["GET"])
def webhooks_outbound_list():
    return jsonify({"webhooks": outbound_hooks.list_webhooks(g.user_id)})

@app.route("/api/webhooks/outbound", methods=["POST"])
def webhook_outbound_create():
    d = request.json or {}
    return jsonify(outbound_hooks.register_webhook(g.user_id, d.get("url",""),
        d.get("events",[]), name=d.get("name",""), secret=d.get("secret","")))

@app.route("/api/webhooks/outbound/<wid>", methods=["DELETE"])
def webhook_outbound_delete(wid):
    return jsonify(outbound_hooks.delete_webhook(wid))

@app.route("/api/webhooks/outbound/<wid>/toggle", methods=["POST"])
def webhook_outbound_toggle(wid):
    return jsonify(outbound_hooks.toggle_webhook(wid))

@app.route("/api/webhooks/outbound/events", methods=["GET"])
def webhook_event_types():
    return jsonify({"events": outbound_hooks.get_event_types()})

@app.route("/api/tasks/<tid>/dependencies", methods=["GET"])
def task_deps_get(tid):
    return jsonify({"blockers": task_deps.get_blockers(tid),
                    "blocking": task_deps.get_blocking(tid),
                    "is_blocked": task_deps.is_blocked(tid)})

@app.route("/api/tasks/<tid>/dependencies", methods=["POST"])
def task_dep_add(tid):
    d = request.json or {}
    return jsonify(task_deps.add_dependency(tid, d.get("blocked_by","")))

@app.route("/api/tasks/<tid>/dependencies", methods=["DELETE"])
def task_dep_remove(tid):
    d = request.json or {}
    return jsonify(task_deps.remove_dependency(tid, d.get("blocked_by","")))

@app.route("/api/tasks/recurring", methods=["GET"])
def recurring_tasks_list():
    return jsonify({"recurring": recurring_tasks.list_recurring(g.user_id)})

@app.route("/api/tasks/recurring", methods=["POST"])
def recurring_task_create():
    d = request.json or {}
    return jsonify(recurring_tasks.create_recurring(g.user_id, d.get("project_id",""),
        d.get("title",""), frequency=d.get("frequency","weekly"),
        priority=d.get("priority","medium"), assigned_to=d.get("assigned_to","")))

@app.route("/api/tasks/recurring/generate", methods=["POST"])
def recurring_tasks_generate():
    return jsonify(recurring_tasks.generate_due_tasks(g.user_id))

@app.route("/api/tasks/recurring/<rid>/toggle", methods=["POST"])
def recurring_task_toggle(rid):
    return jsonify(recurring_tasks.toggle_recurring(rid))

@app.route("/api/tasks/recurring/<rid>", methods=["DELETE"])
def recurring_task_delete(rid):
    return jsonify(recurring_tasks.delete_recurring(rid))

@app.route("/api/invoices/late-fees/policy", methods=["GET"])
def late_fee_policy_get():
    return jsonify(late_fees.get_policy(g.user_id))

@app.route("/api/invoices/late-fees/policy", methods=["POST"])
def late_fee_policy_set():
    d = request.json or {}
    return jsonify(late_fees.set_policy(g.user_id, fee_type=d.get("type","percentage"),
        fee_value=d.get("value",1.5), grace_period_days=d.get("grace_days",5)))

@app.route("/api/invoices/late-fees", methods=["GET"])
def late_fees_calculate():
    return jsonify({"fees": late_fees.calculate_fees(g.user_id)})

@app.route("/api/demo/generate", methods=["POST"])
def demo_generate():
    return jsonify(demo_data.generate(g.user_id))

@app.route("/api/demo/clear", methods=["POST"])
def demo_clear():
    return jsonify(demo_data.clear_demo(g.user_id))

@app.route("/api/settings/theme", methods=["GET"])
def theme_get():
    return jsonify(theme_pref.get_theme(g.user_id))

@app.route("/api/settings/theme", methods=["POST"])
def theme_set():
    d = request.json or {}
    return jsonify(theme_pref.set_theme(g.user_id, theme=d.get("theme","light"),
        accent_color=d.get("accent","#A459F2")))

@app.route("/api/help/<feature>", methods=["GET"])
def help_tooltip(feature):
    return jsonify(help_system.get_tooltip(feature))

@app.route("/api/help", methods=["GET"])
def help_all():
    q = request.args.get("q","")
    if q:
        return jsonify({"results": help_system.search_help(q)})
    return jsonify({"tooltips": help_system.get_all_tooltips()})

@app.route("/api/whatsapp", methods=["GET"])
def whatsapp_list():
    return jsonify({"messages": whatsapp_log.get_log(g.user_id,
        contact_id=request.args.get("contact_id",""))})

@app.route("/api/whatsapp", methods=["POST"])
def whatsapp_add():
    d = request.json or {}
    return jsonify(whatsapp_log.log_message(g.user_id, contact_id=d.get("contact_id",""),
        contact_name=d.get("contact_name",""), phone_number=d.get("phone",""),
        direction=d.get("direction","outbound"), content=d.get("content",""),
        has_media=d.get("has_media",False), notes=d.get("notes","")))

# ── Pedagogy Engine ──

@app.route("/api/education/pedagogy/methods", methods=["GET"])
def pedagogy_methods():
    """List all available teaching methodologies."""
    return jsonify({"methods": pedagogy.get_available_methods()})

@app.route("/api/education/pedagogy/methods/<mid>", methods=["GET"])
def pedagogy_method_detail(mid):
    return jsonify(pedagogy.get_method_detail(mid))

@app.route("/api/education/pedagogy/curricula", methods=["GET"])
def pedagogy_curricula():
    return jsonify({"curricula": pedagogy.get_all_curricula()})

@app.route("/api/education/pedagogy/curricula/<country>", methods=["GET"])
def pedagogy_curriculum(country):
    return jsonify(pedagogy.get_curriculum(country.upper()))

@app.route("/api/education/pedagogy/profile", methods=["POST"])
def pedagogy_profile():
    """Build a student's pedagogical profile based on location + culture."""
    d = request.json or {}
    return jsonify(pedagogy.get_profile(
        d.get("location", "US"), cultural_background=d.get("cultural_background", ""),
        preferred_method=d.get("preferred_method", ""), age=d.get("age", 10)))

@app.route("/api/education/pedagogy/ai-instruction", methods=["POST"])
def pedagogy_ai_instruction():
    """Get the AI teaching instruction for a student's profile."""
    d = request.json or {}
    return jsonify({"instruction": pedagogy.build_ai_instruction(
        d.get("location", "US"), cultural_background=d.get("cultural_background", ""),
        preferred_method=d.get("preferred_method", ""), age=d.get("age", 10))})

# ── Education Pedagogy Engine ──

@app.route("/api/education/methods", methods=["GET"])
def edu_methods():
    """Get all available teaching methodologies."""
    return jsonify({"methods": pedagogy.get_methods()})

@app.route("/api/education/curricula", methods=["GET"])
def edu_curricula():
    """Get all supported curriculum systems by country."""
    return jsonify({"curricula": pedagogy.get_curricula()})

@app.route("/api/education/curricula/<country>/methods", methods=["GET"])
def edu_country_methods(country):
    """Get compatible teaching methods for a country."""
    return jsonify({"methods": pedagogy.get_compatible_methods(country.upper())})

@app.route("/api/education/pedagogy", methods=["POST"])
def edu_pedagogy_profile():
    """Build a personalized pedagogy profile for a student."""
    d = request.json or {}
    return jsonify(pedagogy.get_student_pedagogy(
        d.get("current_country", "US"),
        cultural_background=d.get("cultural_background", ""),
        preferred_methods=d.get("preferred_methods"),
        age=d.get("age", 10), subject=d.get("subject", "math"),
        learning_style=d.get("learning_style", "")))

@app.route("/api/education/pedagogy/ai-instruction", methods=["POST"])
def edu_pedagogy_instruction():
    """Build complete AI instruction for a student's pedagogy profile."""
    d = request.json or {}
    return jsonify({"instruction": pedagogy.build_ai_instruction(
        d.get("current_country", "US"),
        cultural_background=d.get("cultural_background", ""),
        preferred_methods=d.get("preferred_methods"),
        age=d.get("age", 10), subject=d.get("subject", "math"),
        learning_style=d.get("learning_style", ""))})

# ── Teaching Methods ──

@app.route("/api/education/teaching-methods", methods=["GET"])
def edu_methods_list():
    return jsonify({"methods": teaching_methods.get_methods()})

@app.route("/api/education/students/<sid>/teaching-method", methods=["GET"])
def edu_student_method_get(sid):
    return jsonify(teaching_methods.get_student_method(sid))

@app.route("/api/education/students/<sid>/teaching-method", methods=["POST"])
def edu_student_method_set(sid):
    d = request.json or {}
    return jsonify(teaching_methods.set_student_method(sid, d.get("method", "socratic")))

@app.route("/api/education/teaching-methods/recommend", methods=["POST"])
def edu_method_recommend():
    d = request.json or {}
    return jsonify(teaching_methods.recommend_method(
        d.get("grade", ""), d.get("subject", ""), d.get("learning_style", "")))

# ── Curriculum Standards ──

@app.route("/api/education/curriculum/standards", methods=["GET"])
def edu_standards_list():
    return jsonify({"standards": curriculum_mgr.get_standards()})

@app.route("/api/education/curriculum/standards/<sid>", methods=["GET"])
def edu_standard_get(sid):
    s = curriculum_mgr.get_standard(sid)
    return jsonify(s) if s else (jsonify({"error": "Not found"}), 404)

@app.route("/api/education/students/<sid>/standards", methods=["GET"])
def edu_student_standards_get(sid):
    return jsonify({"standards": curriculum_mgr.get_student_standards(sid)})

@app.route("/api/education/students/<sid>/standards", methods=["POST"])
def edu_student_standards_set(sid):
    d = request.json or {}
    return jsonify(curriculum_mgr.set_student_standards(sid, d.get("standards", [])))

# ── Enhanced Parent Dashboard ──

@app.route("/api/education/parent-dashboard", methods=["GET"])
def edu_parent_dash():
    return jsonify(parent_dashboard.get_full_dashboard(g.user_id))

@app.route("/api/education/students/<sid>/progress-report", methods=["GET"])
def edu_progress_report(sid):
    period = request.args.get("period", "month")
    return jsonify(parent_dashboard.get_progress_report(sid, period))

# ── Test Prep ──

@app.route("/api/education/test-prep/programs", methods=["GET"])
def edu_test_programs():
    return jsonify({"programs": test_prep.get_programs()})

@app.route("/api/education/test-prep/programs/<pid>", methods=["GET"])
def edu_test_program_get(pid):
    p = test_prep.get_program(pid)
    return jsonify(p) if p else (jsonify({"error": "Not found"}), 404)

@app.route("/api/education/test-prep/practice", methods=["POST"])
def edu_test_practice():
    d = request.json or {}
    return jsonify(test_prep.start_practice_session(
        d.get("student_id", ""), d.get("program", ""),
        d.get("section", ""), question_count=d.get("count", 10)))

@app.route("/api/education/test-prep/<session_id>/result", methods=["POST"])
def edu_test_result(session_id):
    d = request.json or {}
    return jsonify(test_prep.record_result(
        session_id, d.get("correct", 0), d.get("total", 0),
        time_seconds=d.get("time_seconds", 0)))

@app.route("/api/education/test-prep/history/<student_id>", methods=["GET"])
def edu_test_history(student_id):
    return jsonify({"history": test_prep.get_score_history(
        student_id, program=request.args.get("program"))})

@app.route("/api/education/test-prep/predict/<student_id>/<program>", methods=["GET"])
def edu_test_predict(student_id, program):
    return jsonify(test_prep.get_predicted_score(student_id, program))

# ═══════════════════════════════════════════════════════════════
# EDUCATION SUITE — Parent Dashboard, Curriculum, Reports, Gamification
# ═══════════════════════════════════════════════════════════════

# ── Enhanced Parent Dashboard ──

@app.route("/api/education/parent/overview/<sid>", methods=["GET"])
def parent_overview(sid):
    return jsonify(parent_dash.get_overview(g.user_id, sid))

@app.route("/api/education/parent/screen-time/<sid>", methods=["GET"])
def parent_screen_time(sid):
    days = int(request.args.get("days", 7))
    return jsonify(parent_dash.get_screen_time(g.user_id, sid, days))

@app.route("/api/education/parent/screen-time-limit/<sid>", methods=["POST"])
def parent_screen_limit(sid):
    d = request.json or {}
    return jsonify(parent_dash.set_screen_time_limit(g.user_id, sid, d.get("daily_minutes", 60)))

@app.route("/api/education/parent/safety-alerts/<sid>", methods=["GET"])
def parent_safety_alerts(sid):
    return jsonify({"alerts": parent_dash.get_safety_alerts(g.user_id, sid)})

# ── Curriculum Alignment ──

@app.route("/api/education/curriculum/standards", methods=["GET"])
def curriculum_standards():
    return jsonify({"standards": curriculum.get_standards()})

@app.route("/api/education/curriculum/standards/<sid>", methods=["GET"])
def curriculum_standard_detail(sid):
    return jsonify(curriculum.get_standard_detail(sid))

@app.route("/api/education/curriculum/for-grade/<grade>", methods=["GET"])
def curriculum_for_grade(grade):
    return jsonify({"grade": grade, "standards": curriculum.get_standards_for_grade(grade)})

@app.route("/api/education/curriculum/tag", methods=["POST"])
def curriculum_tag():
    d = request.json or {}
    return jsonify(curriculum.tag_session(d.get("session_id",""), d.get("standard_set",""),
        d.get("domain",""), specific_standard=d.get("standard","")))

@app.route("/api/education/curriculum/coverage/<student_id>", methods=["GET"])
def curriculum_coverage(student_id):
    standard_set = request.args.get("standard_set", "ccss_math")
    return jsonify(curriculum.get_coverage(student_id, standard_set))

# ── Progress Reports ──

@app.route("/api/education/reports/<sid>/weekly", methods=["GET"])
def progress_report_weekly(sid):
    return jsonify(progress_reports.generate_weekly(sid, g.user_id))

@app.route("/api/education/reports/<sid>/monthly", methods=["GET"])
def progress_report_monthly(sid):
    return jsonify(progress_reports.generate_monthly(sid, g.user_id))

# ── Gamification ──

@app.route("/api/education/xp/award", methods=["POST"])
def xp_award():
    d = request.json or {}
    return jsonify(gamification.award_xp(d.get("student_id",""), d.get("event",""),
        subject=d.get("subject",""), detail=d.get("detail","")))

@app.route("/api/education/xp/profile/<sid>", methods=["GET"])
def xp_profile(sid):
    return jsonify(gamification.get_profile(sid))

@app.route("/api/education/leaderboard", methods=["GET"])
def edu_leaderboard():
    return jsonify({"leaderboard": gamification.get_leaderboard(
        grade=request.args.get("grade",""), limit=int(request.args.get("limit", 20)))})

@app.route("/api/education/badges", methods=["GET"])
def edu_badges():
    return jsonify({"badges": gamification.get_all_badges()})

@app.route("/api/education/xp/events", methods=["GET"])
def xp_events():
    return jsonify({"events": gamification.XP_EVENTS})


# ── Document Export Engine ──

@app.route("/api/conversations/<conv_id>/export/docx", methods=["GET"])
def export_conv_docx(conv_id):
    conv = conversations.get_conversation(conv_id, g.user_id)
    if not conv: return jsonify({"error": "Not found"}), 404
    msgs = conversations.get_messages(conv_id)
    data = doc_exporter.conversation_to_docx(conv, msgs)
    return Response(data, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                   headers={"Content-Disposition": f"attachment; filename=conversation-{conv_id[:8]}.docx"})

@app.route("/api/conversations/<conv_id>/export/pdf", methods=["GET"])
def export_conv_pdf(conv_id):
    conv = conversations.get_conversation(conv_id, g.user_id)
    if not conv: return jsonify({"error": "Not found"}), 404
    msgs = conversations.get_messages(conv_id)
    data = doc_exporter.conversation_to_pdf(conv, msgs)
    return Response(data, mimetype="application/pdf",
                   headers={"Content-Disposition": f"attachment; filename=conversation-{conv_id[:8]}.pdf"})

@app.route("/api/conversations/<conv_id>/export/xlsx", methods=["GET"])
def export_conv_xlsx(conv_id):
    conv = conversations.get_conversation(conv_id, g.user_id)
    if not conv: return jsonify({"error": "Not found"}), 404
    msgs = conversations.get_messages(conv_id)
    data = doc_exporter.conversation_to_xlsx(conv, msgs)
    return Response(data, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   headers={"Content-Disposition": f"attachment; filename=conversation-{conv_id[:8]}.xlsx"})

@app.route("/api/conversations/<conv_id>/export/md", methods=["GET"])
def export_conv_md(conv_id):
    conv = conversations.get_conversation(conv_id, g.user_id)
    if not conv: return jsonify({"error": "Not found"}), 404
    msgs = conversations.get_messages(conv_id)
    md = doc_exporter.conversation_to_markdown(conv, msgs)
    return Response(md, mimetype="text/markdown",
                   headers={"Content-Disposition": f"attachment; filename=conversation-{conv_id[:8]}.md"})

@app.route("/api/roundtables/<rid>/export/docx", methods=["GET"])
def export_rt_docx(rid):
    rt = roundtable.get(rid)
    if not rt: return jsonify({"error": "Not found"}), 404
    wb = whiteboard.get(rid)
    data = doc_exporter.roundtable_to_docx(rt, wb)
    return Response(data, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                   headers={"Content-Disposition": f"attachment; filename=roundtable-{rid[:8]}.docx"})

@app.route("/api/roundtables/<rid>/export/pdf", methods=["GET"])
def export_rt_pdf(rid):
    rt = roundtable.get(rid)
    if not rt: return jsonify({"error": "Not found"}), 404
    wb = whiteboard.get(rid)
    data = doc_exporter.roundtable_to_pdf(rt, wb)
    return Response(data, mimetype="application/pdf",
                   headers={"Content-Disposition": f"attachment; filename=roundtable-{rid[:8]}.pdf"})


# ═══════════════════════════════════════════════════════════════
# PASSWORD RESET + EMAIL NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════

@app.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    """Send password reset email."""
    data = request.json or {}
    email = data.get("email", "")
    if not email:
        return jsonify({"error": "email required"}), 400
    # Always return success (don't reveal if email exists)
    with get_db() as db:
        user = db.execute("SELECT id, display_name FROM users WHERE email=?", (email,)).fetchone()
    if user:
        reset_token = secrets.token_urlsafe(32)
        expires = (datetime.now() + timedelta(hours=1)).isoformat()
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES (?, ?)",
                (f"reset_{reset_token}", json.dumps({"user_id": dict(user)["id"], "expires": expires})))
        email_tpl.send_password_reset(email, reset_token, name=dict(user).get("display_name", ""))
    return jsonify({"sent": True, "message": "If this email is registered, a reset link has been sent."})

@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    """Reset password with token."""
    data = request.json or {}
    token = data.get("token", "")
    new_pass = data.get("password", "")
    if not token or not new_pass:
        return jsonify({"error": "token and password required"}), 400
    # Validate password
    pw_check = password_fortress.validate_password(new_pass)
    if not pw_check["valid"]:
        return jsonify({"error": "Password too weak", "issues": pw_check["issues"]}), 400
    with get_db() as db:
        row = db.execute("SELECT value FROM workspace_settings WHERE key=?", (f"reset_{token}",)).fetchone()
    if not row:
        return jsonify({"error": "Invalid or expired token"}), 400
    info = json.loads(dict(row)["value"])
    if datetime.now() > datetime.fromisoformat(info["expires"]):
        return jsonify({"error": "Token expired"}), 400
    user_id = info["user_id"]
    hashed = password_fortress.hash_password(new_pass)
    with get_db() as db:
        db.execute("UPDATE users SET password_hash=? WHERE id=?", (hashed, user_id))
        db.execute("DELETE FROM workspace_settings WHERE key=?", (f"reset_{token}",))
    password_fortress.record_password(user_id, hashed)
    return jsonify({"reset": True, "message": "Password updated. You can now log in."})

@app.route("/api/email/test", methods=["POST"])
def test_email():
    """Send a test email (admin only)."""
    data = request.json or {}
    to = data.get("to", "")
    if not to:
        return jsonify({"error": "to required"}), 400
    result = email_tpl.send_welcome(to, name="Test User")
    return jsonify(result)
