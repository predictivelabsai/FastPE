"""BYOK persistence layer — a small, self-contained SQLite store.

Deliberately ORM-agnostic (raw ``sqlite3``) so the whole ``byok/`` package can be
copied verbatim into any FastSME product regardless of its own data layer. The
store keeps, per *organization*:

  - an optional encrypted LLM API key (the org's "bring your own key"), and
  - a lifetime counter of free queries spent on the deployment's house key.

The database path is ``$BYOK_DB`` or ``byok.sqlite`` beside this file. Point
``BYOK_DB`` at a mounted volume in production so keys/quota survive restarts.
API keys are encrypted at rest with Fernet using ``$BYOK_ENCRYPTION_KEY``.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("byok")

DB_PATH = os.getenv("BYOK_DB") or str(Path(__file__).parent / "byok.sqlite")

_INIT = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init() -> None:
    global _INIT
    if _INIT:
        return
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS byok_credentials(
                   org_id       TEXT PRIMARY KEY,
                   provider     TEXT,
                   api_key_enc  TEXT,
                   model        TEXT,
                   free_used    INTEGER NOT NULL DEFAULT 0,
                   created      TEXT,
                   updated      TEXT)"""
        )
    _INIT = True


# --- encryption -------------------------------------------------------------

def _fernet():
    from cryptography.fernet import Fernet

    raw = os.getenv("BYOK_ENCRYPTION_KEY", "").strip()
    if raw:
        try:
            return Fernet(raw.encode())
        except Exception:
            # Not a valid Fernet key — treat the value as a passphrase and derive one.
            key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
            return Fernet(key)
    log.warning(
        "BYOK_ENCRYPTION_KEY is not set — falling back to an INSECURE dev key. "
        "Stored API keys are NOT safe. Set BYOK_ENCRYPTION_KEY in production."
    )
    key = base64.urlsafe_b64encode(hashlib.sha256(b"byok-insecure-dev-key").digest())
    return Fernet(key)


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


# --- records ----------------------------------------------------------------

def get_record(org_id: str) -> dict | None:
    init()
    with _conn() as c:
        r = c.execute(
            "SELECT * FROM byok_credentials WHERE org_id=?", (org_id,)
        ).fetchone()
        return dict(r) if r else None


def ensure_record(org_id: str) -> dict:
    rec = get_record(org_id)
    if rec:
        return rec
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO byok_credentials(org_id,free_used,created,updated) "
            "VALUES(?,0,?,?)",
            (org_id, _now(), _now()),
        )
    return get_record(org_id)


def set_key(org_id: str, provider: str, api_key: str, model: str | None = None) -> None:
    init()
    enc = encrypt(api_key)
    now = _now()
    with _conn() as c:
        c.execute(
            """INSERT INTO byok_credentials(org_id,provider,api_key_enc,model,free_used,created,updated)
                   VALUES(?,?,?,?,0,?,?)
               ON CONFLICT(org_id) DO UPDATE SET
                   provider=excluded.provider,
                   api_key_enc=excluded.api_key_enc,
                   model=excluded.model,
                   updated=excluded.updated""",
            (org_id, provider, enc, model, now, now),
        )


def clear_key(org_id: str) -> None:
    init()
    with _conn() as c:
        c.execute(
            "UPDATE byok_credentials SET provider=NULL,api_key_enc=NULL,model=NULL,updated=? "
            "WHERE org_id=?",
            (_now(), org_id),
        )


def has_key(org_id: str) -> bool:
    r = get_record(org_id)
    return bool(r and r["api_key_enc"])


def get_key(org_id: str) -> tuple[str, str, str | None] | None:
    """Return (provider, decrypted_api_key, model) or None if no key is stored."""
    r = get_record(org_id)
    if not r or not r["api_key_enc"]:
        return None
    return r["provider"], decrypt(r["api_key_enc"]), r["model"]


def free_used(org_id: str) -> int:
    r = get_record(org_id)
    return int(r["free_used"]) if r else 0


def increment_free(org_id: str) -> int:
    ensure_record(org_id)
    with _conn() as c:
        c.execute(
            "UPDATE byok_credentials SET free_used=free_used+1,updated=? WHERE org_id=?",
            (_now(), org_id),
        )
    return free_used(org_id)
