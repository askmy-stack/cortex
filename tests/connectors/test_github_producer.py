"""Tests for connectors/github/producer.py.

Tests cover:
- PR opened/merged/closed normalisation
- PR review normalisation (approved, changes_requested)
- Push to default branch (commits collapsed)
- Push to non-default branch (skipped)
- Issue created/closed/labeled normalisation
- Unhandled event types skipped
- Webhook signature verification
- Kafka publish (mocked)
"""

from __future__ import annotations

import hashlib
import hmac
from unittest.mock import MagicMock, patch

import pytest

from connectors.github.producer import (
    GitHubConnector,
    normalise_github_event,
    verify_github_signature,
)

WORKSPACE_ID = "test-workspace"


# ─────────────────────────────────────────────────────────────────────────────
# Payload builders
# ─────────────────────────────────────────────────────────────────────────────


def _pr_payload(
    action: str = "opened",
    merged: bool = False,
    title: str = "Migrate payments to CockroachDB",
    body: str = "",
    pr_number: int = 42,
    repo: str = "acme/payments",
) -> dict:
    return {
        "action": action,
        "pull_request": {
            "number": pr_number,
            "title": title,
            "body": body,
            "merged": merged,
            "user": {"login": "priya"},
            "base": {"ref": "main"},
            "head": {"ref": "feature/cockroachdb"},
            "updated_at": "2026-05-11T12:00:00Z",
            "created_at": "2026-05-11T11:00:00Z",
            "labels": [],
            "requested_reviewers": [],
            "additions": 120,
            "deletions": 30,
        },
        "repository": {"full_name": repo, "default_branch": "main"},
    }


def _review_payload(
    state: str = "approved",
    pr_number: int = 42,
    repo: str = "acme/payments",
) -> dict:
    return {
        "action": "submitted",
        "review": {
            "id": 9999,
            "state": state,
            "body": f"LGTM — {state}",
            "user": {"login": "dan"},
            "submitted_at": "2026-05-11T13:00:00Z",
        },
        "pull_request": {
            "number": pr_number,
            "title": "Migrate payments to CockroachDB",
        },
        "repository": {"full_name": repo},
    }


def _push_payload(
    ref: str = "refs/heads/main",
    commits: list[dict] | None = None,
    repo: str = "acme/payments",
) -> dict:
    if commits is None:
        commits = [
            {
                "id": "abc123def456",
                "message": "feat: add CockroachDB driver\nLong description here",
                "timestamp": "2026-05-11T12:00:00Z",
            }
        ]
    return {
        "ref": ref,
        "commits": commits,
        "pusher": {"name": "priya"},
        "repository": {"full_name": repo, "default_branch": "main"},
        "forced": False,
    }


def _issue_payload(
    action: str = "opened",
    issue_number: int = 99,
    repo: str = "acme/payments",
) -> dict:
    return {
        "action": action,
        "issue": {
            "number": issue_number,
            "title": "Payments service crashes on 10M+ transactions",
            "body": "Detailed description of the crash...",
            "state": "open" if action == "opened" else "closed",
            "user": {"login": "dan"},
            "created_at": "2026-05-11T10:00:00Z",
            "updated_at": "2026-05-11T10:00:00Z",
            "labels": [],
        },
        "repository": {"full_name": repo},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Signature verification
# ─────────────────────────────────────────────────────────────────────────────


class TestVerifyGithubSignature:
    def test_valid_signature_returns_true(self) -> None:
        secret = "my-webhook-secret"
        body = b'{"test": "payload"}'
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_github_signature(body, sig, secret) is True

    def test_invalid_signature_returns_false(self) -> None:
        body = b'{"test": "payload"}'
        assert verify_github_signature(body, "sha256=wrongsig", "secret") is False

    def test_missing_sha256_prefix_returns_false(self) -> None:
        body = b'{"test": "payload"}'
        assert verify_github_signature(body, "invalidsig", "secret") is False

    def test_tampered_body_returns_false(self) -> None:
        secret = "my-webhook-secret"
        body = b'{"test": "payload"}'
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_github_signature(b'{"tampered": true}', sig, secret) is False


# ─────────────────────────────────────────────────────────────────────────────
# Pull request normalisation
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalisePullRequest:
    def test_pr_opened_produces_raw_event(self) -> None:
        result = normalise_github_event(_pr_payload("opened"), "pull_request", WORKSPACE_ID)
        assert result is not None
        assert result.source == "github"
        assert result.event_type == "github:pull_request:opened"
        assert result.author == "priya"
        assert result.channel == "acme/payments"

    def test_pr_merged_produces_merged_event_type(self) -> None:
        result = normalise_github_event(
            _pr_payload("closed", merged=True), "pull_request", WORKSPACE_ID
        )
        assert result is not None
        assert result.event_type == "github:pull_request:merged"
        assert result.metadata["merged"] is True

    def test_pr_closed_without_merge_produces_closed_type(self) -> None:
        result = normalise_github_event(
            _pr_payload("closed", merged=False), "pull_request", WORKSPACE_ID
        )
        assert result is not None
        assert result.event_type == "github:pull_request:closed"

    def test_pr_includes_body_in_content(self) -> None:
        result = normalise_github_event(
            _pr_payload(body="This migrates payments to use distributed SQL."),
            "pull_request",
            WORKSPACE_ID,
        )
        assert result is not None
        assert "distributed SQL" in result.content

    def test_pr_metadata_has_pr_number(self) -> None:
        result = normalise_github_event(
            _pr_payload(pr_number=42), "pull_request", WORKSPACE_ID
        )
        assert result is not None
        assert result.metadata["pr_number"] == 42

    def test_pr_skipped_for_unlisted_action(self) -> None:
        result = normalise_github_event(
            _pr_payload("synchronize"), "pull_request", WORKSPACE_ID
        )
        assert result is None

    def test_pr_source_id_includes_repo_and_number(self) -> None:
        result = normalise_github_event(
            _pr_payload(repo="acme/payments", pr_number=55),
            "pull_request",
            WORKSPACE_ID,
        )
        assert result is not None
        assert result.source_id == "acme/payments:pr:55"


# ─────────────────────────────────────────────────────────────────────────────
# Pull request review normalisation
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalisePRReview:
    def test_approved_review_produces_raw_event(self) -> None:
        result = normalise_github_event(
            _review_payload("approved"), "pull_request_review", WORKSPACE_ID
        )
        assert result is not None
        assert result.event_type == "github:pull_request_review:approved"
        assert result.author == "dan"

    def test_changes_requested_produces_raw_event(self) -> None:
        result = normalise_github_event(
            _review_payload("changes_requested"), "pull_request_review", WORKSPACE_ID
        )
        assert result is not None
        assert result.event_type == "github:pull_request_review:changes_requested"

    def test_commented_review_skipped(self) -> None:
        result = normalise_github_event(
            _review_payload("commented"), "pull_request_review", WORKSPACE_ID
        )
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Push normalisation
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalisePush:
    def test_push_to_default_branch_produces_raw_event(self) -> None:
        result = normalise_github_event(
            _push_payload("refs/heads/main"), "push", WORKSPACE_ID
        )
        assert result is not None
        assert result.event_type == "github:push"
        assert result.author == "priya"

    def test_push_to_non_default_branch_skipped(self) -> None:
        result = normalise_github_event(
            _push_payload("refs/heads/feature/cockroachdb"), "push", WORKSPACE_ID
        )
        assert result is None

    def test_push_content_includes_commit_messages(self) -> None:
        result = normalise_github_event(
            _push_payload(commits=[
                {"id": "abc", "message": "feat: add driver", "timestamp": "2026-05-11T12:00:00Z"},
                {"id": "def", "message": "fix: handle null case", "timestamp": "2026-05-11T12:01:00Z"},
            ]),
            "push",
            WORKSPACE_ID,
        )
        assert result is not None
        assert "feat: add driver" in result.content
        assert "fix: handle null case" in result.content

    def test_empty_commits_returns_none(self) -> None:
        payload = _push_payload()
        payload["commits"] = []
        result = normalise_github_event(payload, "push", WORKSPACE_ID)
        assert result is None

    def test_push_metadata_has_commit_count(self) -> None:
        result = normalise_github_event(_push_payload(), "push", WORKSPACE_ID)
        assert result is not None
        assert result.metadata["commit_count"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Issue normalisation
# ─────────────────────────────────────────────────────────────────────────────


class TestNormaliseIssue:
    def test_issue_opened_produces_raw_event(self) -> None:
        result = normalise_github_event(
            _issue_payload("opened"), "issues", WORKSPACE_ID
        )
        assert result is not None
        assert result.event_type == "github:issue:opened"
        assert result.author == "dan"

    def test_issue_closed_produces_raw_event(self) -> None:
        result = normalise_github_event(
            _issue_payload("closed"), "issues", WORKSPACE_ID
        )
        assert result is not None
        assert result.event_type == "github:issue:closed"

    def test_issue_edited_skipped(self) -> None:
        result = normalise_github_event(
            _issue_payload("edited"), "issues", WORKSPACE_ID
        )
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Unhandled event types
# ─────────────────────────────────────────────────────────────────────────────


class TestUnhandledEvents:
    @pytest.mark.parametrize(
        "event_type",
        ["star", "fork", "watch", "create", "delete", "deployment", "status"],
    )
    def test_unhandled_event_type_returns_none(self, event_type: str) -> None:
        result = normalise_github_event({}, event_type, WORKSPACE_ID)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# GitHubConnector
# ─────────────────────────────────────────────────────────────────────────────


class TestGitHubConnector:
    @patch("connectors.github.producer.Producer")
    def test_handle_event_publishes_and_returns_ok(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer = MagicMock()
        mock_producer.flush.return_value = 0
        mock_producer_cls.return_value = mock_producer
        connector = GitHubConnector(workspace_id=WORKSPACE_ID)
        result = connector.handle_event(
            _pr_payload("opened"), event_type="pull_request"
        )
        assert result["status"] == "ok"
        assert "event_id" in result
        mock_producer.flush.assert_called_once()

    @patch("connectors.github.producer.Producer")
    def test_handle_unhandled_event_returns_skipped(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer_cls.return_value = MagicMock()
        connector = GitHubConnector(workspace_id=WORKSPACE_ID)
        result = connector.handle_event({}, event_type="star")
        assert result["status"] == "skipped"

    @patch("connectors.github.producer.Producer")
    def test_invalid_signature_returns_error(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer_cls.return_value = MagicMock()
        connector = GitHubConnector(
            workspace_id=WORKSPACE_ID, webhook_secret="secret123"
        )
        result = connector.handle_event(
            _pr_payload("opened"),
            event_type="pull_request",
            signature="sha256=badsig",
            raw_body=b'{"action": "opened"}',
        )
        assert result["status"] == "error"
        assert result["reason"] == "invalid_signature"
