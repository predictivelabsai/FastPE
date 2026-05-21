"""Compose PEHero demo screenshots into an MP4 video.

Uses Pillow for frame processing and ffmpeg (must be on PATH) for encoding.
No extra pip dependencies beyond Pillow (already in requirements.txt).

Usage:
    python -m scripts.make_video
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"
OUT_VIDEO = ROOT / "docs" / "pehero.mp4"

# Full product tour — landing pages first, then the app.
FRAMES = [
    # (filename, duration_secs, caption)
    ("01-home-full.png",          3.0, "Landing — Your PE AI Agent Squad"),
    ("02-platform-full.png",      2.5, "Platform Overview"),
    ("03-agents-full.png",        2.5, "Agent Roster"),
    ("04-agent-detail-triage.png",2.5, "Agent Detail — Deal Triage"),
    ("05-how-it-works-full.png",  2.5, "How It Works"),
    ("06-pricing-full.png",       2.0, "Pricing"),
    ("07-chat-empty.png",         2.0, "Chat — Empty State"),
    ("08-chat-triage.png",        3.5, "Chat — Deal Triage"),
    ("09-chat-lbo.png",           3.5, "Chat — LBO Model"),
    ("10-chat-memo.png",          3.5, "Chat — IC Memo"),
    ("11-pipeline-kanban.png",    3.0, "Pipeline — Kanban Board"),
    ("12-pipeline-software.png",  2.5, "Pipeline — Software Filter"),
    ("13-pipeline-deal.png",      3.5, "Pipeline — Deal Detail"),
    ("15-analytics-stages.png",   3.0, "Analytics — Deal Stages"),
    ("16-analytics-sector.png",   3.0, "Analytics — EV/EBITDA by Sector"),
    ("17-instructions-list.png",  2.5, "Instructions — Agent List"),
    ("18-instructions-edit.png",  2.5, "Instructions — Prompt Editor"),
]

FPS = 30
TARGET_W = 1920
TARGET_H = 1080
BG = (247, 246, 241)  # pehero parchment
CAPTION_H = 48
CAPTION_BG = (30, 60, 50)  # dark green
CAPTION_FG = (247, 246, 241)


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "Arial.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def load_frame(path: Path, caption: str) -> Image.Image:
    img = Image.open(path).convert("RGB")

    content_h = TARGET_H - CAPTION_H
    scale = min(TARGET_W / img.width, content_h / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (TARGET_W, TARGET_H), BG)
    x = (TARGET_W - new_w) // 2
    canvas.paste(img, (x, 0))

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([(0, TARGET_H - CAPTION_H), (TARGET_W, TARGET_H)], fill=CAPTION_BG)
    font = _get_font(22)
    bbox = draw.textbbox((0, 0), caption, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (TARGET_W - tw) // 2
    ty = TARGET_H - CAPTION_H + (CAPTION_H - th) // 2
    draw.text((tx, ty), caption, fill=CAPTION_FG, font=font)

    return canvas


def main() -> None:
    frames: list[tuple[Image.Image, float]] = []
    for fname, dur, caption in FRAMES:
        p = SHOTS / fname
        if not p.exists():
            print(f"  skip (missing): {p}")
            continue
        frames.append((load_frame(p, caption), dur))
        print(f"  added {fname}  ({dur}s) — {caption}")

    if not frames:
        raise SystemExit("No frames found — run scripts/capture_screenshots.py first.")

    OUT_VIDEO.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        concat_lines: list[str] = []
        for i, (img, dur) in enumerate(frames):
            png = tmp_path / f"frame_{i:04d}.png"
            img.save(png)
            concat_lines.append(f"file '{png}'")
            concat_lines.append(f"duration {dur}")

        # ffmpeg concat demuxer needs the last image repeated without duration
        if frames:
            concat_lines.append(f"file '{tmp_path / f'frame_{len(frames)-1:04d}.png'}'")

        concat_file = tmp_path / "concat.txt"
        concat_file.write_text("\n".join(concat_lines))

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-vf", f"scale={TARGET_W}:{TARGET_H}:flags=lanczos,format=yuv420p",
            "-c:v", "libx264", "-preset", "slow", "-crf", "23",
            "-movflags", "+faststart",
            str(OUT_VIDEO),
        ]
        print(f"\n  encoding with ffmpeg …")
        subprocess.run(cmd, check=True, capture_output=True)

    size_kb = OUT_VIDEO.stat().st_size / 1024
    total_dur = sum(d for _, d in frames)
    print(f"\nWrote {OUT_VIDEO}  ({size_kb:.0f} KB, {len(frames)} frames, {total_dur:.1f}s)")


if __name__ == "__main__":
    main()
