# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# See LICENSE and NOTICE files for full legal terms.
# ═══════════════════════════════════════════════════════════════════

"""
Global Context Engine — Country-aware intelligence for every feature.

Every feature on the platform becomes locale-aware:
  - Sales Coach → interview prep in the client's language + local customs
  - Compliance → country-specific laws and regulations
  - Governance → local corporate governance requirements
  - Deliverables → local business format and conventions
  - Roundtable → multi-language discussion support
  - Policy Engine → jurisdiction-aware policy enforcement

The user sets their locale (or per-deal/per-client locale) and
every AI prompt gets enriched with country-specific context.
"""

import json
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.global_context")


# ══════════════════════════════════════════════════════════════
# COUNTRY PROFILES — Laws, customs, languages, business norms
# ══════════════════════════════════════════════════════════════

COUNTRY_PROFILES = {
    "US": {
        "name": "United States",
        "languages": ["en"],
        "currency": "USD",
        "business_culture": (
            "Direct communication style. Value efficiency and data-driven decisions. "
            "Handshakes common. Business cards exchanged casually. First names used quickly. "
            "Presentations should be concise with clear ROI. Decision-making can be fast."
        ),
        "compliance_laws": {
            "anti_bribery": "Foreign Corrupt Practices Act (FCPA) — 15 U.S.C. § 78dd",
            "data_privacy": "State-level laws (CCPA/CPRA in California, VCDPA in Virginia, etc.). No federal comprehensive privacy law.",
            "employment": "Title VII (discrimination), FLSA (wages), OSHA (safety), ADA (disability), FMLA (leave)",
            "securities": "Securities Exchange Act of 1934, Sarbanes-Oxley Act, Dodd-Frank Act",
            "antitrust": "Sherman Act, Clayton Act, FTC Act",
            "trade_secrets": "Defend Trade Secrets Act (DTSA) — 18 U.S.C. § 1836",
            "consumer_protection": "FTC Act Section 5, state UDAP statutes",
            "whistleblower": "Dodd-Frank, Sarbanes-Oxley whistleblower protections",
        },
        "governance_requirements": (
            "SOX compliance for public companies. SEC reporting requirements. "
            "Board fiduciary duties under state law (typically Delaware). "
            "Annual meetings, proxy statements, 10-K/10-Q filings."
        ),
        "sales_customs": (
            "Proposals should lead with executive summary. Pricing typically at the end. "
            "Case studies and ROI calculations are valued. References expected. "
            "Government contracts follow FAR/DFAR regulations."
        ),
    },
    "GB": {
        "name": "United Kingdom",
        "languages": ["en"],
        "currency": "GBP",
        "business_culture": (
            "Formal but with understated humor. Politeness is crucial — directness is tempered. "
            "Punctuality expected. Business dress tends formal. Tea/coffee offered at meetings. "
            "Decision-making can be slower, consensus-oriented."
        ),
        "compliance_laws": {
            "anti_bribery": "UK Bribery Act 2010 — Sections 1, 2, 6, 7 (strictest in the world — covers private sector bribery and failure to prevent)",
            "data_privacy": "UK GDPR + Data Protection Act 2018. ICO enforcement. Requires DPO for large-scale processing.",
            "employment": "Employment Rights Act 1996, Equality Act 2010, Health and Safety at Work Act 1974",
            "securities": "Financial Services and Markets Act 2000 (FSMA), FCA regulation",
            "antitrust": "Competition Act 1998, Enterprise Act 2002, CMA enforcement",
            "trade_secrets": "Trade Secrets (Enforcement) Regulations 2018 (EU directive transposed)",
            "whistleblower": "Public Interest Disclosure Act 1998 (PIDA)",
        },
        "governance_requirements": (
            "UK Corporate Governance Code (comply or explain). Companies Act 2006. "
            "FCA Listing Rules for public companies. Annual reports, AGM requirements."
        ),
        "sales_customs": (
            "Proposals should be thorough but not aggressive. Understated confidence preferred. "
            "References and track record matter heavily. Public sector follows procurement regulations."
        ),
    },
    "MX": {
        "name": "Mexico",
        "languages": ["es"],
        "currency": "MXN",
        "business_culture": (
            "Relationships come first — build personal rapport before business. Meetings often start late. "
            "Titles are important (Licenciado, Ingeniero, Doctor). Handshakes and sometimes embraces. "
            "Lunch meetings are common and can last 2+ hours. Trust is built over time."
        ),
        "compliance_laws": {
            "anti_bribery": "Ley General de Responsabilidades Administrativas (General Law of Administrative Responsibilities). Federal Anti-Corruption System.",
            "data_privacy": "Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP). INAI enforcement.",
            "employment": "Ley Federal del Trabajo (Federal Labor Law). Strong employee protections, mandatory profit sharing (PTU).",
            "trade_secrets": "Ley Federal de Protección a la Propiedad Industrial (Industrial Property Law)",
            "consumer_protection": "PROFECO (Federal Consumer Protection Agency)",
        },
        "governance_requirements": (
            "Ley General de Sociedades Mercantiles. CNBV regulation for public companies. "
            "Annual shareholder meetings required. Comisario (statutory auditor) oversight."
        ),
        "sales_customs": (
            "Formal proposals in Spanish unless client specifies English. Personal relationships "
            "heavily influence decisions. Government procurement follows Ley de Adquisiciones. "
            "Pricing discussions are often negotiated heavily."
        ),
    },
    "DE": {
        "name": "Germany",
        "languages": ["de"],
        "currency": "EUR",
        "business_culture": (
            "Highly structured and formal. Punctuality is essential — being late is disrespectful. "
            "Use formal titles (Herr/Frau + last name) until invited otherwise. "
            "Thorough preparation expected. Decisions are methodical and evidence-based."
        ),
        "compliance_laws": {
            "anti_bribery": "Strafgesetzbuch (StGB) §§ 299, 331-335. Supply Chain Due Diligence Act (LkSG).",
            "data_privacy": "EU GDPR + Bundesdatenschutzgesetz (BDSG). BfDI enforcement. Very strict — highest GDPR fines in EU.",
            "employment": "Betriebsverfassungsgesetz (Works Council Act). Strong co-determination rights. Kündigungsschutzgesetz (dismissal protection).",
            "trade_secrets": "Geschäftsgeheimnisgesetz (GeschGehG) — Trade Secrets Act (EU directive implementation)",
            "antitrust": "Gesetz gegen Wettbewerbsbeschränkungen (GWB) — Competition Act. Bundeskartellamt enforcement.",
        },
        "governance_requirements": (
            "Aktiengesetz (Stock Corporation Act) for AG companies. Two-tier board structure "
            "(Vorstand + Aufsichtsrat). Co-determination laws require employee representatives on supervisory board."
        ),
        "sales_customs": (
            "Proposals must be detailed and technically precise. Germans value thoroughness over flashiness. "
            "References and certifications (ISO, etc.) carry significant weight."
        ),
    },
    "JP": {
        "name": "Japan",
        "languages": ["ja"],
        "currency": "JPY",
        "business_culture": (
            "Highly formal. Business cards (meishi) exchanged with both hands and read carefully. "
            "Bowing is standard. Hierarchy is important — address the most senior person first. "
            "Silence is not awkward — it indicates thoughtful consideration. Consensus (nemawashi) "
            "is built before meetings. Avoid direct confrontation."
        ),
        "compliance_laws": {
            "anti_bribery": "Unfair Competition Prevention Act (UCPA). National Personnel Authority Act for public officials.",
            "data_privacy": "Act on the Protection of Personal Information (APPI). PPC enforcement.",
            "employment": "Labor Standards Act, Labor Contract Act. Very strong employee protections — termination is difficult.",
            "trade_secrets": "Unfair Competition Prevention Act (UCPA) — criminal penalties for trade secret theft",
            "antitrust": "Act on Prohibition of Private Monopolization and Maintenance of Fair Trade (Antimonopoly Act). JFTC enforcement.",
        },
        "governance_requirements": (
            "Companies Act of Japan. Corporate Governance Code (comply or explain). "
            "Three governance structures available: Company with Board of Auditors, "
            "Company with Audit Committee, Company with Nominating Committee."
        ),
        "sales_customs": (
            "Long sales cycles. Building relationships (trust) is essential before any transaction. "
            "Proposals should be meticulously prepared. Gift-giving is common. "
            "Group consensus means you need buy-in from multiple stakeholders."
        ),
    },
    "BR": {
        "name": "Brazil",
        "languages": ["pt"],
        "currency": "BRL",
        "business_culture": (
            "Warm and relationship-driven. Physical closeness in conversation is normal. "
            "Meetings may start late. Personal conversation before business is expected. "
            "Brazilians value personal connections — who you know matters greatly."
        ),
        "compliance_laws": {
            "anti_bribery": "Lei Anticorrupção (Clean Company Act — Law 12,846/2013). Criminal liability for companies.",
            "data_privacy": "Lei Geral de Proteção de Dados (LGPD — Law 13,709/2018). ANPD enforcement.",
            "employment": "Consolidação das Leis do Trabalho (CLT). Extremely protective of employees — complex labor courts.",
            "trade_secrets": "Industrial Property Law (Law 9,279/1996)",
            "consumer_protection": "Código de Defesa do Consumidor (CDC — Consumer Defense Code)",
        },
        "governance_requirements": (
            "Lei das S.A. (Corporation Law 6,404/1976). CVM regulation for public companies. "
            "Novo Mercado listing rules for highest governance standards."
        ),
        "sales_customs": (
            "Proposals in Portuguese unless multinational client. Relationship building is critical. "
            "Government procurement follows Lei de Licitações (Law 14,133/2021). "
            "Pricing should account for complex tax structure (ICMS, ISS, PIS/COFINS)."
        ),
    },
    "AE": {
        "name": "United Arab Emirates",
        "languages": ["ar", "en"],
        "currency": "AED",
        "business_culture": (
            "Formal and relationship-driven. Arabic coffee and dates offered at meetings. "
            "Right hand for greetings and exchanges. Business discussions may take several meetings. "
            "Friday-Saturday weekend. Ramadan affects business hours significantly."
        ),
        "compliance_laws": {
            "anti_bribery": "Federal Penal Code Articles 234-239. ADGM/DIFC have separate frameworks.",
            "data_privacy": "Federal Decree-Law No. 45 of 2021 (UAE Personal Data Protection Law). DIFC Data Protection Law.",
            "employment": "Federal Decree-Law No. 33 of 2021 (new Labor Law). WPS (Wage Protection System).",
            "trade_secrets": "Federal Law No. 19 of 2016 on Combating Commercial Fraud",
        },
        "governance_requirements": (
            "UAE Commercial Companies Law. Free zone-specific governance (DIFC, ADGM). "
            "Central Bank regulations for financial entities. ESG reporting increasing."
        ),
        "sales_customs": (
            "Patience is essential. Multiple meetings before commitment. "
            "Proposals should be available in both Arabic and English. "
            "Government tenders follow specific procurement regulations per emirate."
        ),
    },
    "IN": {
        "name": "India",
        "languages": ["hi", "en"],
        "currency": "INR",
        "business_culture": (
            "Hierarchical. Address seniors with 'Sir/Ma'am' or titles. Namaste greeting is common. "
            "Meetings may start late but end times are flexible. Relationship building important. "
            "Indirect communication — 'yes' may mean 'I'll consider it'. Vegetarian options at meals."
        ),
        "compliance_laws": {
            "anti_bribery": "Prevention of Corruption Act, 1988 (amended 2018). Companies Act Section 17.",
            "data_privacy": "Digital Personal Data Protection Act (DPDPA), 2023. DPA enforcement.",
            "employment": "Industrial Disputes Act, Shops and Establishments Act, EPF Act, ESI Act. State-level variations.",
            "trade_secrets": "No specific law — protected under contract law and Indian Copyright Act, 1957",
            "antitrust": "Competition Act, 2002. CCI enforcement.",
        },
        "governance_requirements": (
            "Companies Act, 2013. SEBI LODR regulations for listed companies. "
            "Mandatory CSR spending (2% of net profit). Independent directors required."
        ),
        "sales_customs": (
            "Price sensitivity is high. Total cost of ownership arguments are effective. "
            "Government procurement follows GEM (Government e-Marketplace). "
            "Reference clients in India carry more weight than international ones."
        ),
    },
    "FR": {
        "name": "France",
        "languages": ["fr"],
        "currency": "EUR",
        "business_culture": (
            "Formal and intellectual. Use Monsieur/Madame. French language proficiency is respected. "
            "Lunch is important — business lunches can last 1-2 hours. Intellectual debate is valued. "
            "Avoid aggressive sales tactics. Elegance in presentation matters."
        ),
        "compliance_laws": {
            "anti_bribery": "Sapin II Law (2016). Agence Française Anticorruption (AFA) enforcement. Mandatory compliance programs for large companies.",
            "data_privacy": "EU GDPR + Loi Informatique et Libertés. CNIL enforcement (highest fine authority in EU).",
            "employment": "Code du Travail. 35-hour work week. Comité Social et Économique (CSE) employee representation. Very strong employee protections.",
            "trade_secrets": "Law No. 2018-670 on the Protection of Trade Secrets (EU directive transposition)",
            "whistleblower": "Sapin II whistleblower protections + Waserman Law (2022) — strongest in EU",
        },
        "governance_requirements": (
            "Code de Commerce. AFEP-MEDEF Corporate Governance Code. "
            "Two-tier (Directoire/Conseil de Surveillance) or single-tier board structure."
        ),
        "sales_customs": (
            "Proposals in French for French clients. Intellectual rigor in presentations valued. "
            "Procurement follows Code de la Commande Publique for government contracts."
        ),
    },
    "SA": {
        "name": "Saudi Arabia",
        "languages": ["ar"],
        "currency": "SAR",
        "business_culture": (
            "Very formal and relationship-driven. Arabic coffee ceremony at meetings. "
            "Patience essential — business moves at its own pace. Senior authority deferred to. "
            "Right hand for all exchanges. Thursday-Friday weekend. Prayer times interrupt meetings."
        ),
        "compliance_laws": {
            "anti_bribery": "Anti-Bribery Law (Royal Decree M/36). Nazaha (oversight authority).",
            "data_privacy": "Personal Data Protection Law (PDPL), 2021. SDAIA enforcement.",
            "employment": "Saudi Labor Law. Saudization (Nitaqat) quotas. WPS required.",
        },
        "governance_requirements": (
            "Companies Law (2022). CMA regulations for listed companies. Vision 2030 governance reforms."
        ),
        "sales_customs": (
            "Proposals in Arabic and English. Government procurement through Etimad platform. "
            "Local partnership or sponsorship often required. Vision 2030 alignment is a selling point."
        ),
    },
}

# Language codes to full names for prompt generation
LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "ja": "Japanese", "pt": "Portuguese", "ar": "Arabic", "hi": "Hindi",
    "zh": "Chinese (Mandarin)", "ko": "Korean", "it": "Italian",
    "nl": "Dutch", "ru": "Russian", "tr": "Turkish", "pl": "Polish",
    "sv": "Swedish", "da": "Danish", "no": "Norwegian", "fi": "Finnish",
    "th": "Thai", "vi": "Vietnamese", "id": "Indonesian", "ms": "Malay",
}


class GlobalContextEngine:
    """Provides country-specific context to every feature on the platform."""

    def get_country_profile(self, country_code: str) -> dict | None:
        """Get full profile for a country."""
        return COUNTRY_PROFILES.get(country_code.upper())

    def list_countries(self) -> list:
        """List all supported countries."""
        return [{"code": k, "name": v["name"], "languages": v["languages"]}
                for k, v in COUNTRY_PROFILES.items()]

    def get_compliance_context(self, country_code: str) -> str:
        """Build compliance law context for a specific country."""
        profile = COUNTRY_PROFILES.get(country_code.upper())
        if not profile:
            return ""
        laws = profile.get("compliance_laws", {})
        parts = [f"[COMPLIANCE CONTEXT — {profile['name']}]"]
        for category, law in laws.items():
            parts.append(f"• {category.replace('_', ' ').title()}: {law}")
        return "\n".join(parts)

    def get_sales_context(self, country_code: str) -> str:
        """Build sales culture context for interview prep and coaching."""
        profile = COUNTRY_PROFILES.get(country_code.upper())
        if not profile:
            return ""
        parts = [
            f"[BUSINESS CULTURE — {profile['name']}]",
            profile.get("business_culture", ""),
            "",
            f"[SALES CUSTOMS — {profile['name']}]",
            profile.get("sales_customs", ""),
        ]
        return "\n".join(parts)

    def get_governance_context(self, country_code: str) -> str:
        """Build governance/regulatory context."""
        profile = COUNTRY_PROFILES.get(country_code.upper())
        if not profile:
            return ""
        return (f"[GOVERNANCE REQUIREMENTS — {profile['name']}]\n"
                f"{profile.get('governance_requirements', '')}")

    def get_language_instruction(self, country_code: str = None,
                                  language: str = None) -> str:
        """Build a language instruction for AI prompts."""
        if language:
            lang_name = LANGUAGE_NAMES.get(language, language)
        elif country_code:
            profile = COUNTRY_PROFILES.get(country_code.upper(), {})
            primary_lang = profile.get("languages", ["en"])[0]
            lang_name = LANGUAGE_NAMES.get(primary_lang, "English")
        else:
            return ""

        if lang_name == "English":
            return ""

        return (f"[LANGUAGE: Respond entirely in {lang_name}. "
                f"Use professional business vocabulary appropriate for {lang_name}-speaking markets. "
                f"Maintain formal register unless the context calls for casual tone.]")

    def build_full_context(self, country_code: str = None,
                            language: str = None,
                            include_compliance: bool = True,
                            include_sales: bool = False,
                            include_governance: bool = False) -> str:
        """Build complete context injection for any feature."""
        parts = []

        if language and language != "en":
            parts.append(self.get_language_instruction(language=language))
        elif country_code and country_code.upper() != "US":
            parts.append(self.get_language_instruction(country_code=country_code))

        if country_code:
            if include_compliance:
                ctx = self.get_compliance_context(country_code)
                if ctx: parts.append(ctx)
            if include_sales:
                ctx = self.get_sales_context(country_code)
                if ctx: parts.append(ctx)
            if include_governance:
                ctx = self.get_governance_context(country_code)
                if ctx: parts.append(ctx)

        return "\n\n".join(parts)

    # ── Workspace locale settings ────────────────────────────

    def set_workspace_locale(self, country_code: str, language: str = None) -> dict:
        """Set the default locale for the workspace."""
        profile = COUNTRY_PROFILES.get(country_code.upper())
        if not profile:
            return {"error": f"Unsupported country: {country_code}"}

        lang = language or profile["languages"][0]
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES ('locale_country', ?)",
                (country_code.upper(),))
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES ('locale_language', ?)",
                (lang,))
        return {"country": country_code.upper(), "language": lang,
                "country_name": profile["name"]}

    def get_workspace_locale(self) -> dict:
        """Get the current workspace locale."""
        with get_db() as db:
            country = db.execute(
                "SELECT value FROM workspace_settings WHERE key='locale_country'"
            ).fetchone()
            language = db.execute(
                "SELECT value FROM workspace_settings WHERE key='locale_language'"
            ).fetchone()
        cc = dict(country)["value"] if country else "US"
        lang = dict(language)["value"] if language else "en"
        profile = COUNTRY_PROFILES.get(cc, {})
        return {"country": cc, "language": lang,
                "country_name": profile.get("name", ""),
                "currency": profile.get("currency", "USD")}
