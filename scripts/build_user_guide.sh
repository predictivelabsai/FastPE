#!/usr/bin/env bash
# Build the PEHero user guide as PDF (A4 landscape) + PPTX (16:9).
#
#   bash scripts/build_user_guide.sh
#
# Pipeline: pandoc (md→standalone HTML + guide.css) → WeasyPrint (PDF, A4 landscape)
#           and python-pptx (md→16:9 PPTX with native tables + screenshots).
# Requires: pandoc, weasyprint, python-pptx. Run from the repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
cd "$ROOT/docs"

GEN_DATE="$(date +%Y-%m-%d)"
echo "→ building PEHero user guide · ${GEN_DATE}"

# Stamp the PDF page footer with today's date.
sed -i -E "s|content: \"[^\"]*pehero\.chat\"|content: \"${GEN_DATE} · pehero.chat\"|" assets/guide.css

# ── PDF via pandoc + weasyprint ──
pandoc user_guide.md -s -o user_guide.html \
  --from=markdown-implicit_figures \
  --css "assets/guide.css" \
  --metadata pagetitle="PEHero User Guide (${GEN_DATE})"
weasyprint user_guide.html pehero-user-guide.pdf
rm -f user_guide.html
echo "✓ docs/pehero-user-guide.pdf ($(du -h pehero-user-guide.pdf | cut -f1))"

# ── PPTX via python-pptx ──
"$PY" "$ROOT/scripts/build_guide_pptx.py" user_guide.md pehero-user-guide.pptx "PEHero User Guide"
echo "✓ docs/pehero-user-guide.pptx ($(du -h pehero-user-guide.pptx | cut -f1))"

echo "✓ All formats built (${GEN_DATE}): PDF + PPTX."
