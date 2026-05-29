"""Generate a PEHero product tour PDF from the demo screenshots.

Output: docs/pehero-product-tour.pdf

Slide-deck format (landscape, 16:9). App-focused — spends one slide per
product surface (chat, pipeline kanban, deal detail, analytics,
instructions) and keeps landing pages in an appendix.

Usage:
    python -m scripts.make_pdf
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image as RLImage, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, KeepTogether,
)


ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"
OUT = ROOT / "docs" / "pehero-product-tour.pdf"

# 16:9 slide — 33.87 × 19.05 cm (standard PowerPoint 16:9)
SLIDE = (33.87 * cm, 19.05 * cm)

# Palette matches the app (light parchment + forest green).
BG         = HexColor("#F7F6F1")
INK        = HexColor("#14231B")
INK_MUTED  = HexColor("#415046")
INK_DIM    = HexColor("#7A867E")
ACCENT     = HexColor("#1F5D43")
ACCENT_DIM = HexColor("#CFE5DA")
RULE       = HexColor("#E3DFD2")


def _styles():
    ss = getSampleStyleSheet()
    return {
        "hero":     ParagraphStyle("hero",     parent=ss["Title"], fontName="Helvetica-Bold",
                                   fontSize=42, leading=50, textColor=INK, alignment=TA_CENTER,
                                   spaceAfter=10),
        "hero_sub": ParagraphStyle("hero_sub", parent=ss["Normal"], fontName="Helvetica",
                                   fontSize=16, leading=22, textColor=INK_MUTED, alignment=TA_CENTER,
                                   spaceAfter=16),
        "eyebrow":  ParagraphStyle("eyebrow",  parent=ss["Normal"], fontName="Helvetica-Bold",
                                   fontSize=10, leading=12, textColor=ACCENT, spaceAfter=4,
                                   letterSpacing=1.2),
        "title":    ParagraphStyle("title",    parent=ss["Title"], fontName="Helvetica-Bold",
                                   fontSize=28, leading=34, textColor=INK, spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", parent=ss["Normal"], fontName="Helvetica",
                                   fontSize=13, leading=18, textColor=INK_MUTED, spaceAfter=14),
        "body":     ParagraphStyle("body",     parent=ss["BodyText"], fontName="Helvetica",
                                   fontSize=11, leading=15, textColor=INK, alignment=TA_LEFT,
                                   spaceAfter=4),
        "caption":  ParagraphStyle("caption",  parent=ss["Italic"], fontName="Helvetica-Oblique",
                                   fontSize=9, leading=11, textColor=INK_DIM, alignment=TA_CENTER,
                                   spaceBefore=2),
        "bullet":   ParagraphStyle("bullet",   parent=ss["BodyText"], fontName="Helvetica",
                                   fontSize=11, leading=15, textColor=INK, leftIndent=12,
                                   bulletIndent=0),
    }


def _fit_image(path: Path, max_w_mm: float, max_h_mm: float) -> RLImage:
    img = Image.open(path)
    w, h = img.size
    ratio = min(max_w_mm * mm / w, max_h_mm * mm / h)
    return RLImage(str(path), width=w * ratio, height=h * ratio)


def _footer(canvas, doc):
    canvas.saveState()
    # Slide background
    canvas.setFillColor(BG)
    canvas.rect(0, 0, SLIDE[0], SLIDE[1], fill=1, stroke=0)
    # Thin footer line + page number
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(1.5 * cm, 1 * cm, SLIDE[0] - 1.5 * cm, 1 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK_DIM)
    canvas.drawString(1.5 * cm, 0.55 * cm, "PEHero · Your Private Equity AI Agent Squad")
    canvas.drawRightString(SLIDE[0] - 1.5 * cm, 0.55 * cm, f"{doc.page}")
    canvas.restoreState()


def _slide_frame(doc):
    return Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        id="main",
        leftPadding=6, rightPadding=6,
        topPadding=0, bottomPadding=0,
    )


def _hero_slide(styles):
    return [
        Spacer(1, 40 * mm),
        Paragraph("PEHero", styles["hero"]),
        Paragraph("Your Private Equity AI Agent Squad.", styles["hero_sub"]),
        Paragraph("Sourcing · underwriting · diligence · capital · portfolio operations",
                  styles["hero_sub"]),
        PageBreak(),
    ]


def _slide(styles, *, eyebrow: str, title: str, subtitle: str,
           bullets: list[str], screenshot: str, caption: str = None) -> list:
    """A two-column slide: left = text, right = screenshot.

    Using a Table so left/right stay aligned horizontally (Platypus doesn't
    otherwise support columns in a Frame cleanly).
    """
    left_cell = [
        Paragraph(eyebrow.upper(), styles["eyebrow"]),
        Paragraph(title, styles["title"]),
        Paragraph(subtitle, styles["subtitle"]),
    ]
    for b in bullets:
        left_cell.append(Paragraph(f"• {b}", styles["bullet"]))

    shot_path = SHOTS / screenshot
    if shot_path.exists():
        img = _fit_image(shot_path, max_w_mm=170, max_h_mm=135)
        right_cell = [img]
        if caption:
            right_cell.append(Paragraph(caption, styles["caption"]))
    else:
        right_cell = [Paragraph(f"[missing {screenshot}]", styles["caption"])]

    t = Table(
        [[left_cell, right_cell]],
        colWidths=[120 * mm, 180 * mm],
    )
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [Spacer(1, 3 * mm), t, PageBreak()]


def _agenda_slide(styles):
    rows = [
        ["01", "Chat — your Private Equity AI Agent Squad on call",
         "triage, LBO modelling, IC memo, VDR audit"],
        ["02", "Pipeline — kanban across every deal stage",
         "sector + ownership filters, click into a deal"],
        ["03", "Deal detail — brief on the right, chat in the centre",
         "LTM, top customers, DD findings, LBO returns"],
        ["04", "Analytics — ask in English, get a chart",
         "sector multiples, stage counts, LP mix"],
        ["05", "Instructions — tune how each specialist thinks",
         "edit in-app, changes land on the next conversation"],
        ["06", "Extensions — live web + local registries",
         "sourcing beyond your CRM, Baltic registry lookups"],
    ]
    t = Table(rows, colWidths=[20 * mm, 130 * mm, 150 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 12),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 14),
        ("FONT", (1, 0), (1, -1), "Helvetica-Bold", 12),
        ("TEXTCOLOR", (0, 0), (0, -1), ACCENT),
        ("TEXTCOLOR", (1, 0), (1, -1), INK),
        ("TEXTCOLOR", (2, 0), (2, -1), INK_MUTED),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, RULE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [
        Spacer(1, 8 * mm),
        Paragraph("TOUR".upper(), styles["eyebrow"]),
        Paragraph("What you'll see", styles["title"]),
        Paragraph("Six product surfaces, in order of a deal's life.", styles["subtitle"]),
        Spacer(1, 6 * mm),
        t,
        PageBreak(),
    ]


def _closing_slide(styles):
    cta_body = ParagraphStyle(
        "cta_body", parent=styles["body"], alignment=TA_CENTER, fontSize=15, leading=22,
    )
    cta_meta = ParagraphStyle(
        "cta_meta", parent=styles["caption"], alignment=TA_CENTER, fontSize=11, leading=16,
        textColor=INK_MUTED,
    )
    return [
        Spacer(1, 35 * mm),
        Paragraph("LET'S TALK", styles["eyebrow"]),
        Paragraph("See PEHero on your deals.", ParagraphStyle(
            "cta_title", parent=styles["title"], alignment=TA_CENTER, fontSize=38, leading=46,
        )),
        Spacer(1, 6 * mm),
        Paragraph(
            "Book a 20-minute walkthrough. We'll load one of your recent deals into "
            "PEHero and show you the full agent flow — live.",
            cta_body,
        ),
        Spacer(1, 10 * mm),
        Paragraph(
            "<b>hello@pehero.fyi</b> &nbsp;·&nbsp; pehero.fyi/contact",
            cta_meta,
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            "<i>BYOD — bring your own deal data.</i>",
            cta_meta,
        ),
        PageBreak(),
    ]


def build() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()

    doc = BaseDocTemplate(
        str(OUT), pagesize=SLIDE,
        leftMargin=1.2 * cm, rightMargin=1.2 * cm,
        topMargin=1 * cm, bottomMargin=1.5 * cm,
        title="PEHero — Product Tour",
        author="Predictive Labs",
    )
    doc.addPageTemplates([PageTemplate(id="slide", frames=[_slide_frame(doc)], onPage=_footer)])

    story: list = []
    story += _hero_slide(styles)
    story += _agenda_slide(styles)

    # ── Chat product (the main show) ──────────────────────────────
    story += _slide(
        styles,
        eyebrow="01 · Chat",
        title="One chat, every PE specialist",
        subtitle="Type a prefix or plain English — PEHero picks the right agent.",
        bullets=[
            "Left: your sessions, the full agent squad, and Pipeline / Instructions / Analytics.",
            "Centre: the conversation. Contextual sample prompts appear right under the input.",
            "Right: tables, citations, memo previews stream in as the agent works.",
            "A live 'thinking' indicator shows what's happening behind the scenes.",
        ],
        screenshot="07-chat-empty.png",
        caption="Empty chat with contextual prompts",
    )
    story += _slide(
        styles,
        eyebrow="01 · Chat",
        title="Deal Triage — go / no-go in 90 seconds",
        subtitle="A quick decision backed by comps and market signals.",
        bullets=[
            "Type 'triage:' or describe the deal in plain English.",
            "The agent pulls comparables and sector context on its own.",
            "Returns a clear verdict, a three-bullet rationale, and a concrete next step.",
            "'Next step — X' surfaces a follow-up button to keep the thread moving.",
        ],
        screenshot="08-chat-triage.png",
        caption="Live triage on a vertical-SaaS target",
    )
    story += _slide(
        styles,
        eyebrow="01 · Chat",
        title="LBO Model Builder",
        subtitle="Full 5-year model and sensitivity from one sentence of assumptions.",
        bullets=[
            "Normalises seller financials with standard QoE add-backs.",
            "Projects revenue, margin, capex, interest, free cash flow and debt paydown.",
            "Returns IRR, MOIC and a value-creation bridge — kept on hand for re-use.",
            "Year-by-year table appears in the right pane, editable by asking for changes.",
        ],
        screenshot="09-chat-lbo.png",
        caption="LBO built from a plain-English prompt",
    )
    story += _slide(
        styles,
        eyebrow="01 · Chat",
        title="IC Memo Writer",
        subtitle="An investment-committee memo, drafted from the deal's own data.",
        bullets=[
            "Pulls the deal brief, LTM financials, LBO model, debt stack, comps and findings.",
            "Drafts full sections: thesis, market, financials, value-creation plan, risks, recommendation.",
            "Every quantitative claim is sourced from the deal — no invented numbers.",
            "IC length by default; ask for a one-pager and it re-writes accordingly.",
        ],
        screenshot="10-chat-memo.png",
        caption="IC memo generated from the deal data",
    )

    # ── News feed ──────────────────────────────────────────────────
    story += _slide(
        styles,
        eyebrow="01 · Chat",
        title="Live news feed",
        subtitle="PE-relevant headlines from FT, Bloomberg, WSJ, Reuters, BBC — right where you work.",
        bullets=[
            "RSS aggregation from 7 financial news sources, refreshed every 5 minutes.",
            "Titles auto-translated to your session language (LT, ET, FI, SV).",
            "Click any headline to read the full article.",
            "Tables and data from agent tools now render inline — no context switch.",
        ],
        screenshot="11-chat-news.png",
        caption="News feed alongside the chat",
    )

    # ── Pipeline kanban ────────────────────────────────────────────
    story += _slide(
        styles,
        eyebrow="02 · Pipeline",
        title="Kanban across every deal stage",
        subtitle="Sourced → Closed / Held / Exited — every live target on one board.",
        bullets=[
            "Each card shows sector, LTM revenue and EBITDA, ask EV and multiple.",
            "A heat dot on the card reflects seller intent — cold, warm or hot.",
            "Sector and ownership chips filter the board in a click.",
            "Click a card to open the full deal workspace.",
        ],
        screenshot="12-pipeline-kanban.png",
        caption="Full pipeline kanban",
    )
    story += _slide(
        styles,
        eyebrow="03 · Deal detail",
        title="Every deal has its own workspace",
        subtitle="Brief on the right, chat in the centre, artifacts stream in as the squad works.",
        bullets=[
            "Right pane: HQ, LTM financials, top customers, DD findings, margin and multiple.",
            "Centre: per-deal chat. Ask 'triage this', 'draft the IC memo', 'show DD findings'.",
            "Any specialist can be invoked without ever leaving the deal.",
            "New artifacts from tool calls land alongside the brief as they arrive.",
        ],
        screenshot="13-pipeline-deal.png",
        caption="Single-deal workspace",
    )

    # ── Company search ────────────────────────────────────────────
    story += _slide(
        styles,
        eyebrow="02 · Pipeline",
        title="Company search",
        subtitle="Fuzzy name search and sector filter across your entire company database.",
        bullets=[
            "ILIKE fuzzy matching — search by partial name, city, or sector.",
            "Revenue, EBITDA, employees, and deal stage at a glance.",
            "Click any company to jump to its deal workspace.",
            "Sector filter narrows to healthcare, logistics, software, etc.",
        ],
        screenshot="14-companies.png",
        caption="Company search with sector filter",
    )

    # ── Analytics ──────────────────────────────────────────────────
    story += _slide(
        styles,
        eyebrow="04 · Analytics",
        title="Ask in English, get a chart",
        subtitle="Analytics that read the same data your deal team does.",
        bullets=[
            "Natural-language questions run read-only against your deal data.",
            "The right chart and title are picked automatically from the result.",
            "Curated sample questions seed the experience for first-time users.",
            "The underlying query is shown under every chart — fully auditable.",
        ],
        screenshot="17-analytics-stages.png",
        caption="Company count by deal stage",
    )
    story += _slide(
        styles,
        eyebrow="04 · Analytics",
        title="Sector multiples over time",
        subtitle="Median EV/EBITDA by sector, rolling 24 months.",
        bullets=[
            "Market signals cover every sector and sub-sector you're tracking.",
            "A grouped line chart, colour-coded by sector, appears in one click.",
            "Answers 'what's happening to multiples in X' without opening a spreadsheet.",
            "Drops straight into the LP update or IC pre-read.",
        ],
        screenshot="18-analytics-sector.png",
        caption="Median EV/EBITDA by sector",
    )

    # ── Instructions ───────────────────────────────────────────────
    story += _slide(
        styles,
        eyebrow="05 · Instructions",
        title="Tune the squad, live",
        subtitle="Every specialist's instructions are editable — from the same interface.",
        bullets=[
            "Each role has its own set of instructions, plus a shared PE glossary.",
            "Edits save in-place and take effect on the very next conversation.",
            "No restarts. No deploys. Just change how the squad thinks and carry on.",
            "Perfect for onboarding a partner's preferred memo style or diligence approach.",
        ],
        screenshot="19-instructions-list.png",
        caption="The full squad, editable",
    )
    story += _slide(
        styles,
        eyebrow="05 · Instructions",
        title="Editing the Deal Triage instructions",
        subtitle="Workflow, tone and output format — all in one view.",
        bullets=[
            "Rewrite a specialist's instructions the way you'd brief a new associate.",
            "Shared PE context is applied automatically so you don't repeat yourself.",
            "Versioned alongside the product so changes are auditable.",
            "Great for encoding your house style once and letting it apply everywhere.",
        ],
        screenshot="20-instructions-edit.png",
        caption="Editing a specialist's instructions",
    )

    story += _closing_slide(styles)

    doc.build(story)
    print(f"Wrote {OUT}  ({OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    build()
