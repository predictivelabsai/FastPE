"""Chat-UI building blocks."""

from __future__ import annotations

from fasthtml.common import (
    Div, Span, Button, A, P, H1, H2, H3, H4, Ul, Li, NotStr,
    Form, Textarea, Input, Hr, Article,
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
        ("triage: DR VET veterinary clinic, €3.8M revenue, 76 employees, Vilnius", "deal_triage"),
        ("lbo: 5-year model for Kardiolita at 12% rev growth, 300bps margin exp", "pro_forma_builder"),
        ("ltm: what are the financials of DR VET?", "t12_normalizer"),
        ("memo: draft the IC memo for Kardiolita", "investor_memo"),
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
    groups = []
    for cat in CATEGORIES:
        agents = AGENTS_BY_CATEGORY.get(cat["key"], [])
        buttons = [
            Button(
                Span(a.icon, cls="aitem-icon"),
                Span(agent_t(a.slug, "name", lang), cls="aitem-name"),
                Span(a.prefix, cls="aitem-prefix"),
                cls="agent-item",
                onclick=f"fillChat({a.prefix + ' '!r})",
                title=agent_t(a.slug, "one_liner", lang),
            )
            for a in agents
        ]
        groups.append(Div(
            Button(
                Span(cat["icon"], cls="cat-icon"),
                Span(category_t(cat["key"], "name", lang), cls="cat-name"),
                Span(f"{len(agents)}", cls="cat-count"),
                Span("▸", cls="cat-arrow"),
                cls="cat-toggle",
                onclick=f"toggleGroup('cat-{cat['key']}')",
                id=f"btn-cat-{cat['key']}",
            ),
            Div(*buttons, cls="agent-list", id=f"cat-{cat['key']}"),
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
        items.append(Button(
            Span(cls=f"chat-dot{' active' if is_active else ''}"),
            Span(title[:48] + ("…" if len(title) > 48 else ""), cls="chat-session-title"),
            cls=f"chat-history-item{' active' if is_active else ''}",
            onclick=f"window.location.href='/app?sid={s['id']}'",
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
            onclick=f"setCurrency({c!r})",
        ))

    s = settings()
    integrations = [
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
        integration_rows.append(Div(
            dot,
            Span(label_text, cls="integration-name"),
            note_el,
            Span("connected" if connected else "off",
                 cls=f"integration-status{' ok' if connected else ''}"),
            cls="integration-row",
        ))

    return Div(
        # Currency block
        Div(Span(t("cfg_currency", lang), cls="cfg-label"),
            Span(t("cfg_currency_help", lang), cls="cfg-help"),
            cls="cfg-row"),
        Div(*pills, cls="cfg-pills"),
        # Integrations submenu
        Button(
            Span("▸", cls="cfg-arrow"),
            Span(t("cfg_integrations", lang), cls="cfg-label"),
            Span(f"{sum(1 for i in integrations if i[3])}/{len(integrations)}",
                 cls="cfg-count"),
            cls="cfg-integrations-toggle",
            onclick="toggleGroup('integrations-list')",
            id="btn-integrations-list",
        ),
        Div(*integration_rows, cls="integration-list", id="integrations-list"),
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
    return Div(*links, cls="bottom-nav")


def left_pane(*, user_email: str | None, sessions: list[dict], current_sid: str = "",
              current_path: str = "", current_currency: str = "EUR", lang: str = "en"):
    """The full left pane composition."""
    signin_block = (
        Div(
            Span("◇", cls="user-mark"),
            Span(user_email, cls="user-email"),
            Button(t("chat_sign_out", lang), cls="sign-out-btn", onclick="signOut()"),
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
                Button(t("chat_new", lang), cls="new-chat-btn", onclick="newChat()"),
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
            Div(
                A(
                    Span("?", cls="bottom-nav-icon"),
                    Span(t("help_title", lang), cls="bottom-nav-label"),
                    href="/app/help",
                    cls=f"bottom-nav-link{' active' if current_path == '/app/help' else ''}",
                ),
                cls="help-link",
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
            "triage: DR VET veterinary clinic, €3.8M revenue, Vilnius",
            "lbo: 5-year model for Kardiolita at 12% rev growth",
            "ltm: what are the financials of DR VET?",
            "memo: draft the IC memo for Kardiolita",
            "vdr: audit the data room for Northway",
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
            onclick=f"setLang({code!r})",
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
    """News feed pane — populated via /app/news JSON endpoint."""
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
                cls="news-loading",
            ),
            Div(id="news-body", cls="news-body", style="display:none"),
            cls="right-body",
        ),
        id="right-pane", cls="right-pane open",
    )


def signin_overlay(lang: str = "en"):
    return Div(
        Div(
            H3(t("chat_signin_title", lang)),
            P(t("chat_signin_sub", lang), cls="signin-sub"),
            Input(type="email", id="signin-email", placeholder="you@firm.com",
                  onkeydown="if(event.key==='Enter')doSignIn()"),
            Button(t("chat_signin_btn", lang), onclick="doSignIn()"),
            cls="signin-box",
        ),
        cls="signin-overlay", id="signin-overlay",
        onclick="if(event.target===this)this.classList.remove('visible')",
    )
