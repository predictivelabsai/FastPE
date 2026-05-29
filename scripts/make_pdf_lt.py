"""Generate a Lithuanian PEHero product tour PDF from the *_lt.png screenshots.

Output: docs/pehero-product-tour-lt.pdf

Usage:
    python -m scripts.make_pdf_lt
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
    Paragraph, Spacer, Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"
OUT = ROOT / "docs" / "pehero-product-tour-lt.pdf"

SLIDE = (33.87 * cm, 19.05 * cm)

BG         = HexColor("#F7F6F1")
INK        = HexColor("#14231B")
INK_MUTED  = HexColor("#415046")
INK_DIM    = HexColor("#7A867E")
ACCENT     = HexColor("#1F5D43")
RULE       = HexColor("#E3DFD2")


def _styles():
    ss = getSampleStyleSheet()
    return {
        "hero":     ParagraphStyle("hero",     parent=ss["Title"], fontName="Helvetica-Bold",
                                   fontSize=42, leading=50, textColor=INK, alignment=TA_CENTER, spaceAfter=10),
        "hero_sub": ParagraphStyle("hero_sub", parent=ss["Normal"], fontName="Helvetica",
                                   fontSize=16, leading=22, textColor=INK_MUTED, alignment=TA_CENTER, spaceAfter=16),
        "eyebrow":  ParagraphStyle("eyebrow",  parent=ss["Normal"], fontName="Helvetica-Bold",
                                   fontSize=10, leading=12, textColor=ACCENT, spaceAfter=4, letterSpacing=1.2),
        "title":    ParagraphStyle("title",    parent=ss["Title"], fontName="Helvetica-Bold",
                                   fontSize=28, leading=34, textColor=INK, spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", parent=ss["Normal"], fontName="Helvetica",
                                   fontSize=13, leading=18, textColor=INK_MUTED, spaceAfter=14),
        "body":     ParagraphStyle("body",     parent=ss["BodyText"], fontName="Helvetica",
                                   fontSize=11, leading=15, textColor=INK, alignment=TA_LEFT, spaceAfter=4),
        "caption":  ParagraphStyle("caption",  parent=ss["Italic"], fontName="Helvetica-Oblique",
                                   fontSize=9, leading=11, textColor=INK_DIM, alignment=TA_CENTER, spaceBefore=2),
        "bullet":   ParagraphStyle("bullet",   parent=ss["BodyText"], fontName="Helvetica",
                                   fontSize=11, leading=15, textColor=INK, leftIndent=12, bulletIndent=0),
    }


def _fit_image(path: Path, max_w_mm: float, max_h_mm: float) -> RLImage:
    img = Image.open(path)
    w, h = img.size
    ratio = min(max_w_mm * mm / w, max_h_mm * mm / h)
    return RLImage(str(path), width=w * ratio, height=h * ratio)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG)
    canvas.rect(0, 0, SLIDE[0], SLIDE[1], fill=1, stroke=0)
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(1.5 * cm, 1 * cm, SLIDE[0] - 1.5 * cm, 1 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK_DIM)
    canvas.drawString(1.5 * cm, 0.55 * cm, "PEHero · Jūsų privataus kapitalo AI agentų komanda")
    canvas.drawRightString(SLIDE[0] - 1.5 * cm, 0.55 * cm, f"{doc.page}")
    canvas.restoreState()


def _slide_frame(doc):
    return Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                 id="main", leftPadding=6, rightPadding=6, topPadding=0, bottomPadding=0)


def _slide(styles, *, eyebrow, title, subtitle, bullets, screenshot, caption=None):
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
        right_cell = [Paragraph(f"[trūksta {screenshot}]", styles["caption"])]

    t = Table([[left_cell, right_cell]], colWidths=[120 * mm, 180 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [Spacer(1, 3 * mm), t, PageBreak()]


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()

    doc = BaseDocTemplate(
        str(OUT), pagesize=SLIDE,
        leftMargin=1.2 * cm, rightMargin=1.2 * cm,
        topMargin=1 * cm, bottomMargin=1.5 * cm,
        title="PEHero — Produkto apžvalga (LT)",
        author="Predictive Labs",
    )
    doc.addPageTemplates([PageTemplate(id="slide", frames=[_slide_frame(doc)], onPage=_footer)])

    story = []

    # Hero
    story += [
        Spacer(1, 40 * mm),
        Paragraph("PEHero", styles["hero"]),
        Paragraph("Jūsų privataus kapitalo AI agentų komanda.", styles["hero_sub"]),
        Paragraph("Paieška · vertinimas · patikra · kapitalas · portfelio operacijos", styles["hero_sub"]),
        PageBreak(),
    ]

    # Agenda
    rows = [
        ["01", "Pokalbis — AI agentų komanda visada pasiekiama",
         "atranka, LBO modeliavimas, IC memo, VDR auditas"],
        ["02", "Pipeline — kanban per visus sandorių etapus",
         "sektoriaus + nuosavybės filtrai, spustelėkite sandorį"],
        ["03", "Sandorio detalės — aprašymas dešinėje, pokalbis centre",
         "LTM, klientai, DD išvados, LBO grąža"],
        ["04", "Analitika — klauskite lietuviškai, gaukite grafiką",
         "sektoriaus kordajiai, etapų skaičiai, LP struktūra"],
        ["05", "Instrukcijos — koreguokite kiekvieno specialisto elgseną",
         "redaguokite programoje, pakeitimai veikia kitą pokalbį"],
    ]
    t = Table(rows, colWidths=[20 * mm, 140 * mm, 140 * mm])
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
    story += [
        Spacer(1, 8 * mm),
        Paragraph("APŽVALGA", styles["eyebrow"]),
        Paragraph("Ką pamatysite", styles["title"]),
        Paragraph("Penki produkto paviršiai, sandorio gyvavimo tvarka.", styles["subtitle"]),
        Spacer(1, 6 * mm), t, PageBreak(),
    ]

    # Chat slides
    story += _slide(styles,
        eyebrow="01 · Pokalbis",
        title="Vienas pokalbis, kiekvienas PE specialistas",
        subtitle="Įveskite prefiksą arba klauskite lietuviškai — PEHero parinks tinkamą agentą.",
        bullets=[
            "Kairėje: pokalbiai, agentų komanda, Pipeline / Instrukcijos / Analitika.",
            "Centre: pokalbis. Kontekstiniai pavyzdiniai klausimai po įvesties lauku.",
            "Dešinėje: lentelės, citatos, memo peržiūros srautu ateina agentui dirbant.",
            "Gyvas 'galvoju' indikatorius rodo, kas vyksta užkulisiuose.",
        ],
        screenshot="04-chat-empty_lt.png",
        caption="Tuščias pokalbis su kontekstiniais klausimais",
    )
    story += _slide(styles,
        eyebrow="01 · Pokalbis",
        title="Sandorių atranka — taip / ne per 90 sekundžių",
        subtitle="Greitas sprendimas, paremtas lyginamaisiais ir rinkos signalais.",
        bullets=[
            "Įveskite 'triage:' arba aprašykite sandorį paprastai.",
            "Agentas pats suranda lyginamuosius ir sektoriaus kontekstą.",
            "Grąžina aiškų verdiktą, trijų punktų argumentaciją ir konkretų kitą žingsnį.",
            "DR VET — tikra lietuviška veterinarijos klinika su tikrais finansiniais duomenimis.",
        ],
        screenshot="05-chat-triage_lt.png",
        caption="Gyva DR VET atranka lietuvių kalba",
    )
    story += _slide(styles,
        eyebrow="01 · Pokalbis",
        title="LTM finansinių rodiklių normalizavimas",
        subtitle="Tikri DR VET finansiniai duomenys iš duomenų bazės.",
        bullets=[
            "Normalizuoja pardavėjo finansines ataskaitas pagal standartinę sąskaitų struktūrą.",
            "Taiko QoE korekcijas, atskiria vienkartines pozicijas.",
            "Pažymi pajamų / EBITDA anomalijas lyginant su pramonės standartais.",
            "Pajamos, EBITDA marža, augimo tempas — viskas iš tikrų Lietuvos duomenų.",
        ],
        screenshot="06-chat-ltm_lt.png",
        caption="DR VET LTM finansiniai rodikliai",
    )
    story += _slide(styles,
        eyebrow="01 · Pokalbis",
        title="IC Memo rengėjas",
        subtitle="Investicijų komiteto memo, parengtas iš sandorio duomenų.",
        bullets=[
            "Surinka sandorio aprašymą, LTM finansus, LBO modelį, skolos struktūrą ir lyginamuosius.",
            "Parengia visas dalis: tezę, rinką, finansus, vertės kūrimo planą, rizikas.",
            "Kiekvienas kiekybinis teiginys paremtas tikrais duomenimis — ne išgalvotais skaičiais.",
            "Kardiolita — tikra ligoninė, €34M pajamos, Vilnius.",
        ],
        screenshot="07-chat-memo_lt.png",
        caption="IC memo sugeneruotas iš Kardiolita duomenų",
    )

    # Pipeline
    story += _slide(styles,
        eyebrow="02 · Pipeline",
        title="Kanban per visus sandorių etapus",
        subtitle="Surasta → Uždaryta / Valdoma / Parduota — visi tikslai vienoje lentoje.",
        bullets=[
            "Kiekviena kortelė rodo sektorių, LTM pajamas, EBITDA, EV ir kordajų.",
            "Šilumos taškas kortelėje atspindi pardavėjo ketinimą — šalta, šilta ar karšta.",
            "Sektoriaus ir nuosavybės filtrai filtruoja lentą vienu paspaudimu.",
            "157 tikrų Lietuvos įmonių — sveikatos, draudimo, logistikos, NT sektoriuose.",
        ],
        screenshot="08-pipeline-kanban_lt.png",
        caption="Pipeline kanban su tikromis Lietuvos įmonėmis",
    )
    story += _slide(styles,
        eyebrow="03 · Sandorio detalės",
        title="Kiekvienas sandoris turi savo darbo erdvę",
        subtitle="Aprašymas dešinėje, pokalbis centre, artefaktai srautu ateina.",
        bullets=[
            "Dešinė: būstinė, LTM finansai, klientai, DD išvados, marža ir kordajus.",
            "Centras: pokalbis apie sandorį. Klauskite 'triage this', 'draft IC memo'.",
            "Bet kuris specialistas gali būti iškviestas nepaliekant sandorio.",
            "Nauji artefaktai iš įrankių iškart pateikiami šalia aprašymo.",
        ],
        screenshot="09-pipeline-deal_lt.png",
        caption="Sandorio darbo erdvė",
    )

    # Analytics
    story += _slide(styles,
        eyebrow="04 · Analitika",
        title="Klauskite lietuviškai, gaukite grafiką",
        subtitle="Analitika, skaitanti tuos pačius duomenis kaip jūsų komanda.",
        bullets=[
            "Natūralios kalbos klausimai vykdomi tik-skaitymui prieš jūsų duomenis.",
            "Tinkamas grafikas ir pavadinimas parenkami automatiškai.",
            "Pavyzdiniai klausimai padeda pradėti pirmą kartą.",
            "SQL užklausa rodoma po kiekvienu grafiku — visiškai audituojama.",
        ],
        screenshot="11-analytics-revenue_lt.png",
        caption="Top 10 įmonių pagal pajamas",
    )

    # Instructions
    story += _slide(styles,
        eyebrow="05 · Instrukcijos",
        title="Koreguokite komandą gyvai",
        subtitle="Kiekvieno specialisto instrukcijos redaguojamos — iš tos pačios sąsajos.",
        bullets=[
            "Kiekviena rolė turi savo instrukcijų rinkinį, plius bendrą PE žodyną.",
            "Pakeitimai išsaugomi ir pradeda veikti kitame pokalbyje.",
            "Jokių perkrovimų. Jokių diegimų. Tiesiog pakeiskite, kaip komanda galvoja.",
            "Idealiai tinka partnerio pageidaujamam memo stiliui ar patikros požiūriui.",
        ],
        screenshot="12-instructions-list_lt.png",
        caption="Visa komanda, redaguojama",
    )

    # Closing
    cta_body = ParagraphStyle("cta_body", parent=styles["body"], alignment=TA_CENTER, fontSize=15, leading=22)
    cta_meta = ParagraphStyle("cta_meta", parent=styles["caption"], alignment=TA_CENTER, fontSize=11, leading=16, textColor=INK_MUTED)
    story += [
        Spacer(1, 35 * mm),
        Paragraph("SUSISIEKITE", styles["eyebrow"]),
        Paragraph("Pamatykite PEHero su savo sandoriais.", ParagraphStyle(
            "cta_title", parent=styles["title"], alignment=TA_CENTER, fontSize=38, leading=46)),
        Spacer(1, 6 * mm),
        Paragraph("Užsisakykite 20 minučių demonstraciją. Įkelkime vieną iš jūsų "
                  "sandorių į PEHero ir parodysime pilną agentų darbo eigą — gyvai.", cta_body),
        Spacer(1, 10 * mm),
        Paragraph("<b>hello@pehero.fyi</b> &nbsp;·&nbsp; pehero.fyi/contact", cta_meta),
        Spacer(1, 2 * mm),
        Paragraph("<i>BYOD — naudokite savo sandorių duomenis.</i>", cta_meta),
        PageBreak(),
    ]

    doc.build(story)
    print(f"Wrote {OUT}  ({OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    build()
