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

    _apply("""
        CREATE TABLE IF NOT EXISTS pehero.user_preferences (
            id              SERIAL PRIMARY KEY,
            user_id         INTEGER NOT NULL UNIQUE REFERENCES pehero.users(id),
            phone           VARCHAR(30),
            company         VARCHAR(200),
            role            VARCHAR(200),
            country         VARCHAR(5),
            city            VARCHAR(100),
            currency        VARCHAR(3) DEFAULT 'EUR',
            language        VARCHAR(5) DEFAULT 'en',
            deal_size_min   NUMERIC(14,2),
            deal_size_max   NUMERIC(14,2),
            revenue_min     NUMERIC(14,2),
            revenue_max     NUMERIC(14,2),
            ebitda_min      NUMERIC(14,2),
            ebitda_max      NUMERIC(14,2),
            preferred_sectors    JSONB DEFAULT '[]',
            preferred_deal_types JSONB DEFAULT '[]',
            preferred_geographies JSONB DEFAULT '[]',
            preferred_stage      VARCHAR(30),
            notify_new_deals     BOOLEAN DEFAULT TRUE,
            notify_deal_updates  BOOLEAN DEFAULT TRUE,
            notify_weekly_digest BOOLEAN DEFAULT TRUE,
            updated_at      TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    _apply("""
        ALTER TABLE pehero.user_preferences
            ADD COLUMN IF NOT EXISTS unsubscribe_token VARCHAR(64) UNIQUE;
    """)

    _apply("""
        CREATE TABLE IF NOT EXISTS pehero.digest_sends (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES pehero.users(id),
            subject     TEXT,
            message_id  TEXT,
            sent_at     TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # Persons tables for investor prospecting.
    _apply("""
        CREATE TABLE IF NOT EXISTS pehero.persons (
            id              BIGSERIAL PRIMARY KEY,
            name            TEXT NOT NULL,
            slug            TEXT UNIQUE NOT NULL,
            country         TEXT DEFAULT 'EE',
            wealth_eur      NUMERIC(14,2),
            wealth_rank     INTEGER,
            wealth_source   TEXT,
            sector_exposure TEXT[],
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS persons_slug_idx ON pehero.persons(slug);
        CREATE INDEX IF NOT EXISTS persons_wealth_idx ON pehero.persons(wealth_eur DESC NULLS LAST);

        CREATE TABLE IF NOT EXISTS pehero.person_company_links (
            id              BIGSERIAL PRIMARY KEY,
            person_id       BIGINT NOT NULL REFERENCES pehero.persons(id) ON DELETE CASCADE,
            company_id      BIGINT REFERENCES pehero.companies(id) ON DELETE SET NULL,
            company_name    TEXT NOT NULL,
            reg_code        TEXT,
            role            TEXT NOT NULL,
            stake_pct       NUMERIC(5,2),
            control_desc    TEXT,
            UNIQUE(person_id, company_name, role)
        );
        CREATE INDEX IF NOT EXISTS pcl_person_idx ON pehero.person_company_links(person_id);
        CREATE INDEX IF NOT EXISTS pcl_company_idx ON pehero.person_company_links(company_id);
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
