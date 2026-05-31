"""Chat-UI building blocks."""

from __future__ import annotations

from fasthtml.common import (
    Div, Span, Button, A, P, H1, H2, H3, H4, Ul, Li, NotStr,
    Form, Textarea, Input, Hr, Article, Details, Summary,
)

from agents.registry import AGENTS, AGENTS_BY_CATEGORY, CATEGORIES, AGENTS_BY_SLUG
from utils.i18n import t, agent_t, category_t, js_translations, LANGUAGES
from utils.version import __version__, __version_date__


def message_bubble(role: str, content: str, agent_slug: str | None = None):
    """Render a single persisted message."""
    header = None
    if role == "assistant" and agent_slug:
        agent = AGENTS_BY_SLUG.get(agent_slug)
        label = agent.name if agent else agent_slug
        header = Div(
            Span(agent.icon if agent else "◆", cls="msg-agent-icon"),
            Span(label, cls="msg-agent-label"),
            cls="msg-agent",
        )
    return Div(
        header,
        Div(NotStr(_render_content(content)), cls="msg-bubble"),
        cls=f"msg msg-{role}",
    )


_TABLE_PREVIEW_ROWS = 5


def _render_content(content: str) -> str:
    """Server-side markdown → HTML for persisted messages."""
    import html as _html
    import re

    safe = _html.escape(content)
    # code fences → <pre>
    safe = re.sub(r"```(.*?)```", lambda m: f"<pre>{m.group(1)}</pre>", safe, flags=re.DOTALL)
    # **bold**
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)

    lines = safe.split("\n")
    out = []
    in_list = False
    in_table = False
    is_header = True
    table_row_count = 0
    table_hidden_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if re.fullmatch(r"\|[\s\-:|]+\|", stripped):
                continue
            if not in_table:
                out.append('<table>')
                in_table = True
                is_header = True
                table_row_count = 0
                table_hidden_count = 0
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            tag = "th" if is_header else "td"
            if not is_header:
                table_row_count += 1
            if not is_header and table_row_count > _TABLE_PREVIEW_ROWS:
                out.append('<tr class="table-hidden-row" style="display:none">'
                           + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
                table_hidden_count += 1
            else:
                out.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
            is_header = False
        else:
            if in_table:
                out.append("</table>")
                if table_hidden_count > 0:
                    out.append(
                        f'<button class="table-see-more" onclick="toggleTableRows(this)"'
                        f' data-more="See more ({table_hidden_count})"'
                        f' data-less="See less">'
                        f'See more ({table_hidden_count})</button>'
                    )
                in_table = False
            if stripped.startswith("- "):
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append(f"<li>{stripped[2:]}</li>")
            else:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                if stripped.startswith("### "):
                    out.append(f"<h4>{stripped[4:]}</h4>")
                elif stripped.startswith("## "):
                    out.append(f"<h3>{stripped[3:]}</h3>")
                elif stripped.startswith("# "):
                    out.append(f"<h2>{stripped[2:]}</h2>")
                else:
                    out.append(line if line.strip() else "<br>")
    if in_list:
        out.append("</ul>")
    if in_table:
        out.append("</table>")
        if table_hidden_count > 0:
            out.append(
                f'<button class="table-see-more" onclick="toggleTableRows(this)"'
                f' data-more="See more ({table_hidden_count})"'
                f' data-less="See less">'
                f'See more ({table_hidden_count})</button>'
            )
    return "\n".join(out)


def welcome_hero(lang: str = "en"):
    """Empty-state hero with category chips + example prompts."""
    prompts = [
        ("triage: DR VET veterinary clinic, €4.6M revenue, 76 employees, Vilnius", "deal_triage"),
        ("lbo: 5-year model for Eika Construction at 12% rev growth, 300bps margin exp", "pro_forma_builder"),
        ("ltm: what are the financials of DR VET?", "t12_normalizer"),
        ("memo: draft the IC memo for Baltic transline", "investor_memo"),
        ("comps: healthcare clinics precedent M&A 2022-2024 under €100M EV", "comp_finder"),
        ("scan: logistics companies in Lithuania, €20-100M revenue", "market_scanner"),
    ]
    return Div(
        Div(
            Span("◆", cls="hero-mark"),
            H1(t("chat_welcome_title", lang), cls="welcome-title"),
            P(t("chat_welcome_sub", lang), cls="welcome-sub"),
            cls="welcome-head",
        ),
        Div(
            *[Button(
                Span(AGENTS_BY_SLUG[slug].icon if slug in AGENTS_BY_SLUG else "◆", cls="sugg-icon"),
                Span(text, cls="sugg-text"),
                cls="suggestion-chip",
                onclick=f"fillChat({text!r})",
            ) for text, slug in prompts],
            cls="suggestions",
        ),
        id="welcome-hero",
        cls="welcome-hero",
    )


def agent_browser(lang: str = "en"):
    """Left-pane browser of all 22 agents, grouped by category."""
    from urllib.parse import quote
    groups = []
    for cat in CATEGORIES:
        agents = AGENTS_BY_CATEGORY.get(cat["key"], [])
        links = [
            A(
                Span(a.icon, cls="aitem-icon"),
                Span(agent_t(a.slug, "name", lang), cls="aitem-name"),
                Span(a.prefix, cls="aitem-prefix"),
                cls="agent-item",
                href=f"/app?prefill={quote(a.prefix + ' ')}",
                title=agent_t(a.slug, "one_liner", lang),
            )
            for a in agents
        ]
        groups.append(Details(
            Summary(
                Span(cat["icon"], cls="cat-icon"),
                Span(category_t(cat["key"], "name", lang), cls="cat-name"),
                Span(f"{len(agents)}", cls="cat-count"),
                Span("▸", cls="cat-arrow"),
                cls="cat-toggle",
            ),
            Div(*links, cls="agent-list"),
            cls="agent-group",
        ))
    return Div(*groups, cls="agent-browser")


def sessions_list(sessions: list[dict], current_sid: str = "", lang: str = "en"):
    """Renders the left-pane session history."""
    if not sessions:
        return Div(P(t("chat_no_sessions", lang), cls="sessions-empty"))
    items = []
    for s in sessions:
        is_active = str(s["id"]) == str(current_sid)
        title = s.get("title") or t("chat_untitled", lang)
        items.append(A(
            Span(cls=f"chat-dot{' active' if is_active else ''}"),
            Span(title[:48] + ("…" if len(title) > 48 else ""), cls="chat-session-title"),
            cls=f"chat-history-item{' active' if is_active else ''}",
            href=f"/app?sid={s['id']}",
        ))
    return Div(*items, cls="session-list")


def _config_section(current_currency: str = "EUR", lang: str = "en"):
    """Configuration: currency selector (EUR default) + Integrations submenu."""
    from utils.session import CURRENCIES, SYMBOLS
    from utils.config import settings

    pills = []
    for c in CURRENCIES:
        active = c == current_currency
        pills.append(Button(
            Span(SYMBOLS[c], cls="cfg-sym"),
            Span(c, cls="cfg-code"),
            cls=f"cfg-chip{' active' if active else ''}",
            hx_post="/app/config",
            hx_vals=f'{{"currency":"{c}"}}',
            hx_swap="none",
        ))

    s = settings()
    integrations = [
        ("",   "CRM",     "Pipedrive",  bool(s.pipedrive_api_token), s.pipedrive_domain or None),
        ("EE", "Estonia", "Äriregister", bool(s.ee_ari_api_key), "public endpoint"),
        ("EE", "Estonia", "EMTA (tax)",  bool(s.ee_emta_api_key), None),
        ("LT", "Lithuania", "Registrų centras", bool(s.lt_cr_api_key), "public atviri duomenys"),
        ("LT", "Lithuania", "VMI (tax)",  bool(s.lt_vmi_api_key), None),
        ("LV", "Latvia",   "UR",         bool(s.lv_ur_api_key), None),
        ("LV", "Latvia",   "VID (tax)",  bool(s.lv_vid_api_key), None),
        ("",   "Web",      "Tavily",     bool(s.tavily_api_key), "default"),
        ("",   "Web",      "EXA",        bool(s.exa_api_key), "fallback"),
    ]
    integration_rows = []
    for flag, country, name, connected, note in integrations:
        status_cls = "ok" if connected else (" fallback" if note else " off")
        dot = Span(cls=f"integration-dot {'ok' if connected else ''}")
        label_text = f"{flag} {name}" if flag else name
        note_el = Span(note, cls="integration-note") if note else Span("", cls="integration-note")
        row_content = [
            dot,
            Span(label_text, cls="integration-name"),
            note_el,
            Span("connected" if connected else "off",
                 cls=f"integration-status{' ok' if connected else ''}"),
        ]
        if name == "Pipedrive" and connected:
            integration_rows.append(A(
                *row_content,
                href="/app/integrations",
                cls="integration-row integration-link",
            ))
        else:
            integration_rows.append(Div(
                *row_content,
                cls="integration-row",
            ))

    return Div(
        # Currency block
        Div(Span(t("cfg_currency", lang), cls="cfg-label"),
            Span(t("cfg_currency_help", lang), cls="cfg-help"),
            cls="cfg-row"),
        Div(*pills, cls="cfg-pills"),
        # Integrations submenu
        Details(
            Summary(
                Span("▸", cls="cfg-arrow"),
                Span(t("cfg_integrations", lang), cls="cfg-label"),
                Span(f"{sum(1 for i in integrations if i[3])}/{len(integrations)}",
                     cls="cfg-count"),
                cls="cfg-integrations-toggle",
            ),
            Div(*integration_rows, cls="integration-list"),
            cls="config-integrations",
        ),
        cls="config-section",
    )


def _bottom_nav(current_path: str = "", lang: str = "en"):
    items = [
        (t("chat_pipeline", lang),     "/app/pipeline",     "◆"),
        (t("chat_companies", lang),    "/app/companies",    "⊞"),
        (t("dr_title", lang),          "/app/dataroom",     "📁"),
        (t("chat_instructions", lang), "/app/instructions", "✎"),
        (t("chat_analytics", lang),    "/app/analytics",    "∑"),
        (t("val_title", lang),          "/app/valuation",    "◎"),
    ]
    links = []
    for label, href, icon in items:
        active = current_path.startswith(href)
        links.append(A(
            Span(icon, cls="bottom-nav-icon"),
            Span(label, cls="bottom-nav-label"),
            href=href,
            cls=f"bottom-nav-link{' active' if active else ''}",
        ))

    int_active = current_path.startswith("/app/integrations")
    int_subs = [
        ("Pipedrive",           "/app/integrations#pipedrive",  "⇄"),
        ("Teatmik (EE)",        "/app/integrations#ee",         "🇪🇪"),
        ("Rekvizitai (LT)",     "/app/integrations#lt",         "🇱🇹"),
        ("data.gov.lv (LV)",    "/app/integrations#lv",         "🇱🇻"),
        ("ONRC + ANAF (RO)",    "/app/integrations#ro",         "🇷🇴"),
        ("KRS (PL)",            "/app/integrations#pl",         "🇵🇱"),
    ]
    sub_links = [A(
        Span(ic, cls="bottom-nav-icon"),
        Span(lb, cls="bottom-nav-label"),
        href=hr, cls="bottom-nav-link sub",
    ) for lb, hr, ic in int_subs]

    integrations_menu = Details(
        Summary(A(
            Span("⇄", cls="bottom-nav-icon"),
            Span("Integrations", cls="bottom-nav-label"),
            href="/app/integrations",
            cls=f"bottom-nav-link{' active' if int_active else ''}",
        )),
        Div(*sub_links, cls="bottom-nav-sub"),
        open=int_active,
        cls="bottom-nav-details",
    )
    links.append(integrations_menu)

    return Div(*links, cls="bottom-nav")


def left_pane(*, user_email: str | None, sessions: list[dict], current_sid: str = "",
              current_path: str = "", current_currency: str = "EUR", lang: str = "en"):
    """The full left pane composition."""
    signin_block = (
        Div(
            Span("◇", cls="user-mark"),
            Span(user_email, cls="user-email"),
            Button(t("chat_sign_out", lang), cls="sign-out-btn",
                   hx_post="/app/auth/signout", hx_swap="none"),
            cls="signed-in-bar",
        )
        if user_email else
        Button(Span("◇", cls="user-mark"), Span(t("chat_sign_in", lang), cls="sign-in-text"),
               cls="sign-in-btn", onclick="showSignIn()")
    )

    return Div(
        Div(
            A(Span("◆", cls="brand-mark"), Span("PEHero"),
              href="/", cls="brand-link"),
            Span(t("chat_beta", lang), cls="brand-badge"),
            Span(f"v{__version__}", cls="brand-version"),
            cls="left-header",
        ),
        Div(
            Div(
                A(t("chat_new", lang), cls="new-chat-btn", href="/app"),
                Div(Span(t("chat_sessions", lang), cls="section-label")),
                sessions_list(sessions, current_sid, lang=lang),
                cls="sessions-section",
            ),
            Hr(cls="left-hr"),
            Div(
                Div(Span(t("chat_agents", lang), cls="section-label")),
                agent_browser(lang=lang),
                cls="agents-section",
            ),
            Hr(cls="left-hr"),
            Div(
                Div(Span(t("chat_workspace", lang), cls="section-label")),
                _bottom_nav(current_path, lang=lang),
                cls="workspace-section",
            ),
            Hr(cls="left-hr"),
            Details(
                Summary(A(
                    Span("?", cls="bottom-nav-icon"),
                    Span(t("help_title", lang), cls="bottom-nav-label"),
                    href="/app/help",
                    cls=f"bottom-nav-link{' active' if current_path.startswith('/app/help') or current_path.startswith('/app/training') else ''}",
                )),
                Div(
                    A(Span("📖", cls="bottom-nav-icon"),
                      Span("User Guide", cls="bottom-nav-label"),
                      href="/app/help", cls="bottom-nav-link sub"),
                    A(Span("🏈", cls="bottom-nav-icon"),
                      Span("Training", cls="bottom-nav-label"),
                      href="/app/training", cls="bottom-nav-link sub"),
                    cls="bottom-nav-sub",
                ),
                open=current_path.startswith("/app/help") or current_path.startswith("/app/training"),
                cls="bottom-nav-details",
            ),
            Hr(cls="left-hr"),
            Div(
                Div(Span(t("chat_config", lang), cls="section-label")),
                _config_section(current_currency=current_currency, lang=lang),
                cls="config-wrap",
            ),
            cls="left-body",
        ),
        Div(signin_block, cls="left-footer"),
        cls="left-pane", id="left-pane",
    )


def sample_cards(current_agent_slug: str | None = None, lang: str = "en"):
    """Gemini-style contextual sample-question cards below the chat input.

    Renders the current agent's example_prompts (or a curated 6-pack when no
    agent is bound yet). Client-side, `updateSampleCards(slug)` refreshes the
    list whenever the user types a prefix or the router picks a new agent.
    """
    if current_agent_slug and current_agent_slug in AGENTS_BY_SLUG:
        agent = AGENTS_BY_SLUG[current_agent_slug]
        prompts = list(agent.example_prompts[:6])
        label = t("js_try_with", lang) + agent_t(agent.slug, "name", lang)
    else:
        prompts = [
            "triage: DR VET veterinary clinic, €4.6M revenue, Vilnius",
            "lbo: 5-year model for Eika Construction at 12% rev growth",
            "ltm: what are the financials of DR VET?",
            "memo: draft the IC memo for Baltic transline",
            "vdr: audit the data room for Hegelmann transporte",
            "crm: top 10 LPs to reach out to for Fund V",
        ]
        label = t("js_try_prompt", lang)

    chips = [
        Button(
            Span(p, cls="sample-card-text"),
            cls="sample-card",
            onclick=f"fillChat({p!r}); sendMessage(null);",
            title=p,
        )
        for p in prompts
    ]
    return Div(
        Div(
            Span(label, cls="sample-cards-label"),
            id="sample-cards-label",
        ),
        Div(*chips, id="sample-cards-row", cls="sample-cards-row"),
        id="sample-cards",
        cls="sample-cards",
    )


def center_pane(*, messages: list[dict], current_agent_slug: str | None = None,
                readonly: bool = False, lang: str = "en"):
    has_messages = bool(messages)
    bubbles = [message_bubble(m["role"], m["content"], m.get("agent_slug")) for m in messages]

    input_placeholder = t("chat_placeholder", lang)

    # Embed all agents' example_prompts as JSON for the client so we can
    # refresh sample cards without a round-trip whenever the router picks a
    # different slug.
    import json
    prompts_lookup = {a.slug: list(a.example_prompts[:6]) for a in AGENTS}
    names_lookup = {a.slug: agent_t(a.slug, "name", lang) for a in AGENTS}

    # Language dropdown for the header — only the active flag is visible
    current_flag = LANGUAGES.get(lang, LANGUAGES["en"])["flag"]
    lang_options = [
        Button(
            Span(info["flag"], cls="lang-dd-flag"),
            Span(info["native"], cls="lang-dd-label"),
            cls=f"lang-dd-item{' active' if code == lang else ''}",
            hx_post="/app/config",
            hx_vals=f'{{"lang":"{code}"}}',
            hx_swap="none",
        )
        for code, info in LANGUAGES.items()
    ]
    lang_dropdown = Div(
        Button(current_flag, cls="lang-trigger", onclick="toggleLangDropdown(event)"),
        Div(*lang_options, cls="lang-dd-menu", id="lang-dd-menu"),
        cls="lang-dropdown",
    )

    return Div(
        Div(
            Div(
                Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                Span("PEHero", cls="chat-header-title"),
                Span("·", cls="chat-header-dot"),
                Span(
                    agent_t(current_agent_slug, "name", lang) if current_agent_slug and current_agent_slug in AGENTS_BY_SLUG else t("chat_auto_routed", lang),
                    cls="chat-header-agent",
                    id="current-agent-label",
                ),
                cls="chat-header-left",
            ),
            Div(
                lang_dropdown,
                Button(t("chat_copy", lang), id="copy-chat-btn", cls="chat-action-btn",
                       onclick="copyChat()"),
                Button(t("chat_share", lang), id="share-chat-btn", cls="chat-action-btn",
                       onclick="shareChat()"),
                Button(t("news_title", lang), id="news-btn", cls="news-toggle-btn active",
                       onclick="toggleNewsPane()"),
                cls="chat-header-actions",
            ),
            cls="chat-header",
        ),
        Div(*bubbles, id="messages", cls="messages"),
        welcome_hero(lang=lang) if not has_messages else Div(id="welcome-hero", style="display:none"),
        *([] if readonly else [
            Form(
                Textarea(
                    id="chat-input", name="msg",
                    cls="chat-textarea",
                    placeholder=input_placeholder,
                    rows="2",
                    onkeydown="handleKey(event)",
                    oninput="autoResize(this); onInputChange(this)",
                ),
                Button(t("chat_send", lang), type="submit", cls="chat-send", id="send-btn"),
                id="chat-form",
                cls="chat-form",
                onsubmit="sendMessage(event)",
            ),
            sample_cards(current_agent_slug, lang=lang),
        ]),
        # JSON blobs the client reads
        NotStr(f'<script id="agent-prompts-data" type="application/json">{json.dumps(prompts_lookup)}</script>'),
        NotStr(f'<script id="agent-names-data" type="application/json">{json.dumps(names_lookup)}</script>'),
        NotStr(f'<script id="i18n-data" type="application/json">{json.dumps(js_translations(lang))}</script>'),
        cls="center-pane",
    )


def right_pane(lang: str = "en"):
    """News feed pane — loaded via HTMX."""
    return Div(
        Div(
            Div(H3(t("news_title", lang), cls="right-title"),
                Span("", id="news-subtitle", cls="right-subtitle"),
                cls="right-header-left"),
            Button("✕", cls="right-close", onclick="toggleNewsPane()"),
            cls="right-header",
        ),
        Div(
            Div(
                Div("◌", cls="news-loading-icon"),
                P(t("news_loading", lang), cls="news-loading-text"),
                id="news-loading",
                cls="news-loading htmx-indicator",
            ),
            Div(id="news-body", cls="news-body",
                hx_get="/app/news/html",
                hx_trigger="load, every 1800s",
                hx_swap="innerHTML",
                hx_indicator="#news-loading"),
            cls="right-body",
        ),
        id="right-pane", cls="right-pane open",
    )


COPILOT_PROMPTS: dict[str, list[str]] = {
    "Pipeline": [
        "Which companies should I move to screening?",
        "Show me healthcare deals above €10M revenue",
        "What's the average EBITDA margin across the pipeline?",
        "Draft an outreach email for the top logistics company",
    ],
    "Companies": [
        "Top 10 companies by revenue in healthcare",
        "Find software companies in Vilnius above €5M revenue",
        "Compare EBITDA margins across sectors",
        "Which companies have the highest growth rate?",
    ],
    "Analytics": [
        "Revenue distribution by sector",
        "Company count by deal stage",
        "Average EBITDA margin by sector",
        "Top 20 companies by enterprise value",
    ],
    "Valuation": [
        "If I bought this company, how do I increase value?",
        "What's a fair EV/EBITDA multiple for this sector?",
        "Build a 5-year LBO model at 12% revenue growth",
        "What are the key risks for this acquisition?",
    ],
    "Data Room": [
        "What documents are missing for due diligence?",
        "Summarize the uploaded CIM",
        "Are there any red flags in the legal docs?",
        "What's in the data room for this company?",
    ],
    "Instructions": [
        "How should I customize the deal triage prompt?",
        "What does the LBO agent do?",
        "Help me write a system prompt for sector-specific analysis",
        "Which agent handles value creation planning?",
    ],
    "Help": [
        "How do I use the valuation simulator?",
        "What agents are available for due diligence?",
        "How does the pipeline kanban work?",
        "How do I upload documents to the data room?",
    ],
    "Integrations": [
        "Sync all Lithuanian companies to Pipedrive",
        "Which companies are not yet synced to Pipedrive?",
        "Draft an outreach sequence for the top healthcare company",
        "Show LP prospects that haven't been touched in 30 days",
    ],
}


def copilot_pane(*, page_name: str, page_context: dict | None = None,
                 company_slug: str = "", lang: str = "en"):
    """Right-pane copilot chat — page-scoped AI assistant."""
    import json as _json
    context_json = _json.dumps(page_context or {})

    prompts = COPILOT_PROMPTS.get(page_name, COPILOT_PROMPTS.get("Pipeline", []))
    sample_chips = [
        Button(
            Span(p, cls="copilot-chip-text"),
            cls="copilot-chip",
            onclick=f"copilotFillAndSend({p!r})",
        )
        for p in prompts
    ]

    return Div(
        Div(
            Div(H3("Copilot", cls="right-title"),
                Span(page_name, id="copilot-subtitle", cls="right-subtitle"),
                cls="right-header-left"),
            Button("»", cls="right-close copilot-collapse", onclick="toggleCopilotPane()"),
            cls="right-header",
        ),
        Div(
            Div(id="copilot-messages", cls="copilot-messages"),
            cls="right-body copilot-body",
        ),
        Form(
            Input(type="hidden", id="copilot-context", value=context_json),
            Input(type="hidden", id="copilot-page", value=page_name),
            Input(type="hidden", id="copilot-company", value=company_slug),
            Div(
                Textarea(
                    id="copilot-input", name="msg",
                    cls="copilot-textarea",
                    placeholder=f"Ask about {page_name.lower()}...",
                    rows="2",
                    onkeydown="copilotHandleKey(event)",
                ),
                Button("Send", type="submit", cls="copilot-send", id="copilot-send-btn"),
                cls="copilot-input-row",
            ),
            Div(*sample_chips, id="copilot-chips", cls="copilot-chips"),
            id="copilot-form",
            cls="copilot-form",
            onsubmit="copilotSend(event)",
        ),
        id="right-pane", cls="right-pane copilot-pane open",
    )


def copilot_toggle_btn(lang: str = "en"):
    """Toggle button for the copilot pane, used in workspace page headers."""
    return Button("«", id="copilot-btn", cls="copilot-expand-btn",
                  onclick="toggleCopilotPane()", title="Open Copilot")


def signin_overlay(lang: str = "en"):
    return Div(
        Form(
            H3(t("chat_signin_title", lang)),
            P(t("chat_signin_sub", lang), cls="signin-sub"),
            Input(type="email", name="email", id="signin-email", placeholder="you@firm.com"),
            Button(t("chat_signin_btn", lang), type="submit"),
            cls="signin-box",
            hx_post="/app/auth/signin",
            hx_swap="none",
        ),
        cls="signin-overlay", id="signin-overlay",
        onclick="if(event.target===this)this.classList.remove('visible')",
    )
