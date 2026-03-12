"""
MyTeam360 — Database Schema & Connection Management
© 2026 MyTeam360. All Rights Reserved.
"""

import os
import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger("MyTeam360.database")

DB_PATH = os.getenv("DB_PATH", "data/myteam360.db")


def get_db_path():
    return DB_PATH


@contextmanager
def get_db():
    os.makedirs(os.path.dirname(get_db_path()) or "data", exist_ok=True)
    conn = sqlite3.connect(get_db_path(), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    with get_db() as conn:
        conn.executescript(SCHEMA)
    # Migrations — add columns that may not exist
    _migrate(["ALTER TABLE users ADD COLUMN google_id TEXT",
              "ALTER TABLE users ADD COLUMN avatar_url TEXT"])
    logger.info("Database initialized")


def _migrate(stmts):
    """Run ALTER TABLE migrations, ignoring 'duplicate column' errors."""
    with get_db() as conn:
        for sql in stmts:
            try:
                conn.execute(sql)
            except Exception:
                pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'member' CHECK(role IN ('owner','admin','member','viewer')),
    avatar_color TEXT DEFAULT '#7c5cfc',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    invited_by TEXT REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    name TEXT, title TEXT, company TEXT, industry TEXT,
    role_description TEXT, expertise_areas TEXT, target_audience TEXT, competitors TEXT,
    writing_tone TEXT, formality_level TEXT, preferred_length TEXT, avoid_phrases TEXT,
    custom_fields TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS user_api_keys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    encrypted_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    token_prefix TEXT NOT NULL,
    scopes TEXT DEFAULT '*',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    expires_at TIMESTAMP,
    enabled INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform TEXT DEFAULT 'web',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    ip_address TEXT
);

-- DEPARTMENTS

CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    icon TEXT DEFAULT '🏢',
    color TEXT DEFAULT '#3b82f6',
    budget_monthly REAL DEFAULT 0,
    budget_warning_pct REAL DEFAULT 80,
    budget_hard_stop INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS department_members (
    department_id TEXT NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'member' CHECK(role IN ('head','member')),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (department_id, user_id)
);

CREATE TABLE IF NOT EXISTS department_agent_access (
    department_id TEXT NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    PRIMARY KEY (department_id, agent_id)
);

CREATE TABLE IF NOT EXISTS department_kb_access (
    department_id TEXT NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    folder_id TEXT NOT NULL REFERENCES kb_folders(id) ON DELETE CASCADE,
    PRIMARY KEY (department_id, folder_id)
);

-- AGENTS

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT DEFAULT '',
    icon TEXT DEFAULT '🤖',
    color TEXT DEFAULT '#7c5cfc',
    description TEXT DEFAULT '',
    instructions TEXT DEFAULT '',
    additional_context TEXT DEFAULT '',
    provider TEXT DEFAULT '',
    model TEXT DEFAULT '',
    temperature REAL DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 4096,
    use_user_profile INTEGER DEFAULT 1,
    use_user_style INTEGER DEFAULT 1,
    use_knowledge_base INTEGER DEFAULT 0,
    knowledge_folders TEXT DEFAULT '[]',
    company_wide INTEGER DEFAULT 0,
    shared INTEGER DEFAULT 0,
    run_count INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    avg_rating REAL DEFAULT 0,
    rating_count INTEGER DEFAULT 0,
    routing_mode TEXT DEFAULT 'manual',
    can_delegate INTEGER DEFAULT 0,
    delegate_agents TEXT DEFAULT '[]',
    voice_provider TEXT DEFAULT '',
    voice_id TEXT DEFAULT '',
    voice_model TEXT DEFAULT '',
    voice_speed REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATIONS & MESSAGES

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
    department_id TEXT REFERENCES departments(id) ON DELETE SET NULL,
    title TEXT DEFAULT 'New Conversation',
    platform TEXT DEFAULT 'web',
    pinned INTEGER DEFAULT 0,
    archived INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    agent_id TEXT,
    provider TEXT,
    model TEXT,
    tokens_used INTEGER DEFAULT 0,
    cost_estimate REAL DEFAULT 0,
    rating INTEGER DEFAULT 0,
    sources TEXT DEFAULT '[]',
    image_urls TEXT DEFAULT '[]',
    metadata TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_dept ON conversations(department_id);

-- KNOWLEDGE BASE

CREATE TABLE IF NOT EXISTS kb_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '📁',
    department_id TEXT REFERENCES departments(id) ON DELETE SET NULL,
    company_wide INTEGER DEFAULT 0,
    shared INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kb_documents (
    id TEXT PRIMARY KEY,
    folder_id TEXT REFERENCES kb_folders(id) ON DELETE SET NULL,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_type TEXT,
    file_size INTEGER DEFAULT 0,
    page_count INTEGER DEFAULT 0,
    storage_path TEXT,
    status TEXT DEFAULT 'processing' CHECK(status IN ('processing','ready','error')),
    tags TEXT DEFAULT '[]',
    shared INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    section_title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON kb_chunks(document_id, chunk_index);
CREATE VIRTUAL TABLE IF NOT EXISTS kb_search USING fts5(
    chunk_id, content, document_name, tags,
    tokenize='porter'
);

-- WORKFLOWS

CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    icon TEXT DEFAULT '⚡',
    steps TEXT DEFAULT '[]',
    department_id TEXT REFERENCES departments(id) ON DELETE SET NULL,
    company_wide INTEGER DEFAULT 0,
    shared INTEGER DEFAULT 0,
    schedule TEXT,
    webhook_token TEXT,
    run_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    status TEXT DEFAULT 'running' CHECK(status IN ('running','paused','completed','failed','cancelled')),
    input_text TEXT,
    current_step INTEGER DEFAULT 0,
    step_results TEXT DEFAULT '[]',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- CLIENT PORTAL

CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT,
    avatar_color TEXT DEFAULT '#3b82f6',
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS client_users (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE IF NOT EXISTS client_agent_access (
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    PRIMARY KEY (client_id, agent_id)
);

-- APPROVALS

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    workflow_run_id TEXT REFERENCES workflow_runs(id),
    submitted_by TEXT NOT NULL REFERENCES users(id),
    assigned_to TEXT REFERENCES users(id),
    title TEXT NOT NULL,
    content TEXT,
    context TEXT DEFAULT '{}',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','changes_requested')),
    feedback TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- USAGE & BUDGET

CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    department_id TEXT REFERENCES departments(id),
    agent_id TEXT,
    provider TEXT,
    model TEXT,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    cost_estimate REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_dept_date ON usage_log(department_id, created_at);

CREATE TABLE IF NOT EXISTS budget_limits (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL CHECK(scope IN ('workspace','user','department','client')),
    scope_id TEXT,
    monthly_limit REAL NOT NULL,
    warning_pct REAL DEFAULT 80,
    hard_stop INTEGER DEFAULT 1
);

-- AUDIT LOG

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT,
    user_email TEXT,
    ip_address TEXT,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    detail TEXT,
    severity TEXT DEFAULT 'info' CHECK(severity IN ('info','warning','critical'))
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);

CREATE TABLE IF NOT EXISTS auth_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT,
    ip TEXT,
    endpoint TEXT,
    method TEXT,
    status TEXT,
    detail TEXT
);

-- BRANDING / WHITE-LABEL

CREATE TABLE IF NOT EXISTS branding (
    key TEXT PRIMARY KEY,
    value TEXT
);

INSERT OR IGNORE INTO branding (key, value) VALUES ('company_name', 'MyTeam360');
INSERT OR IGNORE INTO branding (key, value) VALUES ('logo_path', '');
INSERT OR IGNORE INTO branding (key, value) VALUES ('primary_color', '#7c5cfc');
INSERT OR IGNORE INTO branding (key, value) VALUES ('accent_color', '#a78bfa');
INSERT OR IGNORE INTO branding (key, value) VALUES ('welcome_message', 'Welcome to your AI workspace');
INSERT OR IGNORE INTO branding (key, value) VALUES ('powered_by_visible', '1');
INSERT OR IGNORE INTO branding (key, value) VALUES ('powered_by_text', 'Powered by MyTeam360');

-- WORKSPACE SETTINGS

CREATE TABLE IF NOT EXISTS workspace_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

INSERT OR IGNORE INTO workspace_settings (key, value) VALUES ('open_registration', '1');
INSERT OR IGNORE INTO workspace_settings (key, value) VALUES ('workspace_name', 'MyTeam360');
INSERT OR IGNORE INTO workspace_settings (key, value) VALUES ('auto_lock_minutes', '15');
INSERT OR IGNORE INTO workspace_settings (key, value) VALUES ('password_min_length', '8');
INSERT OR IGNORE INTO workspace_settings (key, value) VALUES ('session_hours', '24');
INSERT OR IGNORE INTO workspace_settings (key, value) VALUES ('lan_access', '0');
INSERT OR IGNORE INTO workspace_settings (key, value) VALUES ('setup_complete', '0');
INSERT OR IGNORE INTO workspace_settings (key, value) VALUES ('show_tooltips', '1');

-- PROMPT CHAINS

CREATE TABLE IF NOT EXISTS prompt_chains (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    icon TEXT DEFAULT '🔗',
    owner_id TEXT REFERENCES users(id),
    steps TEXT DEFAULT '[]',
    variables TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 1,
    run_count INTEGER DEFAULT 0,
    avg_duration REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MODEL ROUTING RULES

CREATE TABLE IF NOT EXISTS routing_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    strategy TEXT DEFAULT 'cost',
    rules TEXT DEFAULT '[]',
    fallback_provider TEXT DEFAULT '',
    fallback_model TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO routing_rules (id, name, description, strategy, rules, fallback_provider, fallback_model, is_active)
VALUES (
    'route_default', 'Smart Router', 'Auto-select model by task complexity',
    'auto',
    '[{"match":"simple","provider":"anthropic","model":"claude-haiku-4-5-20251001","max_tokens":1024},{"match":"code","provider":"anthropic","model":"claude-sonnet-4-5-20250929","max_tokens":8192},{"match":"complex","provider":"anthropic","model":"claude-sonnet-4-5-20250929","max_tokens":4096},{"match":"creative","provider":"anthropic","model":"claude-sonnet-4-5-20250929","max_tokens":4096}]',
    'anthropic', 'claude-sonnet-4-5-20250929', 1
);
INSERT OR IGNORE INTO workspace_settings (key, value) VALUES ('monthly_budget', '500');

-- PLATFORM LINKS

CREATE TABLE IF NOT EXISTS platform_links (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK(platform IN ('slack','telegram','sms','discord')),
    platform_user_id TEXT NOT NULL,
    display_name TEXT,
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, platform_user_id)
);

CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, key)
);

-- AGENT TEMPLATES (pre-built agent configurations)

CREATE TABLE IF NOT EXISTS agent_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT DEFAULT '',
    icon TEXT DEFAULT '🤖',
    color TEXT DEFAULT '#4f46e5',
    description TEXT DEFAULT '',
    instructions TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    provider TEXT DEFAULT '',
    model TEXT DEFAULT '',
    temperature REAL DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 4096,
    tags TEXT DEFAULT '[]',
    deploy_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AGENT RECOMMENDATIONS (system-suggested agents)

CREATE TABLE IF NOT EXISTS agent_recommendations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT DEFAULT '',
    icon TEXT DEFAULT '🤖',
    description TEXT DEFAULT '',
    instructions TEXT DEFAULT '',
    reason TEXT DEFAULT '',
    confidence REAL DEFAULT 0.0,
    category TEXT DEFAULT 'general',
    source_data TEXT DEFAULT '{}',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','deployed')),
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    template_id TEXT REFERENCES agent_templates(id),
    department_id TEXT REFERENCES departments(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MESSAGE FEEDBACK (thumbs up/down on AI responses)

CREATE TABLE IF NOT EXISTS message_feedback (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    agent_id TEXT REFERENCES agents(id),
    rating INTEGER NOT NULL CHECK(rating IN (-1, 1)),
    comment TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(message_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_feedback_agent ON message_feedback(agent_id, created_at);
CREATE INDEX IF NOT EXISTS idx_recommendations_status ON agent_recommendations(status);

-- PHASE 7: INTEGRATIONS & EVENTS

CREATE TABLE IF NOT EXISTS webhook_endpoints (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    secret TEXT,
    events TEXT DEFAULT '[]',
    headers TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 1,
    last_triggered TEXT,
    last_status INTEGER,
    failure_count INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    source TEXT,
    source_id TEXT,
    payload TEXT DEFAULT '{}',
    user_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_events_type ON event_log(event_type, created_at);

CREATE TABLE IF NOT EXISTS notification_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'webhook',
    channel_config TEXT DEFAULT '{}',
    filter_json TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 1,
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- PHASE 8: ADVANCED CHAT

CREATE TABLE IF NOT EXISTS conversation_pins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    pinned_by TEXT,
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(conversation_id, message_id)
);

CREATE TABLE IF NOT EXISTS file_attachments (
    id TEXT PRIMARY KEY,
    message_id TEXT,
    conversation_id TEXT,
    filename TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER DEFAULT 0,
    storage_path TEXT,
    uploaded_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_attachments_conv ON file_attachments(conversation_id);

CREATE TABLE IF NOT EXISTS conversation_shares (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    shared_by TEXT NOT NULL,
    share_token TEXT NOT NULL UNIQUE,
    expires_at TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS provider_auth (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL UNIQUE,
    auth_method TEXT NOT NULL DEFAULT 'api_key',
    api_key TEXT DEFAULT '',
    oauth_client_id TEXT DEFAULT '',
    oauth_client_secret TEXT DEFAULT '',
    oauth_authorize_url TEXT DEFAULT '',
    oauth_token_url TEXT DEFAULT '',
    oauth_scope TEXT DEFAULT '',
    oauth_access_token TEXT DEFAULT '',
    oauth_refresh_token TEXT DEFAULT '',
    oauth_token_expiry TEXT,
    base_url TEXT DEFAULT '',
    default_model TEXT DEFAULT '',
    custom_models TEXT DEFAULT '[]',
    is_enabled INTEGER DEFAULT 1,
    configured_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS calendar_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS zapier_subscriptions (
    id TEXT PRIMARY KEY,
    hook_url TEXT NOT NULL,
    events TEXT DEFAULT '["*"]',
    hook_secret TEXT,
    api_key TEXT,
    created_by TEXT,
    is_active INTEGER DEFAULT 1,
    failure_count INTEGER DEFAULT 0,
    last_triggered TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS digest_settings (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    frequency TEXT DEFAULT 'off',
    send_time TEXT DEFAULT '09:00',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policies (
    id TEXT PRIMARY KEY,
    policy_type TEXT NOT NULL DEFAULT 'aup',
    version INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL DEFAULT 'Acceptable Use Policy',
    content TEXT NOT NULL DEFAULT '',
    is_active INTEGER DEFAULT 1,
    requires_acceptance INTEGER DEFAULT 1,
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    published_at TEXT
);

CREATE TABLE IF NOT EXISTS policy_acceptances (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    accepted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,
    user_agent TEXT,
    UNIQUE(policy_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_policy_accept_user ON policy_acceptances(user_id);

CREATE TABLE IF NOT EXISTS setup_wizard_state (
    id TEXT PRIMARY KEY DEFAULT 'wizard',
    is_complete INTEGER DEFAULT 0,
    current_step INTEGER DEFAULT 0,
    completed_steps TEXT DEFAULT '[]',
    org_name TEXT DEFAULT '',
    org_industry TEXT DEFAULT '',
    org_size TEXT DEFAULT '',
    selected_providers TEXT DEFAULT '[]',
    selected_departments TEXT DEFAULT '[]',
    admin_configured INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_retention_policies (
    id TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL,
    retention_days INTEGER DEFAULT 365,
    auto_delete INTEGER DEFAULT 0,
    archive_before_delete INTEGER DEFAULT 1,
    is_enabled INTEGER DEFAULT 0,
    configured_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ip_allowlist (
    id TEXT PRIMARY KEY,
    ip_address TEXT NOT NULL,
    cidr_range TEXT,
    description TEXT DEFAULT '',
    is_enabled INTEGER DEFAULT 1,
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS password_history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pw_history_user ON password_history(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS account_lockout (
    user_id TEXT PRIMARY KEY,
    failed_attempts INTEGER DEFAULT 0,
    locked_until TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS active_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    device_type TEXT DEFAULT 'unknown',
    last_activity TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON active_sessions(user_id, is_active);

CREATE TABLE IF NOT EXISTS mfa_config (
    user_id TEXT PRIMARY KEY,
    method TEXT DEFAULT 'totp',
    totp_secret TEXT,
    backup_codes TEXT DEFAULT '[]',
    is_verified INTEGER DEFAULT 0,
    is_enabled INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prompt_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    category TEXT DEFAULT 'general',
    variables TEXT DEFAULT '[]',
    is_shared INTEGER DEFAULT 0,
    department_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_templates_owner ON prompt_templates(owner_id);

CREATE TABLE IF NOT EXISTS template_usage (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    used_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_template_usage ON template_usage(template_id);

CREATE TABLE IF NOT EXISTS user_quotas (
    id TEXT PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL,
    monthly_tokens INTEGER DEFAULT 0,
    monthly_cost REAL DEFAULT 0.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS department_quotas (
    id TEXT PRIMARY KEY,
    department_id TEXT UNIQUE NOT NULL,
    monthly_tokens INTEGER DEFAULT 0,
    monthly_cost REAL DEFAULT 0.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""
