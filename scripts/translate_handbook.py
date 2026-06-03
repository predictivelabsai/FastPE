"""Translate the PE Handbook to Lithuanian and Estonian.

Two-stage pipeline:
  1. xAI Grok translates each chunk (by ## heading)
  2. Claude reviews a sample of chunks and flags issues

Usage:
    python -m scripts.translate_handbook --lang lt
    python -m scripts.translate_handbook --lang ee
    python -m scripts.translate_handbook              # both
    python -m scripts.translate_handbook --review-only # review existing translations
"""
import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
HANDBOOK_MD = ROOT / "docs" / "pe-handbook.md"
OUT_DIR = ROOT / "docs"

LANG_NAMES = {"lt": "Lithuanian", "ee": "Estonian", "ro": "Romanian"}

TRANSLATE_SYSTEM = """\
You are an expert financial translator. Translate the following markdown content \
from English to {lang_name}.

RULES:
1. Preserve ALL markdown formatting exactly (headings, bold, italic, links, tables, \
lists, code blocks, blockquotes, horizontal rules)
2. Preserve ALL image references (![...](path)) exactly as they are — do not translate file paths
3. Keep technical PE/finance terms that are commonly used in English even in {lang_name} \
financial contexts (e.g. EBITDA, IRR, MOIC, TVPI, LBO, LP, GP, carry, hurdle rate, \
dry powder). You may add the {lang_name} equivalent in parentheses on first use.
4. Keep company names, fund names, and proper nouns in their original form
5. Keep all numbers, currencies (€, $), and percentages as-is
6. Translate the Table of Contents anchor links to match the translated headings
7. Maintain the same paragraph structure and line breaks
8. Do NOT add any commentary or notes — output ONLY the translated markdown
9. The translation should read naturally in {lang_name}, not as a word-for-word translation
{extra_rules}"""

LANG_EXTRA_RULES = {
    "ro": (
        '10. IMPORTANT: Wherever the text says "Baltic Perspective", "Baltic" region, '
        'or "Baltic case studies", replace with "Romanian Perspective", "Romanian" region, '
        'and "Romanian case studies" respectively. The book title should be '
        '"Manualul de Private Equity — O Perspectivă Românească". '
        'Keep the actual case study company names and deal details unchanged — '
        'only change the framing/perspective references from Baltic to Romanian.\n'
    ),
}

REVIEW_SYSTEM = """\
You are a bilingual translation reviewer for {lang_name} financial content. \
You will receive an English original and its {lang_name} translation.

Review the translation and output a JSON object with these fields:
- "score": integer 1-10 (10 = perfect, 7+ = acceptable, <7 = needs revision)
- "issues": list of strings describing specific problems (empty list if none)
- "markdown_intact": boolean — is the markdown formatting preserved correctly?
- "terms_correct": boolean — are PE/finance terms handled correctly?
- "natural": boolean — does it read naturally in {lang_name}?

Be strict but fair. Common acceptable choices:
- Keeping English PE terms (EBITDA, IRR, LBO) is CORRECT
- Translating section headings is CORRECT
- Keeping company names in English is CORRECT

Output ONLY valid JSON, no other text.
"""


def _chunk_by_heading(md_text: str) -> list[str]:
    """Split markdown into chunks at ## headings."""
    lines = md_text.split("\n")
    chunks = []
    current = []

    for line in lines:
        if line.startswith("## ") and current:
            chunks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        chunks.append("\n".join(current))

    return chunks


def _translate_chunk(client: OpenAI, chunk: str, lang: str, idx: int, total: int) -> str:
    lang_name = LANG_NAMES[lang]
    heading = chunk.split("\n")[0][:60] if chunk.strip() else "(empty)"
    print(f"  [{idx+1}/{total}] Translating: {heading}...")

    response = client.chat.completions.create(
        model="grok-3-mini",
        messages=[
            {"role": "system", "content": TRANSLATE_SYSTEM.format(
                lang_name=lang_name, extra_rules=LANG_EXTRA_RULES.get(lang, ""))},
            {"role": "user", "content": chunk},
        ],
        temperature=0.3,
        max_tokens=16000,
    )
    return response.choices[0].message.content


def _review_chunk(
    claude: OpenAI, original: str, translated: str, lang: str, idx: int,
) -> dict:
    lang_name = LANG_NAMES[lang]
    heading = original.split("\n")[0][:50]
    print(f"  Reviewing chunk {idx}: {heading}...")

    prompt = (
        f"## English original:\n\n{original[:3000]}\n\n"
        f"## {lang_name} translation:\n\n{translated[:3000]}"
    )

    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=REVIEW_SYSTEM.format(lang_name=lang_name),
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    text = text.removeprefix("```json").removesuffix("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"score": 0, "issues": [f"Review parse error: {text[:200]}"],
                "markdown_intact": True, "terms_correct": True, "natural": True}


def translate(lang: str, skip_review: bool = False):
    lang_name = LANG_NAMES[lang]
    out_path = OUT_DIR / f"pe-handbook_{lang}.md"
    review_path = OUT_DIR / f"pe-handbook_{lang}_review.json"

    print(f"\n{'='*60}")
    print(f"  STAGE 1: Translating to {lang_name} via xAI Grok")
    print(f"{'='*60}")

    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        api_key = os.environ.get("XAI_API_KEY")

    if not api_key:
        print("  ERROR: XAI_API_KEY not set")
        return False

    xai = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

    md_text = HANDBOOK_MD.read_text()
    chunks = _chunk_by_heading(md_text)
    print(f"  Split into {len(chunks)} chunks")

    translated_chunks = []
    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            translated_chunks.append(chunk)
            continue

        try:
            translated = _translate_chunk(xai, chunk, lang, i, len(chunks))
            translated_chunks.append(translated)
        except Exception as e:
            print(f"  ERROR on chunk {i}: {e}")
            translated_chunks.append(chunk)
        time.sleep(0.3)

    result = "\n\n".join(translated_chunks)
    out_path.write_text(result)
    print(f"  Saved: {out_path} ({out_path.stat().st_size // 1024} KB)")

    if skip_review:
        return True

    return review(lang, chunks, translated_chunks, review_path)


def review(
    lang: str,
    original_chunks: list[str] | None = None,
    translated_chunks: list[str] | None = None,
    review_path: Path | None = None,
):
    lang_name = LANG_NAMES[lang]
    if review_path is None:
        review_path = OUT_DIR / f"pe-handbook_{lang}_review.json"

    print(f"\n{'='*60}")
    print(f"  STAGE 2: Claude review of {lang_name} translation")
    print(f"{'='*60}")

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if not anthropic_key:
        print("  WARNING: ANTHROPIC_API_KEY not set, skipping review")
        return True

    import anthropic
    claude = anthropic.Anthropic(api_key=anthropic_key)

    if original_chunks is None:
        md_text = HANDBOOK_MD.read_text()
        original_chunks = _chunk_by_heading(md_text)

    if translated_chunks is None:
        translated_path = OUT_DIR / f"pe-handbook_{lang}.md"
        if not translated_path.exists():
            print(f"  ERROR: {translated_path} not found")
            return False
        translated_chunks = _chunk_by_heading(translated_path.read_text())

    substantive = [
        (i, o, t) for i, (o, t) in enumerate(zip(original_chunks, translated_chunks))
        if o.strip() and len(o.strip()) > 100
    ]

    sample_size = min(8, len(substantive))
    sample = random.sample(substantive, sample_size)

    reviews = []
    for idx, orig, trans in sample:
        try:
            result = _review_chunk(claude, orig, trans, lang, idx)
            result["chunk_idx"] = idx
            result["heading"] = orig.split("\n")[0][:80]
            reviews.append(result)
        except Exception as e:
            print(f"  Review error on chunk {idx}: {e}")
            reviews.append({"chunk_idx": idx, "score": 0, "issues": [str(e)]})
        time.sleep(0.5)

    review_path.write_text(json.dumps(reviews, indent=2, ensure_ascii=False))

    scores = [r["score"] for r in reviews if r.get("score", 0) > 0]
    avg = sum(scores) / len(scores) if scores else 0
    issues = [iss for r in reviews for iss in r.get("issues", [])]

    print(f"\n  Review summary ({lang_name}):")
    print(f"    Chunks reviewed: {len(reviews)}/{len(substantive)}")
    print(f"    Average score:   {avg:.1f}/10")
    print(f"    Issues found:    {len(issues)}")
    for iss in issues[:10]:
        print(f"      - {iss}")
    if avg < 7:
        print(f"    WARNING: Average score below 7 — translation may need manual review")
    else:
        print(f"    PASS: Translation quality acceptable")

    return avg >= 6


def main():
    parser = argparse.ArgumentParser(description="Translate PE Handbook")
    parser.add_argument("--lang", choices=["lt", "ee", "ro"], help="Target language (default: all)")
    parser.add_argument("--review-only", action="store_true", help="Only run Claude review")
    parser.add_argument("--skip-review", action="store_true", help="Skip Claude review step")
    args = parser.parse_args()

    langs = [args.lang] if args.lang else ["lt", "ee"]

    ok = True
    for lang in langs:
        if args.review_only:
            ok = review(lang) and ok
        else:
            ok = translate(lang, skip_review=args.skip_review) and ok

    if ok:
        print("\nDone. Now run: python -m scripts.make_handbook --pdf")
    else:
        print("\nCompleted with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
