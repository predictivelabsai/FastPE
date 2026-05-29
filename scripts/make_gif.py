"""Compose PEHero demo screenshots into an animated GIF.

Usage:
    python -m scripts.make_gif                # English (default)
    python -m scripts.make_gif --lang lt      # Lithuanian
    python -m scripts.make_gif --lang all     # Both EN + LT
    python -m scripts.make_gif --home         # Home page hero GIF only
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"

# App-focused tour frames (skips landing pages — the GIF lives on them).
FRAMES = [
    ("07-chat-empty.png",          1800),
    ("08-chat-triage.png",         3200),
    ("09-chat-lbo.png",            3200),
    ("10-chat-memo.png",           3200),
    ("11-chat-news.png",           2800),
    ("12-pipeline-kanban.png",     3200),
    ("13-pipeline-deal.png",       3400),
    ("14-companies.png",           2800),
    ("15-companies-health.png",    2400),
    ("17-analytics-stages.png",    3200),
    ("18-analytics-sector.png",    3200),
    ("19-instructions-list.png",   2400),
    ("20-instructions-edit.png",   2400),
]

# Home page hero GIF — landing pages only
HOME_FRAMES = [
    ("01-home-full.png",           2500),
    ("02-platform-full.png",       2800),
    ("03-agents-full.png",         2800),
    ("05-how-it-works-full.png",   2800),
    ("06-pricing-full.png",        2500),
]

TARGET_W = 1200
TARGET_H = 820
BG = (247, 246, 241)  # pehero parchment (#F7F6F1)


def load_frame(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGB")
    ratio = TARGET_W / img.width
    img = img.resize((TARGET_W, int(img.height * ratio)), Image.LANCZOS)
    if img.height > TARGET_H:
        img = img.crop((0, 0, TARGET_W, TARGET_H))
    else:
        canvas = Image.new("RGB", (TARGET_W, TARGET_H), BG)
        canvas.paste(img, (0, 0))
        img = canvas
    return img


def build_gif(frame_list: list[tuple[str, int]], shots_dir: Path, out_path: Path) -> None:
    frames: list[Image.Image] = []
    durations: list[int] = []
    for fname, dur in frame_list:
        p = shots_dir / fname
        if not p.exists():
            print(f"  skip (missing): {p}")
            continue
        frames.append(load_frame(p))
        durations.append(dur)
        print(f"  added {fname}  ({dur} ms)")

    if not frames:
        print(f"  No frames found in {shots_dir}")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        optimize=True,
        duration=durations,
        loop=0,
        disposal=2,
    )
    print(f"\nWrote {out_path}  ({out_path.stat().st_size / 1024:.1f} KB, {len(frames)} frames)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="en", help="en, lt, or all")
    parser.add_argument("--home", action="store_true", help="Build home page hero GIF only")
    args = parser.parse_args()

    if args.home:
        build_gif(HOME_FRAMES, SHOTS, ROOT / "docs" / "pehero-home.gif")
        return

    if args.lang == "all":
        build_gif(FRAMES, SHOTS, ROOT / "docs" / "pehero.gif")
        build_gif(FRAMES, SHOTS / "lt", ROOT / "docs" / "pehero-lt.gif")
    elif args.lang == "en":
        build_gif(FRAMES, SHOTS, ROOT / "docs" / "pehero.gif")
    else:
        lang_dir = SHOTS / args.lang
        build_gif(FRAMES, lang_dir, ROOT / "docs" / f"pehero-{args.lang}.gif")


if __name__ == "__main__":
    main()
