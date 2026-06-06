"""Postmark email sender."""

from __future__ import annotations

import httpx

from utils.config import settings


def send_email(*, to: str, subject: str, html_body: str, text_body: str = "") -> dict:
    s = settings()
    if not s.postmark_api_token:
        raise RuntimeError("POSTMARK_API_TOKEN not set")
    resp = httpx.post(
        "https://api.postmarkapp.com/email",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": s.postmark_api_token,
        },
        json={
            "From": s.postmark_from_email,
            "To": to,
            "Subject": subject,
            "HtmlBody": html_body,
            "TextBody": text_body or subject,
            "MessageStream": "outbound",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
