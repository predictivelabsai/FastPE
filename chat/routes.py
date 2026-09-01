"""Chat product routes — 3-pane UI + SSE streaming + auth + sessions."""

from __future__ import annotations

import html
import json
import logging
import re
import uuid
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from starlette.requests import Request
from urllib.parse import urlparse
from starlette.responses import StreamingResponse, JSONResponse, RedirectResponse, Response

from fasthtml.common import Div, Span, A, H1, P

from app import rt
from agents import router as agent_router
from agents.registry import AGENTS_BY_SLUG, by_slug
from chat.layout import chat_page
from chat import sse
from db import connect, fetch_all, fetch_one
from landing.components import page
from utils.llm import default_llm
from utils.session import (get_user_email, set_user_email, clear_user,
                           get_user_id, set_user_id,
                           get_currency, set_currency, SYMBOLS)
from utils.i18n import get_lang, set_lang, LANGUAGES

log = logging.getLogger(__name__)


_MARKDOWN_TABLE_SEPARATOR = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")


def _plain_artifact_text(value: object, limit: int = 360) -> str:
    """Turn untrusted search-result Markdown/HTML into compact display text."""
    text = html.unescape(str(value or ""))
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text,
                  flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)

    clean_lines = []
    for line in text.replace("```", "").splitlines():
        if _MARKDOWN_TABLE_SEPARATOR.fullmatch(line):
            continue
        line = re.sub(r"^\s{0,3}(?:#{1,6}|>|[-*+]\s|\d+[.)]\s)+", "", line)
        line = line.replace("|", " · ")
        clean_lines.append(line)

    text = " ".join(clean_lines)
    text = re.sub(r"[*_~`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"
    return text


def _public_artifact(payload: dict) -> dict:
    """Return the browser-safe representation of a structured artifact."""
    if payload.get("kind") != "citations" or not isinstance(payload.get("items"), list):
        return payload

    public = dict(payload)
    public_items = []
    for item in payload["items"]:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        if not re.match(r"^https?://", url, re.IGNORECASE):
            url = ""
        public_items.append({
            **item,
            "url": url,
            "snippet": _plain_artifact_text(item.get("snippet")),
        })
    public["items"] = public_items
    return public


# ── helpers ──────────────────────────────────────────────────────────

def _ensure_user(sess) -> tuple[int | None, str | None]:
    email = get_user_email(sess)
    if not email:
        return None, None
    uid = get_user_id(sess)
    if uid:
        return uid, email
    # upsert user and cache id
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO pehero.users (email) VALUES (%s) "
            "ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email "
            "RETURNING id",
            (email,),
        )
        uid = cur.fetchone()[0]
        conn.commit()
    set_user_id(sess, uid)
    return uid, email


def _ensure_session(user_id: int, sid: str | int | None, first_message: str | None = None) -> int:
    if sid:
        try:
            sid_int = int(sid)
        except (TypeError, ValueError):
            sid_int = 0
        if sid_int:
            row = fetch_one("SELECT id FROM pehero.chat_sessions WHERE id = %s AND user_id = %s",
                            (sid_int, user_id))
            if row:
                return sid_int

    title = (first_message or "New chat")[:80] if first_message else "New chat"
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO pehero.chat_sessions (user_id, title) VALUES (%s, %s) RETURNING id",
            (user_id, title),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
    return new_id


def _list_sessions(user_id: int, limit: int = 30) -> list[dict]:
    return fetch_all(
        "SELECT id, title, agent_slug, updated_at "
        "FROM pehero.chat_sessions WHERE user_id = %s "
        "ORDER BY updated_at DESC LIMIT %s",
        (user_id, limit),
    )


def _session_messages(session_id: int) -> list[dict]:
    return fetch_all(
        "SELECT role, content, agent_slug FROM pehero.chat_messages "
        "WHERE session_id = %s ORDER BY id ASC",
        (session_id,),
    )


def _persist_message(session_id: int, role: str, content: str,
                     agent_slug: str | None = None, tool_calls: list | None = None):
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO pehero.chat_messages (session_id, role, content, agent_slug, tool_calls) "
            "VALUES (%s, %s, %s, %s, %s::jsonb)",
            (session_id, role, content, agent_slug,
             json.dumps(tool_calls) if tool_calls else None),
        )
        cur.execute(
            "UPDATE pehero.chat_sessions SET updated_at = now() WHERE id = %s",
            (session_id,),
        )
        conn.commit()


# ── GET /app ─────────────────────────────────────────────────────────

@rt("/app")
def app_home(sess, sid: str = "", prefill: str = ""):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    messages: list[dict] = []
    current_agent = None
    if uid and sid:
        try:
            sid_int = int(sid)
            row = fetch_one("SELECT id, agent_slug FROM pehero.chat_sessions "
                            "WHERE id = %s AND user_id = %s", (sid_int, uid))
            if row:
                messages = _session_messages(sid_int)
                current_agent = row.get("agent_slug")
        except (TypeError, ValueError):
            pass

    return chat_page(
        user_email=email,
        sessions=sessions,
        current_sid=str(sid) if sid else "",
        messages=messages,
        current_agent_slug=current_agent,
        current_currency=get_currency(sess),
        lang=get_lang(sess),
        prefill=prefill,
    )


# ── POST /app/chat — SSE ─────────────────────────────────────────────

@rt("/app/chat", methods=["POST"])
async def chat_stream(request: Request):
    sess = request.session
    form = await request.form()
    user_msg = (form.get("msg") or "").strip()
    sid_str = form.get("sid") or ""
    context_raw = (form.get("context") or "").strip()

    if not user_msg:
        return JSONResponse({"error": "empty message"}, status_code=400)

    uid, email = _ensure_user(sess)
    if not uid:
        # Create a transient "guest" user on first message so signed-out users can try.
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pehero.users (email) VALUES (%s) "
                "ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email RETURNING id",
                (f"guest+{id(sess):x}@pehero.local",),
            )
            uid = cur.fetchone()[0]
            conn.commit()
        set_user_id(sess, uid)

    session_id = _ensure_session(uid, sid_str, first_message=user_msg)

    # If the message is purely about switching language, stay on the current agent
    from agents.router import is_language_intent
    if is_language_intent(user_msg):
        row = fetch_one("SELECT agent_slug FROM pehero.chat_sessions WHERE id = %s", (session_id,))
        agent_slug = (row.get("agent_slug") if row else None) or agent_router.route(user_msg)
    else:
        agent_slug = agent_router.route(user_msg)
    spec = by_slug(agent_slug)

    # Persist the user message upfront
    _persist_message(session_id, "user", user_msg)

    history = _session_messages(session_id)[:-1]  # exclude the one we just inserted
    stripped_msg = agent_router.strip_prefix(user_msg)

    # Prepend a short currency directive so any specialist defaults to the
    # user's preferred currency when formatting figures. Does not affect the
    # stored user message.
    currency = get_currency(sess)
    lang = get_lang(sess)
    lang_info = LANGUAGES.get(lang, LANGUAGES["en"])

    lang_directive = ""
    if lang != "en":
        lang_directive = (
            f"\nUser language: {lang} ({lang_info['name']}). "
            f"Respond in {lang_info['name']}. All agent output including emails, "
            f"memos, LOIs, and analysis should be in {lang_info['name']} unless "
            f"the user explicitly requests otherwise."
        )

    currency_directive = (
        f"[Session preferences] Reporting currency: {currency} "
        f"({SYMBOLS.get(currency, '€')}). Format all monetary figures in "
        f"{currency} unless the user explicitly overrides in this turn."
        f"{lang_directive}"
    )

    async def event_stream():
        yield sse.event("session", {"sid": session_id})
        yield sse.event(sse.AGENT_ROUTE, {
            "slug": agent_slug,
            "agent": spec.name if spec else agent_slug,
            "icon": spec.icon if spec else "◆",
        })

        # Build LangChain messages
        lc_messages = [SystemMessage(content=currency_directive)]
        if context_raw:
            lc_messages.append(SystemMessage(content=f"[Page context] {context_raw}"))
        for h in history[-20:]:
            if h["role"] == "user":
                lc_messages.append(HumanMessage(content=h["content"]))
            elif h["role"] == "assistant":
                lc_messages.append(AIMessage(content=h["content"]))
        lc_messages.append(HumanMessage(content=stripped_msg))

        accumulated = []
        tool_calls_log = []

        try:
            from agents.base import cached_agent
            try:
                graph = cached_agent(agent_slug)
            except Exception as e:  # noqa: BLE001
                log.warning("agent %s not yet implemented — falling back to generalist: %s", agent_slug, e)
                from agents.generalist import build as build_generalist
                graph = build_generalist()

            async for event in graph.astream_events({"messages": lc_messages}, version="v2"):
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    if chunk and hasattr(chunk, "content") and isinstance(chunk.content, str) and chunk.content:
                        if not getattr(chunk, "tool_call_chunks", None):
                            accumulated.append(chunk.content)
                            yield sse.event(sse.TOKEN, {"text": chunk.content})
                elif kind == "on_tool_start":
                    name = event.get("name", "unknown")
                    args = event["data"].get("input", {})
                    tool_calls_log.append({"name": name, "args": args})
                    # Tool arguments stay in the server-side audit log.  The UI only
                    # needs a status label and must never receive raw payloads.
                    yield sse.event(sse.TOOL_START, {"name": name})
                elif kind == "on_tool_end":
                    name = event.get("name", "unknown")
                    raw = event["data"].get("output", "")
                    output = getattr(raw, "content", None) or (raw if isinstance(raw, str) else str(raw))
                    yield sse.event(sse.TOOL_END, {"name": name})

                    # If the tool returned a structured artifact descriptor, forward it.
                    if isinstance(output, str) and output.startswith("__ARTIFACT__"):
                        try:
                            payload = json.loads(output[len("__ARTIFACT__"):])
                            yield sse.event(sse.ARTIFACT, _public_artifact(payload))
                        except Exception:
                            pass
        except Exception as e:  # noqa: BLE001
            log.exception("chat stream failed")
            yield sse.event(sse.ERROR, {"message": str(e)})

        final = "".join(accumulated) or "(no response)"
        _persist_message(session_id, "assistant", final, agent_slug=agent_slug,
                         tool_calls=tool_calls_log or None)
        # Update session agent_slug to the last-used one
        with connect() as conn, conn.cursor() as cur:
            cur.execute("UPDATE pehero.chat_sessions SET agent_slug = %s WHERE id = %s",
                        (agent_slug, session_id))
            conn.commit()
        yield sse.event(sse.DONE, {"slug": agent_slug, "tools": len(tool_calls_log)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Auth ─────────────────────────────────────────────────────────────

def _htmx_redirect(request: Request, fallback: str = "/app") -> Response:
    """Return an HX-Redirect response that sends the browser back to the current page."""
    current_url = request.headers.get("HX-Current-URL", fallback)
    path = urlparse(current_url).path or fallback
    return Response("", headers={"HX-Redirect": path})


@rt("/app/auth/signin", methods=["POST"])
async def signin(request: Request):
    """Legacy email-only signin — kept for backward compatibility."""
    form = await request.form()
    email = (form.get("email") or "").strip().lower()
    if "@" not in email:
        if request.headers.get("HX-Request"):
            return Response("Invalid email", status_code=400)
        return JSONResponse({"ok": False, "error": "invalid email"}, status_code=400)
    set_user_email(request.session, email)
    _ensure_user(request.session)
    if request.headers.get("HX-Request"):
        return _htmx_redirect(request)
    return JSONResponse({"ok": True, "email": email})


@rt("/app/auth/signout", methods=["POST"])
async def signout(request: Request):
    clear_user(request.session)
    if request.headers.get("HX-Request"):
        return Response("", headers={"HX-Redirect": "/app"})
    return JSONResponse({"ok": True})


# ── Config (currency, etc.) ──────────────────────────────────────────

@rt("/app/config", methods=["POST"])
async def app_config(request: Request):
    form = await request.form()
    currency = (form.get("currency") or "").strip()
    if currency:
        current = set_currency(request.session, currency)
    else:
        current = get_currency(request.session)
    lang_code = (form.get("lang") or "").strip()
    if lang_code:
        set_lang(request.session, lang_code)
    if request.headers.get("HX-Request"):
        return _htmx_redirect(request)
    current_lang = get_lang(request.session)
    return JSONResponse({"ok": True, "currency": current, "symbol": SYMBOLS.get(current, "€"),
                         "lang": current_lang})


# ── Share links ────────────────────────────────────────────────────

@rt("/app/share", methods=["POST"])
async def share_session(request: Request):
    sess = request.session
    form = await request.form()
    sid = form.get("sid") or ""
    uid, _ = _ensure_user(sess)
    if not uid or not sid:
        return JSONResponse({"ok": False, "error": "not authenticated"}, status_code=401)
    try:
        sid_int = int(sid)
    except (TypeError, ValueError):
        return JSONResponse({"ok": False, "error": "bad sid"}, status_code=400)
    row = fetch_one(
        "SELECT id, share_token FROM pehero.chat_sessions WHERE id = %s AND user_id = %s",
        (sid_int, uid),
    )
    if not row:
        return JSONResponse({"ok": False, "error": "session not found"}, status_code=404)
    token = row.get("share_token")
    if not token:
        token = uuid.uuid4().hex
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE pehero.chat_sessions SET share_token = %s WHERE id = %s",
                (token, sid_int),
            )
            conn.commit()
    url = f"/app/s/{token}"
    return JSONResponse({"ok": True, "token": token, "url": url})


@rt("/app/s/{token}")
def shared_chat(token: str):
    row = fetch_one(
        "SELECT cs.id, cs.title, cs.agent_slug, cs.user_id "
        "FROM pehero.chat_sessions cs WHERE cs.share_token = %s",
        (token,),
    )
    if not row:
        return page(
            Div(H1("Not found"), P("This shared chat link is invalid or has expired."),
                cls="max-w-xl mx-auto py-24 text-center"),
        )
    messages = _session_messages(row["id"])
    return chat_page(
        user_email=None,
        sessions=[],
        current_sid="",
        messages=messages,
        current_agent_slug=row.get("agent_slug"),
        current_currency="EUR",
        readonly=True,
    )


# ── News feed ──────────────────────────────────────────────────────

@rt("/app/news")
async def news_feed(request: Request):
    lang = get_lang(request.session)
    from utils.news import fetch_news_translated, _cache_ttl
    articles = await fetch_news_translated(lang)
    return JSONResponse({
        "articles": articles,
        "interval": _cache_ttl(),
    })


def _time_ago(iso_str: str) -> str:
    from datetime import datetime, timezone
    try:
        d = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        mins = int((now - d).total_seconds() / 60)
        if mins < 1:
            return "just now"
        if mins < 60:
            return f"{mins}m ago"
        hours = mins // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except Exception:
        return ""


@rt("/app/news/html")
async def news_feed_html(request: Request):
    """HTMX endpoint — returns rendered HTML fragment for news items."""
    import html as _html
    from starlette.responses import HTMLResponse
    from fasthtml.common import to_xml
    lang = get_lang(request.session)
    from utils.news import fetch_news_translated
    from utils.i18n import t
    articles = await fetch_news_translated(lang)

    if not articles:
        return HTMLResponse(to_xml(P(t("news_empty", lang), cls="news-empty")))

    items = []
    for a in articles:
        summary_el = Div(
            _html.escape((a.get("summary") or "")[:120]),
            cls="news-item-summary",
        ) if a.get("summary") else None
        items.append(A(
            Div(
                Span(_html.escape(a.get("icon") or a["source"]), cls="news-source"),
                Span(_time_ago(a.get("published", "")), cls="news-time"),
                cls="news-item-header",
            ),
            Div(_html.escape(a["title"]), cls="news-item-title"),
            summary_el,
            href=a["url"],
            target="_blank",
            rel="noopener",
            cls="news-item",
        ))
    return HTMLResponse(to_xml(Div(*items)))


# ── Copilot session ───────────────────────────────────────────────

@rt("/app/copilot/session")
def copilot_session(sess, page: str = "", company: str = ""):
    """Return (or create) a per-page copilot chat session."""
    uid, _ = _ensure_user(sess)
    if not uid:
        return JSONResponse({"sid": None})
    title = f"Copilot: {page}" if not company else f"Copilot: {page}: {company}"
    row = fetch_one(
        "SELECT id FROM pehero.chat_sessions WHERE user_id = %s AND title = %s "
        "ORDER BY updated_at DESC LIMIT 1",
        (uid, title),
    )
    if row:
        messages = _session_messages(row["id"])
        return JSONResponse({"sid": row["id"], "messages": messages})
    sid = _ensure_session(uid, None, first_message=title)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("UPDATE pehero.chat_sessions SET title = %s WHERE id = %s", (title, sid))
        conn.commit()
    return JSONResponse({"sid": sid, "messages": []})


# ── Debug ping (kept from Phase 0) ──────────────────────────────────

@rt("/app/_debug/ping")
def debug_ping():
    try:
        llm = default_llm()
        out = llm.invoke("Reply with exactly the word: pong").content
        return JSONResponse({"ok": True, "model": llm.model_name, "reply": out})
    except Exception as e:  # noqa: BLE001
        log.exception("ping failed")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
