"""Internationalisation — English + Lithuanian.

Translation catalog, session language helpers, and the `t()` / `agent_t()` lookup
functions used by every UI module.
"""

from __future__ import annotations

from typing import Any

LANGUAGES: dict[str, dict[str, str]] = {
    "en": {"name": "English", "flag": "\U0001f1ec\U0001f1e7", "native": "English"},
    "lt": {"name": "Lithuanian", "flag": "\U0001f1f1\U0001f1f9", "native": "Lietuvių"},
}

DEFAULT_LANG = "en"
SUPPORTED_LANGS = tuple(LANGUAGES.keys())

# ── IP-based detection for Lithuanian visitors ─────────────────────────
_LITHUANIAN_IP_PREFIXES = (
    "78.56.", "78.57.", "78.58.", "78.59.",       # Telia LT
    "82.135.", "84.15.", "86.38.", "86.100.",      # Tele2 LT
    "88.118.", "88.119.",                          # Bite
    "90.131.", "91.204.", "91.211.",               # Various LT ISPs
    "193.219.", "195.14.", "212.52.", "213.252.",  # TEO / academic
)


def detect_language(request) -> str:
    """Detect language from IP address (Lithuanian ISP ranges)."""
    ip = _get_client_ip(request)
    if ip and any(ip.startswith(p) for p in _LITHUANIAN_IP_PREFIXES):
        return "lt"
    return DEFAULT_LANG


def _get_client_ip(request) -> str | None:
    if not request:
        return None
    for header in ("x-forwarded-for", "x-real-ip"):
        val = request.headers.get(header) if hasattr(request, "headers") else None
        if val:
            return val.split(",")[0].strip()
    client = getattr(request, "client", None)
    if client:
        return client.host
    return None


# ── Session helpers ────────────────────────────────────────────────────

def get_lang(sess: dict[str, Any], request=None) -> str:
    lang = (sess.get("lang") or "").lower()
    if lang in SUPPORTED_LANGS:
        return lang
    if request:
        detected = detect_language(request)
        sess["lang"] = detected
        return detected
    return DEFAULT_LANG


def set_lang(sess: dict[str, Any], lang: str) -> str:
    code = (lang or "").lower()
    if code in SUPPORTED_LANGS:
        sess["lang"] = code
    return get_lang(sess)


# ── Translation catalog ───────────────────────────────────────────────
#
# Flat dict keyed by identifier.  Each value is {"en": "...", "lt": "..."}.
# Fall-through: requested lang → English → key itself.

TRANSLATIONS: dict[str, dict[str, str]] = {

    # ── Navigation ─────────────────────────────────────────────────
    "nav_platform":      {"en": "Platform",      "lt": "Platforma"},
    "nav_agents":        {"en": "Agents",         "lt": "Agentai"},
    "nav_how":           {"en": "How it works",   "lt": "Kaip tai veikia"},
    "nav_pricing":       {"en": "Pricing",        "lt": "Kainos"},
    "nav_contact":       {"en": "Contact",        "lt": "Kontaktai"},
    "nav_book_demo":     {"en": "Book a demo",    "lt": "Rezervuoti demo"},
    "nav_open_app":      {"en": "Open app",       "lt": "Atidaryti"},

    # ── Hero section ──────────────────────────────────────────────
    "hero_eyebrow":      {"en": "Agentic AI for private equity",
                          "lt": "Agentinė AI privataus kapitalo komandai"},
    "hero_h1_1":         {"en": "Your Private Equity ",       "lt": "Jūsų privataus kapitalo "},
    "hero_h1_2":         {"en": "AI Agent Squad",             "lt": "AI agentų komanda"},
    "hero_h1_3":         {"en": " — ",                   "lt": " — "},
    "hero_h1_4":         {"en": "sourcing, ",                 "lt": "ieško, "},
    "hero_h1_5":         {"en": "underwriting, ",             "lt": "vertina, "},
    "hero_h1_6":         {"en": "and closing ",               "lt": "ir uždaro "},
    "hero_h1_7":         {"en": "your next platform.",        "lt": "jūsų kitą platformą."},
    "hero_lede":         {"en": "Not a prompt pack. Not a build-it-yourself kit. PEHero is a full agentic system "
                                "already wired into your deal flow — scanning targets, running QoE, building LBO "
                                "models, and drafting IC memos while your team focuses on the call.",
                          "lt": "Ne promptų rinkinys. Ne „pasidaryk pats“. PEHero — pilna agentinė sistema, "
                                "jau integruota į jūsų sandorių srautą: skentuoja įmones, atlieka QoE, stato LBO "
                                "modelius ir rašo IC memo, kol jūsų komanda kalba telefonu."},
    "hero_cta_open":     {"en": "Open the app",   "lt": "Atidaryti programą"},
    "hero_cta_meet":     {"en": "Meet the squad",  "lt": "Susipažinkite su komanda"},

    # ── Stat cells ─────────────────────────────────────────────────
    "stat_squad":        {"en": "Squad",            "lt": "Komanda"},
    "stat_squad_cap":    {"en": "of PE specialists, on call",
                          "lt": "PE specialistų, visada pasiekiamų"},
    "stat_5":            {"en": "5",                "lt": "5"},
    "stat_5_cap":        {"en": "workflow stages, end-to-end",
                          "lt": "darbo etapų, nuo pradžios iki galo"},
    "stat_90s":          {"en": "<90s",             "lt": "<90s"},
    "stat_90s_cap":      {"en": "to a go / no-go decision",
                          "lt": "iki „taip / ne“ sprendimo"},
    "stat_byod":         {"en": "BYOD",             "lt": "BYOD"},
    "stat_byod_cap":     {"en": "bring your own data",
                          "lt": "naudokite savo duomenis"},

    # ── Product tour ──────────────────────────────────────────────
    "tour_eyebrow":      {"en": "Product tour",     "lt": "Produkto apžvalga"},
    "tour_heading":      {"en": "See it in motion.", "lt": "Pamatykite veikime."},
    "tour_body":         {"en": "A 30-second walk through chat, the pipeline kanban, deal detail, "
                                "analytics and prompt editing — BYOD: bring your own data and "
                                "see the squad in action on your deals.",
                          "lt": "30 sekundžių apžvalga: pokalbiai, sandorių kanban, sandorių detalės, "
                                "analitika ir promptų redagavimas — BYOD: naudokite savo duomenis "
                                "ir išbandykite komandą su tikrais sandoriais."},
    "tour_pdf":          {"en": "Product tour (PDF)",  "lt": "Apžvalga (PDF)"},
    "tour_pptx":         {"en": "Product tour (PPTX)", "lt": "Apžvalga (PPTX)"},
    "tour_readme":       {"en": "View README",        "lt": "Žiūrėti README"},
    "tour_open_app":     {"en": "Open the app",        "lt": "Atidaryti programą"},

    # ── Pillars section ───────────────────────────────────────────
    "pillars_eyebrow":   {"en": "Five stages, one system",
                          "lt": "Penki etapai, viena sistema"},
    "pillars_heading":   {"en": "Every role your deal team plays — live inside PEHero.",
                          "lt": "Visos jūsų sandorių komandos rolės — veikia PEHero viduje."},
    "agents_count":      {"en": "{n} agents",       "lt": "{n} agentų"},
    "see_all":           {"en": "See all {n} → ", "lt": "Žiūrėti visus {n} → "},

    # ── How it works (home page) ──────────────────────────────────
    "how_eyebrow":       {"en": "How it works",         "lt": "Kaip tai veikia"},
    "how_heading":       {"en": "Source → Underwrite → Close → Hold.",
                          "lt": "Ieškoti → Vertinti → Uždaryti → Valdyti."},
    "how_01_title":      {"en": "Source deals that fit your mandate",
                          "lt": "Raskite sandorius pagal savo mandatą"},
    "how_01_body":       {"en": "Market Scanner watches PitchBook, Grata, banker feeds, and proprietary founder outreach. "
                                "Deal Triage returns a go/no-go on each in under 90 seconds against your fund’s criteria.",
                          "lt": "Market Scanner stebi PitchBook, Grata, bankininkų srautus ir tiesiogines įkūrėjų užklausas. "
                                "Deal Triage pateikia „taip/ne“ sprendimą per 90 sekundžių pagal jūsų fondo kriterijus."},
    "how_02_title":      {"en": "Model them in hours, not weeks",
                          "lt": "Sumodeliuokite per valandas, ne savaites"},
    "how_02_body":       {"en": "Cap Table Parser, LTM Normalizer, and LBO Model Builder take seller financials "
                                "into an IC-ready 5-year model with sensitivity and debt stack — already benchmarked "
                                "against live transaction comps.",
                          "lt": "Cap Table Parser, LTM Normalizer ir LBO Model Builder paverčia pardavėjo finansinę ataskaitą "
                                "į IC parengtą 5 metų modelį su jautrumo analize ir skolos struktūra — jau palygintą "
                                "su rinkos sandorių dauginamaisiais."},
    "how_03_title":      {"en": "Close, raise, and hold with conviction",
                          "lt": "Uždarykite, pritraukite ir valdykite užtikrintai"},
    "how_03_body":       {"en": "IC Memo Writer, Teaser Designer, LP Update Generator, and Portfolio Ops agents keep "
                                "every thesis, covenant, and KPI variance in view from signing through exit.",
                          "lt": "IC Memo Writer, Teaser Designer, LP Update Generator ir Portfolio Ops agentai išlaiko "
                                "visą tezę, kovenantas ir KPI nukrypimus matomus nuo pasirašymo iki išėjimo."},

    # ── Case study strip ──────────────────────────────────────────
    "case_eyebrow":      {"en": "What you get",     "lt": "Ką gausite"},
    "case_heading":      {"en": "Time compressed, confidence higher.",
                          "lt": "Laikas suspaustas, pasitikėjimas didesnis."},
    "case_1_label":      {"en": "Sourcing → triage",    "lt": "Paieška → atranka"},
    "case_1_metric":     {"en": "1,240 deals",              "lt": "1 240 sandorių"},
    "case_1_caption":    {"en": "surfaced and triaged against a lower-middle-market software mandate in one week of scanning.",
                          "lt": "surasta ir atrinkta pagal žemesnės vidurinės rinkos programinės įrangos mandatą per vieną skenavimo savaitę."},
    "case_2_label":      {"en": "Underwriting",             "lt": "Vertinimas"},
    "case_2_metric":     {"en": "3 days → 40 min",     "lt": "3 dienos → 40 min"},
    "case_2_caption":    {"en": "from seller financials + cap table to a full 5-year LBO model with sensitivity and debt stack.",
                          "lt": "nuo pardavėjo finansinių ataskaitų + cap table iki pilno 5 metų LBO modelio su jautrumo analize ir skolos struktūra."},
    "case_3_label":      {"en": "Capital",                  "lt": "Kapitalas"},
    "case_3_metric":     {"en": "60 LPs, ranked",           "lt": "60 LP, suranguoti"},
    "case_3_caption":    {"en": "by fund-fit, staleness, and commitment size — with drafted re-engagement emails.",
                          "lt": "pagal tinkamumą fondui, senumą ir įsipareigojimo dydį — su parengtais pakartotinio kontakto laiškais."},

    # ── CTA section ───────────────────────────────────────────────
    "cta_eyebrow":       {"en": "Talk to us",        "lt": "Susisiekite"},
    "cta_headline":      {"en": "Stop stitching tools. Start closing deals.",
                          "lt": "Nustokite lipdyti įrankius. Pradėkite uždaryti sandorius."},
    "cta_body":          {"en": "Book a 20-minute walkthrough. We’ll load one of your recent deals into PEHero "
                                "and show you the full agent flow end-to-end.",
                          "lt": "Užsisakykite 20 minučių demonstraciją. Įkelkime vieną iš jūsų sandorių "
                                "į PEHero ir parodysime pilną agentų darbo eigą."},
    "cta_book":          {"en": "Book a demo",       "lt": "Rezervuoti demo"},
    "cta_byod":          {"en": "BYOD — bring your own data",
                          "lt": "BYOD — naudokite savo duomenis"},

    # ── Footer ────────────────────────────────────────────────────
    "footer_product":    {"en": "Product",           "lt": "Produktas"},
    "footer_company":    {"en": "Company",           "lt": "Įmonė"},
    "footer_tagline":    {"en": "Built by a small team that’s sourced, underwritten, and held the phone at 2 AM the night before IC.",
                          "lt": "Sukurta nedidelės komandos, kuri ieškojo, vertino ir laikė telefoną 2 val. nakties prieš IC."},
    "footer_open_app":   {"en": "Open the app",      "lt": "Atidaryti programą"},

    # ── Platform page ─────────────────────────────────────────────
    "platform_title":    {"en": "Platform",          "lt": "Platforma"},
    "platform_h1":       {"en": "One system. Every stage. All your deal data.",
                          "lt": "Viena sistema. Visi etapai. Visi jūsų sandorių duomenys."},
    "platform_body":     {"en": "PEHero lives where your deal team already works. Twenty-two specialist "
                                "agents share a single model of your pipeline, your portfolio, and your market. "
                                "Each agent has its own tools and prompts — and they pass artifacts between each "
                                "other without the associate re-keying anything.",
                          "lt": "PEHero veikia ten, kur jūsų sandorių komanda jau dirba. Dvidešimt du specialistų "
                                "agentai dalijasi vienu jūsų pipeline, portfelio ir rinkos modeliu. "
                                "Kiekvienas agentas turi savo įrankius ir promptus — ir jie perduoda artefaktus vieni "
                                "kitiems be pakartotinio duomenų įvedimo."},
    "platform_hood":     {"en": "Under the hood",    "lt": "Po dangčiu"},
    "platform_not_wrap": {"en": "Not a wrapper. A system.",
                          "lt": "Ne apvalkalas. Sistema."},
    "platform_squad":    {"en": "A full squad of specialist agents, one per role, sharing a common tool registry and prompt library.",
                          "lt": "Pilna specialistų agentų komanda, po vieną kiekvienai rolei, besidalijanti bendru įrankių registru ir promptų biblioteka."},
    "platform_tools":    {"en": "70+ StructuredTools that read cap tables, financials, VDR PDFs, and sector comps directly — not through copy-paste.",
                          "lt": "70+ įrankių, kurie tiesiogiai skaito cap tables, finansines ataskaitas, VDR PDF ir sektoriaus lyginamuosius — ne per copy-paste."},
    "platform_rag":      {"en": "Postgres + pgvector index of every CIM, QoE, MSA, legal DD memo, ESG assessment, and industry report in your deal.",
                          "lt": "Postgres + pgvector indeksas kiekvienam CIM, QoE, MSA, teisiniam DD memo, ESG vertinimui ir pramonės ataskaitai jūsų sandoryje."},
    "platform_memory":   {"en": "Every conversation and every artifact persists, queryable across agents, so Week 3 of diligence still knows what Week 1 agreed.",
                          "lt": "Kiekvienas pokalbis ir kiekvienas artefaktas išsaugomas, užklausomas per visus agentus — 3-ioji patikros savaitė vis dar žino, ką nutarė 1-oji."},

    # ── Agents page ───────────────────────────────────────────────
    "agents_eyebrow":    {"en": "Your Private Equity AI Agent Squad",
                          "lt": "Jūsų privataus kapitalo AI agentų komanda"},
    "agents_h1":         {"en": "Every role already wired in.",
                          "lt": "Kiekviena rolė jau sujungta."},
    "agents_body":       {"en": "Each agent has a narrow remit, deep tooling, and a prefix you can type in the chat "
                                "to call it directly. Or just ask in plain English — the router picks the right one.",
                          "lt": "Kiekvienas agentas turi siaurą kompetenciją, giluminius įrankius ir prefiksą, "
                                "kurį galite įvesti pokalbyje. Arba tiesiog klauskite — maršrutizatorius parinks tinkamą."},

    # ── Agent detail page ─────────────────────────────────────────
    "agent_not_found":   {"en": "Not found",         "lt": "Nerasta"},
    "agent_no_url":      {"en": "No agent at that URL. See the ",
                          "lt": "Nėra agento šiuo adresu. Žiūrėkite "},
    "agent_full_squad":  {"en": "full squad",        "lt": "visą komandą"},
    "agent_all":         {"en": "← All agents",  "lt": "← Visi agentai"},
    "agent_what":        {"en": "What it does",      "lt": "Ką daro"},
    "agent_examples":    {"en": "Example prompts",   "lt": "Pavyzdžiai"},
    "agent_try":         {"en": "Try {name} now.",    "lt": "Išbandykite {name} dabar."},
    "agent_try_body":    {"en": "BYOD — bring your own deal data and try the example prompt above against it.",
                          "lt": "BYOD — naudokite savo sandorių duomenis ir išbandykite aukščiau esančią užklausą."},

    # ── How-it-works page (detailed) ──────────────────────────────
    "hiw_title":         {"en": "How it works",      "lt": "Kaip tai veikia"},
    "hiw_h1":            {"en": "From teaser to signed SPA — in one system.",
                          "lt": "Nuo teaserio iki pasirašyto SPA — vienoje sistemoje."},
    "hiw_01_num":        {"en": "01 — Source",   "lt": "01 — Paieška"},
    "hiw_01_title":      {"en": "Surface the right deals faster than the next MD.",
                          "lt": "Suraskite tinkamus sandorius greičiau nei kitas MD."},
    "hiw_01_body":       {"en": "Market Scanner watches PitchBook, Grata, banker feeds, and off-market founder-intent signals. "
                                "Deal Triage returns a go/no-go in under 90 seconds. Transaction Comps tightens multiple benchmarks before you sign an NDA.",
                          "lt": "Market Scanner stebi PitchBook, Grata, bankininkų srautus ir nešalinius įkūrėjų ketinimo signalus. "
                                "Deal Triage pateikia „taip/ne“ per 90 sekundžių. Transaction Comps sugriežtina dauginamuosius prieš pasirašant NDA."},
    "hiw_02_num":        {"en": "02 — Underwrite", "lt": "02 — Vertinimas"},
    "hiw_02_title":      {"en": "Seller financials to IC-ready LBO in under an hour.",
                          "lt": "Pardavėjo finansinės ataskaitos iki IC parengt LBO per valandą."},
    "hiw_02_body":       {"en": "Cap Table Parser and LTM Normalizer ingest whatever format the banker sends. "
                                "LBO Model Builder produces a 5-year model with sensitivity. Debt Stack Modeler sizes the capital structure. "
                                "Return Metrics outputs IRR, MOIC, and the value-creation bridge.",
                          "lt": "Cap Table Parser ir LTM Normalizer apdoroja bet kokį bankininkui siųstamą formatą. "
                                "LBO Model Builder sukuria 5 metų modelį su jautrumo analize. Debt Stack Modeler sudaro kapitalo struktūrą. "
                                "Return Metrics pateikia IRR, MOIC ir vertės kūrimo tiltą."},
    "hiw_03_num":        {"en": "03 — Diligence", "lt": "03 — Patikra"},
    "hiw_03_title":      {"en": "No surprises at signing.",
                          "lt": "Jokių staigmenų pasirašant."},
    "hiw_03_body":       {"en": "VDR Auditor checks the seller data room against a 140-item PE checklist. "
                                "Contract Abstractor reads every MSA. Legal & Regulatory, Operational Diligence, "
                                "and ESG agents flag material issues with page-level citations.",
                          "lt": "VDR Auditor patikrina pardavėjo duomenų kambarį pagal 140 punktų PE kontrolę. "
                                "Contract Abstractor perskaito kiekvieną MSA. Legal & Regulatory, Operational Diligence "
                                "ir ESG agentai pažymi esminius dalykus su puslapio lygio citatomis."},
    "hiw_04_num":        {"en": "04 — Raise",    "lt": "04 — Kapitalas"},
    "hiw_04_title":      {"en": "LP material your chair will actually sign.",
                          "lt": "LP medžiaga, kurią jūsų pirmininkas tikrai pasirašys."},
    "hiw_04_body":       {"en": "IC Memo Writer drafts the investment-committee memo from your own data. "
                                "Teaser Designer produces a 2-page blind teaser for co-invest distribution. "
                                "LP Update Generator writes the quarterly letter. Fundraising CRM Copilot ranks prospects and drafts outreach.",
                          "lt": "IC Memo Writer parengia investicijų komiteto memo iš jūsų duomenų. "
                                "Teaser Designer sukuria 2 puslapių anoniminį teaserį bendram investavimui. "
                                "LP Update Generator rašo ketvirtį laišką. Fundraising CRM Copilot ranguoja prospektus ir rengia raištinius."},
    "hiw_05_num":        {"en": "05 — Hold & Grow", "lt": "05 — Valdymas ir augimas"},
    "hiw_05_title":      {"en": "Post-close, the agents stay on.",
                          "lt": "Po uždarymo agentai lieka."},
    "hiw_05_body":       {"en": "Pricing Optimization recommends increases at renewal. EBITDA Variance Watcher flags monthly drift. "
                                "Value Creation Prioritizer ranks VCP initiatives by ROI. Customer Churn Predictor scores renewal risk across the ARR base.",
                          "lt": "Pricing Optimization rekomenduoja kėlimus atnaujinat. EBITDA Variance Watcher fiksuoja mėnesinį nukrypimą. "
                                "Value Creation Prioritizer ranguoja VCP iniciatyvas pagal ROI. Customer Churn Predictor vertina atsinaujinimo riziką per ARR bazę."},

    # ── Pricing page ──────────────────────────────────────────────
    "pricing_eyebrow":   {"en": "Pricing",           "lt": "Kainos"},
    "pricing_h1":        {"en": "BYOD — bring your own data. Upgrade when it sticks.",
                          "lt": "BYOD — naudokite savo duomenis. Atnaujinkite, kai patiks."},
    "pricing_sub":       {"en": "No setup fee. No per-seat tax. No prompt-token surprise.",
                          "lt": "Be pradiniamą. Be mokestis už vietą. Be prompt-token staigmenų."},
    "pricing_pilot":     {"en": "Pilot",             "lt": "Pilotinis"},
    "pricing_pilot_price": {"en": "BYOD",            "lt": "BYOD"},
    "pricing_pilot_sub": {"en": "bring your own data · 30-day pilot",
                          "lt": "naudokite savo duomenis · 30 dienų bandomasis"},
    "pricing_pilot_blurb": {"en": "One associate, one deal, the full squad — running against your own data.",
                            "lt": "Vienas asocijuotas partneris, vienas sandoris, visa komanda — su jūsų duomenimis."},
    "pricing_team":      {"en": "Team",              "lt": "Komanda"},
    "pricing_team_price": {"en": "Contact us",       "lt": "Susisiekite"},
    "pricing_team_sub":  {"en": "per fund",          "lt": "už fondą"},
    "pricing_team_blurb": {"en": "Fund actively deploying capital with 5-25 investment professionals.",
                           "lt": "Fondas, aktyviai investuojantis kapitalą su 5-25 investicijų profesionalais."},
    "pricing_platform":  {"en": "Platform",          "lt": "Platforma"},
    "pricing_platform_price": {"en": "Custom",       "lt": "Individuali"},
    "pricing_platform_sub": {"en": "for multi-fund GPs",
                             "lt": "multi-fund GP"},
    "pricing_platform_blurb": {"en": "Dedicated cluster, your brand, custom agents.",
                               "lt": "Atskiras klasteris, jūsų prekės ženklas, individualūs agentai."},
    "pricing_start_pilot": {"en": "Start pilot",     "lt": "Pradėti pilotą"},
    "pricing_book_demo": {"en": "Book a demo",       "lt": "Rezervuoti demo"},
    "pricing_contact":   {"en": "Contact sales",     "lt": "Susisiekti su pardavimais"},
    # Features (shared across tiers)
    "feat_full_squad":   {"en": "Full squad of specialists",    "lt": "Visa specialistų komanda"},
    "feat_1_user":       {"en": "1 concurrent user",            "lt": "1 vartotojas"},
    "feat_5_deals":      {"en": "Up to 5 live deals",           "lt": "Iki 5 aktyvių sandorių"},
    "feat_byod":         {"en": "BYOD — connect your deal data on day one",
                          "lt": "BYOD — prijunkite savo duomenis nuo pirmos dienos"},
    "feat_email":        {"en": "Email support",                "lt": "El. pašto palaikymas"},
    "feat_25_seats":     {"en": "Up to 25 seats",               "lt": "Iki 25 vietų"},
    "feat_unlimited":    {"en": "Unlimited deals + portcos",    "lt": "Neriboti sandoriai + portfeliai"},
    "feat_sso":          {"en": "SSO + audit log",              "lt": "SSO + audito žurnalas"},
    "feat_shared":       {"en": "Shared memory across team",    "lt": "Bendra atmintis komandai"},
    "feat_priority":     {"en": "Priority support",             "lt": "Prioritetinis palaikymas"},
    "feat_everything":   {"en": "Everything in Team",           "lt": "Viskas, kas Team plane"},
    "feat_unlimited_seats": {"en": "Unlimited seats",           "lt": "Neribota vieta"},
    "feat_dedicated":    {"en": "Dedicated instance",           "lt": "Atskira instancija"},
    "feat_own_llm":      {"en": "Bring your own LLM provider", "lt": "Naudokite savo LLM tiekėją"},
    "feat_custom":       {"en": "Custom agents and tools",      "lt": "Individualūs agentai ir įrankiai"},
    "feat_onsite":       {"en": "Onsite training",              "lt": "Mokymai vietoje"},

    # ── Contact page ──────────────────────────────────────────────
    "contact_eyebrow":   {"en": "Contact",           "lt": "Kontaktai"},
    "contact_h1":        {"en": "Let’s look at one of your deals.",
                          "lt": "Pažiūrėkime vieną jūsų sandorį."},
    "contact_body":      {"en": "Send us a note and we’ll set up a 20-minute walkthrough. We’ll load one of your "
                                "recent deals into PEHero and show you the full agent flow — live.",
                          "lt": "Parašykite mums ir suorganizuosime 20 minučių demonstraciją. Įkelkime vieną iš jūsų "
                                "paskutinių sandorių į PEHero ir parodysime pilną agentų darbo eigą — gyvai."},
    "contact_name":      {"en": "Your name",         "lt": "Jūsų vardas"},
    "contact_email":     {"en": "Email",             "lt": "El. paštas"},
    "contact_firm":      {"en": "Firm (optional)",   "lt": "Įmonė (neprivaloma)"},
    "contact_pipeline":  {"en": "Tell us about your pipeline",
                          "lt": "Papasakokite apie savo pipeline"},
    "contact_send":      {"en": "Send message →",       "lt": "Siųsti žinutę →"},
    "contact_thanks":    {"en": "Thanks — we’ll be in touch shortly.",
                          "lt": "Ačiū — netrukus susisieksime."},
    "contact_usually":   {"en": "Usually within one business day.",
                          "lt": "Paprastai per vieną darbo dieną."},
    "contact_meanwhile": {"en": "In the meantime, ",  "lt": "Tuo tarpu, "},
    "contact_open_app":  {"en": "open the app",       "lt": "atidarykite programą"},
    "contact_byod_post": {"en": " — BYOD: connect your deal data to see the squad on real work.",
                          "lt": " — BYOD: prijunkite savo sandorių duomenis ir pamatykite komandą tikrame darbe."},

    # ── Chat UI ───────────────────────────────────────────────────
    "chat_new":          {"en": "+ New chat",        "lt": "+ Naujas pokalbis"},
    "chat_sessions":     {"en": "Sessions",          "lt": "Pokalbiai"},
    "chat_no_sessions":  {"en": "No sessions yet — send a message to start.",
                          "lt": "Dar nėra pokalbių — parašykite žinutę, kad pradėtumėte."},
    "chat_untitled":     {"en": "Untitled session",  "lt": "Be pavadinimo"},
    "chat_agents":       {"en": "Agents",            "lt": "Agentai"},
    "chat_workspace":    {"en": "Workspace",         "lt": "Darbo erdvė"},
    "chat_config":       {"en": "Configuration",     "lt": "Nustatymai"},
    "chat_pipeline":     {"en": "Pipeline",          "lt": "Pipeline"},
    "chat_instructions": {"en": "Instructions",      "lt": "Instrukcijos"},
    "chat_analytics":    {"en": "Analytics",         "lt": "Analitika"},
    "chat_sign_in":      {"en": "Sign in",           "lt": "Prisijungti"},
    "chat_sign_out":     {"en": "Sign out",          "lt": "Atsijungti"},
    "chat_beta":         {"en": "Beta",              "lt": "Beta"},
    "chat_send":         {"en": "Send",              "lt": "Siųsti"},
    "chat_auto_routed":  {"en": "Auto-routed",       "lt": "Automatinis"},
    "chat_copy":         {"en": "Copy chat",         "lt": "Kopijuoti pokalbį"},
    "chat_share":        {"en": "Share",             "lt": "Dalintis"},
    "chat_canvas":       {"en": "Canvas",            "lt": "Drobė"},
    "chat_back":         {"en": "Back to chat",      "lt": "Grįžti į pokalbį"},
    "chat_placeholder":  {"en": "Ask anything — or type a prefix like `triage:`, `memo:`, `pf:`",
                          "lt": "Klauskite bet ko — arba įveskite prefiksą kaip `triage:`, `memo:`, `pf:`"},
    "chat_welcome_title": {"en": "PEHero",           "lt": "PEHero"},
    "chat_welcome_sub":  {"en": "Your Private Equity AI Agent Squad. Type a prompt — the router picks the right specialist.",
                          "lt": "Jūsų privataus kapitalo AI agentų komanda. Įveskite užklausą — maršrutizatorius parinks tinkamą specialistą."},
    "chat_canvas_empty": {"en": "Canvas renders here as agents produce them — company briefs, LBO models, comps tables, IC memo previews, RAG citations.",
                          "lt": "Drobė rodoma, kai agentai sukuria artefaktus — įmonių aprašymus, LBO modelius, lyginimuosius, IC memo peržiūras, RAG citatas."},
    "chat_signin_title": {"en": "Sign in to PEHero", "lt": "Prisijungti prie PEHero"},
    "chat_signin_sub":   {"en": "Email only — we’ll send a confirmation later.",
                          "lt": "Tik el. paštu — patvirtinimas bus vėliau."},
    "chat_signin_btn":   {"en": "Continue →",    "lt": "Tęsti →"},

    # ── Chat config ───────────────────────────────────────────────
    "cfg_currency":      {"en": "Currency",          "lt": "Valiuta"},
    "cfg_currency_help":  {"en": "affects agents + displays",
                          "lt": "įtakoja agentus ir atvaizdavimą"},
    "cfg_integrations":  {"en": "Integrations",      "lt": "Integracijos"},
    "cfg_connected":     {"en": "connected",         "lt": "prijungta"},
    "cfg_off":           {"en": "off",               "lt": "išj."},
    "cfg_language":      {"en": "Language",          "lt": "Kalba"},

    # ── JS strings (injected as JSON) ─────────────────────────────
    "js_thinking":       {"en": "Thinking… ",    "lt": "Galvoju… "},
    "js_calling":        {"en": "calling ",           "lt": "vykdau "},
    "js_copy_csv":       {"en": "Copy CSV",           "lt": "Kopijuoti CSV"},
    "js_copied":         {"en": "Copied!",            "lt": "Nukopijuota!"},
    "js_download_csv":   {"en": "Download CSV",       "lt": "Atsisiųsti CSV"},
    "js_try_prompt":     {"en": "Try a prompt",       "lt": "Išbandykite užklausą"},
    "js_try_with":       {"en": "Try with ",           "lt": "Išbandykite su "},
    "js_copy_chat":      {"en": "Copy chat",          "lt": "Kopijuoti pokalbį"},
    "js_share":          {"en": "Share",              "lt": "Dalintis"},
    "js_link_copied":    {"en": "Link copied!",       "lt": "Nuoroda nukopijuota!"},
    "js_no_session":     {"en": "No session",         "lt": "Nėra pokalbio"},
    "js_error":          {"en": "Error",              "lt": "Klaida"},
    "js_error_prefix":   {"en": "Error: ",            "lt": "Klaida: "},
    "js_rendering":      {"en": "Rendering…",    "lt": "Generuojama…"},
    "js_open_pdf":       {"en": "✓ Open PDF",     "lt": "✓ Atidaryti PDF"},
    "js_render_failed":  {"en": "Render failed",      "lt": "Generavimas nepavyko"},
    "js_preview_pdf":    {"en": "\U0001f4c4 Preview PDF",  "lt": "\U0001f4c4 Peržiūrėti PDF"},
    "js_download_pdf":   {"en": "⬇ Download PDF",     "lt": "⬇ Atsisiųsti PDF"},
    "js_yes_do":         {"en": "Yes, do that",       "lt": "Taip, vykdyk"},
    "js_no_thanks":      {"en": "No thanks",          "lt": "Ne, ačiū"},
    "js_canvas":         {"en": "Canvas",             "lt": "Drobė"},
    "js_no_rows":        {"en": "No rows.",            "lt": "Nėra įrašų."},
    "js_you":            {"en": "You",                "lt": "Jūs"},
    "js_pehero":         {"en": "PEHero",             "lt": "PEHero"},
    "js_send":           {"en": "Send",               "lt": "Siųsti"},
    "js_pdf_preview":    {"en": "PDF preview",        "lt": "PDF peržiūra"},
    "js_memo_preview":   {"en": "Memo preview",       "lt": "Memo peržiūra"},

    # ── Pipeline page ─────────────────────────────────────────────
    "pipe_title":        {"en": "Pipeline",           "lt": "Pipeline"},
    "pipe_companies":    {"en": "{n} companies",      "lt": "{n} įmonių"},
    "pipe_all":          {"en": "All",                "lt": "Visos"},
    "pipe_back":         {"en": "Back to chat",       "lt": "Grįžti į pokalbį"},
    "pipe_deal_not_found": {"en": "Deal not found",   "lt": "Sandoris nerastas"},
    "pipe_back_pipe":    {"en": "← Pipeline",     "lt": "← Pipeline"},
    # Stage labels
    "stage_sourced":     {"en": "Sourced",            "lt": "Surasta"},
    "stage_screened":    {"en": "Screened",           "lt": "Atrinkta"},
    "stage_loi":         {"en": "LOI / IOI",          "lt": "LOI / IOI"},
    "stage_diligence":   {"en": "Diligence",          "lt": "Patikra"},
    "stage_ic":          {"en": "IC",                 "lt": "IC"},
    "stage_signed":      {"en": "Signed",             "lt": "Pasirašyta"},
    "stage_closed":      {"en": "Closed",             "lt": "Uždaryta"},
    "stage_held":        {"en": "Held",               "lt": "Valdoma"},
    "stage_exited":      {"en": "Exited",             "lt": "Parduota"},
    "stage_passed":      {"en": "Passed",             "lt": "Atmesta"},
    # Deal brief
    "brief_ltm":         {"en": "LTM financials",     "lt": "LTM finansinės ataskaitos"},
    "brief_customers":   {"en": "Top customers",      "lt": "Pagrindiniai klientai"},
    "brief_dd":          {"en": "DD findings",        "lt": "DD išvados"},
    "brief_hq":          {"en": "HQ",                 "lt": "Būstinė"},
    "brief_employees":   {"en": "Employees",          "lt": "Darbuotojai"},
    "brief_founded":     {"en": "Founded",            "lt": "Įkurta"},
    "brief_ownership":   {"en": "Ownership",          "lt": "Nuosavybė"},
    "brief_revenue":     {"en": "Revenue",            "lt": "Pajamos"},
    "brief_adj_ebitda":  {"en": "Adj. EBITDA",        "lt": "Adj. EBITDA"},
    "brief_margin":      {"en": "Margin",             "lt": "Marža"},
    "brief_ask_ev":      {"en": "Ask EV",             "lt": "Prašoma EV"},
    "brief_no_contracts": {"en": "No contracts loaded.", "lt": "Nėra įkeltų sutarčių."},
    "brief_no_findings": {"en": "No findings yet. Try running VDR Auditor.",
                          "lt": "Kol kas nėra išvadų. Išbandykite VDR Auditor."},
    "pipe_chat_hint":    {"en": "Ask about {company} — the deal brief is on the right. Try ‘triage this deal’, ‘draft IC memo’, or ‘summarize DD findings’.",
                          "lt": "Klauskite apie {company} — sandorio aprašymas dešinėje. Išbandykite „triage this deal“, „draft IC memo“ arba „summarize DD findings“."},
    "pipe_input_hint":   {"en": "Ask about {company} — e.g. triage, LBO, DD findings",
                          "lt": "Klauskite apie {company} — pvz. triage, LBO, DD findings"},

    # ── Analytics page ────────────────────────────────────────────
    "analytics_title":   {"en": "Analytics",          "lt": "Analitika"},
    "analytics_sub":     {"en": "Text → SQL → Plotly",
                          "lt": "Tekstas → SQL → Plotly"},
    "analytics_h2":      {"en": "Ask a question of your PE database.",
                          "lt": "Paklauskite savo PE duomenų bazės."},
    "analytics_body":    {"en": "Questions are translated to SQL against the pehero schema, run read-only, "
                                "and rendered as a Plotly chart plus the raw table.",
                          "lt": "Užklausos verčiamos į SQL pagal pehero schemą, vykdomos tik-skaitymui "
                                "ir atvaizduojamos Plotly grafike bei lentele."},
    "analytics_run":     {"en": "Run",               "lt": "Vykdyti"},
    "analytics_thinking": {"en": "Thinking…",    "lt": "Galvoju…"},

    # ── Instructions page ─────────────────────────────────────────
    "instr_title":       {"en": "Instructions",       "lt": "Instrukcijos"},
    "instr_count":       {"en": "{n} agent prompts",  "lt": "{n} agentų promptų"},
    "instr_intro":       {"en": "Edit the system prompts that drive each agent. Saves write to "
                                "prompts/system/<slug>.md and are versioned in the database.",
                          "lt": "Redaguokite sistemos promptus, kurie valdo kiekvieną agentą. Išsaugojimai rašomi į "
                                "prompts/system/<slug>.md ir versijuojami duomenų bazėje."},
    "instr_shared":      {"en": "Edit shared PE glossary",
                          "lt": "Redaguoti bendrą PE žodyną"},
    "instr_shared_title": {"en": "Shared PE glossary",
                           "lt": "Bendras PE žodynas"},
    "instr_shared_sub":  {"en": "Prepended to every agent’s system prompt",
                          "lt": "Pridedėta prie kiekvieno agento sistemos promptų"},
    "instr_editor":      {"en": "Editor",             "lt": "Redaktorius"},
    "instr_markdown":    {"en": "Markdown",           "lt": "Markdown"},
    "instr_history":     {"en": "History",            "lt": "Istorija"},
    "instr_save":        {"en": "Save",               "lt": "Išsaugoti"},
    "instr_cancel":      {"en": "Cancel",             "lt": "Atšaukti"},
}


def t(key: str, lang: str = DEFAULT_LANG) -> str:
    """Look up a translation. Falls back to English, then to the key itself."""
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    return entry.get(lang, entry.get("en", key))


# ── Agent & category translations ─────────────────────────────────────

CATEGORY_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = {
    "sourcing": {
        "name": {"en": "Deal Sourcing & Screening",
                 "lt": "Sandorių paieška ir atranka"},
        "blurb": {"en": "Find proprietary deals before they hit the auction.",
                  "lt": "Raskite savitus sandorius anksčiau nei jie pateks į aukcioną."},
    },
    "underwriting": {
        "name": {"en": "LBO Underwriting Engine",
                 "lt": "LBO vertinimo variklis"},
        "blurb": {"en": "Teaser to IC-ready LBO model in hours.",
                  "lt": "Nuo teaserio iki IC parengt LBO modelio per valandas."},
    },
    "diligence": {
        "name": {"en": "Due Diligence Stack",
                 "lt": "Due Diligence sistema"},
        "blurb": {"en": "VDR audited, QoE validated, risks surfaced early.",
                  "lt": "VDR patikrintas, QoE patvirtintas, rizikos atskleistos anksti."},
    },
    "capital": {
        "name": {"en": "Capital & LP Relations",
                 "lt": "Kapitalas ir LP santykiai"},
        "blurb": {"en": "IC memos, teasers and LP updates your GP will sign.",
                  "lt": "IC memo, teaser ir LP ataskaitos, kurias jūsų GP pasirašys."},
    },
    "asset_mgmt": {
        "name": {"en": "Portfolio Operations",
                 "lt": "Portfelio operacijos"},
        "blurb": {"en": "Drive EBITDA growth and value creation post-close.",
                  "lt": "Skatinkite EBITDA augimą ir vertės kūrimą po uždarymo."},
    },
}

AGENT_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = {
    "market_scanner": {
        "name": {"en": "Market Scanner", "lt": "Rinkos skeneris"},
        "one_liner": {"en": "PitchBook + banker feeds + proprietary outreach, ranked by fit.",
                      "lt": "PitchBook + bankininkų srautai + tiesioginė paieška, suranguota pagal tinkamumą."},
    },
    "deal_triage": {
        "name": {"en": "Deal Triage Agent", "lt": "Sandorių atrankos agentas"},
        "one_liner": {"en": "Go / no-go in 90 seconds against your fund mandate.",
                      "lt": "Taip / ne per 90 sekundžių pagal jūsų fondo mandatą."},
    },
    "comp_finder": {
        "name": {"en": "Transaction Comps Finder", "lt": "Sandorių lyginamųjų paieška"},
        "one_liner": {"en": "M&A + trading comps across 3 sources with outlier filtering.",
                      "lt": "M&A + prekybinės komp. iš 3 šaltinių su išskirčių filtru."},
    },
    "seller_intent": {
        "name": {"en": "Owner Intent Signal", "lt": "Savininko ketinimo signalas"},
        "one_liner": {"en": "Ranks companies by likelihood of sale in the next 12 months.",
                      "lt": "Ranguoja įmones pagal pardavimo tikimybę per artimiausius 12 mėnesių."},
    },
    "outreach_email": {
        "name": {"en": "Outreach Email Drafter", "lt": "Kontaktinių laiškų rengėjas"},
        "one_liner": {"en": "Personalized founder/broker outreach emails in your fund’s voice.",
                      "lt": "Personalizuoti kontaktiniai laiškai įkūrėjams/tarpininkams jūsų fondo tonu."},
    },
    "loi_writer": {
        "name": {"en": "LOI Writer", "lt": "LOI rengėjas"},
        "one_liner": {"en": "Non-binding letter of intent — price, structure, conditions, timeline.",
                      "lt": "Neįpareigojantis ketinimo laškas — kaina, struktūra, sąlygos, terminai."},
    },
    "rent_roll_parser": {
        "name": {"en": "Cap Table Parser", "lt": "Cap Table analizatorius"},
        "one_liner": {"en": "Any cap table format → clean, fully-diluted ownership with waterfalls.",
                      "lt": "Bet koks cap table formatas → švarus, pilnai praskiestas nuosavybės vaizdas."},
    },
    "t12_normalizer": {
        "name": {"en": "LTM Financials Normalizer", "lt": "LTM finansinių normalizatorius"},
        "one_liner": {"en": "Messy owner financials → clean, add-back-adjusted LTM EBITDA.",
                      "lt": "Netvarkingos savininko ataskaitos → švarus, koreguotas LTM EBITDA."},
    },
    "pro_forma_builder": {
        "name": {"en": "LBO Model Builder", "lt": "LBO modelio statytojas"},
        "one_liner": {"en": "5-year LBO model with sensitivity grid — editable assumptions.",
                      "lt": "5 metų LBO modelis su jautrumo lentele — redaguojamos prielaidos."},
    },
    "debt_stack_modeler": {
        "name": {"en": "Debt Stack Modeler", "lt": "Skolos struktūros modeliuotojas"},
        "one_liner": {"en": "Unitranche + mezz + revolver — with live leverage + DSCR.",
                      "lt": "Unitranche + mezz + revolver — su gyvais sverto + DSCR rodikliais."},
    },
    "return_metrics": {
        "name": {"en": "Return Metrics", "lt": "Grąžos metrikos"},
        "one_liner": {"en": "IRR, MOIC, levered/unlevered, with a value-creation bridge.",
                      "lt": "IRR, MOIC, su svertu / be sverto, su vertės kūrimo tiltu."},
    },
    "doc_room_auditor": {
        "name": {"en": "VDR Auditor", "lt": "VDR auditorius"},
        "one_liner": {"en": "Cross-checks the data room against a full PE DD checklist.",
                      "lt": "Kryžminai tikrina duomenų kambarį pagal pilną PE DD kontrolę."},
    },
    "lease_abstractor": {
        "name": {"en": "Contract Abstractor", "lt": "Sutarčių abstraktorius"},
        "one_liner": {"en": "PDFs → contract abstracts with key terms, options, and risks.",
                      "lt": "PDF → sutarčių santraukos su pagrindinėmis sąlygomis, opcijomis ir rizikomis."},
    },
    "title_zoning": {
        "name": {"en": "Legal & Regulatory Checker", "lt": "Teisinės ir reguliavimo patikra"},
        "one_liner": {"en": "Corporate records + litigation + regulatory review, flags material issues.",
                      "lt": "Įmonės dokumentai + bylinjimas + reguliavimo peržiūra, pažymi esminius dalykus."},
    },
    "physical_condition": {
        "name": {"en": "Operational Diligence Reviewer", "lt": "Operacinės patikros peržiūrėtojas"},
        "one_liner": {"en": "Reads operational DD + QoE, builds a 100-day value-creation plan.",
                      "lt": "Skaito operacinę DD + QoE, kuria 100 dienų vertės kūrimo planą."},
    },
    "environmental_risk": {
        "name": {"en": "ESG & Compliance Risk Flagger", "lt": "ESG ir atitikties rizikos žymiklis"},
        "one_liner": {"en": "ESG review — flags environmental, social, governance exposures.",
                      "lt": "ESG peržiūra — fiksuoja aplinkosaugos, socialines, valdymo rizikas."},
    },
    "investor_memo": {
        "name": {"en": "IC Memo Writer", "lt": "IC Memo rengėjas"},
        "one_liner": {"en": "IC memo your investment committee will actually read.",
                      "lt": "IC memo, kurį jūsų investicijų komitetas tikrai perskaitys."},
    },
    "deal_teaser": {
        "name": {"en": "Teaser Designer", "lt": "Teaserio dizaineris"},
        "one_liner": {"en": "2-page teaser with thesis, financials, returns snapshot.",
                      "lt": "2 puslapių teaseris su teze, finansais, grąžos momentine nuotrauka."},
    },
    "lp_update": {
        "name": {"en": "LP Update Generator", "lt": "LP ataskaitų generatorius"},
        "one_liner": {"en": "Quarterly LP letter with portfolio performance + outlook.",
                      "lt": "Ketvirtinis LP laiškas su portfelio rezultatais + prognozėmis."},
    },
    "fundraising_crm": {
        "name": {"en": "Fundraising CRM Copilot", "lt": "Lėšų pritraukimo CRM kopilotas"},
        "one_liner": {"en": "LP pipeline ranked by fit, staleness, and commitment size.",
                      "lt": "LP pipeline, suranguotas pagal tinkamumą, senumą ir įsipareigojimo dydį."},
    },
    "rent_optimization": {
        "name": {"en": "Pricing Optimization Agent", "lt": "Kainodara optimizavimo agentas"},
        "one_liner": {"en": "SKU/segment pricing recommendations from elasticity + peer benchmarks.",
                      "lt": "SKU/segmento kainodaros rekomendacijos pagal elastingumą + lyginamuosius."},
    },
    "opex_variance": {
        "name": {"en": "EBITDA Variance Watcher", "lt": "EBITDA nuokrypių stebėtojas"},
        "one_liner": {"en": "Monthly EBITDA variance vs. budget — with root-cause commentary.",
                      "lt": "Mėnesinis EBITDA nuokrypis nuo biudžeto — su priežasčių komentarais."},
    },
    "capex_prioritizer": {
        "name": {"en": "Value Creation Prioritizer", "lt": "Vertės kūrimo prioritizatorius"},
        "one_liner": {"en": "Ranks value-creation initiatives by EBITDA impact and ROI.",
                      "lt": "Ranguoja vertės kūrimo iniciatyvas pagal EBITDA poveikį ir ROI."},
    },
    "tenant_churn": {
        "name": {"en": "Customer Churn Predictor", "lt": "Klientų praradimo prognozuotojas"},
        "one_liner": {"en": "Scores each customer’s renewal likelihood; drives retention actions.",
                      "lt": "Vertina kiekvieno kliento atsinaujinimo tikimybę; skatina išlaikymo veiksmus."},
    },
}


def agent_t(slug: str, field: str, lang: str = DEFAULT_LANG) -> str:
    """Translate an agent field. Falls back to English AgentSpec attribute."""
    entry = AGENT_TRANSLATIONS.get(slug, {}).get(field)
    if entry:
        return entry.get(lang, entry.get("en", ""))
    from agents.registry import AGENTS_BY_SLUG
    spec = AGENTS_BY_SLUG.get(slug)
    if spec:
        return getattr(spec, field, "")
    return ""


def category_t(key: str, field: str, lang: str = DEFAULT_LANG) -> str:
    """Translate a category field."""
    entry = CATEGORY_TRANSLATIONS.get(key, {}).get(field)
    if entry:
        return entry.get(lang, entry.get("en", ""))
    return key


def js_translations(lang: str = DEFAULT_LANG) -> dict[str, str]:
    """Return the ~30 JS-facing translation strings for the given language."""
    return {k.removeprefix("js_"): t(k, lang)
            for k in TRANSLATIONS if k.startswith("js_")}
