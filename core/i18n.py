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
Internationalization (i18n) — Multi-language support for MyTeam360.

Architecture:
  - UI strings stored in language packs (JSON dictionaries)
  - Language auto-detected from browser or user preference
  - API responses include translated error messages
  - Agent instructions stay in the user's chosen language
  - Voice learning works in any language (pattern-based, not word-based)

Adding a new language: copy LANG_EN, translate the values, add to LANGUAGES.
"""

import json
import logging
from .database import get_db

logger = logging.getLogger("MyTeam360.i18n")

# ══════════════════════════════════════════════════════════════
# LANGUAGE PACKS
# ══════════════════════════════════════════════════════════════

LANG_EN = {
    "_code": "en",
    "_name": "English",
    "_native": "English",
    "_dir": "ltr",

    # Portal
    "app_name": "MyTeam360",
    "tagline": "Your AI. Your Data. Your Control.",
    "login_email": "Email",
    "login_password": "Password",
    "login_enter": "Enter",
    "login_connecting": "Connecting…",
    "login_google": "Continue with Google",
    "login_or": "or",
    "login_error_creds": "Invalid credentials",
    "login_error_server": "Cannot reach server",
    "login_footer": "encrypted · private · yours",

    # Create
    "create_tag": "Let's Begin",
    "create_title": "What do you want to build?",
    "create_desc": "Pick a starting point or create from scratch. You can always customize later.",
    "create_go": "Create My Space →",
    "create_skip": "Show me around first",
    "create_creating": "Creating…",
    "tpl_blank": "Start from Scratch",
    "tpl_blank_desc": "Empty canvas — you define everything",
    "tpl_writer": "Content Writer",
    "tpl_writer_desc": "Blog posts, social media, marketing copy",
    "tpl_coder": "Code Assistant",
    "tpl_coder_desc": "Debug, review, build, and explain code",
    "tpl_analyst": "Data Analyst",
    "tpl_analyst_desc": "Break down numbers, trends, insights",
    "tpl_strategist": "Strategy Advisor",
    "tpl_strategist_desc": "Business planning, decisions, trade-offs",
    "tpl_support": "Customer Support",
    "tpl_support_desc": "Draft replies, handle complaints",
    "tpl_import": "Import My GPTs",
    "tpl_import_desc": "Bring your OpenAI assistants here",

    # Home
    "home_your_spaces": "Your Spaces",
    "home_import": "Import GPTs",
    "home_new": "+ New Space",
    "home_no_desc": "No description",
    "home_add": "New Space",
    "home_from_openai": "From OpenAI",
    "home_imported": "Imported",

    # Chat
    "chat_message": "Message…",
    "chat_welcome": "Start a conversation…",
    "chat_default_model": "Default model",
    "chat_error": "Something went wrong. Please try again.",
    "chat_no_key": "I need an AI provider to respond. Click below to connect one.",
    "chat_connect": "Connect AI Provider →",

    # Starters
    "hint_write_blog": "Write a blog intro about…",
    "hint_improve": "Improve this paragraph",
    "hint_social": "Create social media copy",
    "hint_review_code": "Review this code",
    "hint_explain": "Explain how to…",
    "hint_debug": "Debug this error",
    "hint_analyze": "Analyze this data",
    "hint_trends": "What trends do you see?",
    "hint_summary": "Create a summary",
    "hint_tradeoffs": "What are the trade-offs?",
    "hint_plan": "Help me plan…",
    "hint_pros_cons": "Pros and cons of…",
    "hint_help": "Help me with…",
    "hint_think": "What do you think about…",
    "hint_explain_gen": "Can you explain…",

    # Shield
    "shield_protected": "Protected",
    "shield_title": "Your Data is Safe",
    "shield_encrypt": "End-to-end encrypted storage",
    "shield_keys": "API keys encrypted at rest",
    "shield_no_train": "Your data never trains AI models",
    "shield_own": "You own everything — export anytime",
    "shield_dlp": "DLP scans block sensitive data",
    "shield_self_host": "Self-hosted — data stays on your server",

    # Key Modal
    "key_title": "Connect Your AI",
    "key_desc": "Add an API key from any provider — takes 30 seconds. Your key is encrypted and never leaves your server.",
    "key_warn": "AI provider charges are billed by your provider, not MyTeam360.",
    "key_later": "I'll do this later",
    "key_done": "Done",
    "key_save": "Save",
    "key_saving": "Saving…",
    "key_connected": "Connected",
    "key_ready": "Ready",
    "key_get": "Get a key →",
    "key_enter": "Enter a key",

    # Billing
    "tos_title": "Before We Start",
    "tos_desc": "Quick agreement — we keep things transparent.",
    "tos_agree": "I agree to the Terms of Service",
    "tos_cost": "I understand AI provider costs are separate and my responsibility",
    "tos_accept": "Accept & Start Free Trial",
    "tos_recording": "Recording…",
    "pay_title": "Your trial has ended",
    "pay_desc": "Choose a plan to keep your AI team running.",
    "pay_month": "per month",
    "pay_year": "per year",
    "pay_save": "Save 28%",
    "pay_subscribe": "Subscribe Now →",
    "pay_guarantee": "7-day money-back guarantee · Cancel anytime",

    # DLP
    "dlp_blocked": "Sensitive data detected — message blocked for your protection.",

    # Misc
    "runs": "runs",
    "space": "Space",
    "spaces": "Spaces",
    "by": "by",
    "loading": "Loading…",
}

LANG_ES = {
    "_code": "es",
    "_name": "Spanish",
    "_native": "Español",
    "_dir": "ltr",

    "app_name": "MyTeam360",
    "tagline": "Tu IA. Tus Datos. Tu Control.",
    "login_email": "Correo electrónico",
    "login_password": "Contraseña",
    "login_enter": "Entrar",
    "login_connecting": "Conectando…",
    "login_google": "Continuar con Google",
    "login_or": "o",
    "login_error_creds": "Credenciales inválidas",
    "login_error_server": "No se puede conectar al servidor",
    "login_footer": "cifrado · privado · tuyo",

    "create_tag": "Comencemos",
    "create_title": "¿Qué quieres construir?",
    "create_desc": "Elige un punto de partida o crea desde cero. Siempre puedes personalizar después.",
    "create_go": "Crear Mi Espacio →",
    "create_skip": "Primero muéstrame",
    "create_creating": "Creando…",
    "tpl_blank": "Empezar desde Cero",
    "tpl_blank_desc": "Lienzo vacío — tú defines todo",
    "tpl_writer": "Escritor de Contenido",
    "tpl_writer_desc": "Posts de blog, redes sociales, textos",
    "tpl_coder": "Asistente de Código",
    "tpl_coder_desc": "Depurar, revisar, construir código",
    "tpl_analyst": "Analista de Datos",
    "tpl_analyst_desc": "Analizar números, tendencias, insights",
    "tpl_strategist": "Asesor Estratégico",
    "tpl_strategist_desc": "Planificación, decisiones, pros y contras",
    "tpl_support": "Soporte al Cliente",
    "tpl_support_desc": "Redactar respuestas, manejar quejas",
    "tpl_import": "Importar Mis GPTs",
    "tpl_import_desc": "Trae tus asistentes de OpenAI aquí",

    "home_your_spaces": "Tus Espacios",
    "home_import": "Importar GPTs",
    "home_new": "+ Nuevo Espacio",
    "home_no_desc": "Sin descripción",
    "home_add": "Nuevo Espacio",
    "home_from_openai": "De OpenAI",
    "home_imported": "Importado",

    "chat_message": "Mensaje…",
    "chat_welcome": "Inicia una conversación…",
    "chat_default_model": "Modelo predeterminado",
    "chat_error": "Algo salió mal. Intenta de nuevo.",
    "chat_no_key": "Necesito un proveedor de IA para responder. Haz clic abajo para conectar uno.",
    "chat_connect": "Conectar Proveedor de IA →",

    "shield_protected": "Protegido",
    "shield_title": "Tus Datos Están Seguros",
    "shield_encrypt": "Almacenamiento cifrado de extremo a extremo",
    "shield_keys": "Claves API cifradas en reposo",
    "shield_no_train": "Tus datos nunca entrenan modelos de IA",
    "shield_own": "Todo es tuyo — exporta cuando quieras",
    "shield_dlp": "DLP bloquea datos sensibles",
    "shield_self_host": "Auto-hospedado — datos en tu servidor",

    "key_title": "Conecta Tu IA",
    "key_desc": "Agrega una clave API de cualquier proveedor — toma 30 segundos. Tu clave está cifrada y nunca sale de tu servidor.",
    "key_warn": "Los cargos del proveedor de IA son facturados por tu proveedor, no por MyTeam360.",
    "key_later": "Lo haré después",
    "key_done": "Listo",
    "key_save": "Guardar",

    "tos_title": "Antes de Comenzar",
    "tos_desc": "Acuerdo rápido — mantenemos las cosas transparentes.",
    "tos_accept": "Aceptar e Iniciar Prueba Gratuita",
    "pay_title": "Tu prueba ha terminado",
    "pay_desc": "Elige un plan para mantener tu equipo de IA funcionando.",
    "pay_subscribe": "Suscribirse Ahora →",
    "pay_guarantee": "Garantía de 7 días · Cancela cuando quieras",

    "dlp_blocked": "Datos sensibles detectados — mensaje bloqueado para tu protección.",

    "runs": "ejecuciones",
    "space": "Espacio",
    "spaces": "Espacios",
    "loading": "Cargando…",
}

LANG_JA = {
    "_code": "ja",
    "_name": "Japanese",
    "_native": "日本語",
    "_dir": "ltr",

    "app_name": "MyTeam360",
    "tagline": "あなたのAI。あなたのデータ。あなたの管理。",
    "login_email": "メールアドレス",
    "login_password": "パスワード",
    "login_enter": "ログイン",
    "login_connecting": "接続中…",
    "login_google": "Googleで続ける",
    "login_or": "または",
    "login_error_creds": "認証情報が無効です",
    "login_error_server": "サーバーに接続できません",
    "login_footer": "暗号化 · プライベート · あなたのもの",

    "create_tag": "始めましょう",
    "create_title": "何を作りたいですか？",
    "create_desc": "出発点を選ぶか、ゼロから作成してください。後からいつでもカスタマイズできます。",
    "create_go": "スペースを作成 →",
    "create_skip": "まず見せてください",
    "create_creating": "作成中…",
    "tpl_blank": "ゼロから始める",
    "tpl_blank_desc": "白紙のキャンバス — すべてを自分で定義",
    "tpl_writer": "コンテンツライター",
    "tpl_writer_desc": "ブログ、SNS、マーケティングコピー",
    "tpl_coder": "コードアシスタント",
    "tpl_coder_desc": "デバッグ、レビュー、コード作成",
    "tpl_analyst": "データアナリスト",
    "tpl_analyst_desc": "数値、トレンド、インサイトの分析",
    "tpl_strategist": "戦略アドバイザー",
    "tpl_strategist_desc": "事業計画、意思決定、トレードオフ",
    "tpl_support": "カスタマーサポート",
    "tpl_support_desc": "返信の作成、クレーム対応",
    "tpl_import": "GPTをインポート",
    "tpl_import_desc": "OpenAIアシスタントをここに持ってくる",

    "home_your_spaces": "あなたのスペース",
    "home_import": "GPTをインポート",
    "home_new": "+ 新しいスペース",
    "home_no_desc": "説明なし",
    "home_add": "新しいスペース",

    "chat_message": "メッセージ…",
    "chat_welcome": "会話を始めましょう…",
    "chat_error": "エラーが発生しました。もう一度お試しください。",
    "chat_connect": "AIプロバイダーを接続 →",

    "shield_protected": "保護済み",
    "shield_title": "データは安全です",
    "shield_encrypt": "エンドツーエンド暗号化ストレージ",
    "shield_keys": "APIキーは暗号化して保存",
    "shield_no_train": "データはAIモデルの訓練に使われません",
    "shield_own": "すべてのデータはあなたのもの",
    "shield_dlp": "DLPが機密データをブロック",
    "shield_self_host": "セルフホスト — データはあなたのサーバーに",

    "key_title": "AIを接続",
    "key_desc": "AIプロバイダーのAPIキーを追加 — 30秒で完了。キーは暗号化され、サーバーから出ることはありません。",
    "key_save": "保存",

    "tos_title": "始める前に",
    "tos_accept": "同意して無料トライアルを開始",
    "pay_title": "トライアルが終了しました",
    "pay_subscribe": "今すぐ登録 →",

    "dlp_blocked": "機密データが検出されました — メッセージはブロックされました。",

    "runs": "回実行",
    "space": "スペース",
    "spaces": "スペース",
    "loading": "読み込み中…",
}

LANG_PT = {
    "_code": "pt",
    "_name": "Portuguese",
    "_native": "Português",
    "_dir": "ltr",
    "app_name": "MyTeam360",
    "tagline": "Sua IA. Seus Dados. Seu Controle.",
    "login_email": "E-mail",
    "login_password": "Senha",
    "login_enter": "Entrar",
    "login_connecting": "Conectando…",
    "login_footer": "criptografado · privado · seu",
    "create_tag": "Vamos Começar",
    "create_title": "O que você quer construir?",
    "create_go": "Criar Meu Espaço →",
    "home_your_spaces": "Seus Espaços",
    "home_new": "+ Novo Espaço",
    "chat_message": "Mensagem…",
    "shield_protected": "Protegido",
    "shield_title": "Seus Dados Estão Seguros",
    "key_title": "Conecte Sua IA",
    "loading": "Carregando…",
}

LANG_FR = {
    "_code": "fr",
    "_name": "French",
    "_native": "Français",
    "_dir": "ltr",
    "app_name": "MyTeam360",
    "tagline": "Votre IA. Vos Données. Votre Contrôle.",
    "login_email": "E-mail",
    "login_password": "Mot de passe",
    "login_enter": "Entrer",
    "login_connecting": "Connexion…",
    "login_footer": "chiffré · privé · le vôtre",
    "create_tag": "Commençons",
    "create_title": "Que voulez-vous construire ?",
    "create_go": "Créer Mon Espace →",
    "home_your_spaces": "Vos Espaces",
    "home_new": "+ Nouvel Espace",
    "chat_message": "Message…",
    "shield_protected": "Protégé",
    "shield_title": "Vos Données Sont Sécurisées",
    "key_title": "Connectez Votre IA",
    "loading": "Chargement…",
}

LANG_ZH = {
    "_code": "zh",
    "_name": "Chinese (Simplified)",
    "_native": "中文",
    "_dir": "ltr",
    "app_name": "MyTeam360",
    "tagline": "你的AI。你的数据。你的控制。",
    "login_email": "邮箱",
    "login_password": "密码",
    "login_enter": "登录",
    "login_connecting": "连接中…",
    "login_footer": "加密 · 私密 · 属于你",
    "create_tag": "开始吧",
    "create_title": "你想构建什么？",
    "create_go": "创建我的空间 →",
    "home_your_spaces": "你的空间",
    "home_new": "+ 新空间",
    "chat_message": "消息…",
    "shield_protected": "已保护",
    "shield_title": "你的数据是安全的",
    "key_title": "连接你的AI",
    "loading": "加载中…",
}

LANG_AR = {
    "_code": "ar",
    "_name": "Arabic",
    "_native": "العربية",
    "_dir": "rtl",
    "app_name": "MyTeam360",
    "tagline": "الذكاء الاصطناعي الخاص بك. بياناتك. تحكمك.",
    "login_email": "البريد الإلكتروني",
    "login_password": "كلمة المرور",
    "login_enter": "دخول",
    "login_connecting": "جاري الاتصال…",
    "login_footer": "مشفر · خاص · ملكك",
    "create_tag": "لنبدأ",
    "create_title": "ماذا تريد أن تبني؟",
    "create_go": "← إنشاء مساحتي",
    "home_your_spaces": "مساحاتك",
    "home_new": "+ مساحة جديدة",
    "chat_message": "رسالة…",
    "shield_protected": "محمي",
    "shield_title": "بياناتك آمنة",
    "key_title": "اربط الذكاء الاصطناعي الخاص بك",
    "loading": "جاري التحميل…",
}

# ══════════════════════════════════════════════════════════════
# LANGUAGE REGISTRY
# ══════════════════════════════════════════════════════════════

LANGUAGES = {
    "en": LANG_EN,
    "es": LANG_ES,
    "ja": LANG_JA,
    "pt": LANG_PT,
    "fr": LANG_FR,
    "zh": LANG_ZH,
    "ar": LANG_AR,
}

def get_available_languages() -> list:
    """Return list of supported languages."""
    return [{"code": v["_code"], "name": v["_name"], "native": v["_native"],
             "dir": v.get("_dir", "ltr")}
            for v in LANGUAGES.values()]

def get_translations(lang_code: str) -> dict:
    """Get all translations for a language. Falls back to English for missing keys."""
    lang = LANGUAGES.get(lang_code, LANG_EN)
    # Merge with English as fallback
    merged = {**LANG_EN, **lang}
    return merged

def translate(key: str, lang_code: str = "en") -> str:
    """Get a single translated string."""
    lang = LANGUAGES.get(lang_code, LANG_EN)
    return lang.get(key, LANG_EN.get(key, key))


class I18nManager:
    """Manages user language preferences and serves translations."""

    def set_user_language(self, user_id: str, lang_code: str):
        """Set a user's preferred language."""
        if lang_code not in LANGUAGES:
            raise ValueError(f"Unsupported language: {lang_code}")
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO user_preferences (user_id, key, value) VALUES (?,?,?)",
                (user_id, "language", lang_code)
            )

    def get_user_language(self, user_id: str) -> str:
        """Get a user's preferred language (default: en)."""
        with get_db() as db:
            row = db.execute(
                "SELECT value FROM user_preferences WHERE user_id=? AND key='language'",
                (user_id,)
            ).fetchone()
        return row["value"] if row else "en"

    def get_user_translations(self, user_id: str) -> dict:
        """Get full translation pack for a user."""
        lang = self.get_user_language(user_id)
        return get_translations(lang)

    def detect_language(self, accept_language_header: str) -> str:
        """Auto-detect language from browser Accept-Language header."""
        if not accept_language_header:
            return "en"
        # Parse "es-MX,es;q=0.9,en;q=0.8" format
        langs = []
        for part in accept_language_header.split(","):
            part = part.strip()
            if ";q=" in part:
                code, q = part.split(";q=")
                langs.append((code.strip().split("-")[0], float(q)))
            else:
                langs.append((part.strip().split("-")[0], 1.0))
        langs.sort(key=lambda x: -x[1])
        for code, _ in langs:
            if code in LANGUAGES:
                return code
        return "en"
