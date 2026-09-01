"""Regression tests for browser-safe chat streaming."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import app

routes = app._chat_routes


class _Request:
    session = {}

    async def form(self):
        return {"msg": "scan: revenue for TestCo", "sid": ""}


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args, **_kwargs):
        return None


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return _Cursor()

    def commit(self):
        return None


class _Graph:
    async def astream_events(self, _inputs, version="v2"):
        assert version == "v2"
        yield {
            "event": "on_tool_start",
            "name": "web_search",
            "data": {"input": {"query": "PRIVATE RAW ARGUMENT"}},
        }
        artifact = {
            "kind": "citations",
            "title": "Sources",
            "items": [{
                "title": "Registry",
                "url": "https://example.test",
                "snippet": "# PRIVATE HEADING\n\n| Year | Revenue |\n| --- | --- |\n| 2025 | **EUR 4m** |",
                "score": 0.9,
            }],
        }
        yield {
            "event": "on_tool_end",
            "name": "web_search",
            "data": {"output": "__ARTIFACT__" + json.dumps(artifact)},
        }
        yield {
            "event": "on_chat_model_stream",
            "data": {"chunk": SimpleNamespace(content="Revenue is **EUR 4m**.", tool_call_chunks=None)},
        }


@pytest.mark.asyncio
async def test_chat_stream_never_exposes_raw_tool_payloads(monkeypatch):
    monkeypatch.setattr(routes, "_ensure_user", lambda _sess: (1, "user@example.test"))
    monkeypatch.setattr(routes, "_ensure_session", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(routes, "_persist_message", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(routes, "_session_messages", lambda _sid: [])
    monkeypatch.setattr(routes, "connect", lambda: _Connection())
    monkeypatch.setattr(routes.agent_router, "route", lambda _msg: "market_scanner")
    monkeypatch.setattr(routes.agent_router, "strip_prefix", lambda msg: msg)
    monkeypatch.setattr(routes, "by_slug", lambda _slug: SimpleNamespace(name="Market Scanner", icon="◆"))

    from agents import base
    monkeypatch.setattr(base, "cached_agent", lambda _slug: _Graph())

    response = await routes.chat_stream(_Request())
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    body = "".join(chunks)

    assert "PRIVATE RAW ARGUMENT" not in body
    assert '"output"' not in body
    assert "# PRIVATE HEADING" not in body
    assert "**EUR 4m**" not in next(
        part for part in body.split("\n\n") if part.startswith("event: artifact_show")
    )
    assert "PRIVATE HEADING" in body
    assert "Revenue is **EUR 4m**." in body


def test_plain_artifact_text_removes_markdown_and_html():
    raw = "## Result\n<script>alert(1)</script>\n- **Revenue:** [EUR 4m](https://example.test)"
    assert routes._plain_artifact_text(raw) == "Result Revenue: EUR 4m"


def test_public_artifact_rejects_non_web_links():
    payload = {
        "kind": "citations",
        "items": [{"title": "Bad link", "url": "javascript:alert(1)", "snippet": "# Safe"}],
    }
    assert routes._public_artifact(payload)["items"] == [
        {"title": "Bad link", "url": "", "snippet": "Safe"},
    ]
