"""Tests for connectors/jira/producer.py.

Tests cover:
- issue_created normalisation
- issue_updated (signal changes only — status transitions, priority, assignee)
- issue_updated with no-signal changes (skipped)
- issue_commented normalisation
- sprint_started / sprint_closed normalisation
- ADF (Atlassian Document Format) text extraction
- Unhandled event types skipped
- Kafka publish (mocked)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from connectors.jira.producer import (
    JiraConnector,
    _extract_adf_text,
    _get_account_name,
    normalise_jira_event,
)

WORKSPACE_ID = "test-workspace"


# ─────────────────────────────────────────────────────────────────────────────
# Payload builders
# ─────────────────────────────────────────────────────────────────────────────


def _issue_created_payload(
    issue_key: str = "PAY-42",
    summary: str = "Payments service crashes at 10M txn/day",
    description: str = "We need to migrate to CockroachDB.",
    project_key: str = "PAY",
    issue_type: str = "Bug",
) -> dict:
    return {
        "webhookEvent": "jira:issue_created",
        "issue": {
            "key": issue_key,
            "fields": {
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
                "project": {"key": project_key},
                "priority": {"name": "High"},
                "reporter": {"emailAddress": "dan@company.com", "displayName": "Dan"},
                "labels": [],
                "components": [],
                "fixVersions": [],
                "created": "2026-05-11T12:00:00.000+0000",
            },
        },
    }


def _issue_updated_payload(
    issue_key: str = "PAY-42",
    from_status: str = "In Progress",
    to_status: str = "Done",
) -> dict:
    return {
        "webhookEvent": "jira:issue_updated",
        "user": {"emailAddress": "priya@company.com"},
        "issue": {
            "key": issue_key,
            "fields": {
                "summary": "Payments migration",
                "project": {"key": "PAY"},
                "updated": "2026-05-11T13:00:00.000+0000",
            },
        },
        "changelog": {
            "id": "10001",
            "items": [
                {
                    "field": "status",
                    "fromString": from_status,
                    "toString": to_status,
                }
            ],
        },
    }


def _issue_commented_payload(
    issue_key: str = "PAY-42",
    comment_body: str = "We decided to use CockroachDB for this.",
) -> dict:
    return {
        "webhookEvent": "jira:issue_commented",
        "issue": {
            "key": issue_key,
            "fields": {
                "summary": "Payments migration",
                "project": {"key": "PAY"},
            },
        },
        "comment": {
            "id": "20001",
            "body": comment_body,
            "author": {"emailAddress": "priya@company.com"},
            "created": "2026-05-11T14:00:00.000+0000",
        },
    }


def _sprint_payload(event: str, sprint_name: str = "Sprint 12") -> dict:
    return {
        "webhookEvent": event,
        "sprint": {
            "id": 12,
            "name": sprint_name,
            "goal": "Ship payments migration",
            "state": "active" if event == "jira:sprint_started" else "closed",
            "originBoardId": 5,
            "startDate": "2026-05-11T09:00:00.000+0000",
            "endDate": "2026-05-25T09:00:00.000+0000",
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# ADF text extraction
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractAdfText:
    def test_plain_text_node(self) -> None:
        adf = {
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Hello world"}]}
            ]
        }
        assert "Hello world" in _extract_adf_text(adf)

    def test_multiple_paragraphs(self) -> None:
        adf = {
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "First."}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Second."}]},
            ]
        }
        result = _extract_adf_text(adf)
        assert "First." in result
        assert "Second." in result

    def test_empty_adf_returns_empty_string(self) -> None:
        assert _extract_adf_text({}) == ""

    def test_nested_adf(self) -> None:
        adf = {
            "content": [
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Bullet point"}],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        assert "Bullet point" in _extract_adf_text(adf)


# ─────────────────────────────────────────────────────────────────────────────
# User name extraction
# ─────────────────────────────────────────────────────────────────────────────


class TestGetAccountName:
    def test_email_preferred_over_display_name(self) -> None:
        user = {"emailAddress": "alice@co.com", "displayName": "Alice"}
        assert _get_account_name(user) == "alice@co.com"

    def test_display_name_fallback(self) -> None:
        user = {"displayName": "Alice"}
        assert _get_account_name(user) == "Alice"

    def test_account_id_fallback(self) -> None:
        user = {"accountId": "5def1234abc"}
        assert _get_account_name(user) == "5def1234abc"

    def test_none_returns_unknown(self) -> None:
        assert _get_account_name(None) == "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Issue created
# ─────────────────────────────────────────────────────────────────────────────


class TestNormaliseIssueCreated:
    def test_produces_raw_event(self) -> None:
        result = normalise_jira_event(
            _issue_created_payload(), "jira:issue_created", WORKSPACE_ID
        )
        assert result is not None
        assert result.source == "jira"
        assert result.event_type == "jira:issue_created"
        assert result.source_id == "PAY-42"

    def test_content_includes_summary(self) -> None:
        result = normalise_jira_event(
            _issue_created_payload(summary="Migrate to CockroachDB"),
            "jira:issue_created",
            WORKSPACE_ID,
        )
        assert result is not None
        assert "Migrate to CockroachDB" in result.content

    def test_author_is_reporter_email(self) -> None:
        result = normalise_jira_event(
            _issue_created_payload(), "jira:issue_created", WORKSPACE_ID
        )
        assert result is not None
        assert result.author == "dan@company.com"

    def test_channel_is_project_key(self) -> None:
        result = normalise_jira_event(
            _issue_created_payload(project_key="ENG"),
            "jira:issue_created",
            WORKSPACE_ID,
        )
        assert result is not None
        assert result.channel == "ENG"

    def test_metadata_has_issue_key(self) -> None:
        result = normalise_jira_event(
            _issue_created_payload(issue_key="ENG-99"),
            "jira:issue_created",
            WORKSPACE_ID,
        )
        assert result is not None
        assert result.metadata["issue_key"] == "ENG-99"


# ─────────────────────────────────────────────────────────────────────────────
# Issue updated
# ─────────────────────────────────────────────────────────────────────────────


class TestNormaliseIssueUpdated:
    def test_status_done_produces_raw_event(self) -> None:
        result = normalise_jira_event(
            _issue_updated_payload(to_status="Done"),
            "jira:issue_updated",
            WORKSPACE_ID,
        )
        assert result is not None
        assert "Done" in result.content

    def test_status_resolved_produces_raw_event(self) -> None:
        result = normalise_jira_event(
            _issue_updated_payload(to_status="Resolved"),
            "jira:issue_updated",
            WORKSPACE_ID,
        )
        assert result is not None

    def test_non_signal_status_transition_skipped(self) -> None:
        payload = _issue_updated_payload(to_status="To Do")
        result = normalise_jira_event(payload, "jira:issue_updated", WORKSPACE_ID)
        assert result is None

    def test_priority_change_produces_raw_event(self) -> None:
        payload = {
            "webhookEvent": "jira:issue_updated",
            "user": {"emailAddress": "priya@company.com"},
            "issue": {
                "key": "PAY-42",
                "fields": {
                    "summary": "Payments migration",
                    "project": {"key": "PAY"},
                    "updated": "2026-05-11T13:00:00.000+0000",
                },
            },
            "changelog": {
                "id": "10002",
                "items": [
                    {
                        "field": "priority",
                        "fromString": "Medium",
                        "toString": "Critical",
                    }
                ],
            },
        }
        result = normalise_jira_event(payload, "jira:issue_updated", WORKSPACE_ID)
        assert result is not None
        assert "Critical" in result.content

    def test_empty_changelog_skipped(self) -> None:
        payload = _issue_updated_payload()
        payload["changelog"]["items"] = []
        result = normalise_jira_event(payload, "jira:issue_updated", WORKSPACE_ID)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Issue commented
# ─────────────────────────────────────────────────────────────────────────────


class TestNormaliseIssueCommented:
    def test_produces_raw_event_with_body(self) -> None:
        result = normalise_jira_event(
            _issue_commented_payload(comment_body="We need to migrate to CockroachDB."),
            "jira:issue_commented",
            WORKSPACE_ID,
        )
        assert result is not None
        assert "CockroachDB" in result.content

    def test_empty_comment_skipped(self) -> None:
        result = normalise_jira_event(
            _issue_commented_payload(comment_body=""),
            "jira:issue_commented",
            WORKSPACE_ID,
        )
        assert result is None

    def test_author_is_commenter_email(self) -> None:
        result = normalise_jira_event(
            _issue_commented_payload(), "jira:issue_commented", WORKSPACE_ID
        )
        assert result is not None
        assert result.author == "priya@company.com"


# ─────────────────────────────────────────────────────────────────────────────
# Sprint events
# ─────────────────────────────────────────────────────────────────────────────


class TestNormaliseSprintEvents:
    def test_sprint_started_produces_raw_event(self) -> None:
        result = normalise_jira_event(
            _sprint_payload("jira:sprint_started"), "jira:sprint_started", WORKSPACE_ID
        )
        assert result is not None
        assert result.event_type == "jira:sprint_started"
        assert "started" in result.content

    def test_sprint_closed_produces_raw_event(self) -> None:
        result = normalise_jira_event(
            _sprint_payload("jira:sprint_closed"), "jira:sprint_closed", WORKSPACE_ID
        )
        assert result is not None
        assert result.event_type == "jira:sprint_closed"
        assert "closed" in result.content

    def test_sprint_goal_included_in_content(self) -> None:
        result = normalise_jira_event(
            _sprint_payload("jira:sprint_started"),
            "jira:sprint_started",
            WORKSPACE_ID,
        )
        assert result is not None
        assert "Ship payments migration" in result.content

    def test_sprint_metadata_has_sprint_id(self) -> None:
        result = normalise_jira_event(
            _sprint_payload("jira:sprint_started"), "jira:sprint_started", WORKSPACE_ID
        )
        assert result is not None
        assert result.metadata["sprint_id"] == "12"


# ─────────────────────────────────────────────────────────────────────────────
# Unhandled events
# ─────────────────────────────────────────────────────────────────────────────


class TestUnhandledJiraEvents:
    @pytest.mark.parametrize(
        "event_name",
        [
            "jira:worklog_created",
            "jira:version_released",
            "jira:board_created",
            "jira:project_created",
        ],
    )
    def test_unhandled_event_returns_none(self, event_name: str) -> None:
        result = normalise_jira_event({}, event_name, WORKSPACE_ID)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# JiraConnector
# ─────────────────────────────────────────────────────────────────────────────


class TestJiraConnector:
    @patch("connectors.jira.producer.Producer")
    def test_handle_event_publishes_and_returns_ok(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer = MagicMock()
        mock_producer.flush.return_value = 0
        mock_producer_cls.return_value = mock_producer
        connector = JiraConnector(workspace_id=WORKSPACE_ID)
        result = connector.handle_event(_issue_created_payload())
        assert result["status"] == "ok"
        assert "event_id" in result
        mock_producer.flush.assert_called_once()

    @patch("connectors.jira.producer.Producer")
    def test_unhandled_event_returns_skipped(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer_cls.return_value = MagicMock()
        connector = JiraConnector(workspace_id=WORKSPACE_ID)
        result = connector.handle_event({"webhookEvent": "jira:board_created"})
        assert result["status"] == "skipped"
