"""
MyTeam360 — AI Platform
Main application with API routes, streaming, and integration initialization.
"""

import os
import json
import uuid
import secrets
import logging
from datetime import datetime
from flask import Flask, request, jsonify, Response, g, session, send_from_directory, send_file
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
from core.security_hardening import (FieldEncryptor, get_encryptor, PasswordPolicyManager,
                                      SessionManager, MFAManager, DLPScanner)
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
password_policy = PasswordPolicyManager()
session_mgr = SessionManager()
mfa_mgr = MFAManager()
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
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ═══════════════════════════════════════════════════════════════
# ROUTES — Dashboard & Status
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory("templates", "landing.html")

@app.route("/app")
def app_page():
    return send_from_directory("templates", "app.html")

@app.route("/security")
def security_page():
    return send_from_directory("templates", "security.html")

@app.route("/terms")
def terms_page():
    return send_from_directory("templates", "terms.html")

@app.route("/static/native-bridge.js")
def native_bridge_js():
    return send_from_directory("templates", "native-bridge.js", mimetype="application/javascript")


@app.route("/api/status")
def api_status():
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
    return jsonify({"user": u, "permissions": list(users.get_permissions(g.user_id))})


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
    return jsonify({"agent": agents.update_agent(agent_id, request.json)})


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

    sources = result.get("sources", [])
    conversations.add_message(conv_id, "assistant", reply_text,
                              agent_id=agent_id, provider=result.get("provider"),
                              model=result.get("model"),
                              tokens_used=result.get("usage",{}).get("total_tokens",0),
                              sources=sources)

    usage = result.get("usage", {})
    users.log_usage(g.user_id, agent_id, result.get("provider",""), result.get("model",""),
                    usage.get("input_tokens",0), usage.get("output_tokens",0), usage.get("cost",0))

    return jsonify({
        "message": {"content": reply_text, "sources": json.dumps(sources)},
        "conversation_id": conv_id,
        "route_info": route_info,
        "image_urls": image_urls,
    })


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
    session_id = voice_sessions.start_session(
        g.user_id, agent_id=data.get("agent_id"),
        tts_provider=data.get("tts_provider", "browser"))
    return jsonify({"session_id": session_id})

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
