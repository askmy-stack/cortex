"""Tests for connectors/linear/producer.py."""

from __future__ import annotations

from connectors.linear.producer import (
    normalise_linear_event,
    verify_linear_signature,
)


def test_verify_linear_signature() -> None:
    body = b'{"type":"Issue"}'
    secret = "test-secret"
    import hashlib
    import hmac

    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_linear_signature(body, sig, secret) is True
    assert verify_linear_signature(body, "bad", secret) is False


def test_normalise_issue_create() -> None:
    payload = {
        "type": "Issue",
        "action": "create",
        "data": {
            "id": "issue-1",
            "title": "Add tracing",
            "description": "Use OTel",
            "identifier": "ENG-1",
            "team": {"key": "ENG"},
            "state": {"name": "Todo"},
            "creator": {"email": "alice@co.com"},
            "createdAt": "2026-05-11T12:00:00Z",
        },
    }
    raw = normalise_linear_event(payload, "ws-1")
    assert raw is not None
    assert raw.source == "linear"
    assert raw.event_type == "linear:issue:create"
    assert "Add tracing" in raw.content


def test_normalise_skips_unknown_type() -> None:
    assert normalise_linear_event({"type": "Project"}, "ws-1") is None


def test_normalise_comment_create() -> None:
    payload = {
        "type": "Comment",
        "action": "create",
        "data": {
            "id": "cmt-1",
            "body": "We decided to use OTel for tracing.",
            "createdAt": "2026-05-11T12:00:00Z",
            "user": {"email": "bob@co.com"},
            "issue": {
                "id": "issue-1",
                "identifier": "ENG-9",
                "team": {"key": "ENG"},
            },
        },
    }
    raw = normalise_linear_event(payload, "ws-1")
    assert raw is not None
    assert raw.event_type == "linear:comment:create"
    assert "OTel" in raw.content
