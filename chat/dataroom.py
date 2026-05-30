"""Data Room — upload, list, and download deal documents.

Virtual folder tree grouped by company_slug. Untagged files go under "General".

/app/dataroom                  → folder tree + upload form
POST /app/dataroom/upload      → handle file upload
GET  /app/dataroom/{id}/download → download a file
POST /app/dataroom/{id}/delete  → delete a file
"""

from __future__ import annotations

from collections import defaultdict

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H2, H3, P, A, Button, Form, Input, Select, Option, Label,
    Table, Thead, Tbody, Tr, Th, Td,
)
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse

import logging
import threading

from app import rt
from chat.components import left_pane, signin_overlay
from chat.layout import _versioned
from utils.session import get_currency
from utils.i18n import t, get_lang
from chat.routes import _ensure_user, _list_sessions
from db import connect, fetch_all, fetch_one
from landing.components import TAILWIND_CONFIG, _favicon_links

log = logging.getLogger(__name__)


def _index_into_rag(filename: str, data: bytes, company_slug: str | None):
    """Extract text from uploaded file and index into RAG (background thread)."""
    try:
        from rag.extract import extract_text, doc_type_from_filename
        from rag.indexer import DocIn, upsert_document

        text = extract_text(filename, data)
        if not text:
            return

        company_id = None
        if company_slug:
            row = fetch_one(
                "SELECT id FROM pehero.companies WHERE slug = %s", (company_slug,)
            )
            if row:
                company_id = row["id"]

        doc = DocIn(
            title=filename.rsplit(".", 1)[0],
            doc_type=doc_type_from_filename(filename),
            text=text,
            company_id=company_id,
            source_path=f"dataroom/{filename}",
            metadata={"filename": filename, "company_slug": company_slug, "size_bytes": len(data)},
        )
        doc_id = upsert_document(doc, replace=True)
        log.info("RAG indexed %s → document_id=%d", filename, doc_id)
    except Exception:
        log.exception("RAG indexing failed for %s", filename)


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


_ICON_MAP = {
    "pdf": "📄", "word": "📝", "docx": "📝", "doc": "📝",
    "sheet": "📊", "excel": "📊", "xlsx": "📊", "csv": "📊",
    "presentation": "📋", "pptx": "📋",
    "image": "🖼", "png": "🖼", "jpg": "🖼", "jpeg": "🖼",
}


def _file_icon(content_type: str, filename: str = "") -> str:
    ct = (content_type or "").lower()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    for key, icon in _ICON_MAP.items():
        if key in ct or key == ext:
            return icon
    return "📎"


def _folder_node(folder_name: str, docs: list[dict], lang: str, folder_id: str,
                 is_open: bool = False) -> Div:
    """Render a collapsible folder with its file rows."""
    total_size = sum(d.get("size_bytes") or 0 for d in docs)
    file_rows = []
    for d in docs:
        file_rows.append(
            Div(
                Span(_file_icon(d["content_type"], d["filename"]), cls="dr-file-icon"),
                A(d["filename"], href=f"/app/dataroom/{d['id']}/download", cls="dr-file-name"),
                Span(_fmt_size(d["size_bytes"]), cls="dr-file-size"),
                Span(str(d["uploaded_at"])[:16] if d["uploaded_at"] else "", cls="dr-file-date"),
                Form(
                    Button("✕", type="submit", cls="dr-delete-btn", title=t("dr_delete", lang)),
                    method="post", action=f"/app/dataroom/{d['id']}/delete",
                ),
                cls="dr-file-row",
            )
        )

    return Div(
        Button(
            Span("▸", cls="dr-folder-arrow"),
            Span("📁", cls="dr-folder-icon"),
            Span(folder_name, cls="dr-folder-name"),
            Span(f"{len(docs)}", cls="dr-folder-count"),
            Span(_fmt_size(total_size), cls="dr-folder-size"),
            cls=f"dr-folder-toggle{' open' if is_open else ''}",
            onclick=f"toggleGroup('{folder_id}')",
            id=f"btn-{folder_id}",
        ),
        Div(*file_rows, cls=f"dr-folder-files{' open' if is_open else ''}", id=folder_id),
        cls="dr-folder",
    )


def _company_display_name(slug: str) -> str:
    """Look up company name from slug, fallback to formatted slug."""
    row = fetch_one("SELECT name FROM pehero.companies WHERE slug = %s", (slug,))
    if row:
        return row["name"]
    return slug.replace("_", " ").title()


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

    # Build company dropdown for upload form
    companies = fetch_all(
        "SELECT slug, name FROM pehero.companies ORDER BY name LIMIT 100"
    )

    upload_form = Form(
        Div(
            Div(
                Label(t("dr_file", lang), cls="dr-label"),
                Input(type="file", name="file", required=True, cls="dr-file-input",
                      multiple=True,
                      accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.txt"),
                cls="dr-field",
            ),
            Div(
                Label(t("dr_company", lang), cls="dr-label"),
                Select(
                    Option(t("dr_general", lang), value=""),
                    *[Option(c["name"][:40], value=c["slug"]) for c in companies],
                    name="company_slug", cls="dr-select",
                ),
                cls="dr-field",
            ),
            Button(t("dr_upload_btn", lang), type="submit", cls="dr-upload-btn"),
            cls="dr-upload-bar",
        ),
        method="post",
        action="/app/dataroom/upload",
        enctype="multipart/form-data",
    )

    # Group docs into folders by company_slug
    folders: dict[str, list[dict]] = defaultdict(list)
    for d in docs:
        key = d["company_slug"] or "__general__"
        folders[key].append(d)

    folder_nodes = []
    # Company folders first (sorted by name), then general
    company_keys = sorted([k for k in folders if k != "__general__"],
                          key=lambda k: _company_display_name(k).lower())
    for i, slug in enumerate(company_keys):
        name = _company_display_name(slug)
        folder_nodes.append(
            _folder_node(name, folders[slug], lang, f"dr-{slug}", is_open=(i == 0))
        )
    if "__general__" in folders:
        folder_nodes.append(
            _folder_node(t("dr_general", lang), folders["__general__"], lang,
                         "dr-general", is_open=not company_keys)
        )

    if docs:
        total = Span(t("dr_count", lang).format(n=len(docs)), cls="search-count")
        tree = Div(*folder_nodes, cls="dr-tree")
    else:
        total = None
        tree = Div(P(t("dr_empty", lang), cls="search-empty"))

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
                    Span("·", cls="chat-header-dot"),
                    Span(t("dr_count", lang).format(n=len(docs)) if docs else "",
                         cls="chat-header-agent"),
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
                tree,
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
    company_slug = (form.get("company_slug") or "").strip() or None

    files = form.getlist("file")
    if not files:
        return RedirectResponse("/app/dataroom", status_code=303)

    uploaded = []
    with connect() as conn, conn.cursor() as cur:
        for upload in files:
            if not hasattr(upload, "read"):
                continue
            data = await upload.read()
            if not data:
                continue
            filename = upload.filename or "untitled"
            content_type = upload.content_type or "application/octet-stream"
            cur.execute(
                "INSERT INTO pehero.data_room (user_id, company_slug, filename, content_type, size_bytes, data) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (uid, company_slug, filename, content_type, len(data), data),
            )
            uploaded.append((filename, data, company_slug))
        conn.commit()

    for filename, data, cs in uploaded:
        threading.Thread(
            target=_index_into_rag, args=(filename, data, cs), daemon=True
        ).start()

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
