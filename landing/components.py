"""Landing-page components — PE repositioning of the predictivelabsai-landing kit.

Lighter, slightly warmer palette than Bricksmith: off-white parchment background
with a slate/forest-green accent that plays to PE's "institutional but modern"
feel. All pages share the `page()` wrapper below.
"""

from __future__ import annotations

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Nav, Main, Footer, Section, Article, Div, Span, A, Img,
    H1, H2, H3, H4, P, Ul, Li, Button, Form, Input, Textarea, Label,
)

from agents.registry import CATEGORIES, AGENTS, AGENTS_BY_CATEGORY
from utils.i18n import t, agent_t, category_t, LANGUAGES

SITE_NAME = "PEHero"
SITE_TAGLINE = "Agentic AI for private equity deal teams."
CONTACT_EMAIL = "hello@pehero.fyi"
GITHUB_URL = "https://github.com/predictivelabsai/pehero"
LINKEDIN_URL = "https://www.linkedin.com/company/predictive-labs-ltd/"

NAV_ITEMS = [
    ("nav_platform", "/platform"),
    ("nav_agents", "/agents"),
    ("nav_how", "/how-it-works"),
    ("nav_pricing", "/pricing"),
    ("nav_contact", "/contact"),
]

# Lighter parchment background with a deep-forest / slate accent.
# Distinct from Bricksmith's dark-navy + amber but keeps a similar cadence.
TAILWIND_CONFIG = """
tailwind.config = {
  theme: {
    extend: {
      colors: {
        bg:     { DEFAULT: '#F7F6F1', elevated: '#FFFFFF', raised: '#EFEDE4' },
        ink:    { DEFAULT: '#14231B', muted: '#415046', dim: '#7A867E' },
        line:   { DEFAULT: '#E3DFD2', bright: '#CFC8B4' },
        accent: { DEFAULT: '#1F5D43', dim: '#CFE5DA', deep: '#0F3226' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      letterSpacing: { tightest: '-0.04em', tighter: '-0.025em' },
    },
  },
};
"""


def Eyebrow(text: str, *, cls: str = ""):
    return Span(text, cls=f"font-mono text-[11px] tracking-[0.18em] uppercase text-accent {cls}".strip())


def Heading(level: int, text, *, cls: str = ""):
    tag = {1: H1, 2: H2, 3: H3, 4: H4}[level]
    base = {
        1: "text-4xl sm:text-5xl md:text-7xl font-medium tracking-tightest text-ink leading-[1.05] md:leading-[1.02]",
        2: "text-2xl sm:text-3xl md:text-5xl font-medium tracking-tighter text-ink leading-[1.12] md:leading-[1.08]",
        3: "text-lg sm:text-xl md:text-2xl font-medium tracking-tight text-ink",
        4: "text-base md:text-lg font-medium text-ink",
    }[level]
    return tag(text if not isinstance(text, tuple) else Span(*text), cls=f"{base} {cls}".strip())


def Body_(text, *, cls: str = "", muted: bool = True):
    tone = "text-ink-muted" if muted else "text-ink"
    return P(text, cls=f"text-base md:text-lg leading-relaxed {tone} {cls}".strip())


def Button_(text: str, *, href: str = "#", primary: bool = True, cls: str = ""):
    base = "inline-flex items-center gap-2 px-5 py-3 rounded-full text-sm font-medium transition-all duration-200"
    if primary:
        style = "bg-accent text-bg hover:bg-ink shadow-[0_0_0_1px_#1F5D43] hover:shadow-[0_0_0_1px_#14231B]"
    else:
        style = "bg-transparent text-ink border border-line-bright hover:border-accent hover:text-accent"
    return A(text, Span("→", cls="text-base"), href=href, cls=f"{base} {style} {cls}".strip())


def Pill(text: str, *, cls: str = ""):
    return Span(
        text,
        cls=f"inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono tracking-wider uppercase text-ink-muted bg-bg-elevated border border-line {cls}".strip(),
    )


def _navbar(current_path: str = "/", lang: str = "en"):
    items = [
        Li(A(t(key, lang), href=href,
             cls=f"text-sm text-ink-muted hover:text-ink transition-colors {'text-ink' if current_path == href or current_path.startswith(href + '/') else ''}"))
        for key, href in NAV_ITEMS
    ]
    current_flag = LANGUAGES.get(lang, LANGUAGES["en"])["flag"]
    lang_options = [
        A(Span(info["flag"], cls="mr-2"), Span(info["native"], cls="text-xs"),
          href=f"/set-lang/{code}",
          cls=f"flex items-center gap-1 px-3 py-1.5 rounded text-sm text-ink-muted hover:bg-bg-raised hover:text-ink transition-colors {'font-semibold text-accent-deep' if code == lang else ''}")
        for code, info in LANGUAGES.items()
    ]
    lang_dropdown = Div(
        Button(current_flag,
               cls="text-base leading-none px-1.5 py-1 border border-transparent rounded hover:border-line-bright transition-colors cursor-pointer bg-transparent",
               onclick="this.nextElementSibling.classList.toggle('hidden')"),
        Div(*lang_options,
            cls="hidden absolute right-0 top-full mt-1 bg-bg-elevated border border-line rounded-lg shadow-lg z-50 py-1 min-w-[130px] flex flex-col"),
        cls="relative",
    )
    return Nav(
        Div(
            A(
                Span("◆", cls="text-accent mr-2"),
                Span(SITE_NAME, cls="font-medium tracking-tight"),
                href="/",
                cls="flex items-center text-ink text-base hover:text-accent transition-colors",
            ),
            Ul(*items, cls="hidden lg:flex items-center gap-7"),
            Div(
                lang_dropdown,
                A(t("nav_book_demo", lang), href="/contact",
                  cls="hidden lg:inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium text-ink border border-line-bright hover:border-accent hover:text-accent transition-colors"),
                A(t("nav_open_app", lang), href="/app",
                  cls="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium bg-accent text-bg hover:bg-ink transition-colors"),
                cls="flex items-center gap-3",
            ),
            cls="max-w-7xl mx-auto px-5 md:px-6 flex items-center justify-between h-16 gap-4",
        ),
        cls="sticky top-0 z-50 backdrop-blur-md bg-bg/80 border-b border-line",
    )


def _footer(lang: str = "en"):
    return Footer(
        Div(
            Div(
                Div(
                    A(Span("◆", cls="text-accent mr-2"), Span(SITE_NAME, cls="font-medium text-ink"),
                      href="/", cls="flex items-center text-lg mb-4"),
                    P(SITE_TAGLINE, cls="text-ink-muted text-sm max-w-xs mb-5"),
                    P(t("footer_tagline", lang),
                      cls="text-ink-dim text-xs leading-relaxed max-w-xs"),
                ),
                Div(
                    H4(t("footer_product", lang), cls="text-xs font-mono tracking-[0.18em] uppercase text-ink-muted mb-5"),
                    Ul(
                        Li(A(t("nav_platform", lang), href="/platform", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                        Li(A(t("nav_agents", lang), href="/agents", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                        Li(A(t("nav_how", lang), href="/how-it-works", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                        Li(A(t("nav_pricing", lang), href="/pricing", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                        Li(A(t("footer_open_app", lang), href="/app", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                    ),
                ),
                Div(
                    H4(t("footer_company", lang), cls="text-xs font-mono tracking-[0.18em] uppercase text-ink-muted mb-5"),
                    Ul(
                        Li(A(t("nav_contact", lang), href="/contact", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                        Li(A("GitHub", href=GITHUB_URL, cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                        Li(A("LinkedIn", href=LINKEDIN_URL, cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                    ),
                ),
                cls="grid grid-cols-2 md:grid-cols-3 gap-10",
            ),
            Div(
                Div(f"© {__import__('datetime').datetime.now().year} PEHero · Predictive Labs Ltd.",
                    cls="text-ink-dim text-xs"),
                A(CONTACT_EMAIL, href=f"mailto:{CONTACT_EMAIL}",
                  cls="text-ink-dim text-xs hover:text-accent"),
                cls="mt-10 md:mt-14 pt-6 border-t border-line flex items-start md:items-center justify-between flex-wrap gap-4",
            ),
            cls="max-w-7xl mx-auto px-5 md:px-6",
        ),
        cls="py-12 md:py-16 border-t border-line bg-bg-elevated",
    )


def _favicon_links():
    """Shared favicon <link>s — included on every page (landing + app)."""
    return [
        Link(rel="icon", type="image/svg+xml", href="/static/favicon.svg"),
        Link(rel="icon", type="image/png", sizes="32x32", href="/static/favicon.png"),
        Link(rel="alternate icon", href="/static/favicon.ico"),
        Link(rel="apple-touch-icon", sizes="180x180", href="/static/apple-touch-icon.png"),
        Meta(name="theme-color", content="#1F5D43"),
    ]


def page(title: str, *content, current_path: str = "/", head_extra=None, lang: str = "en"):
    head_children = [
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Meta(name="description", content=f"{SITE_NAME} — {SITE_TAGLINE}"),
        Title(f"{title} · {SITE_NAME}"),
        *_favicon_links(),
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        Link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap",
        ),
        Script(src="https://cdn.tailwindcss.com"),
        Script(NotStr(TAILWIND_CONFIG)),
        Link(rel="stylesheet", href="/static/site.css"),
    ]
    if head_extra:
        head_children.extend(head_extra if isinstance(head_extra, list) else [head_extra])

    return Html(
        Head(*head_children),
        Body(
            _navbar(current_path, lang=lang),
            Main(*content, cls="min-h-screen"),
            _footer(lang=lang),
            cls="bg-bg text-ink font-sans antialiased",
        ),
        lang=lang,
    )


# ─── Higher-level blocks ───────────────────────────────────────────────

def Section_(*content, bleed: bool = False, cls: str = ""):
    inner_cls = "max-w-7xl mx-auto px-5 md:px-6" if not bleed else "w-full"
    return Section(Div(*content, cls=inner_cls), cls=f"py-14 md:py-20 lg:py-24 {cls}".strip())


def Hero(lang: str = "en"):
    headline = (
        Span(t("hero_h1_1", lang)),
        Span(t("hero_h1_2", lang), cls="text-accent"),
        Span(t("hero_h1_3", lang)),
        Span(t("hero_h1_4", lang), cls="text-accent"),
        Span(t("hero_h1_5", lang)),
        Span(t("hero_h1_6", lang), cls="text-accent"),
        Span(t("hero_h1_7", lang)),
    )
    return Section(
        Div(
            Div(id="hero-grid", cls="absolute inset-0 z-10 opacity-40 pointer-events-none"),
            Div(cls="absolute inset-0 z-20 bg-gradient-to-b from-bg/40 via-transparent to-bg pointer-events-none"),
            Div(
                Eyebrow(t("hero_eyebrow", lang)),
                H1(*headline,
                   cls="mt-5 md:mt-6 text-[40px] sm:text-5xl md:text-7xl lg:text-[84px] font-medium tracking-tightest text-ink leading-[1.05] md:leading-[1.02] max-w-5xl"),
                P(t("hero_lede", lang), cls="mt-6 md:mt-8 text-base md:text-xl text-ink-muted max-w-2xl leading-relaxed"),
                Div(
                    Button_(t("hero_cta_open", lang), href="/app", primary=True),
                    Button_(t("hero_cta_meet", lang), href="/agents", primary=False),
                    cls="mt-8 md:mt-10 flex items-center gap-3 flex-wrap",
                ),
                cls="relative z-30 max-w-7xl mx-auto px-5 md:px-6 py-24 md:py-0",
            ),
            cls="relative min-h-[80vh] md:min-h-[86vh] flex items-center overflow-hidden bg-bg",
        ),
        Div(
            Div(
                _StatCell(t("stat_squad", lang), t("stat_squad_cap", lang)),
                _StatCell(t("stat_5", lang), t("stat_5_cap", lang)),
                _StatCell(t("stat_90s", lang), t("stat_90s_cap", lang)),
                _StatCell(t("stat_byod", lang), t("stat_byod_cap", lang)),
                cls="max-w-7xl mx-auto px-5 md:px-6 py-5 md:py-6 grid grid-cols-2 md:grid-cols-4 gap-6",
            ),
            cls="border-y border-line bg-bg-elevated/60",
        ),
    )


def ProductTour(lang: str = "en"):
    """Rotating GIF preview + CTA into the app / README / PDF tour."""
    return Section(
        Div(
            Div(
                Eyebrow(t("tour_eyebrow", lang)),
                Heading(2, t("tour_heading", lang), cls="mt-3 max-w-3xl mb-2"),
                P(t("tour_body", lang),
                  cls="mt-2 text-ink-muted text-base max-w-2xl leading-relaxed mb-6"),
                cls="mb-6",
            ),
            A(
                Img(src="/docs/pehero.gif",
                    alt="PEHero product tour — chat, pipeline, analytics",
                    cls="block w-full h-auto rounded-2xl border border-line shadow-[0_8px_40px_rgba(0,0,0,0.06)]",
                    loading="lazy"),
                href="https://github.com/predictivelabsai/pehero#readme",
                target="_blank", rel="noopener",
                cls="block rounded-2xl overflow-hidden hover:opacity-95 transition-opacity",
                title="Open the README",
            ),
            Div(
                A(Span(t("tour_pdf", lang)), Span("↓", cls="ml-1"),
                  href="/docs/pehero-product-tour.pdf",
                  cls="inline-flex items-center gap-2 text-sm text-accent hover:text-ink"),
                Span("·", cls="text-ink-dim mx-3"),
                A(Span(t("tour_pptx", lang)), Span("↓", cls="ml-1"),
                  href="/docs/pehero-product-tour.pptx",
                  cls="inline-flex items-center gap-2 text-sm text-accent hover:text-ink"),
                Span("·", cls="text-ink-dim mx-3"),
                A(Span(t("tour_readme", lang)), Span("→", cls="ml-1"),
                  href="https://github.com/predictivelabsai/pehero#readme",
                  target="_blank", rel="noopener",
                  cls="inline-flex items-center gap-2 text-sm text-accent hover:text-ink"),
                Span("·", cls="text-ink-dim mx-3"),
                A(Span(t("tour_open_app", lang)), Span("→", cls="ml-1"),
                  href="/app",
                  cls="inline-flex items-center gap-2 text-sm text-ink hover:text-accent"),
                cls="mt-5 flex items-center flex-wrap gap-y-2",
            ),
            cls="max-w-7xl mx-auto px-5 md:px-6 py-14 md:py-20 border-t border-line",
        ),
    )


def _StatCell(value: str, caption: str):
    return Div(
        Span(value, cls="text-2xl md:text-3xl font-medium tracking-tighter text-ink"),
        P(caption, cls="text-ink-muted text-xs md:text-sm mt-1"),
    )


def CategoryPillar(cat: dict, *, sample_count: int = 4, lang: str = "en"):
    agents_in_cat = AGENTS_BY_CATEGORY.get(cat["key"], [])
    sample = agents_in_cat[:sample_count]
    total = len(agents_in_cat)
    return Article(
        Div(
            Span(cat["icon"], cls="text-accent text-2xl"),
            Span(t("agents_count", lang).format(n=total), cls="ml-auto font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
            cls="flex items-center mb-5",
        ),
        Heading(3, category_t(cat["key"], "name", lang), cls="mb-2"),
        P(category_t(cat["key"], "blurb", lang), cls="text-ink-muted text-sm leading-relaxed mb-5"),
        Ul(
            *[Li(
                Div(
                    Span("•", cls="text-accent mr-2"),
                    Span(agent_t(a.slug, "name", lang), cls="text-ink text-sm"),
                    cls="flex items-baseline",
                ),
                cls="mb-1.5",
            ) for a in sample],
            cls="space-y-1",
        ),
        A(t("see_all", lang).format(n=total), href=f"/agents#{cat['key']}", cls="text-accent text-xs font-mono tracking-wider uppercase hover:text-ink mt-6 inline-block"),
        cls="p-7 rounded-2xl bg-bg-elevated border border-line hover:border-accent/50 transition-colors group h-full flex flex-col",
    )


def AgentCard(agent, *, as_link: bool = True, lang: str = "en"):
    inner = Article(
        Div(
            Span(agent.icon, cls="text-accent text-xl"),
            Span(agent.prefix, cls="ml-auto font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
            cls="flex items-center mb-4",
        ),
        H4(agent_t(agent.slug, "name", lang), cls="text-ink font-medium mb-1.5"),
        P(agent_t(agent.slug, "one_liner", lang), cls="text-ink-muted text-sm leading-relaxed"),
        cls="p-6 rounded-2xl bg-bg-elevated border border-line hover:border-accent/50 transition-colors h-full",
    )
    if as_link:
        return A(inner, href=f"/agents/{agent.slug}", cls="block h-full")
    return inner


def CategorySection(cat: dict, lang: str = "en"):
    agents_in_cat = AGENTS_BY_CATEGORY.get(cat["key"], [])
    return Section(
        Div(id=cat["key"]),
        Div(
            Div(
                Eyebrow(category_t(cat["key"], "name", lang)),
                Heading(2, category_t(cat["key"], "blurb", lang), cls="mt-3 max-w-3xl"),
                cls="mb-10",
            ),
            Div(
                *[AgentCard(a, lang=lang) for a in agents_in_cat],
                cls="grid sm:grid-cols-2 lg:grid-cols-3 gap-4",
            ),
            cls="max-w-7xl mx-auto px-5 md:px-6",
        ),
        cls="py-14 md:py-20 border-t border-line",
    )


def CaseStudyStrip(lang: str = "en"):
    cases = [
        {"label": t("case_1_label", lang), "metric": t("case_1_metric", lang), "caption": t("case_1_caption", lang)},
        {"label": t("case_2_label", lang), "metric": t("case_2_metric", lang), "caption": t("case_2_caption", lang)},
        {"label": t("case_3_label", lang), "metric": t("case_3_metric", lang), "caption": t("case_3_caption", lang)},
    ]
    return Section_(
        Eyebrow(t("case_eyebrow", lang)),
        Heading(2, t("case_heading", lang), cls="mt-3 max-w-3xl mb-10"),
        Div(
            *[Article(
                P(c["label"], cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-3"),
                P(c["metric"], cls="text-3xl md:text-4xl font-medium tracking-tighter text-ink mb-3"),
                P(c["caption"], cls="text-ink-muted text-sm leading-relaxed"),
                cls="p-7 rounded-2xl bg-bg-elevated border border-line",
            ) for c in cases],
            cls="grid md:grid-cols-3 gap-4",
        ),
        cls="border-t border-line",
    )


def PENewsSection(lang: str = "en"):
    """PE industry news from RSS feeds — rendered server-side from cache."""
    from utils.news import fetch_news
    import asyncio

    try:
        articles = asyncio.get_event_loop().run_until_complete(fetch_news())
    except RuntimeError:
        articles = asyncio.run(fetch_news())

    pe_sources = {"PEH", "BUY", "PEI"}
    pe_articles = [a for a in articles if a.get("icon") in pe_sources][:8]

    if not pe_articles:
        return Div()

    def _time_ago(iso_str: str) -> str:
        from datetime import datetime, timezone
        try:
            d = datetime.fromisoformat(iso_str)
            now = datetime.now(tz=timezone.utc)
            mins = int((now - d).total_seconds() / 60)
            if mins < 60:
                return f"{mins}m ago"
            hours = mins // 60
            if hours < 24:
                return f"{hours}h ago"
            return f"{hours // 24}d ago"
        except Exception:
            return ""

    def _item(a):
        pub = _time_ago(a.get("published", ""))
        return A(
            Div(
                H4(a["title"],
                   cls="text-ink text-base font-medium leading-snug mb-3 group-hover:text-accent transition-colors"),
                Div(
                    Span(a.get("source", a.get("icon", "")),
                         cls="text-ink-dim text-xs font-mono"),
                    Span("·", cls="text-ink-dim text-xs mx-2") if pub else None,
                    Span(pub, cls="text-ink-dim text-xs") if pub else None,
                    cls="flex items-center flex-wrap",
                ),
                cls="p-5 md:p-6 h-full rounded-2xl bg-bg-elevated border border-line group-hover:border-accent/60 transition-colors",
            ),
            href=a["url"],
            target="_blank",
            rel="noopener",
            cls="block group",
        )

    return Section_(
        Div(
            Div(
                Eyebrow(t("news_title", lang)),
                Heading(2, t("news_pe_heading", lang), cls="mt-4 max-w-3xl"),
                cls="md:flex-1",
            ),
            Div(
                Span(t("news_pe_sources", lang),
                     cls="text-ink-dim text-xs"),
                cls="text-left md:text-right md:max-w-xs mt-4 md:mt-0",
            ),
            cls="mb-10 flex flex-col md:flex-row md:items-end md:justify-between gap-4",
        ),
        Div(
            *[_item(a) for a in pe_articles],
            cls="grid md:grid-cols-2 gap-4",
        ),
        cls="border-t border-line",
    )


def CTASection(*, headline: str | None = None, body: str | None = None,
               cta_label: str | None = None, cta_href: str = "/contact", lang: str = "en"):
    _headline = headline or t("cta_headline", lang)
    _body = body or t("cta_body", lang)
    _cta_label = cta_label or t("cta_book", lang)
    return Section(
        Div(
            Div(
                Eyebrow(t("cta_eyebrow", lang)),
                Heading(2, _headline, cls="mt-3 max-w-3xl"),
                P(_body, cls="mt-5 text-ink-muted text-lg max-w-2xl leading-relaxed"),
                Div(
                    Button_(_cta_label, href=cta_href, primary=True),
                    Button_(t("cta_byod", lang), href="/app", primary=False),
                    cls="mt-8 flex items-center gap-3 flex-wrap",
                ),
                cls="max-w-7xl mx-auto px-5 md:px-6 py-20 md:py-28 relative z-10",
            ),
            Div(cls="absolute inset-0 bg-gradient-to-br from-accent/5 via-transparent to-transparent pointer-events-none"),
            cls="relative border-y border-line bg-bg-elevated/60 overflow-hidden",
        ),
    )
