"""Marketing routes: /, /platform, /agents, /agents/<slug>, /how-it-works, /pricing, /contact."""

from __future__ import annotations

from fasthtml.common import (
    Div, H1, H2, H3, H4, P, Ul, Li, Section, Article, Span, A, Form, Input, Textarea, Label, Button, NotStr,
)

from starlette.responses import RedirectResponse

from app import rt
from agents.registry import AGENTS, AGENTS_BY_CATEGORY, AGENTS_BY_SLUG, CATEGORIES
from landing.components import (
    page, Hero, ProductTour, CategoryPillar, AgentCard, CategorySection, CaseStudyStrip, PENewsSection, CTASection,
    Eyebrow, Heading, Body_, Button_, Pill, Section_, SITE_NAME, SITE_TAGLINE,
)
from utils.i18n import t, agent_t, category_t, get_lang, set_lang, LANGUAGES


# ── Language switch ────────────────────────────────────────────────────
@rt("/set-lang/{code}")
def set_language(code: str, sess):
    if code in LANGUAGES:
        set_lang(sess, code)
    return RedirectResponse("/", status_code=303)


# ── / ────────────────────────────────────────────────────────────────
@rt("/")
def home(sess):
    lang = get_lang(sess)
    pillars = Section_(
        Div(
            Eyebrow(t("pillars_eyebrow", lang)),
            Heading(2, t("pillars_heading", lang), cls="mt-3 max-w-4xl mb-10"),
            cls="mb-6",
        ),
        Div(
            *[CategoryPillar(c, lang=lang) for c in CATEGORIES],
            cls="grid md:grid-cols-2 lg:grid-cols-5 gap-4",
        ),
        cls="border-t border-line",
    )

    how = Section_(
        Div(
            Eyebrow(t("how_eyebrow", lang)),
            Heading(2, t("how_heading", lang), cls="mt-3 max-w-3xl mb-10"),
            cls="mb-6",
        ),
        Div(
            *[Article(
                P(num, cls="font-mono text-[11px] tracking-widest uppercase text-ink-dim mb-3"),
                H3(title, cls="text-ink text-xl font-medium mb-3"),
                P(body, cls="text-ink-muted text-sm leading-relaxed"),
                cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
            ) for (num, title, body) in [
                ("01", t("how_01_title", lang), t("how_01_body", lang)),
                ("02", t("how_02_title", lang), t("how_02_body", lang)),
                ("03", t("how_03_title", lang), t("how_03_body", lang)),
            ]],
            cls="grid md:grid-cols-3 gap-4",
        ),
        cls="border-t border-line",
    )

    return page(
        t("hero_eyebrow", lang),
        Hero(lang=lang),
        ProductTour(lang=lang),
        pillars,
        how,
        CaseStudyStrip(lang=lang),
        PENewsSection(lang=lang),
        CTASection(lang=lang),
        current_path="/",
        lang=lang,
    )


# ── /platform ────────────────────────────────────────────────────────
@rt("/platform")
def platform(sess):
    lang = get_lang(sess)
    return page(
        t("platform_title", lang),
        Section_(
            Eyebrow(t("platform_title", lang)),
            Heading(1, t("platform_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("platform_body", lang),
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        Section_(
            Div(
                *[Article(
                    Div(Span(c["icon"], cls="text-accent text-xl"),
                        Span(t("agents_count", lang).format(n=len(AGENTS_BY_CATEGORY[c['key']])),
                             cls="ml-auto font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
                        cls="flex items-center mb-4"),
                    H3(category_t(c["key"], "name", lang), cls="text-ink text-xl font-medium mb-2"),
                    P(category_t(c["key"], "blurb", lang), cls="text-ink-muted leading-relaxed"),
                    cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
                ) for c in CATEGORIES],
                cls="grid md:grid-cols-2 lg:grid-cols-5 gap-4",
            ),
            cls="border-t border-line",
        ),
        Section_(
            Eyebrow(t("platform_hood", lang)),
            Heading(2, t("platform_not_wrap", lang), cls="mt-3 max-w-3xl mb-10"),
            Div(
                *[Article(
                    P(k, cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-3"),
                    P(v, cls="text-ink leading-relaxed"),
                    cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
                ) for (k, v) in [
                    ("Squad", t("platform_squad", lang)),
                    ("Tools", t("platform_tools", lang)),
                    ("RAG",   t("platform_rag", lang)),
                    ("Memory", t("platform_memory", lang)),
                ]],
                cls="grid md:grid-cols-2 lg:grid-cols-4 gap-4",
            ),
            cls="border-t border-line",
        ),
        CTASection(lang=lang),
        current_path="/platform",
        lang=lang,
    )


# ── /agents ──────────────────────────────────────────────────────────
@rt("/agents")
def agents_page(sess):
    lang = get_lang(sess)
    return page(
        t("nav_agents", lang),
        Section_(
            Eyebrow(t("agents_eyebrow", lang)),
            Heading(1, t("agents_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("agents_body", lang),
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        *[CategorySection(c, lang=lang) for c in CATEGORIES],
        CTASection(lang=lang),
        current_path="/agents",
        lang=lang,
    )


# ── /agents/<slug> ───────────────────────────────────────────────────
@rt("/agents/{slug}")
def agent_detail(slug: str, sess):
    lang = get_lang(sess)
    agent = AGENTS_BY_SLUG.get(slug)
    if agent is None:
        return page(
            t("agent_not_found", lang),
            Section_(
                H1(t("agent_not_found", lang), cls="text-ink text-3xl"),
                P(t("agent_no_url", lang), A(t("agent_full_squad", lang), href="/agents", cls="text-accent underline"), ".",
                  cls="text-ink-muted mt-4"),
            ),
            current_path="/agents",
            lang=lang,
        )
    cat = next(c for c in CATEGORIES if c["key"] == agent.category)
    agent_name = agent_t(slug, "name", lang)
    return page(
        agent_name,
        Section_(
            Div(
                A(t("agent_all", lang), href="/agents", cls="text-ink-dim text-xs hover:text-accent"),
                cls="mb-6",
            ),
            Div(
                Span(agent.icon, cls="text-accent text-4xl"),
                Span(category_t(cat["key"], "name", lang), cls="ml-4 font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
                cls="flex items-center mb-4",
            ),
            Heading(1, agent_name, cls="max-w-4xl"),
            P(agent_t(slug, "one_liner", lang), cls="mt-5 text-ink-muted text-lg max-w-3xl"),
            Div(Pill(f"prefix: {agent.prefix}"),
                Pill(f"category: {cat['key']}"),
                cls="mt-6 flex flex-wrap gap-2"),
            cls="border-t border-line",
        ),
        Section_(
            Div(
                Div(
                    Eyebrow(t("agent_what", lang)),
                    P(agent.description, cls="mt-4 text-ink leading-relaxed"),
                    cls="md:col-span-2",
                ),
                Div(
                    Eyebrow(t("agent_examples", lang)),
                    Ul(
                        *[Li(
                            Div(f'"{p}"', cls="px-4 py-3 rounded-xl bg-bg-elevated border border-line text-sm text-ink leading-relaxed"),
                            cls="mb-2",
                        ) for p in agent.example_prompts],
                        cls="mt-4 space-y-2",
                    ),
                    cls="",
                ),
                cls="grid md:grid-cols-3 gap-10",
            ),
            cls="border-t border-line",
        ),
        CTASection(headline=t("agent_try", lang).format(name=agent_name),
                   body=t("agent_try_body", lang),
                   cta_label=t("hero_cta_open", lang), cta_href="/app", lang=lang),
        current_path="/agents",
        lang=lang,
    )


# ── /how-it-works ────────────────────────────────────────────────────
@rt("/how-it-works")
def how_it_works(sess):
    lang = get_lang(sess)
    return page(
        t("hiw_title", lang),
        Section_(
            Eyebrow(t("hiw_title", lang)),
            Heading(1, t("hiw_h1", lang), cls="mt-4 max-w-4xl"),
            cls="border-t border-line",
        ),
        *[Section_(
            Div(
                Span(num, cls="font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
                Heading(2, title, cls="mt-3 max-w-3xl"),
                P(body, cls="mt-5 text-ink-muted text-lg max-w-3xl leading-relaxed"),
                cls="mb-8",
            ),
            Div(*[Pill(name) for name in agents], cls="flex flex-wrap gap-2"),
            cls="border-t border-line",
        ) for (num, title, body, agents) in [
            (t("hiw_01_num", lang), t("hiw_01_title", lang), t("hiw_01_body", lang),
             ["Market Scanner", "Deal Triage", "Transaction Comps", "Owner Intent"]),
            (t("hiw_02_num", lang), t("hiw_02_title", lang), t("hiw_02_body", lang),
             ["Cap Table Parser", "LTM Normalizer", "LBO Model Builder", "Debt Stack Modeler", "Return Metrics"]),
            (t("hiw_03_num", lang), t("hiw_03_title", lang), t("hiw_03_body", lang),
             ["VDR Auditor", "Contract Abstractor", "Legal & Regulatory", "Operational Diligence", "ESG Risk"]),
            (t("hiw_04_num", lang), t("hiw_04_title", lang), t("hiw_04_body", lang),
             ["IC Memo Writer", "Teaser Designer", "LP Update Generator", "Fundraising CRM Copilot"]),
            (t("hiw_05_num", lang), t("hiw_05_title", lang), t("hiw_05_body", lang),
             ["Pricing Optimization", "EBITDA Variance Watcher", "Value Creation Prioritizer", "Customer Churn Predictor"]),
        ]],
        CTASection(lang=lang),
        current_path="/how-it-works",
        lang=lang,
    )


# ── /pricing ─────────────────────────────────────────────────────────
@rt("/pricing")
def pricing(sess):
    lang = get_lang(sess)
    tiers = [
        {
            "name": t("pricing_pilot", lang),
            "price": t("pricing_pilot_price", lang),
            "sub": t("pricing_pilot_sub", lang),
            "blurb": t("pricing_pilot_blurb", lang),
            "features": [
                t("feat_full_squad", lang), t("feat_1_user", lang), t("feat_5_deals", lang),
                t("feat_byod", lang), t("feat_email", lang),
            ],
            "cta": (t("pricing_start_pilot", lang), "/contact"),
            "primary": False,
        },
        {
            "name": t("pricing_team", lang),
            "price": t("pricing_team_price", lang),
            "sub": t("pricing_team_sub", lang),
            "blurb": t("pricing_team_blurb", lang),
            "features": [
                t("feat_full_squad", lang), t("feat_25_seats", lang), t("feat_unlimited", lang),
                t("feat_sso", lang), t("feat_shared", lang), t("feat_priority", lang),
            ],
            "cta": (t("pricing_book_demo", lang), "/contact"),
            "primary": True,
        },
        {
            "name": t("pricing_platform", lang),
            "price": t("pricing_platform_price", lang),
            "sub": t("pricing_platform_sub", lang),
            "blurb": t("pricing_platform_blurb", lang),
            "features": [
                t("feat_everything", lang), t("feat_unlimited_seats", lang), t("feat_dedicated", lang),
                t("feat_own_llm", lang), t("feat_custom", lang), t("feat_onsite", lang),
            ],
            "cta": (t("pricing_contact", lang), "/contact"),
            "primary": False,
        },
    ]
    return page(
        t("pricing_eyebrow", lang),
        Section_(
            Eyebrow(t("pricing_eyebrow", lang)),
            Heading(1, t("pricing_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("pricing_sub", lang),
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        Section_(
            Div(
                *[Article(
                    P(t["name"], cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-3"),
                    Div(
                        Span(t["price"], cls="text-4xl md:text-5xl font-medium tracking-tighter text-ink"),
                        Span(f" {t['sub']}", cls="text-ink-muted text-sm ml-2"),
                        cls="mb-4",
                    ),
                    P(t["blurb"], cls="text-ink-muted leading-relaxed mb-6"),
                    Ul(
                        *[Li(
                            Span("✓ ", cls="text-accent mr-2"),
                            Span(f, cls="text-ink text-sm"),
                            cls="mb-2 flex items-baseline",
                        ) for f in t["features"]],
                        cls="mb-8 space-y-1",
                    ),
                    Button_(t["cta"][0], href=t["cta"][1], primary=t["primary"]),
                    cls=("p-8 rounded-2xl bg-bg-elevated h-full flex flex-col " +
                         ("border border-accent/60" if t["primary"] else "border border-line")),
                ) for t in tiers],
                cls="grid md:grid-cols-3 gap-4",
            ),
            cls="border-t border-line",
        ),
        CTASection(lang=lang),
        current_path="/pricing",
        lang=lang,
    )


# ── /contact ─────────────────────────────────────────────────────────
@rt("/contact")
def contact(sess, sent: bool = False):
    lang = get_lang(sess)
    form = Form(
        Div(
            Label(t("contact_name", lang), cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Input(name="name", type="text", required=True,
                  cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-5",
        ),
        Div(
            Label(t("contact_email", lang), cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Input(name="email", type="email", required=True,
                  cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-5",
        ),
        Div(
            Label(t("contact_firm", lang), cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Input(name="firm", type="text",
                  cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-5",
        ),
        Div(
            Label(t("contact_pipeline", lang), cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Textarea(name="message", rows="5", required=True,
                     cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-8",
        ),
        Button(t("contact_send", lang), type="submit",
               cls="inline-flex items-center gap-2 px-5 py-3 rounded-full text-sm font-medium bg-accent text-bg hover:bg-ink transition-all"),
        method="post",
        action="/contact",
    )

    success = Div(
        Div(
            Span("✓", cls="text-accent text-2xl"),
            cls="mb-4",
        ),
        H3(t("contact_thanks", lang), cls="text-ink text-xl mb-2"),
        P(t("contact_usually", lang), cls="text-ink-muted"),
        cls="p-8 rounded-2xl bg-bg-elevated border border-line",
    )

    return page(
        t("contact_eyebrow", lang),
        Section_(
            Eyebrow(t("contact_eyebrow", lang)),
            Heading(1, t("contact_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("contact_body", lang),
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            Div(
                success if sent else form,
                cls="mt-12 max-w-xl",
            ),
            cls="border-t border-line",
        ),
        current_path="/contact",
        lang=lang,
    )


@rt("/contact", methods=["POST"])
def contact_post(sess, name: str = "", email: str = "", firm: str = "", message: str = ""):
    lang = get_lang(sess)
    import logging
    logging.getLogger(__name__).info("contact form submitted: %s (%s) %s chars",
                                     name, email, len(message or ""))
    return page(
        t("contact_thanks", lang),
        Section_(
            Eyebrow(t("contact_eyebrow", lang)),
            Heading(1, t("contact_thanks", lang), cls="mt-4 max-w-4xl"),
            P(t("contact_usually", lang), " ", t("contact_meanwhile", lang),
              A(t("contact_open_app", lang), href="/app", cls="text-accent underline"),
              t("contact_byod_post", lang),
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        current_path="/contact",
        lang=lang,
    )
