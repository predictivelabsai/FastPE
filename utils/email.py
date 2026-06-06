"""Postmark email sender for PEHero."""
from __future__ import annotations

import logging
import os

import httpx

from utils.config import settings

log = logging.getLogger(__name__)

POSTMARK_API_URL = "https://api.postmarkapp.com/email"


def send_email(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str = "",
    from_email: str | None = None,
    tag: str = "",
) -> dict:
    s = settings()
    token = s.postmark_api_token
    if not token:
        log.warning("POSTMARK_API_TOKEN not set — email not sent to %s", to)
        return {"error": "POSTMARK_API_TOKEN not set"}

    sender = from_email or s.from_email
    sender_name = s.from_name
    if sender_name and "<" not in sender:
        sender = f"{sender_name} <{sender}>"

    payload = {
        "From": sender,
        "To": to,
        "Subject": subject,
        "HtmlBody": html_body,
        "MessageStream": "outbound",
    }
    if text_body:
        payload["TextBody"] = text_body
    if tag:
        payload["Tag"] = tag

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": token,
    }

    try:
        resp = httpx.post(POSTMARK_API_URL, headers=headers,
                          json=payload, timeout=15)
        result = resp.json()
        if resp.status_code == 200 and result.get("ErrorCode") == 0:
            log.info("Email sent to %s: %s", to, result.get("MessageID"))
        else:
            log.error("Postmark error: %s", result)
        return result
    except Exception:
        log.exception("Postmark send failed")
        return {"error": "send failed"}
