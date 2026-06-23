# Capture Screenshots

Capture product screenshots for the user guide, product tour, and marketing materials.

## What it does

Runs the Playwright-based screenshot script against a running PEHero server to produce numbered PNG screenshots of every major page and feature.

## Run

```bash
# Ensure server is running first
PORT=5058 python main.py &
sleep 3

# Capture all screenshots
python -m scripts.capture_screenshots
```

## Output

- `screenshots/*.png` — 24+ numbered frames (EN + LT variants)
- Used by the user guide PDF/PPTX and the product tour deck

## Notes

- Requires `playwright install chromium` (one-off)
- Server must be running on port 5058
- Screenshots are committed to the repo and referenced by `docs/user_guide.md`
- After capturing, rebuild the user guide: `bash scripts/build_user_guide.sh`
