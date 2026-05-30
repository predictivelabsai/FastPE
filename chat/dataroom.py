"""Data Room — upload, list, and download deal documents.

/app/dataroom                  → file list + upload form
POST /app/dataroom/upload      → handle file upload
GET  /app/dataroom/{id}/download → download a file
POST /app/dataroom/{id}/delete  → delete a file
"""

from __future__ import annotations

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H2, H3, P, A, Button, Form, Input, Label,
    Table, Thead, Tbody, Tr, Th, Td,
)
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse

from app import rt
from chat.components import left_pane, signin_overlay
from chat.layout import _versioned
from utils.session import get_currency
from utils.i18n import t, get_lang
from chat.routes import _ensure_user, _list_sessions
from db import connect, fetch_all, fetch_one
from landing.components import TAILWIND_CONFIG, _favicon_links


def _head(title: str):
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title(f"{title} · PEHero"),
        *_favicon_links(),
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        Link(rel="stylesheet",
             href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"),
        Script(src="https://cdn.tailwindcss.com"),
        Script(NotStr(TAILWIND_CONFIG)),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href=_versioned("app.css")),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


def _fmt_size(size_bytes) -> str:
    if not size_bytes:
        return "—"
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.1f} MB"
    if size_bytes >= 1_000:
        return f"{size_bytes / 1_000:.0f} KB"
    return f"{size_bytes} B"


def _file_icon(content_type: str) -> str:
    ct = (content_type or "").lower()
    if "pdf" in ct:
        return "📄"
    if "word" in ct or "docx" in ct:
        return "📝"
    if "sheet" in ct or "excel" in ct or "xlsx" in ct or "csv" in ct:
        return "📊"
    if "presentation" in ct or "pptx" in ct:
        return "📋"
    if "image" in ct:
        return "🖼"
    return "📎"


@rt("/app/dataroom")
def dataroom_home(sess):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)

    docs = []
    if uid:
        docs = fetch_all(
            "SELECT id, filename, content_type, size_bytes, company_slug, uploaded_at "
            "FROM pehero.data_room WHERE user_id = %s ORDER BY uploaded_at DESC",
            (uid,),
        )

    upload_form = Form(
        Div(
            Div(
                Label(t("dr_file", lang), cls="dr-label"),
                Input(type="file", name="file", required=True, cls="dr-file-input",
                      accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.txt"),
                cls="dr-field",
            ),
            Div(
                Label(t("dr_company", lang), cls="dr-label"),
                Input(type="text", name="company_slug", placeholder=t("dr_company_placeholder", lang),
                      cls="dr-text-input"),
                cls="dr-field",
            ),
            Button(t("dr_upload_btn", lang), type="submit", cls="dr-upload-btn"),
            cls="dr-upload-bar",
        ),
        method="post",
        action="/app/dataroom/upload",
        enctype="multipart/form-data",
    )

    if docs:
        table = Table(
            Thead(Tr(
                Th(""),
                Th(t("dr_col_name", lang)),
                Th(t("dr_col_company", lang)),
                Th(t("dr_col_size", lang), cls="text-right"),
                Th(t("dr_col_date", lang)),
                Th(""),
            )),
            Tbody(
                *[Tr(
                    Td(_file_icon(d["content_type"])),
                    Td(A(d["filename"], href=f"/app/dataroom/{d['id']}/download",
                         cls="company-link")),
                    Td(d["company_slug"] or "—"),
                    Td(_fmt_size(d["size_bytes"]), cls="text-right mono"),
                    Td(str(d["uploaded_at"])[:16] if d["uploaded_at"] else "—"),
                    Td(
                        Form(
                            Button("✕", type="submit", cls="dr-delete-btn",
                                   title=t("dr_delete", lang)),
                            method="post",
                            action=f"/app/dataroom/{d['id']}/delete",
                        ),
                    ),
                    cls="search-row",
                ) for d in docs],
            ),
            cls="search-table",
        )
        result_count = Span(t("dr_count", lang).format(n=len(docs)), cls="search-count")
    else:
        table = Div(P(t("dr_empty", lang), cls="search-empty"))
        result_count = None

    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_currency=get_currency(sess),
                  current_path="/app/dataroom", lang=lang),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span(t("dr_title", lang), cls="chat-header-title"),
                    cls="chat-header-left",
                ),
                Div(
                    A(t("chat_back", lang), href="/app", cls="back-to-chat-btn"),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            Div(
                upload_form,
                result_count,
                table,
                cls="companies-wrap",
            ),
            cls="center-pane pipeline-center",
        ),
        Script(src=_versioned("chat.js")),
        cls="bg-bg text-ink font-sans antialiased app pane-closed pipeline-app",
    )
    return Html(_head(t("dr_title", lang)), body, lang=lang)


@rt("/app/dataroom/upload", methods=["POST"])
async def dataroom_upload(request: Request):
    sess = request.session
    uid, _ = _ensure_user(sess)
    if not uid:
        return RedirectResponse("/app/dataroom", status_code=303)

    form = await request.form()
    upload = form.get("file")
    company_slug = (form.get("company_slug") or "").strip() or None

    if not upload or not hasattr(upload, "read"):
        return RedirectResponse("/app/dataroom", status_code=303)

    data = await upload.read()
    filename = upload.filename or "untitled"
    content_type = upload.content_type or "application/octet-stream"

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO pehero.data_room (user_id, company_slug, filename, content_type, size_bytes, data) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (uid, company_slug, filename, content_type, len(data), data),
        )
        conn.commit()

    return RedirectResponse("/app/dataroom", status_code=303)


@rt("/app/dataroom/{doc_id}/download")
def dataroom_download(doc_id: int, sess):
    uid, _ = _ensure_user(sess)
    row = fetch_one(
        "SELECT filename, content_type, data FROM pehero.data_room WHERE id = %s AND user_id = %s",
        (doc_id, uid),
    )
    if not row:
        return Response("Not found", status_code=404)

    return Response(
        content=bytes(row["data"]),
        media_type=row["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{row["filename"]}"'},
    )


@rt("/app/dataroom/{doc_id}/delete", methods=["POST"])
def dataroom_delete(doc_id: int, sess):
    uid, _ = _ensure_user(sess)
    if uid:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM pehero.data_room WHERE id = %s AND user_id = %s",
                        (doc_id, uid))
            conn.commit()
    return RedirectResponse("/app/dataroom", status_code=303)
