"""Apply schema.sql + rag_schema.sql idempotently.

Usage:
    python -m db.migrate          # apply both
    python -m db.migrate --drop   # DANGER: drops pehero schemas first
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from db import connect
from utils.config import settings

log = logging.getLogger(__name__)

SCHEMA_FILES = [
    Path(__file__).with_name("schema.sql"),
    Path(__file__).with_name("rag_schema.sql"),
]


def _apply(sql: str) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


def _render(path: Path) -> str:
    text = path.read_text()
    return text.replace("{{EMBEDDING_DIM}}", str(settings().embedding_dim))


def migrate(drop: bool = False) -> None:
    if drop:
        print("dropping pehero + pehero_rag schemas…")
        _apply("DROP SCHEMA IF EXISTS pehero_rag CASCADE; DROP SCHEMA IF EXISTS pehero CASCADE;")

    for f in SCHEMA_FILES:
        print(f"applying {f.name} (embedding_dim={settings().embedding_dim})")
        _apply(_render(f))

    # Incremental column additions (idempotent).
    _apply("""
        ALTER TABLE pehero.chat_sessions
            ADD COLUMN IF NOT EXISTS share_token TEXT UNIQUE;
    """)

    _apply("""
        ALTER TABLE pehero.users
            ADD COLUMN IF NOT EXISTS password_hash TEXT;
        ALTER TABLE pehero.users
            ADD COLUMN IF NOT EXISTS name VARCHAR(200);
        ALTER TABLE pehero.users
            ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;
        ALTER TABLE pehero.users
            ADD COLUMN IF NOT EXISTS verify_token VARCHAR(64);
        ALTER TABLE pehero.users
            ADD COLUMN IF NOT EXISTS reset_token VARCHAR(64);
        ALTER TABLE pehero.users
            ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMPTZ;
    """)

    # Seed existing prompt files as v1 if prompt_versions is empty.
    _seed_prompt_versions()

    print("migration complete")


def _seed_prompt_versions() -> None:
    from pathlib import Path
    prompts_dir = Path(__file__).resolve().parent.parent / "prompts" / "system"
    shared_path = Path(__file__).resolve().parent.parent / "prompts" / "shared" / "pe_context.md"

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM pehero.prompt_versions")
        if cur.fetchone()[0] > 0:
            return

        seeded = 0
        for md in sorted(prompts_dir.glob("*.md")):
            slug = md.stem
            content = md.read_text()
            cur.execute(
                "INSERT INTO pehero.prompt_versions (slug, content, changed_by) VALUES (%s, %s, %s)",
                (slug, content, "seed"),
            )
            seeded += 1

        if shared_path.exists():
            cur.execute(
                "INSERT INTO pehero.prompt_versions (slug, content, changed_by) VALUES (%s, %s, %s)",
                ("__shared__", shared_path.read_text(), "seed"),
            )
            seeded += 1

        conn.commit()
        if seeded:
            print(f"  seeded {seeded} prompt versions")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", action="store_true", help="drop pehero schemas first")
    args = ap.parse_args()
    migrate(drop=args.drop)
