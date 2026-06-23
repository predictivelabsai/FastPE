# Build PE Handbook

Generate the PE handbook (comprehensive private equity guide with Baltic case studies) as PDF and EPUB.

## What it does

1. Generates 9 Plotly charts as PNG images (J-curve, value creation bridge, sensitivity heatmap, etc.)
2. Renders the handbook markdown with charts embedded
3. Outputs PDF via pandoc + wkhtmltopdf, and EPUB via pandoc

## Run

```bash
# English original
python -m scripts.make_handbook

# Translate to Estonian, Lithuanian, Romanian
python -m scripts.translate_handbook
```

## Output

- `docs/pe-handbook.pdf` — English PDF (~1.6 MB)
- `docs/pe-handbook.epub` — English EPUB (~1 MB)
- `docs/pe-handbook_{lt,ee,ro}.pdf` — translated versions

## Source

- `docs/pe-handbook.md` — English markdown source (159 KB, 9 Baltic case studies)
- `docs/_handbook.css` — A4 portrait CSS (serif typography)
- `docs/charts/` — generated PNG charts

## Notes

- Translation uses the Anthropic API (`scripts/translate_handbook.py`)
- Charts are regenerated each build from inline Plotly code
- Requires `pandoc` and `wkhtmltopdf` system packages
