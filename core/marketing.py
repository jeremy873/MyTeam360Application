# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# See LICENSE and NOTICE files for full legal terms.
# ═══════════════════════════════════════════════════════════════════

"""
Digital Marketing Engine — Country-Aware Marketing Intelligence

Locale-aware marketing that understands:
  - Which platforms dominate in each country
  - Local advertising regulations and restrictions
  - Cultural sensitivities and seasonal events
  - Content formats that work in each market
  - Local SEO requirements and search engines
  - Influencer marketing norms per region

Features:
  1. Campaign Planner — strategy based on market, audience, budget
  2. Content Calendar — locale-aware scheduling with local holidays
  3. Platform Advisor — which channels work in which country
  4. Copy Generator — ad copy, social posts, email in local language + style
  5. Ad Compliance — local advertising regulations checker
  6. SEO Advisor — local search engines, keywords, and ranking factors
  7. Campaign Performance Tracker — metrics, attribution, optimization
"""

import json
import uuid
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.marketing")


# ══════════════════════════════════════════════════════════════
# MARKET INTELLIGENCE — Platform + regulatory data per country
# ══════════════════════════════════════════════════════════════

MARKET_PROFILES = {
    "US": {
        "top_platforms": ["Google Ads", "Meta (Facebook/Instagram)", "TikTok", "LinkedIn", "X (Twitter)", "YouTube", "Reddit", "Pinterest", "Snapchat"],
        "search_engines": ["Google (~88%)", "Bing (~7%)", "Yahoo (~2.5%)"],
        "messaging_apps": ["iMessage", "WhatsApp", "Facebook Messenger"],
        "ad_regulations": {
            "authority": "FTC (Federal Trade Commission)",
            "key_rules": [
                "FTC Act Section 5 — ads must be truthful and non-deceptive",
                "Endorsement Guides — influencers must disclose #ad or #sponsored",
                "CAN-SPAM Act — email marketing opt-out required",
                "COPPA — no targeting children under 13 without parental consent",
                "TCPA — telemarketing and SMS consent requirements",
                "State-specific: California's CCPA affects ad targeting with personal data",
            ],
        },
        "cultural_notes": "Diversity and inclusion in imagery expected. Humor works. Urgency/scarcity effective. Holiday calendar: Black Friday, Cyber Monday, Super Bowl, July 4th, Thanksgiving.",
        "content_style": "Casual to professional depending on brand. Short-form video dominant. UGC highly effective. Mobile-first.",
    },
    "GB": {
        "top_platforms": ["Google Ads", "Meta (Facebook/Instagram)", "TikTok", "LinkedIn", "X (Twitter)", "YouTube"],
        "search_engines": ["Google (~92%)", "Bing (~5%)"],
        "messaging_apps": ["WhatsApp", "iMessage", "Facebook Messenger"],
        "ad_regulations": {
            "authority": "ASA (Advertising Standards Authority) + CAP Code",
            "key_rules": [
                "CAP Code — all ads must be legal, decent, honest, and truthful",
                "ASA enforces across all media including social and influencer",
                "Influencers must label ads clearly — #ad at the start of posts",
                "UK GDPR — consent required for marketing cookies and email",
                "HFSS (junk food) advertising restrictions near implementation",
                "Gambling advertising heavily restricted — GambleAware requirements",
            ],
        },
        "cultural_notes": "Understatement and dry humor appreciated. Avoid hard-sell tactics. NHS and public services are sensitive topics in ad context. Key dates: Boxing Day sales, Bank Holidays, Bonfire Night.",
        "content_style": "Slightly more formal than US. Self-deprecating humor works. Quality over quantity. Video content growing fast on TikTok/Reels.",
    },
    "MX": {
        "top_platforms": ["Meta (Facebook/Instagram)", "TikTok", "YouTube", "X (Twitter)", "LinkedIn (business)", "WhatsApp Business"],
        "search_engines": ["Google (~95%)"],
        "messaging_apps": ["WhatsApp (dominant)", "Facebook Messenger", "Telegram"],
        "ad_regulations": {
            "authority": "PROFECO + Ley Federal de Protección al Consumidor",
            "key_rules": [
                "Advertising must be truthful — PROFECO enforcement",
                "COFEPRIS regulates health/pharma/food advertising",
                "Children's advertising restricted — Ley General de Salud",
                "LFPDPPP — consent for marketing with personal data (privacy notice required)",
                "Alcohol advertising restricted to specific hours",
            ],
        },
        "cultural_notes": "Family-centered messaging resonates. Humor is warm and inclusive. Religious holidays major (Día de los Muertos, Christmas, Easter). Regional differences between Mexico City, Monterrey, Guadalajara. WhatsApp is THE business communication channel.",
        "content_style": "Emotional storytelling performs well. Video content highly consumed. Spanish-language content essential. Local influencers more trusted than international celebrities.",
    },
    "DE": {
        "top_platforms": ["Google Ads", "Meta (Facebook/Instagram)", "LinkedIn (XING for DACH)", "YouTube", "TikTok", "Pinterest"],
        "search_engines": ["Google (~90%)", "Bing (~5%)", "Ecosia (~2% — German eco search engine)"],
        "messaging_apps": ["WhatsApp (dominant)", "Telegram", "Signal"],
        "ad_regulations": {
            "authority": "Wettbewerbszentrale + Landesmedienanstalten",
            "key_rules": [
                "Gesetz gegen den unlauteren Wettbewerb (UWG) — Unfair Competition Act",
                "GDPR/BDSG — strictest enforcement in EU for marketing consent",
                "TMG (Telemediengesetz) — cookie consent must be opt-in with granularity",
                "Impressum required on all commercial websites and social profiles",
                "Influencer marketing must be clearly labeled (Kennzeichnungspflicht)",
                "Comparative advertising allowed but must be factual and verifiable",
            ],
        },
        "cultural_notes": "Quality and precision valued. Environmental consciousness strong — green messaging resonates. Skepticism toward flashy advertising. Data privacy is a MAJOR concern. Key dates: Oktoberfest, Christmas markets, trade fairs (CeBIT, IFA, Hannover Messe).",
        "content_style": "Formal and informative. Technical specifications appreciated. Case studies and certifications carry weight. German-language content essential — English accepted in tech but not broadly.",
    },
    "JP": {
        "top_platforms": ["LINE Ads", "Yahoo! Japan Ads", "Google Ads", "X (Twitter — huge in Japan)", "Instagram", "YouTube", "TikTok"],
        "search_engines": ["Google (~76%)", "Yahoo! Japan (~20% — uses Google's engine but different ad platform)"],
        "messaging_apps": ["LINE (dominant — 90M+ users)", "Facebook Messenger"],
        "ad_regulations": {
            "authority": "JARO (Japan Advertising Review Organization) + Consumer Affairs Agency",
            "key_rules": [
                "Act Against Unjustifiable Premiums and Misleading Representations",
                "Pharmaceutical and Medical Device Act — strict health claims regulation",
                "APPI — consent required for marketing use of personal data",
                "Stealth marketing banned (2023) — influencer disclosure mandatory",
                "Alcohol/tobacco advertising restricted",
            ],
        },
        "cultural_notes": "Aesthetic quality extremely important. Cute (kawaii) culture influences design. Seasonal marketing critical (cherry blossom, Golden Week, New Year). Trust built through longevity and reputation. LINE is more important than email for many demographics.",
        "content_style": "High production quality expected. Manga/anime style can work for certain demographics. Detailed product information valued. Mobile-centric — most browsing is on phones.",
    },
    "BR": {
        "top_platforms": ["Meta (Facebook/Instagram — Instagram is HUGE)", "YouTube", "TikTok", "LinkedIn", "Google Ads", "Twitter/X", "Kwai"],
        "search_engines": ["Google (~96%)"],
        "messaging_apps": ["WhatsApp (universal — 99% smartphone penetration)", "Telegram"],
        "ad_regulations": {
            "authority": "CONAR (Conselho Nacional de Autorregulamentação Publicitária)",
            "key_rules": [
                "Código de Defesa do Consumidor — consumer protection in advertising",
                "CONAR self-regulation code — ethical advertising standards",
                "LGPD — consent required for marketing with personal data",
                "ANVISA regulates health/pharma/food claims",
                "Children's advertising severely restricted",
                "Political advertising regulated by TSE (electoral court)",
            ],
        },
        "cultural_notes": "Passion and emotion in messaging. Carnival, São João, Christmas are major. Soccer/football references resonate. Strong regional identities (São Paulo vs Rio vs Northeast). Social media engagement rates among highest globally. Installment payments (parcelamento) expected in e-commerce.",
        "content_style": "Vibrant, colorful, emotional. Video dominates. Instagram Reels and TikTok massive. Portuguese essential — Brazilian Portuguese specifically (not European). Informal, warm tone preferred.",
    },
    "AE": {
        "top_platforms": ["Instagram", "TikTok", "Snapchat", "YouTube", "LinkedIn", "Google Ads", "X (Twitter)"],
        "search_engines": ["Google (~97%)"],
        "messaging_apps": ["WhatsApp (dominant)", "Telegram", "Botim"],
        "ad_regulations": {
            "authority": "National Media Council + Dubai Media Regulatory Office",
            "key_rules": [
                "Content must respect Islamic values and local customs",
                "Alcohol advertising restricted (except in free zones with permits)",
                "Pork-related products cannot be advertised publicly",
                "Ramadan advertising has special rules — respectful messaging required",
                "UAE Data Protection Law — consent for marketing data usage",
                "Influencer marketing requires NMC license",
            ],
        },
        "cultural_notes": "Luxury and aspiration messaging works. Bilingual content (Arabic + English) often needed. Friday-Saturday weekend. Ramadan is the biggest marketing season. National Day (December 2) major. Diverse expat population — consider multiple cultural contexts. Dubai vs Abu Dhabi have different vibes.",
        "content_style": "High-end visual quality. Arabic and English bilingual. Influencer marketing massive. Snapchat very popular with younger demographics. Video content preferred.",
    },
    "IN": {
        "top_platforms": ["Google Ads", "Meta (Facebook/Instagram)", "YouTube", "WhatsApp Business", "LinkedIn", "X (Twitter)", "ShareChat", "Moj"],
        "search_engines": ["Google (~98%)"],
        "messaging_apps": ["WhatsApp (dominant)", "Telegram", "Signal"],
        "ad_regulations": {
            "authority": "ASCI (Advertising Standards Council of India)",
            "key_rules": [
                "ASCI Code — ads must be truthful, not misleading",
                "Consumer Protection Act 2019 — CCPA enforcement",
                "DPDPA 2023 — consent for marketing data usage",
                "AYUSH Ministry regulates health product claims",
                "Surrogate advertising (alcohol brands) heavily scrutinized",
                "Celebrity endorsements must be truthful — personal liability",
            ],
        },
        "cultural_notes": "Festival marketing essential (Diwali, Holi, Eid, Pongal, Navratri). Cricket is THE sport for sponsorship. Extremely price-sensitive market. Regional language content (Hindi, Tamil, Telugu, etc.) often outperforms English. Family and aspiration themes resonate. UPI/digital payments ubiquitous.",
        "content_style": "Multilingual approach needed. Short-form video exploding. WhatsApp marketing growing fast. Mobile-first — affordable smartphones. Local language content has 3-5x engagement vs English. Bollywood references can work.",
    },
    "FR": {
        "top_platforms": ["Google Ads", "Meta (Facebook/Instagram)", "YouTube", "LinkedIn", "TikTok", "Snapchat", "X (Twitter)"],
        "search_engines": ["Google (~92%)", "Bing (~4%)", "Qwant (~1% — French privacy search engine)"],
        "messaging_apps": ["WhatsApp", "iMessage", "Facebook Messenger"],
        "ad_regulations": {
            "authority": "ARPP (Autorité de Régulation Professionnelle de la Publicité)",
            "key_rules": [
                "Loi Évin — strict prohibition on alcohol advertising (very limited exceptions)",
                "GDPR/CNIL — strictest cookie consent enforcement. CNIL fines are massive.",
                "Influencer marketing law (2023) — one of the most regulated in the world",
                "French language law (Loi Toubon) — advertising must be in French (translations permitted alongside)",
                "Environmental claims must be substantiated (anti-greenwashing law 2024)",
                "Children's advertising of unhealthy food restricted",
            ],
        },
        "cultural_notes": "French language is REQUIRED in advertising (Loi Toubon). Subtlety and elegance valued. Food and wine culture central. Les Soldes (official sale periods) are regulated by law. Bastille Day, vacation culture (August shutdown). Anti-consumerism sentiment exists — authentic messaging important.",
        "content_style": "French language mandatory. Elegant, intellectual, artistic. Quality imagery essential. Less aggressive CTAs than US. Long-form content works better than in many markets. LinkedIn very strong for B2B.",
    },
    "SA": {
        "top_platforms": ["Snapchat (highest per-capita in world)", "Instagram", "TikTok", "X (Twitter — very active)", "YouTube", "Google Ads"],
        "search_engines": ["Google (~97%)"],
        "messaging_apps": ["WhatsApp", "Telegram"],
        "ad_regulations": {
            "authority": "General Authority for Media Regulation",
            "key_rules": [
                "All content must align with Islamic values and Saudi customs",
                "Women can appear in ads but modesty standards apply",
                "Alcohol and pork products cannot be advertised",
                "PDPL — consent for marketing data usage",
                "Vision 2030 entertainment reforms expanding what's permissible",
                "Influencer registration required — CITC license",
            ],
        },
        "cultural_notes": "Youngest population in G20 — digital-first generation. Snapchat usage is phenomenal. Vision 2030 creating entertainment boom. Ramadan is the Super Bowl of marketing. Arabic content essential. Saudi National Day (September 23) major. Gender-mixed events now permitted — reflects cultural shift.",
        "content_style": "Arabic-first. High production quality. Snapchat and TikTok dominate younger demographics. Twitter/X highly active for conversation. Mobile consumption near 100%. Gaming and esports growing rapidly.",
    },
}


class DigitalMarketingEngine:
    """Country-aware digital marketing intelligence and campaign management."""

    def __init__(self, agent_manager=None, global_context=None):
        self.agents = agent_manager
        self.global_ctx = global_context

    # ── CAMPAIGN PLANNER ────────────────────────────────────

    def create_campaign(self, owner_id: str, name: str, objective: str,
                        target_country: str, target_audience: str = "",
                        budget: float = 0, budget_currency: str = "USD",
                        start_date: str = None, end_date: str = None,
                        notes: str = "") -> dict:
        cid = f"camp_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO marketing_campaigns
                    (id, owner_id, name, objective, target_country, target_audience,
                     budget, budget_currency, start_date, end_date, notes, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cid, owner_id, name, objective, target_country.upper(),
                  target_audience, budget, budget_currency,
                  start_date, end_date, notes, "planning"))
        return {"id": cid, "name": name, "country": target_country.upper()}

    def get_campaign(self, cid: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM marketing_campaigns WHERE id=?", (cid,)).fetchone()
        return dict(row) if row else None

    def list_campaigns(self, owner_id: str, status: str = None) -> list:
        with get_db() as db:
            if status:
                rows = db.execute(
                    "SELECT * FROM marketing_campaigns WHERE owner_id=? AND status=? ORDER BY created_at DESC",
                    (owner_id, status)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM marketing_campaigns WHERE owner_id=? ORDER BY created_at DESC",
                    (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def update_campaign(self, cid: str, updates: dict) -> dict:
        safe = {"name", "objective", "target_country", "target_audience", "budget",
                "budget_currency", "start_date", "end_date", "notes", "status"}
        filtered = {k: v for k, v in updates.items() if k in safe}
        filtered["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in filtered)
        vals = list(filtered.values()) + [cid]
        with get_db() as db:
            db.execute(f"UPDATE marketing_campaigns SET {sets} WHERE id=?", vals)
        return self.get_campaign(cid)

    # ── AI-POWERED FEATURES ─────────────────────────────────

    def generate_strategy(self, cid: str, owner_id: str) -> dict:
        """AI generates a full marketing strategy for the campaign."""
        camp = self.get_campaign(cid)
        if not camp: return {"error": "Campaign not found"}

        country = camp["target_country"]
        market = MARKET_PROFILES.get(country, {})
        lang_ctx = ""
        if self.global_ctx:
            lang_ctx = self.global_ctx.get_language_instruction(country_code=country)

        prompt = (
            f"{lang_ctx}\n\n"
            f"You are a digital marketing strategist with expertise in the {market.get('name', country)} market.\n\n"
            f"Create a comprehensive marketing strategy for:\n"
            f"Campaign: {camp['name']}\n"
            f"Objective: {camp['objective']}\n"
            f"Target Country: {market.get('name', country)}\n"
            f"Target Audience: {camp.get('target_audience', 'General')}\n"
            f"Budget: {camp.get('budget_currency','USD')} {camp.get('budget',0):,.0f}\n\n"
            f"Market Intelligence:\n"
            f"Top platforms: {', '.join(market.get('top_platforms', []))}\n"
            f"Search engines: {', '.join(market.get('search_engines', []))}\n"
            f"Messaging apps: {', '.join(market.get('messaging_apps', []))}\n"
            f"Content style: {market.get('content_style', '')}\n"
            f"Cultural notes: {market.get('cultural_notes', '')}\n\n"
            "Provide:\n"
            "1. CHANNEL MIX — Which platforms and what % of budget for each\n"
            "2. CONTENT STRATEGY — What types of content for each channel\n"
            "3. MESSAGING FRAMEWORK — Key messages adapted to local culture\n"
            "4. TIMELINE — Phased rollout with milestones\n"
            "5. KPIs — Specific metrics to track\n"
            "6. LOCAL CONSIDERATIONS — Cultural sensitivities, seasonal events, regulatory constraints\n"
            "7. BUDGET ALLOCATION — Detailed breakdown\n"
        )

        strategy = self._run_agent(owner_id, prompt)
        self._save_content(cid, "strategy", strategy)
        return {"campaign_id": cid, "strategy": strategy}

    def generate_content(self, cid: str, owner_id: str,
                         content_type: str, platform: str = "",
                         topic: str = "", tone: str = "",
                         additional_instructions: str = "") -> dict:
        """Generate locale-aware marketing content."""
        camp = self.get_campaign(cid)
        if not camp: return {"error": "Campaign not found"}

        country = camp["target_country"]
        market = MARKET_PROFILES.get(country, {})
        lang_ctx = ""
        if self.global_ctx:
            lang_ctx = self.global_ctx.get_language_instruction(country_code=country)

        content_types = {
            "social_post": "a social media post",
            "ad_copy": "advertising copy (headline + body + CTA)",
            "email": "a marketing email (subject + preview + body)",
            "blog_outline": "a blog post outline with SEO keywords",
            "landing_page": "landing page copy (headline, subhead, features, CTA)",
            "video_script": "a short video script (hook, body, CTA)",
            "press_release": "a press release",
            "newsletter": "a newsletter edition",
        }

        type_desc = content_types.get(content_type, content_type)
        platform_note = f" for {platform}" if platform else ""

        prompt = (
            f"{lang_ctx}\n\n"
            f"Create {type_desc}{platform_note} for the {market.get('name', country)} market.\n\n"
            f"Campaign: {camp['name']}\n"
            f"Objective: {camp['objective']}\n"
            f"Audience: {camp.get('target_audience', 'General')}\n"
            f"Content style for this market: {market.get('content_style', '')}\n"
            f"Cultural context: {market.get('cultural_notes', '')}\n"
        )
        if topic: prompt += f"Topic: {topic}\n"
        if tone: prompt += f"Tone: {tone}\n"
        if additional_instructions: prompt += f"Additional: {additional_instructions}\n"

        prompt += (
            "\nEnsure the content:\n"
            "- Is culturally appropriate for the target market\n"
            "- Uses local language conventions and idioms\n"
            "- References relevant local context where appropriate\n"
            "- Follows local advertising regulations\n"
            "- Includes appropriate hashtags/keywords for the market\n"
        )

        content = self._run_agent(owner_id, prompt)
        self._save_content(cid, content_type, content, platform=platform)
        return {"campaign_id": cid, "content_type": content_type, "content": content}

    def check_ad_compliance(self, cid: str, owner_id: str,
                             ad_text: str) -> dict:
        """Check ad copy against local advertising regulations."""
        camp = self.get_campaign(cid)
        if not camp: return {"error": "Campaign not found"}

        country = camp["target_country"]
        market = MARKET_PROFILES.get(country, {})
        regs = market.get("ad_regulations", {})

        prompt = (
            f"You are an advertising compliance specialist for {market.get('name', country)}.\n\n"
            f"Review this ad copy for compliance with local regulations:\n\n"
            f"Regulatory authority: {regs.get('authority', 'N/A')}\n"
            f"Key rules:\n" + "\n".join(f"• {r}" for r in regs.get("key_rules", [])) + "\n\n"
            f"Ad copy to review:\n{ad_text}\n\n"
            "Provide:\n"
            "1. COMPLIANCE STATUS — Pass / Fail / Needs Revision\n"
            "2. ISSUES FOUND — Specific regulatory violations or risks\n"
            "3. RECOMMENDED CHANGES — Exact revisions to fix each issue\n"
            "4. RISK LEVEL — Low / Medium / High\n"
        )

        result = self._run_agent(owner_id, prompt)
        return {"campaign_id": cid, "country": country, "compliance_check": result}

    def get_platform_guide(self, country_code: str) -> dict:
        """Get platform strategy guide for a specific country."""
        market = MARKET_PROFILES.get(country_code.upper())
        if not market: return {"error": f"No market data for {country_code}"}
        return {
            "country": country_code.upper(),
            "top_platforms": market.get("top_platforms", []),
            "search_engines": market.get("search_engines", []),
            "messaging_apps": market.get("messaging_apps", []),
            "content_style": market.get("content_style", ""),
            "cultural_notes": market.get("cultural_notes", ""),
            "ad_regulations": market.get("ad_regulations", {}),
        }

    def get_seo_brief(self, cid: str, owner_id: str,
                       keywords: list = None) -> dict:
        """Generate an SEO brief tailored to the local search landscape."""
        camp = self.get_campaign(cid)
        if not camp: return {"error": "Campaign not found"}

        country = camp["target_country"]
        market = MARKET_PROFILES.get(country, {})
        lang_ctx = ""
        if self.global_ctx:
            lang_ctx = self.global_ctx.get_language_instruction(country_code=country)

        prompt = (
            f"{lang_ctx}\n\n"
            f"Create an SEO brief for the {market.get('name', country)} market.\n\n"
            f"Business: {camp['name']}\n"
            f"Objective: {camp['objective']}\n"
            f"Search engines in this market: {', '.join(market.get('search_engines', []))}\n"
        )
        if keywords:
            prompt += f"Seed keywords: {', '.join(keywords)}\n"
        prompt += (
            "\nProvide:\n"
            "1. LOCAL KEYWORD STRATEGY — Keywords in the local language with search intent\n"
            "2. ON-PAGE SEO — Title tags, meta descriptions, headers in local language\n"
            "3. LOCAL SEO — Google Business Profile, local directories, NAP consistency\n"
            "4. CONTENT RECOMMENDATIONS — Topics that rank in this market\n"
            "5. TECHNICAL CONSIDERATIONS — hreflang tags, local hosting, CDN\n"
            "6. LINK BUILDING — Local directories, PR outlets, industry sites\n"
        )

        brief = self._run_agent(owner_id, prompt)
        return {"campaign_id": cid, "country": country, "seo_brief": brief}

    # ── INTERNAL ────────────────────────────────────────────

    def _run_agent(self, owner_id: str, prompt: str) -> str:
        if not self.agents:
            return "(Agent manager not connected)"
        with get_db() as db:
            agent = db.execute("SELECT id FROM agents WHERE owner_id=? LIMIT 1",
                              (owner_id,)).fetchone()
        if not agent:
            return "(No Spaces configured)"
        result = self.agents.run_agent(dict(agent)["id"], prompt, user_id=owner_id)
        return result.get("text", "")

    def _save_content(self, campaign_id: str, content_type: str,
                      content: str, platform: str = ""):
        cid = f"mc_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO marketing_content
                    (id, campaign_id, content_type, platform, content)
                VALUES (?,?,?,?,?)
            """, (cid, campaign_id, content_type, platform, content[:10000]))
