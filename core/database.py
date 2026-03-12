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
MyTeam360 — Database Layer (Postgres primary, SQLite fallback)

Set DATABASE_URL for Postgres:  postgres://user:pass@host:5432/myteam360
Leave unset or set DB_PATH for SQLite fallback (self-hosted/dev mode).
"""

import os
import re
import logging
from contextlib import contextmanager

logger = logging.getLogger("MyTeam360.database")

DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_PATH = os.getenv("DB_PATH", "data/myteam360.db")
_USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))

# ═══════════════════════════════════════════════════════════════
# CONNECTION POOL (Postgres) or File (SQLite)
# ═══════════════════════════════════════════════════════════════

_pg_pool = None

def _get_pg_pool():
    """Lazy-init a threaded PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool is None:
        import psycopg2
        from psycopg2 import pool as pg_pool
        from psycopg2.extras import RealDictCursor
        _pg_pool = pg_pool.ThreadedConnectionPool(
            minconn=2, maxconn=20, dsn=DATABASE_URL,
            cursor_factory=RealDictCursor,
        )
        logger.info(f"PostgreSQL pool created (2-20 connections)")
    return _pg_pool


# ═══════════════════════════════════════════════════════════════
# COMPATIBILITY WRAPPER
# Translates ? → %s, INSERT OR REPLACE → ON CONFLICT, etc.
# All 31 modules keep using the same API unchanged.
# ═══════════════════════════════════════════════════════════════

class _CompatCursor:
    """Wraps a database cursor to provide cross-backend compatibility."""

    def __init__(self, cursor, is_pg=False):
        self._cursor = cursor
        self._is_pg = is_pg

    def execute(self, sql, params=None):
        sql = self._translate(sql)
        if params and self._is_pg:
            # Convert tuple/list params for psycopg2
            if isinstance(params, (list, tuple)):
                params = tuple(params)
        try:
            if params:
                self._cursor.execute(sql, params)
            else:
                self._cursor.execute(sql)
        except Exception as e:
            # For Postgres, re-raise with cleaner message
            raise
        return self

    def executescript(self, sql):
        """Execute multiple statements. Postgres doesn't have executescript."""
        if self._is_pg:
            self._cursor.execute(sql)
        else:
            self._cursor.executescript(sql)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        if self._is_pg:
            return dict(row)  # RealDictCursor returns RealDictRow
        return row  # sqlite3.Row already supports dict-like access

    def fetchall(self):
        rows = self._cursor.fetchall()
        if self._is_pg:
            return [dict(r) for r in rows]
        return rows  # sqlite3.Row objects

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        if self._is_pg:
            return None  # Postgres uses RETURNING
        return self._cursor.lastrowid

    @property
    def description(self):
        return self._cursor.description

    def _translate(self, sql):
        """Translate SQLite SQL to Postgres-compatible SQL."""
        if not self._is_pg:
            return sql

        # ? → %s (but not inside strings)
        # Simple approach: replace ? that are parameters
        sql = sql.replace("?", "%s")

        # INSERT OR REPLACE → INSERT ... ON CONFLICT DO UPDATE
        m = re.match(r"INSERT OR REPLACE INTO (\w+)\s*\((.+?)\)\s*VALUES\s*\((.+?)\)",
                     sql, re.IGNORECASE | re.DOTALL)
        if m:
            table, cols, vals = m.group(1), m.group(2), m.group(3)
            col_list = [c.strip() for c in cols.split(",")]
            pk = col_list[0]  # assume first column is PK
            updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in col_list[1:])
            if updates:
                sql = f"INSERT INTO {table} ({cols}) VALUES ({vals}) ON CONFLICT ({pk}) DO UPDATE SET {updates}"
            else:
                sql = f"INSERT INTO {table} ({cols}) VALUES ({vals}) ON CONFLICT ({pk}) DO NOTHING"

        # INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING
        if "INSERT OR IGNORE" in sql.upper():
            sql = re.sub(r"INSERT OR IGNORE INTO (\w+)\s*\((.+?)\)\s*VALUES\s*\((.+?)\)",
                        lambda m: f"INSERT INTO {m.group(1)} ({m.group(2)}) VALUES ({m.group(3)}) ON CONFLICT DO NOTHING",
                        sql, flags=re.IGNORECASE)

        # datetime('now') → NOW()
        sql = sql.replace("datetime('now')", "NOW()")
        sql = sql.replace("datetime('now')", "NOW()")

        # AUTOINCREMENT → handled in schema (already converted)

        return sql


class _CompatConnection:
    """Wraps a database connection for cross-backend compatibility."""

    def __init__(self, conn, is_pg=False):
        self._conn = conn
        self._is_pg = is_pg

    def execute(self, sql, params=None):
        cursor = self._conn.cursor()
        wrapper = _CompatCursor(cursor, self._is_pg)
        wrapper.execute(sql, params)
        return wrapper

    def executescript(self, sql):
        if self._is_pg:
            cursor = self._conn.cursor()
            cursor.execute(sql)
        else:
            self._conn.executescript(sql)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def cursor(self):
        return _CompatCursor(self._conn.cursor(), self._is_pg)


# ═══════════════════════════════════════════════════════════════
# PUBLIC API — get_db() context manager
# Used by all 31 modules unchanged.
# ═══════════════════════════════════════════════════════════════

@contextmanager
def get_db():
    """Get a database connection. Postgres if DATABASE_URL is set, else SQLite."""
    if _USE_POSTGRES:
        pool = _get_pg_pool()
        raw_conn = pool.getconn()
        conn = _CompatConnection(raw_conn, is_pg=True)
        try:
            yield conn
            raw_conn.commit()
        except Exception:
            raw_conn.rollback()
            raise
        finally:
            pool.putconn(raw_conn)
    else:
        import sqlite3
        os.makedirs(os.path.dirname(DB_PATH) or "data", exist_ok=True)
        raw_conn = sqlite3.connect(DB_PATH, timeout=15)
        raw_conn.row_factory = sqlite3.Row
        raw_conn.execute("PRAGMA journal_mode=WAL")
        raw_conn.execute("PRAGMA foreign_keys=ON")
        conn = _CompatConnection(raw_conn, is_pg=False)
        try:
            yield conn
            raw_conn.commit()
        except Exception:
            raw_conn.rollback()
            raise
        finally:
            raw_conn.close()


def get_backend():
    """Return which database backend is active."""
    return "postgres" if _USE_POSTGRES else "sqlite"


# ═══════════════════════════════════════════════════════════════
# INITIALIZATION
# ═══════════════════════════════════════════════════════════════

def init_database():
    """Create all tables and run migrations."""
    if _USE_POSTGRES:
        pool = _get_pg_pool()
        conn = pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(SCHEMA_PG)
            conn.commit()
            logger.info("PostgreSQL schema initialized")
        finally:
            pool.putconn(conn)
        _migrate_pg()
    else:
        import sqlite3
        os.makedirs(os.path.dirname(DB_PATH) or "data", exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA_SQLITE)
        conn.commit()
        conn.close()
        _migrate_sqlite()
    logger.info(f"Database initialized ({get_backend()})")


MIGRATIONS = ["ALTER TABLE users ADD COLUMN google_id TEXT",
              "ALTER TABLE users ADD COLUMN avatar_url TEXT",
              # Agent import/sync fields
              "ALTER TABLE agents ADD COLUMN source TEXT DEFAULT 'local'",
              "ALTER TABLE agents ADD COLUMN source_id TEXT DEFAULT ''",
              "ALTER TABLE agents ADD COLUMN source_provider TEXT DEFAULT ''",
              "ALTER TABLE agents ADD COLUMN source_meta TEXT DEFAULT '{}'",
              "ALTER TABLE agents ADD COLUMN last_synced_at TIMESTAMP",
              "ALTER TABLE agents ADD COLUMN sync_enabled INTEGER DEFAULT 0",
              "ALTER TABLE agents ADD COLUMN prompt_version INTEGER DEFAULT 1",
              "ALTER TABLE agents ADD COLUMN prompt_history TEXT DEFAULT '[]'",
              # Spaces: persistent memory per agent
              "ALTER TABLE agents ADD COLUMN space_memory TEXT DEFAULT '{}'",
              "ALTER TABLE agents ADD COLUMN pinned_files TEXT DEFAULT '[]'",
              "ALTER TABLE agents ADD COLUMN sticky_context TEXT DEFAULT ''",
              "ALTER TABLE agents ADD COLUMN last_used_at TIMESTAMP",
              "ALTER TABLE agents ADD COLUMN favorite INTEGER DEFAULT 0",
              # Conversations: branching
              "ALTER TABLE conversations ADD COLUMN parent_id TEXT",
              "ALTER TABLE conversations ADD COLUMN branch_name TEXT DEFAULT ''",
              "ALTER TABLE conversations ADD COLUMN branch_point_msg TEXT",
              # Messages: scoring
              "ALTER TABLE messages ADD COLUMN feedback TEXT DEFAULT ''",
              "ALTER TABLE messages ADD COLUMN feedback_tags TEXT DEFAULT '[]'",
              # Voice learning
              "ALTER TABLE user_profiles ADD COLUMN voice_profile TEXT DEFAULT '{}'",
              
]


def _migrate_sqlite():
    """Run ALTER TABLE migrations for SQLite, ignoring duplicate column errors."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH, timeout=15)
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            pass
    conn.close()


def _migrate_pg():
    """Run ALTER TABLE migrations for Postgres, ignoring 'already exists' errors."""
    pool = _get_pg_pool()
    conn = pool.getconn()
    for sql in MIGRATIONS:
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
        except Exception:
            conn.rollback()
    pool.putconn(conn)


# ═══════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'member' CHECK(role IN ('owner','admin','member','viewer')),
    avatar_color TEXT DEFAULT '#a459f2',
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
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    encrypted_key TEXT NOT NULL,
    masked_key TEXT DEFAULT '',
    label TEXT DEFAULT '',
    preferred_model TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    color TEXT DEFAULT '#a459f2',
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
INSERT OR IGNORE INTO branding (key, value) VALUES ('primary_color', '#a459f2');
INSERT OR IGNORE INTO branding (key, value) VALUES ('accent_color', '#c084fc');
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

-- CONVERSATION DNA / DIGITAL TWIN
CREATE TABLE IF NOT EXISTS business_dna (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    confidence REAL DEFAULT 0.8,
    source_conversations TEXT DEFAULT '[]',
    times_referenced INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI-TO-AI NEGOTIATION
CREATE TABLE IF NOT EXISTS negotiations (
    id TEXT PRIMARY KEY,
    party_a_user TEXT NOT NULL,
    party_a_agent TEXT NOT NULL,
    party_b_user TEXT NOT NULL,
    party_b_agent TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','agreed','failed','cancelled')),
    party_a_params TEXT DEFAULT '{}',
    party_b_params TEXT DEFAULT '{}',
    rounds TEXT DEFAULT '[]',
    final_terms TEXT DEFAULT '',
    max_rounds INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TIME-TRAVEL DECISIONS
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT,
    agent_id TEXT,
    decision TEXT NOT NULL,
    reasoning TEXT DEFAULT '',
    context TEXT DEFAULT '',
    participants TEXT DEFAULT '[]',
    tags TEXT DEFAULT '[]',
    superseded_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SPACE CLONES
CREATE TABLE IF NOT EXISTS space_clones (
    id TEXT PRIMARY KEY,
    source_agent_id TEXT NOT NULL,
    cloned_agent_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    adaptation_profile TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COST TICKER













-- CRISIS INTERVENTION — Always On, Cannot Be Disabled
CREATE TABLE IF NOT EXISTS crisis_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    tier TEXT NOT NULL,
    snippet TEXT DEFAULT '',
    handled INTEGER DEFAULT 0,
    handled_by TEXT DEFAULT '',
    handled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EDUCATION — Students and Tutoring
CREATE TABLE IF NOT EXISTS students (
    id TEXT PRIMARY KEY,
    parent_id TEXT NOT NULL,
    name TEXT NOT NULL,
    grade TEXT DEFAULT '6',
    subjects TEXT DEFAULT '[]',
    learning_style TEXT DEFAULT '',
    special_needs TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tutoring_sessions (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    subtopic TEXT DEFAULT '',
    question TEXT DEFAULT '',
    response_length INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);




-- CRISIS INTERVENTION — Always On, Cannot Be Disabled
CREATE TABLE IF NOT EXISTS crisis_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    tier TEXT NOT NULL,
    snippet TEXT DEFAULT '',
    handled INTEGER DEFAULT 0,
    handled_by TEXT DEFAULT '',
    handled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

























-- OUTBOUND WEBHOOKS (Zapier/Make)
CREATE TABLE IF NOT EXISTS outbound_webhooks (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT DEFAULT 'Webhook',
    url TEXT NOT NULL,
    events TEXT DEFAULT '[]',
    secret TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK DEPENDENCIES
CREATE TABLE IF NOT EXISTS task_dependencies (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    blocked_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, blocked_by)
);

-- RECURRING TASKS
CREATE TABLE IF NOT EXISTS recurring_tasks (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    frequency TEXT DEFAULT 'weekly',
    day_of_week INTEGER,
    day_of_month INTEGER,
    custom_interval_days INTEGER,
    priority TEXT DEFAULT 'medium',
    assigned_to TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    last_generated TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- LATE FEE POLICIES
CREATE TABLE IF NOT EXISTS late_fee_policies (
    owner_id TEXT PRIMARY KEY,
    fee_type TEXT DEFAULT 'percentage',
    fee_value REAL DEFAULT 1.5,
    grace_period_days INTEGER DEFAULT 5,
    max_fee_pct REAL DEFAULT 25.0
);

-- WHATSAPP LOG
CREATE TABLE IF NOT EXISTS whatsapp_log (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    contact_name TEXT DEFAULT '',
    phone_number TEXT DEFAULT '',
    direction TEXT DEFAULT 'outbound',
    content TEXT DEFAULT '',
    has_media INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- BETA WAITLIST
CREATE TABLE IF NOT EXISTS beta_waitlist (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    referral_code TEXT DEFAULT '',
    source TEXT DEFAULT 'website',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM KEY GOVERNANCE
CREATE TABLE IF NOT EXISTS platform_key_approvals (
    id TEXT PRIMARY KEY,
    approved_by TEXT NOT NULL,
    use_case TEXT NOT NULL,
    description TEXT DEFAULT '',
    max_calls_per_day INTEGER DEFAULT 50,
    max_cost_per_day REAL DEFAULT 1.0,
    revoked INTEGER DEFAULT 0,
    revoked_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS platform_key_audit (
    id TEXT PRIMARY KEY,
    use_case TEXT NOT NULL,
    provider TEXT DEFAULT '',
    model TEXT DEFAULT '',
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    estimated_cost REAL DEFAULT 0,
    detail TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API USAGE LOG (BYOK transparency)
CREATE TABLE IF NOT EXISTS api_usage_log (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT DEFAULT '',
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    estimated_cost REAL DEFAULT 0,
    feature TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- WIN/LOSS LOG
CREATE TABLE IF NOT EXISTS win_loss_log (
    id TEXT PRIMARY KEY,
    deal_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    reason TEXT DEFAULT '',
    competitor TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    feedback TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- UNDO LOG
CREATE TABLE IF NOT EXISTS undo_log (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT DEFAULT '',
    reverse_data TEXT DEFAULT '{}',
    expires_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TEXT MESSAGE LOG
CREATE TABLE IF NOT EXISTS text_message_log (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    contact_name TEXT DEFAULT '',
    phone_number TEXT DEFAULT '',
    direction TEXT DEFAULT 'outbound',
    content TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFE INTEGRATIONS (OAuth tokens for read-only access)
CREATE TABLE IF NOT EXISTS safe_integrations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FLIGHT TRACKING
CREATE TABLE IF NOT EXISTS tracked_flights (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    flight_number TEXT NOT NULL,
    airline TEXT DEFAULT '',
    flight_date TEXT NOT NULL,
    confirmation TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'scheduled',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FAVORITES / PINS
CREATE TABLE IF NOT EXISTS favorites (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    label TEXT DEFAULT '',
    icon TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ACTIVITY FEED
CREATE TABLE IF NOT EXISTS activity_feed (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT DEFAULT '',
    detail TEXT DEFAULT '',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SCRATCH NOTES
CREATE TABLE IF NOT EXISTS scratch_notes (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT DEFAULT 'Untitled Note',
    content TEXT DEFAULT '',
    color TEXT DEFAULT '#FEF3C7',
    pinned INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- BOOKING LINKS
CREATE TABLE IF NOT EXISTS booking_links (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    description TEXT DEFAULT '',
    availability TEXT DEFAULT '{}',
    questions TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS booking_requests (
    id TEXT PRIMARY KEY,
    link_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    booker_name TEXT NOT NULL,
    booker_email TEXT NOT NULL,
    requested_time TEXT NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    answers TEXT DEFAULT '{}',
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- LIFESTYLE INTELLIGENCE
CREATE TABLE IF NOT EXISTS lifestyle_preferences (
    owner_id TEXT NOT NULL,
    category TEXT NOT NULL,
    preferences TEXT DEFAULT '{}',
    updated_at TEXT DEFAULT '',
    PRIMARY KEY (owner_id, category)
);

CREATE TABLE IF NOT EXISTS weekly_rhythms (
    owner_id TEXT NOT NULL,
    day_of_week TEXT NOT NULL,
    rhythm TEXT DEFAULT '{}',
    PRIMARY KEY (owner_id, day_of_week)
);

CREATE TABLE IF NOT EXISTS activity_patterns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    day_of_week TEXT DEFAULT '',
    hour INTEGER DEFAULT 0,
    context TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lifestyle_feedback (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    suggestion_type TEXT NOT NULL,
    suggestion_id TEXT DEFAULT '',
    rating INTEGER DEFAULT 3,
    feedback TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- QUICK CAPTURES
CREATE TABLE IF NOT EXISTS quick_captures (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    capture_type TEXT DEFAULT 'crm_note',
    entities TEXT DEFAULT '{}',
    processed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- WORKFLOW AUTOMATIONS
CREATE TABLE IF NOT EXISTS automation_workflows (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    conditions TEXT DEFAULT '{}',
    actions TEXT DEFAULT '[]',
    enabled INTEGER DEFAULT 1,
    run_count INTEGER DEFAULT 0,
    last_run TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SETUP CONCIERGE SESSIONS
CREATE TABLE IF NOT EXISTS setup_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    intent TEXT NOT NULL,
    current_step INTEGER DEFAULT 0,
    collected_data TEXT DEFAULT '{}',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Health Events
CREATE TABLE IF NOT EXISTS platform_health_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    detail TEXT DEFAULT '',
    count_value INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Change Proposals
CREATE TABLE IF NOT EXISTS change_proposals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    change_type TEXT DEFAULT 'configuration',
    proposed_changes TEXT DEFAULT '{}',
    source TEXT DEFAULT 'platform_intelligence',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','applied')),
    reviewed_by TEXT DEFAULT '',
    review_notes TEXT DEFAULT '',
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RESILIENCE — Space Versions
CREATE TABLE IF NOT EXISTS space_versions (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    snapshot TEXT DEFAULT '{}',
    change_note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Health Events
CREATE TABLE IF NOT EXISTS platform_health_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    detail TEXT DEFAULT '',
    count_value INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Change Proposals
CREATE TABLE IF NOT EXISTS change_proposals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    change_type TEXT DEFAULT 'configuration',
    proposed_changes TEXT DEFAULT '{}',
    source TEXT DEFAULT 'platform_intelligence',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','applied')),
    reviewed_by TEXT DEFAULT '',
    review_notes TEXT DEFAULT '',
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RESILIENCE — Response Feedback
CREATE TABLE IF NOT EXISTS response_feedback (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    agent_id TEXT DEFAULT '',
    model TEXT DEFAULT '',
    provider TEXT DEFAULT '',
    rating TEXT NOT NULL,
    comment TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Health Events
CREATE TABLE IF NOT EXISTS platform_health_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    detail TEXT DEFAULT '',
    count_value INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Change Proposals
CREATE TABLE IF NOT EXISTS change_proposals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    change_type TEXT DEFAULT 'configuration',
    proposed_changes TEXT DEFAULT '{}',
    source TEXT DEFAULT 'platform_intelligence',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','applied')),
    reviewed_by TEXT DEFAULT '',
    review_notes TEXT DEFAULT '',
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RESILIENCE — Webhooks
CREATE TABLE IF NOT EXISTS webhooks (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT DEFAULT '',
    url TEXT NOT NULL,
    events TEXT DEFAULT '[]',
    secret TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id TEXT PRIMARY KEY,
    webhook_id TEXT NOT NULL,
    event TEXT DEFAULT '',
    payload TEXT DEFAULT '{}',
    status TEXT DEFAULT 'queued',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Health Events
CREATE TABLE IF NOT EXISTS platform_health_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    detail TEXT DEFAULT '',
    count_value INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Change Proposals
CREATE TABLE IF NOT EXISTS change_proposals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    change_type TEXT DEFAULT 'configuration',
    proposed_changes TEXT DEFAULT '{}',
    source TEXT DEFAULT 'platform_intelligence',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','applied')),
    reviewed_by TEXT DEFAULT '',
    review_notes TEXT DEFAULT '',
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RESILIENCE — Backup Log
CREATE TABLE IF NOT EXISTS backup_log (
    id TEXT PRIMARY KEY,
    backup_type TEXT DEFAULT 'full',
    table_counts TEXT DEFAULT '{}',
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TEAM BUILDER — Learned Professions (AI-generated, stored for reuse)
CREATE TABLE IF NOT EXISTS learned_professions (
    id TEXT PRIMARY KEY,
    role_id TEXT NOT NULL UNIQUE,
    role_label TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    recommendation TEXT DEFAULT '{}',
    times_used INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FOUNDATIONS — Sponsorships
CREATE TABLE IF NOT EXISTS sponsorships (
    id TEXT PRIMARY KEY,
    sponsor_user_id TEXT NOT NULL,
    months INTEGER DEFAULT 1,
    amount_per_month REAL DEFAULT 7.0,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sponsorship_applications (
    id TEXT PRIMARY KEY,
    applicant_user_id TEXT NOT NULL,
    reason TEXT DEFAULT '',
    organization TEXT DEFAULT '',
    role TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','denied')),
    reviewed_by TEXT DEFAULT '',
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EDUCATION — Learning DNA
CREATE TABLE IF NOT EXISTS learning_dna (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    academic_level TEXT DEFAULT 'bachelors',
    strong_subjects TEXT DEFAULT '[]',
    weak_subjects TEXT DEFAULT '[]',
    preferred_styles TEXT DEFAULT '[]',
    effective_approaches TEXT DEFAULT '[]',
    ineffective_approaches TEXT DEFAULT '[]',
    subject_history TEXT DEFAULT '{}',
    struggle_score INTEGER DEFAULT 0,
    total_interactions INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- CRISIS INTERVENTION — Always On, Cannot Be Disabled
CREATE TABLE IF NOT EXISTS crisis_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    tier TEXT NOT NULL,
    snippet TEXT DEFAULT '',
    handled INTEGER DEFAULT 0,
    handled_by TEXT DEFAULT '',
    handled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EDUCATION — Courses
CREATE TABLE IF NOT EXISTS student_courses (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    code TEXT DEFAULT '',
    professor TEXT DEFAULT '',
    credits INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- CRISIS INTERVENTION — Always On, Cannot Be Disabled
CREATE TABLE IF NOT EXISTS crisis_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    tier TEXT NOT NULL,
    snippet TEXT DEFAULT '',
    handled INTEGER DEFAULT 0,
    handled_by TEXT DEFAULT '',
    handled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EDUCATION — Assignments
CREATE TABLE IF NOT EXISTS student_assignments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    course_id TEXT DEFAULT '',
    title TEXT NOT NULL,
    due_date TEXT,
    assignment_type TEXT DEFAULT 'homework',
    weight REAL DEFAULT 0,
    grade TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','in_progress','submitted','graded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GUARDRAILS — Age Verification and Parental Consent
CREATE TABLE IF NOT EXISTS user_age_verification (
    user_id TEXT PRIMARY KEY,
    date_of_birth TEXT NOT NULL,
    age_at_verification INTEGER,
    is_minor INTEGER DEFAULT 0,
    consent_required INTEGER DEFAULT 0,
    consent_granted INTEGER DEFAULT 0,
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parental_consents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    parent_name TEXT NOT NULL,
    parent_email TEXT NOT NULL,
    relationship TEXT NOT NULL,
    tos_version TEXT DEFAULT '1.0',
    consent_agreed INTEGER DEFAULT 0,
    consent_hash TEXT DEFAULT '',
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- DIGITAL MARKETING — Campaigns and Content
CREATE TABLE IF NOT EXISTS marketing_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    target_country TEXT DEFAULT 'US',
    target_audience TEXT DEFAULT '',
    budget REAL DEFAULT 0,
    budget_currency TEXT DEFAULT 'USD',
    start_date TEXT,
    end_date TEXT,
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'planning' CHECK(status IN ('planning','active','paused','completed','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS marketing_content (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    content_type TEXT NOT NULL,
    platform TEXT DEFAULT '',
    content TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SALES COACH — Deals and Coaching
CREATE TABLE IF NOT EXISTS sales_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    deal_value REAL DEFAULT 0,
    close_date TEXT,
    stage TEXT DEFAULT 'prospect' CHECK(stage IN ('prospect','qualification','proposal','negotiation','closed')),
    outcome TEXT DEFAULT '' CHECK(outcome IN ('','won','lost','no_decision','cancelled')),
    loss_reason TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    rfp_text TEXT DEFAULT '',
    proposal_text TEXT DEFAULT '',
    client_requirements TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sales_coaching_sessions (
    id TEXT PRIMARY KEY,
    deal_id TEXT NOT NULL,
    session_type TEXT NOT NULL,
    prompt TEXT DEFAULT '',
    response TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- IP SHIELD — Evidence Log
CREATE TABLE IF NOT EXISTS ip_evidence_log (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    description TEXT DEFAULT '',
    details TEXT DEFAULT '{}',
    hash_proof TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FEATURE GATES — Admin-controlled activation
CREATE TABLE IF NOT EXISTS feature_gates (
    feature TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    changed_by TEXT DEFAULT '',
    changed_by_name TEXT DEFAULT '',
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feature_gate_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature TEXT NOT NULL,
    action TEXT NOT NULL,
    admin_id TEXT DEFAULT '',
    admin_name TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Teams
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_members (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT DEFAULT 'member' CHECK(role IN ('owner','admin','member','viewer')),
    status TEXT DEFAULT 'active' CHECK(status IN ('active','removed','left')),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_invites (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    inviter_id TEXT NOT NULL,
    email TEXT NOT NULL,
    target_user_id TEXT,
    role TEXT DEFAULT 'member',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','accepted','declined','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);








-- CRISIS INTERVENTION — Always On, Cannot Be Disabled
CREATE TABLE IF NOT EXISTS crisis_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    tier TEXT NOT NULL,
    snippet TEXT DEFAULT '',
    handled INTEGER DEFAULT 0,
    handled_by TEXT DEFAULT '',
    handled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EDUCATION — Students and Tutoring
CREATE TABLE IF NOT EXISTS students (
    id TEXT PRIMARY KEY,
    parent_id TEXT NOT NULL,
    name TEXT NOT NULL,
    grade TEXT DEFAULT '6',
    subjects TEXT DEFAULT '[]',
    learning_style TEXT DEFAULT '',
    special_needs TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tutoring_sessions (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    subtopic TEXT DEFAULT '',
    question TEXT DEFAULT '',
    response_length INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);




-- CRISIS INTERVENTION — Always On, Cannot Be Disabled
CREATE TABLE IF NOT EXISTS crisis_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    tier TEXT NOT NULL,
    snippet TEXT DEFAULT '',
    handled INTEGER DEFAULT 0,
    handled_by TEXT DEFAULT '',
    handled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Health Events
CREATE TABLE IF NOT EXISTS platform_health_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    detail TEXT DEFAULT '',
    count_value INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Change Proposals
CREATE TABLE IF NOT EXISTS change_proposals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    change_type TEXT DEFAULT 'configuration',
    proposed_changes TEXT DEFAULT '{}',
    source TEXT DEFAULT 'platform_intelligence',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','applied')),
    reviewed_by TEXT DEFAULT '',
    review_notes TEXT DEFAULT '',
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RESILIENCE — Space Versions
CREATE TABLE IF NOT EXISTS space_versions (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    snapshot TEXT DEFAULT '{}',
    change_note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Health Events
CREATE TABLE IF NOT EXISTS platform_health_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    detail TEXT DEFAULT '',
    count_value INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Change Proposals
CREATE TABLE IF NOT EXISTS change_proposals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    change_type TEXT DEFAULT 'configuration',
    proposed_changes TEXT DEFAULT '{}',
    source TEXT DEFAULT 'platform_intelligence',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','applied')),
    reviewed_by TEXT DEFAULT '',
    review_notes TEXT DEFAULT '',
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RESILIENCE — Response Feedback
CREATE TABLE IF NOT EXISTS response_feedback (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    agent_id TEXT DEFAULT '',
    model TEXT DEFAULT '',
    provider TEXT DEFAULT '',
    rating TEXT NOT NULL,
    comment TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Health Events
CREATE TABLE IF NOT EXISTS platform_health_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    detail TEXT DEFAULT '',
    count_value INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Change Proposals
CREATE TABLE IF NOT EXISTS change_proposals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    change_type TEXT DEFAULT 'configuration',
    proposed_changes TEXT DEFAULT '{}',
    source TEXT DEFAULT 'platform_intelligence',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','applied')),
    reviewed_by TEXT DEFAULT '',
    review_notes TEXT DEFAULT '',
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RESILIENCE — Webhooks
CREATE TABLE IF NOT EXISTS webhooks (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT DEFAULT '',
    url TEXT NOT NULL,
    events TEXT DEFAULT '[]',
    secret TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id TEXT PRIMARY KEY,
    webhook_id TEXT NOT NULL,
    event TEXT DEFAULT '',
    payload TEXT DEFAULT '{}',
    status TEXT DEFAULT 'queued',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Health Events
CREATE TABLE IF NOT EXISTS platform_health_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    detail TEXT DEFAULT '',
    count_value INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);















-- BILLING — Cancellation Surveys
CREATE TABLE IF NOT EXISTS cancellation_surveys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    would_return TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONVERSATION FOLDERS
CREATE TABLE IF NOT EXISTS conversation_folders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#94a3b8',
    icon TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_folder_items (
    conversation_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    PRIMARY KEY (conversation_id, folder_id)
);

-- SPEND BUDGETS
CREATE TABLE IF NOT EXISTS spend_budgets (
    owner_id TEXT PRIMARY KEY,
    monthly_budget REAL DEFAULT 0,
    alert_at_pct INTEGER DEFAULT 80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING INVOICES
CREATE TABLE IF NOT EXISTS recurring_invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    frequency TEXT DEFAULT 'monthly',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    auto_send INTEGER DEFAULT 0,
    next_date TEXT DEFAULT '',
    invoices_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','ended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICE PAYMENTS (partial payment tracking)
CREATE TABLE IF NOT EXISTS invoice_payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK TIME TRACKING
CREATE TABLE IF NOT EXISTS task_time_entries (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT '',
    duration_minutes REAL DEFAULT 0,
    note TEXT DEFAULT '',
    manual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL TEMPLATES
CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_signatures (
    owner_id TEXT PRIMARY KEY,
    signature TEXT DEFAULT ''
);

-- CUSTOM EXPENSE CATEGORIES
CREATE TABLE IF NOT EXISTS custom_expense_categories (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    tax_deductible INTEGER DEFAULT 1,
    PRIMARY KEY (id, owner_id)
);

-- HASHTAG GROUPS
CREATE TABLE IF NOT EXISTS hashtag_groups (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hashtags TEXT DEFAULT '[]',
    platform TEXT DEFAULT 'all',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Field Definitions
CREATE TABLE IF NOT EXISTS crm_custom_fields (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    field_key TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type TEXT DEFAULT 'text',
    options TEXT DEFAULT '[]',
    required INTEGER DEFAULT 0,
    default_value TEXT DEFAULT '',
    placeholder TEXT DEFAULT '',
    field_group TEXT DEFAULT '',
    position INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Pipelines
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM CUSTOMIZATION — Custom Activity Types
CREATE TABLE IF NOT EXISTS crm_activity_types (
    id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '',
    color TEXT DEFAULT '#94a3b8',
    position INTEGER DEFAULT 100,
    PRIMARY KEY (id, owner_id)
);

-- CRM CUSTOMIZATION — Saved Views
CREATE TABLE IF NOT EXISTS crm_saved_views (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    filters TEXT DEFAULT '{}',
    sort_by TEXT DEFAULT '',
    sort_order TEXT DEFAULT 'desc',
    columns TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS / KPIs / OKRs
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    goal_type TEXT DEFAULT 'objective',
    target_value REAL DEFAULT 0,
    target_unit TEXT DEFAULT '',
    current_value REAL DEFAULT 0,
    progress_pct REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    parent_id TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    category TEXT DEFAULT 'business',
    status TEXT DEFAULT 'active',
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_updates (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    value REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EMAIL OUTBOX
CREATE TABLE IF NOT EXISTS email_outbox (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    cc TEXT DEFAULT '',
    bcc TEXT DEFAULT '',
    reply_to TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','sending','sent','failed')),
    sent_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EXPENSE TRACKING
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'other',
    vendor TEXT DEFAULT '',
    expense_date TEXT NOT NULL,
    receipt_url TEXT DEFAULT '',
    recurring INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COMPETITIVE INTELLIGENCE
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competitor_intel (
    id TEXT PRIMARY KEY,
    competitor_id TEXT NOT NULL,
    intel_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CLIENT PORTAL
CREATE TABLE IF NOT EXISTS client_shares (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    last_viewed TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CRM — Contacts
CREATE TABLE IF NOT EXISTS crm_contacts (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    source TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    lead_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    size TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    value REAL DEFAULT 0,
    contact_id TEXT DEFAULT '',
    company_id TEXT DEFAULT '',
    stage TEXT DEFAULT 'lead',
    expected_close TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_activities (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    contact_id TEXT DEFAULT '',
    deal_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INVOICING
CREATE TABLE IF NOT EXISTS invoice_profiles (
    owner_id TEXT PRIMARY KEY,
    profile TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    client_address TEXT DEFAULT '',
    line_items TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    notes TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    sent_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','partial','paid','overdue','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    proposal_number TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    sections TEXT DEFAULT '[]',
    pricing_items TEXT DEFAULT '[]',
    total REAL DEFAULT 0,
    valid_until TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    terms TEXT DEFAULT '',
    accepted_at TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','sent','viewed','accepted','rejected','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASK / PROJECT BOARD
CREATE TABLE IF NOT EXISTS task_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    column_id TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
    assigned_to TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    labels TEXT DEFAULT '[]',
    position INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','completed','archived')),
    completed_at TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE WHITEBOARDS
CREATE TABLE IF NOT EXISTS roundtable_whiteboards (
    id TEXT PRIMARY KEY,
    roundtable_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    sections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Connections
CREATE TABLE IF NOT EXISTS social_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_name TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    access_token TEXT DEFAULT '',
    refresh_token TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Campaigns
CREATE TABLE IF NOT EXISTS social_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    platforms TEXT DEFAULT '[]',
    target_audience TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    tone TEXT DEFAULT 'professional',
    posting_frequency TEXT DEFAULT 'daily',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','active','paused','completed','archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SOCIAL MEDIA — Posts
CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    scheduled_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    link_url TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','scheduled','publishing','published','failed')),
    error_message TEXT DEFAULT '',
    engagement_likes INTEGER DEFAULT 0,
    engagement_comments INTEGER DEFAULT 0,
    engagement_shares INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Acknowledgments (legally binding record)
CREATE TABLE IF NOT EXISTS violation_acknowledgments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strike_id TEXT NOT NULL,
    violation_label TEXT NOT NULL,
    tos_section TEXT NOT NULL,
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT NOT NULL,
    strike_number INTEGER NOT NULL,
    acknowledgment_text TEXT NOT NULL,
    acknowledged_at TIMESTAMP NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    session_id TEXT DEFAULT ''
);

-- THREE STRIKES — User Violation Tracking
CREATE TABLE IF NOT EXISTS user_strikes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    detail TEXT DEFAULT '',
    strike_number INTEGER DEFAULT 1,
    violation_label TEXT DEFAULT '',
    tos_section TEXT DEFAULT '',
    query_excerpt TEXT DEFAULT '',
    violation_timestamp TEXT DEFAULT '',
    expired INTEGER DEFAULT 0,
    expiry_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Violation Log
CREATE TABLE IF NOT EXISTS safety_violations (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'high',
    action_taken TEXT DEFAULT 'blocked',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SAFETY — Abuse Reports
CREATE TABLE IF NOT EXISTS abuse_reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    conversation_id TEXT DEFAULT '',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
    resolved_by TEXT DEFAULT '',
    resolution_action TEXT DEFAULT '',
    resolution_notes TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TOS Acceptance Tracking
CREATE TABLE IF NOT EXISTS tos_acceptance (
    user_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, version)
);

-- SSO Configuration
CREATE TABLE IF NOT EXISTS sso_config (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_type TEXT DEFAULT 'saml',
    config TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom Roles (RBAC)
CREATE TABLE IF NOT EXISTS custom_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions TEXT DEFAULT '[]',
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Affiliates
CREATE TABLE IF NOT EXISTS affiliates (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    ref_code TEXT UNIQUE NOT NULL,
    platform TEXT DEFAULT '',
    followers INTEGER DEFAULT 0,
    audience TEXT DEFAULT '',
    pitch TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','rejected','paused')),
    commission_pct REAL DEFAULT 20,
    current_tier TEXT DEFAULT 'Bronze',
    total_clicks INTEGER DEFAULT 0,
    total_referrals INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    approved_by TEXT DEFAULT '',
    approved_at TIMESTAMP,
    rejection_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    ref_code TEXT NOT NULL,
    user_id TEXT DEFAULT '',
    plan TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    commission_pct REAL DEFAULT 0,
    commission_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','payout_requested','paid','refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id TEXT PRIMARY KEY,
    affiliate_id TEXT NOT NULL,
    amount REAL DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','rejected')),
    processed_by TEXT DEFAULT '',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MFA — Trusted Devices
CREATE TABLE IF NOT EXISTS trusted_devices (
    user_id TEXT NOT NULL,
    device_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, device_token)
);

-- MFA — Recovery Tokens
CREATE TABLE IF NOT EXISTS mfa_recovery (
    user_id TEXT NOT NULL,
    recovery_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SECURITY FORTRESS — Password History
CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PLATFORM INTELLIGENCE — Change Proposals
CREATE TABLE IF NOT EXISTS change_proposals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    change_type TEXT DEFAULT 'configuration',
    proposed_changes TEXT DEFAULT '{}',
    source TEXT DEFAULT 'platform_intelligence',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','applied')),
    reviewed_by TEXT DEFAULT '',
    review_notes TEXT DEFAULT '',
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RESILIENCE — Backup Log
CREATE TABLE IF NOT EXISTS backup_log (
    id TEXT PRIMARY KEY,
    backup_type TEXT DEFAULT 'full',
    table_counts TEXT DEFAULT '{}',
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TEAM BUILDER — Learned Professions (AI-generated, stored for reuse)
CREATE TABLE IF NOT EXISTS learned_professions (
    id TEXT PRIMARY KEY,
    role_id TEXT NOT NULL UNIQUE,
    role_label TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    recommendation TEXT DEFAULT '{}',
    times_used INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FOUNDATIONS — Sponsorships
CREATE TABLE IF NOT EXISTS sponsorships (
    id TEXT PRIMARY KEY,
    sponsor_user_id TEXT NOT NULL,
    months INTEGER DEFAULT 1,
    amount_per_month REAL DEFAULT 7.0,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sponsorship_applications (
    id TEXT PRIMARY KEY,
    applicant_user_id TEXT NOT NULL,
    reason TEXT DEFAULT '',
    organization TEXT DEFAULT '',
    role TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','denied')),
    reviewed_by TEXT DEFAULT '',
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EDUCATION — Learning DNA
CREATE TABLE IF NOT EXISTS learning_dna (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    academic_level TEXT DEFAULT 'bachelors',
    strong_subjects TEXT DEFAULT '[]',
    weak_subjects TEXT DEFAULT '[]',
    preferred_styles TEXT DEFAULT '[]',
    effective_approaches TEXT DEFAULT '[]',
    ineffective_approaches TEXT DEFAULT '[]',
    subject_history TEXT DEFAULT '{}',
    struggle_score INTEGER DEFAULT 0,
    total_interactions INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- CRISIS INTERVENTION — Always On, Cannot Be Disabled
CREATE TABLE IF NOT EXISTS crisis_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    tier TEXT NOT NULL,
    snippet TEXT DEFAULT '',
    handled INTEGER DEFAULT 0,
    handled_by TEXT DEFAULT '',
    handled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EDUCATION — Courses
CREATE TABLE IF NOT EXISTS student_courses (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    code TEXT DEFAULT '',
    professor TEXT DEFAULT '',
    credits INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- CRISIS INTERVENTION — Always On, Cannot Be Disabled
CREATE TABLE IF NOT EXISTS crisis_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    tier TEXT NOT NULL,
    snippet TEXT DEFAULT '',
    handled INTEGER DEFAULT 0,
    handled_by TEXT DEFAULT '',
    handled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- EDUCATION — Assignments
CREATE TABLE IF NOT EXISTS student_assignments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    course_id TEXT DEFAULT '',
    title TEXT NOT NULL,
    due_date TEXT,
    assignment_type TEXT DEFAULT 'homework',
    weight REAL DEFAULT 0,
    grade TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','in_progress','submitted','graded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GUARDRAILS — Age Verification and Parental Consent
CREATE TABLE IF NOT EXISTS user_age_verification (
    user_id TEXT PRIMARY KEY,
    date_of_birth TEXT NOT NULL,
    age_at_verification INTEGER,
    is_minor INTEGER DEFAULT 0,
    consent_required INTEGER DEFAULT 0,
    consent_granted INTEGER DEFAULT 0,
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parental_consents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    parent_name TEXT NOT NULL,
    parent_email TEXT NOT NULL,
    relationship TEXT NOT NULL,
    tos_version TEXT DEFAULT '1.0',
    consent_agreed INTEGER DEFAULT 0,
    consent_hash TEXT DEFAULT '',
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- DIGITAL MARKETING — Campaigns and Content
CREATE TABLE IF NOT EXISTS marketing_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    objective TEXT DEFAULT '',
    target_country TEXT DEFAULT 'US',
    target_audience TEXT DEFAULT '',
    budget REAL DEFAULT 0,
    budget_currency TEXT DEFAULT 'USD',
    start_date TEXT,
    end_date TEXT,
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'planning' CHECK(status IN ('planning','active','paused','completed','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS marketing_content (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    content_type TEXT NOT NULL,
    platform TEXT DEFAULT '',
    content TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SALES COACH — Deals and Coaching
CREATE TABLE IF NOT EXISTS sales_deals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    deal_value REAL DEFAULT 0,
    close_date TEXT,
    stage TEXT DEFAULT 'prospect' CHECK(stage IN ('prospect','qualification','proposal','negotiation','closed')),
    outcome TEXT DEFAULT '' CHECK(outcome IN ('','won','lost','no_decision','cancelled')),
    loss_reason TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    rfp_text TEXT DEFAULT '',
    proposal_text TEXT DEFAULT '',
    client_requirements TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sales_coaching_sessions (
    id TEXT PRIMARY KEY,
    deal_id TEXT NOT NULL,
    session_type TEXT NOT NULL,
    prompt TEXT DEFAULT '',
    response TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- IP SHIELD — Evidence Log
CREATE TABLE IF NOT EXISTS ip_evidence_log (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    description TEXT DEFAULT '',
    details TEXT DEFAULT '{}',
    hash_proof TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FEATURE GATES — Admin-controlled activation
CREATE TABLE IF NOT EXISTS feature_gates (
    feature TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    changed_by TEXT DEFAULT '',
    changed_by_name TEXT DEFAULT '',
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feature_gate_log (
    id SERIAL PRIMARY KEY,
    feature TEXT NOT NULL,
    action TEXT NOT NULL,
    admin_id TEXT DEFAULT '',
    admin_name TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Presence
CREATE TABLE IF NOT EXISTS user_presence (
    user_id TEXT NOT NULL,
    context TEXT DEFAULT 'app',
    context_id TEXT DEFAULT '',
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, context, context_id)
);


-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Activity Feed
CREATE TABLE IF NOT EXISTS team_activity (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT DEFAULT '',
    action TEXT NOT NULL,
    detail TEXT DEFAULT '',
    resource_type TEXT DEFAULT '',
    resource_id TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOVERNANCE — Meeting Minutes
CREATE TABLE IF NOT EXISTS meeting_minutes (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    topic TEXT NOT NULL,
    participants TEXT DEFAULT '[]',
    minutes_text TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','approved','archived')),
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);




-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Teams
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_members (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT DEFAULT 'member' CHECK(role IN ('owner','admin','member','viewer')),
    status TEXT DEFAULT 'active' CHECK(status IN ('active','removed','left')),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_invites (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    inviter_id TEXT NOT NULL,
    email TEXT NOT NULL,
    target_user_id TEXT,
    role TEXT DEFAULT 'member',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','accepted','declined','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Presence
CREATE TABLE IF NOT EXISTS user_presence (
    user_id TEXT NOT NULL,
    context TEXT DEFAULT 'app',
    context_id TEXT DEFAULT '',
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, context, context_id)
);


-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Activity Feed
CREATE TABLE IF NOT EXISTS team_activity (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT DEFAULT '',
    action TEXT NOT NULL,
    detail TEXT DEFAULT '',
    resource_type TEXT DEFAULT '',
    resource_id TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOVERNANCE — Corporate Records
CREATE TABLE IF NOT EXISTS corporate_records (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    record_type TEXT DEFAULT 'general',
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    retention_days INTEGER DEFAULT 0,
    expires_at TIMESTAMP,
    attachments TEXT DEFAULT '[]',
    related_ids TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);




-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Teams
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_members (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT DEFAULT 'member' CHECK(role IN ('owner','admin','member','viewer')),
    status TEXT DEFAULT 'active' CHECK(status IN ('active','removed','left')),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_invites (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    inviter_id TEXT NOT NULL,
    email TEXT NOT NULL,
    target_user_id TEXT,
    role TEXT DEFAULT 'member',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','accepted','declined','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Presence
CREATE TABLE IF NOT EXISTS user_presence (
    user_id TEXT NOT NULL,
    context TEXT DEFAULT 'app',
    context_id TEXT DEFAULT '',
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, context, context_id)
);


-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Activity Feed
CREATE TABLE IF NOT EXISTS team_activity (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT DEFAULT '',
    action TEXT NOT NULL,
    detail TEXT DEFAULT '',
    resource_type TEXT DEFAULT '',
    resource_id TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOVERNANCE — Resolutions and Votes
CREATE TABLE IF NOT EXISTS resolutions (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    required_approvers TEXT DEFAULT '[]',
    threshold TEXT DEFAULT 'majority',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','withdrawn')),
    decided_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resolution_votes (
    id TEXT PRIMARY KEY,
    resolution_id TEXT NOT NULL,
    voter_name TEXT NOT NULL,
    vote TEXT NOT NULL CHECK(vote IN ('approve','reject','abstain')),
    comment TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE — Multi-Agent Collaborative Discussions
CREATE TABLE IF NOT EXISTS roundtables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    mode TEXT DEFAULT 'debate',
    participants TEXT DEFAULT '[]',
    transcript TEXT DEFAULT '[]',
    initial_context TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    max_rounds INTEGER DEFAULT 5,
    status TEXT DEFAULT 'created' CHECK(status IN ('created','active','completed','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_costs (
    conversation_id TEXT PRIMARY KEY,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0.0,
    message_count INTEGER DEFAULT 0,
    budget_cap REAL DEFAULT 0,
    budget_alert_sent INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- SHARED CONTEXT LAYER (Company Brain)
CREATE TABLE IF NOT EXISTS shared_context (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    embedding TEXT DEFAULT '',
    source_agent_id TEXT,
    ttl_days INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS context_links (
    agent_id TEXT NOT NULL,
    context_id TEXT NOT NULL REFERENCES shared_context(id) ON DELETE CASCADE,
    relevance REAL DEFAULT 1.0,
    PRIMARY KEY (agent_id, context_id)
);

-- AGENT TRIGGERS (Automation)
CREATE TABLE IF NOT EXISTS agent_triggers (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    trigger_type TEXT NOT NULL CHECK(trigger_type IN ('schedule','webhook','event','watch')),
    config TEXT NOT NULL DEFAULT '{}',
    input_template TEXT DEFAULT '',
    output_action TEXT DEFAULT 'store',
    output_config TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 1,
    last_fired_at TIMESTAMP,
    fire_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    last_error TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trigger_log (
    id TEXT PRIMARY KEY,
    trigger_id TEXT NOT NULL REFERENCES agent_triggers(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('success','error','skipped')),
    input_data TEXT DEFAULT '',
    output_data TEXT DEFAULT '',
    tokens_used INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    error_message TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AGENT PIPELINES (Assembly Line)
CREATE TABLE IF NOT EXISTS pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    steps TEXT NOT NULL DEFAULT '[]',
    is_active INTEGER DEFAULT 1,
    run_count INTEGER DEFAULT 0,
    avg_duration_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id TEXT PRIMARY KEY,
    pipeline_id TEXT NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('running','completed','failed','cancelled')),
    input_data TEXT DEFAULT '',
    step_results TEXT DEFAULT '[]',
    final_output TEXT DEFAULT '',
    total_tokens INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    error_message TEXT DEFAULT '',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- CLIENT PORTALS
CREATE TABLE IF NOT EXISTS client_portals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    branding TEXT DEFAULT '{}',
    welcome_message TEXT DEFAULT '',
    allowed_domains TEXT DEFAULT '[]',
    require_email INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    max_messages_per_session INTEGER DEFAULT 50,
    total_sessions INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portal_sessions (
    id TEXT PRIMARY KEY,
    portal_id TEXT NOT NULL REFERENCES client_portals(id) ON DELETE CASCADE,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    message_count INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    cost REAL DEFAULT 0,
    ip_address TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP
);

-- PROOF OF WORK / AUDIT REPORTS
CREATE TABLE IF NOT EXISTS work_reports (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    agent_ids TEXT DEFAULT '[]',
    summary TEXT DEFAULT '{}',
    detail_rows TEXT DEFAULT '[]',
    total_tokens INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0,
    total_conversations INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'member' CHECK(role IN ('owner','admin','member','viewer')),
    avatar_color TEXT DEFAULT '#a459f2',
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
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    encrypted_key TEXT NOT NULL,
    masked_key TEXT DEFAULT '',
    label TEXT DEFAULT '',
    preferred_model TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    color TEXT DEFAULT '#a459f2',
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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

INSERT INTO branding (key, value) VALUES ('company_name', 'MyTeam360') ON CONFLICT (key) DO NOTHING;
INSERT INTO branding (key, value) VALUES ('logo_path', '') ON CONFLICT (key) DO NOTHING;
INSERT INTO branding (key, value) VALUES ('primary_color', '#a459f2') ON CONFLICT (key) DO NOTHING;
INSERT INTO branding (key, value) VALUES ('accent_color', '#c084fc') ON CONFLICT (key) DO NOTHING;
INSERT INTO branding (key, value) VALUES ('welcome_message', 'Welcome to your AI workspace') ON CONFLICT (key) DO NOTHING;
INSERT INTO branding (key, value) VALUES ('powered_by_visible', '1') ON CONFLICT (key) DO NOTHING;
INSERT INTO branding (key, value) VALUES ('powered_by_text', 'Powered by MyTeam360') ON CONFLICT (key) DO NOTHING;

-- WORKSPACE SETTINGS

CREATE TABLE IF NOT EXISTS workspace_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

INSERT INTO workspace_settings (key, value) VALUES ('open_registration', '1') ON CONFLICT (key) DO NOTHING;
INSERT INTO workspace_settings (key, value) VALUES ('workspace_name', 'MyTeam360') ON CONFLICT (key) DO NOTHING;
INSERT INTO workspace_settings (key, value) VALUES ('auto_lock_minutes', '15') ON CONFLICT (key) DO NOTHING;
INSERT INTO workspace_settings (key, value) VALUES ('password_min_length', '8') ON CONFLICT (key) DO NOTHING;
INSERT INTO workspace_settings (key, value) VALUES ('session_hours', '24') ON CONFLICT (key) DO NOTHING;
INSERT INTO workspace_settings (key, value) VALUES ('lan_access', '0') ON CONFLICT (key) DO NOTHING;
INSERT INTO workspace_settings (key, value) VALUES ('setup_complete', '0') ON CONFLICT (key) DO NOTHING;
INSERT INTO workspace_settings (key, value) VALUES ('show_tooltips', '1') ON CONFLICT (key) DO NOTHING;

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

INSERT INTO routing_rules (id, name, description, strategy, rules, fallback_provider, fallback_model, is_active)
VALUES (
    'route_default', 'Smart Router', 'Auto-select model by task complexity',
    'auto',
    '[{"match":"simple","provider":"anthropic","model":"claude-haiku-4-5-20251001","max_tokens":1024},{"match":"code","provider":"anthropic","model":"claude-sonnet-4-5-20250929","max_tokens":8192},{"match":"complex","provider":"anthropic","model":"claude-sonnet-4-5-20250929","max_tokens":4096},{"match":"creative","provider":"anthropic","model":"claude-sonnet-4-5-20250929","max_tokens":4096}]',
    'anthropic', 'claude-sonnet-4-5-20250929', 1
);
INSERT INTO workspace_settings (key, value) VALUES ('monthly_budget', '500') ON CONFLICT (key) DO NOTHING;

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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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

-- CONVERSATION DNA / DIGITAL TWIN
CREATE TABLE IF NOT EXISTS business_dna (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    confidence REAL DEFAULT 0.8,
    source_conversations TEXT DEFAULT '[]',
    times_referenced INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI-TO-AI NEGOTIATION
CREATE TABLE IF NOT EXISTS negotiations (
    id TEXT PRIMARY KEY,
    party_a_user TEXT NOT NULL,
    party_a_agent TEXT NOT NULL,
    party_b_user TEXT NOT NULL,
    party_b_agent TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','agreed','failed','cancelled')),
    party_a_params TEXT DEFAULT '{}',
    party_b_params TEXT DEFAULT '{}',
    rounds TEXT DEFAULT '[]',
    final_terms TEXT DEFAULT '',
    max_rounds INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TIME-TRAVEL DECISIONS
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT,
    agent_id TEXT,
    decision TEXT NOT NULL,
    reasoning TEXT DEFAULT '',
    context TEXT DEFAULT '',
    participants TEXT DEFAULT '[]',
    tags TEXT DEFAULT '[]',
    superseded_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SPACE CLONES
CREATE TABLE IF NOT EXISTS space_clones (
    id TEXT PRIMARY KEY,
    source_agent_id TEXT NOT NULL,
    cloned_agent_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    client_name TEXT DEFAULT '',
    adaptation_profile TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COST TICKER







-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Teams
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_members (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT DEFAULT 'member' CHECK(role IN ('owner','admin','member','viewer')),
    status TEXT DEFAULT 'active' CHECK(status IN ('active','removed','left')),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_invites (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    inviter_id TEXT NOT NULL,
    email TEXT NOT NULL,
    target_user_id TEXT,
    role TEXT DEFAULT 'member',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','accepted','declined','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Presence
CREATE TABLE IF NOT EXISTS user_presence (
    user_id TEXT NOT NULL,
    context TEXT DEFAULT 'app',
    context_id TEXT DEFAULT '',
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, context, context_id)
);


-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Activity Feed
CREATE TABLE IF NOT EXISTS team_activity (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT DEFAULT '',
    action TEXT NOT NULL,
    detail TEXT DEFAULT '',
    resource_type TEXT DEFAULT '',
    resource_id TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOVERNANCE — Meeting Minutes
CREATE TABLE IF NOT EXISTS meeting_minutes (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    topic TEXT NOT NULL,
    participants TEXT DEFAULT '[]',
    minutes_text TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','approved','archived')),
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);




-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Teams
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_members (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT DEFAULT 'member' CHECK(role IN ('owner','admin','member','viewer')),
    status TEXT DEFAULT 'active' CHECK(status IN ('active','removed','left')),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_invites (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    inviter_id TEXT NOT NULL,
    email TEXT NOT NULL,
    target_user_id TEXT,
    role TEXT DEFAULT 'member',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','accepted','declined','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Presence
CREATE TABLE IF NOT EXISTS user_presence (
    user_id TEXT NOT NULL,
    context TEXT DEFAULT 'app',
    context_id TEXT DEFAULT '',
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, context, context_id)
);


-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Activity Feed
CREATE TABLE IF NOT EXISTS team_activity (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT DEFAULT '',
    action TEXT NOT NULL,
    detail TEXT DEFAULT '',
    resource_type TEXT DEFAULT '',
    resource_id TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOVERNANCE — Corporate Records
CREATE TABLE IF NOT EXISTS corporate_records (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    record_type TEXT DEFAULT 'general',
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    retention_days INTEGER DEFAULT 0,
    expires_at TIMESTAMP,
    attachments TEXT DEFAULT '[]',
    related_ids TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);




-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Teams
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_members (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT DEFAULT 'member' CHECK(role IN ('owner','admin','member','viewer')),
    status TEXT DEFAULT 'active' CHECK(status IN ('active','removed','left')),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_invites (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    inviter_id TEXT NOT NULL,
    email TEXT NOT NULL,
    target_user_id TEXT,
    role TEXT DEFAULT 'member',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','accepted','declined','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Presence
CREATE TABLE IF NOT EXISTS user_presence (
    user_id TEXT NOT NULL,
    context TEXT DEFAULT 'app',
    context_id TEXT DEFAULT '',
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, context, context_id)
);


-- ENTERPRISE — Action Items
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    due_date TEXT,
    source_type TEXT DEFAULT 'manual',
    source_id TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','completed','cancelled')),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- ENTERPRISE — Compliance Custom Rules (company-defined)
CREATE TABLE IF NOT EXISTS compliance_custom_rules (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    patterns TEXT DEFAULT '[]',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Violations (escalation pipeline)
CREATE TABLE IF NOT EXISTS compliance_violations (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    tier INTEGER DEFAULT 1,
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    user_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed','escalated')),
    requires_external_report INTEGER DEFAULT 0,
    resolution TEXT DEFAULT '',
    resolved_by TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Compliance Flags
CREATE TABLE IF NOT EXISTS compliance_flags (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    rule_name TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    label TEXT DEFAULT '',
    matched_text TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','resolved','dismissed')),
    resolution TEXT DEFAULT '',
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Client Deliverables
CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    conversation_id TEXT DEFAULT '',
    style TEXT DEFAULT 'report',
    client_name TEXT DEFAULT '',
    content TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft','final','sent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Delegation of Authority
CREATE TABLE IF NOT EXISTS authority_delegations (
    id TEXT PRIMARY KEY,
    delegator_id TEXT NOT NULL,
    delegator_name TEXT DEFAULT '',
    delegate_id TEXT NOT NULL,
    delegate_name TEXT DEFAULT '',
    scope TEXT DEFAULT 'all',
    expires_at TIMESTAMP,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK(status IN ('active','revoked','expired')),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Risk Register
CREATE TABLE IF NOT EXISTS risk_register (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    severity TEXT DEFAULT 'medium',
    likelihood TEXT DEFAULT 'medium',
    risk_score INTEGER DEFAULT 4,
    mitigation TEXT DEFAULT '',
    risk_owner TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open','mitigated','accepted','closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ENTERPRISE — Policy Engine v2
CREATE TABLE IF NOT EXISTS policies_v2 (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rule TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    enforcement TEXT DEFAULT 'warn' CHECK(enforcement IN ('warn','block','inject')),
    applies_to TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- COLLABORATION — Activity Feed
CREATE TABLE IF NOT EXISTS team_activity (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT DEFAULT '',
    action TEXT NOT NULL,
    detail TEXT DEFAULT '',
    resource_type TEXT DEFAULT '',
    resource_id TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOVERNANCE — Resolutions and Votes
CREATE TABLE IF NOT EXISTS resolutions (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    required_approvers TEXT DEFAULT '[]',
    threshold TEXT DEFAULT 'majority',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','withdrawn')),
    decided_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resolution_votes (
    id TEXT PRIMARY KEY,
    resolution_id TEXT NOT NULL,
    voter_name TEXT NOT NULL,
    vote TEXT NOT NULL CHECK(vote IN ('approve','reject','abstain')),
    comment TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ROUNDTABLE — Multi-Agent Collaborative Discussions
CREATE TABLE IF NOT EXISTS roundtables (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    mode TEXT DEFAULT 'debate',
    participants TEXT DEFAULT '[]',
    transcript TEXT DEFAULT '[]',
    initial_context TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    max_rounds INTEGER DEFAULT 5,
    status TEXT DEFAULT 'created' CHECK(status IN ('created','active','completed','cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_costs (
    conversation_id TEXT PRIMARY KEY,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0.0,
    message_count INTEGER DEFAULT 0,
    budget_cap REAL DEFAULT 0,
    budget_alert_sent INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- SHARED CONTEXT LAYER (Company Brain)
CREATE TABLE IF NOT EXISTS shared_context (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    embedding TEXT DEFAULT '',
    source_agent_id TEXT,
    ttl_days INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS context_links (
    agent_id TEXT NOT NULL,
    context_id TEXT NOT NULL REFERENCES shared_context(id) ON DELETE CASCADE,
    relevance REAL DEFAULT 1.0,
    PRIMARY KEY (agent_id, context_id)
);

-- AGENT TRIGGERS (Automation)
CREATE TABLE IF NOT EXISTS agent_triggers (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    trigger_type TEXT NOT NULL CHECK(trigger_type IN ('schedule','webhook','event','watch')),
    config TEXT NOT NULL DEFAULT '{}',
    input_template TEXT DEFAULT '',
    output_action TEXT DEFAULT 'store',
    output_config TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 1,
    last_fired_at TIMESTAMP,
    fire_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    last_error TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trigger_log (
    id TEXT PRIMARY KEY,
    trigger_id TEXT NOT NULL REFERENCES agent_triggers(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('success','error','skipped')),
    input_data TEXT DEFAULT '',
    output_data TEXT DEFAULT '',
    tokens_used INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    error_message TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AGENT PIPELINES (Assembly Line)
CREATE TABLE IF NOT EXISTS pipelines (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    steps TEXT NOT NULL DEFAULT '[]',
    is_active INTEGER DEFAULT 1,
    run_count INTEGER DEFAULT 0,
    avg_duration_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id TEXT PRIMARY KEY,
    pipeline_id TEXT NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('running','completed','failed','cancelled')),
    input_data TEXT DEFAULT '',
    step_results TEXT DEFAULT '[]',
    final_output TEXT DEFAULT '',
    total_tokens INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    error_message TEXT DEFAULT '',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- CLIENT PORTALS
CREATE TABLE IF NOT EXISTS client_portals (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    branding TEXT DEFAULT '{}',
    welcome_message TEXT DEFAULT '',
    allowed_domains TEXT DEFAULT '[]',
    require_email INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    max_messages_per_session INTEGER DEFAULT 50,
    total_sessions INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portal_sessions (
    id TEXT PRIMARY KEY,
    portal_id TEXT NOT NULL REFERENCES client_portals(id) ON DELETE CASCADE,
    client_name TEXT DEFAULT '',
    client_email TEXT DEFAULT '',
    message_count INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    cost REAL DEFAULT 0,
    ip_address TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP
);

-- PROOF OF WORK / AUDIT REPORTS
CREATE TABLE IF NOT EXISTS work_reports (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    agent_ids TEXT DEFAULT '[]',
    summary TEXT DEFAULT '{}',
    detail_rows TEXT DEFAULT '[]',
    total_tokens INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0,
    total_conversations INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Use the right schema
SCHEMA = SCHEMA_PG if _USE_POSTGRES else SCHEMA_SQLITE
