"""GitHub connector — transforms GitHub webhook payloads into RawEvents.

Handles:
  - pull_request (opened, merged, closed, review_requested)
  - pull_request_review (submitted — approved, changes_requested)
  - issue_comment (PR thread comments)
  - pull_request_review_comment (inline review comments)
  - push (commits to default branch)
  - issues (opened, closed, labeled)

Architecture (ARCHITECTURE.md, Layer 1):
  Stateless — no business logic beyond schema normalisation.
  Publishes to Kafka topic: cortex.raw.github.events

Decision: D-001 — Kafka as single event bus.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime
from typing import Any

import structlog
from confluent_kafka import KafkaException, Producer
from pydantic import ValidationError

from shared.models import RawEvent

log = structlog.get_logger(__name__)

KAFKA_TOPIC = "cortex.raw.github.events"
SCHEMA_VERSION = "1.0"

_HANDLED_EVENTS = frozenset(
    {
        "pull_request",
        "pull_request_review",
        "pull_request_review_comment",
        "issue_comment",
        "push",
        "issues",
    }
)


# ─────────────────────────────────────────────────────────────────────────────
# Webhook signature verification
# ─────────────────────────────────────────────────────────────────────────────


def verify_github_signature(
    payload_bytes: bytes,
    signature_header: str,
    secret: str,
) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature.

    Args:
        payload_bytes: Raw request body bytes.
        signature_header: Value of X-Hub-Signature-256 header.
        secret: GitHub webhook secret from env.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


# ─────────────────────────────────────────────────────────────────────────────
# GitHub event normalisers
# ─────────────────────────────────────────────────────────────────────────────


def _parse_timestamp(ts_str: str | None) -> datetime:
    """Parse ISO 8601 timestamp string from GitHub payload."""
    if not ts_str:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(UTC)


def _normalise_pull_request(
    payload: dict[str, Any],
    workspace_id: str,
) -> RawEvent | None:
    """Normalise a pull_request event."""
    action = payload.get("action", "")
    pr = payload.get("pull_request", {})

    if action not in {"opened", "closed", "merged", "review_requested"}:
        return None

    repo = payload.get("repository", {})
    repo_name = repo.get("full_name", "unknown")

    is_merged = pr.get("merged", False)
    actual_action = "merged" if (action == "closed" and is_merged) else action

    title = pr.get("title", "")
    body = pr.get("body") or ""
    content = f"PR {actual_action}: {title}"
    if body:
        content += f"\n\n{body[:500]}"

    author = (pr.get("user") or {}).get("login", "unknown")
    pr_number = pr.get("number", 0)

    return RawEvent(
        source="github",
        source_id=f"{repo_name}:pr:{pr_number}",
        workspace_id=workspace_id,
        event_type=f"github:pull_request:{actual_action}",
        content=content,
        author=author,
        channel=repo_name,
        timestamp=_parse_timestamp(pr.get("updated_at") or pr.get("created_at")),
        metadata={
            "pr_number": pr_number,
            "action": actual_action,
            "base_branch": (pr.get("base") or {}).get("ref", ""),
            "head_branch": (pr.get("head") or {}).get("ref", ""),
            "merged": is_merged,
            "reviewers": [
                r.get("login") for r in pr.get("requested_reviewers", [])
            ],
            "labels": [lb.get("name") for lb in pr.get("labels", [])],
            "repo": repo_name,
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),
        },
        schema_version=SCHEMA_VERSION,
    )


def _normalise_pull_request_review(
    payload: dict[str, Any],
    workspace_id: str,
) -> RawEvent | None:
    """Normalise a pull_request_review event."""
    review = payload.get("review", {})
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    repo_name = repo.get("full_name", "unknown")

    state = review.get("state", "").lower()
    if state not in {"approved", "changes_requested", "dismissed"}:
        return None

    body = review.get("body") or ""
    pr_title = pr.get("title", "")
    content = f"PR review ({state}): {pr_title}"
    if body:
        content += f"\n\n{body[:500]}"

    author = (review.get("user") or {}).get("login", "unknown")
    pr_number = pr.get("number", 0)
    review_id = review.get("id", 0)

    return RawEvent(
        source="github",
        source_id=f"{repo_name}:review:{review_id}",
        workspace_id=workspace_id,
        event_type=f"github:pull_request_review:{state}",
        content=content,
        author=author,
        channel=repo_name,
        timestamp=_parse_timestamp(review.get("submitted_at")),
        metadata={
            "pr_number": pr_number,
            "review_id": review_id,
            "state": state,
            "repo": repo_name,
        },
        schema_version=SCHEMA_VERSION,
    )


def _normalise_push(
    payload: dict[str, Any],
    workspace_id: str,
) -> RawEvent | None:
    """Normalise a push event — only default branch pushes."""
    ref = payload.get("ref", "")
    repo = payload.get("repository", {})
    default_branch = repo.get("default_branch", "main")

    if ref != f"refs/heads/{default_branch}":
        log.debug("github.push.skipped", ref=ref, reason="non_default_branch")
        return None

    commits: list[dict] = payload.get("commits", [])
    if not commits:
        return None

    repo_name = repo.get("full_name", "unknown")
    pusher = (payload.get("pusher") or {}).get("name", "unknown")
    commit_messages = [c.get("message", "").split("\n")[0] for c in commits[:5]]
    content = f"Push to {default_branch} ({len(commits)} commit{'s' if len(commits) != 1 else ''}):\n" + "\n".join(
        f"- {m}" for m in commit_messages
    )

    head_commit = commits[-1]
    timestamp_str = head_commit.get("timestamp")

    return RawEvent(
        source="github",
        source_id=f"{repo_name}:push:{head_commit.get('id', '')[:8]}",
        workspace_id=workspace_id,
        event_type="github:push",
        content=content,
        author=pusher,
        channel=repo_name,
        timestamp=_parse_timestamp(timestamp_str),
        metadata={
            "ref": ref,
            "commit_count": len(commits),
            "head_commit_id": head_commit.get("id", ""),
            "head_commit_message": head_commit.get("message", "").split("\n")[0],
            "repo": repo_name,
            "forced": payload.get("forced", False),
        },
        schema_version=SCHEMA_VERSION,
    )


def _normalise_issue(
    payload: dict[str, Any],
    workspace_id: str,
) -> RawEvent | None:
    """Normalise an issues event."""
    action = payload.get("action", "")
    if action not in {"opened", "closed", "labeled"}:
        return None

    issue = payload.get("issue", {})
    repo = payload.get("repository", {})
    repo_name = repo.get("full_name", "unknown")

    title = issue.get("title", "")
    body = issue.get("body") or ""
    content = f"Issue {action}: {title}"
    if body and action == "opened":
        content += f"\n\n{body[:500]}"

    author = (issue.get("user") or {}).get("login", "unknown")
    issue_number = issue.get("number", 0)

    return RawEvent(
        source="github",
        source_id=f"{repo_name}:issue:{issue_number}",
        workspace_id=workspace_id,
        event_type=f"github:issue:{action}",
        content=content,
        author=author,
        channel=repo_name,
        timestamp=_parse_timestamp(issue.get("updated_at") or issue.get("created_at")),
        metadata={
            "issue_number": issue_number,
            "action": action,
            "labels": [lb.get("name") for lb in issue.get("labels", [])],
            "state": issue.get("state", ""),
            "repo": repo_name,
        },
        schema_version=SCHEMA_VERSION,
    )


def _normalise_issue_comment(
    payload: dict[str, Any],
    workspace_id: str,
) -> RawEvent | None:
    """Normalise issue_comment events — PR thread comments only."""
    action = payload.get("action", "")
    if action not in {"created", "edited"}:
        return None

    issue = payload.get("issue", {})
    if not issue.get("pull_request"):
        return None

    comment = payload.get("comment", {})
    body = (comment.get("body") or "").strip()
    if not body:
        return None

    repo = payload.get("repository", {})
    repo_name = repo.get("full_name", "unknown")
    pr_number = issue.get("number", 0)
    comment_id = comment.get("id", 0)
    author = (comment.get("user") or {}).get("login", "unknown")

    return RawEvent(
        source="github",
        source_id=f"{repo_name}:pr_comment:{comment_id}",
        workspace_id=workspace_id,
        event_type=f"github:issue_comment:{action}",
        content=f"PR #{pr_number} comment ({action}): {body[:800]}",
        author=author,
        channel=repo_name,
        timestamp=_parse_timestamp(comment.get("updated_at") or comment.get("created_at")),
        metadata={
            "pr_number": pr_number,
            "comment_id": comment_id,
            "action": action,
            "repo": repo_name,
        },
        schema_version=SCHEMA_VERSION,
    )


def _normalise_pull_request_review_comment(
    payload: dict[str, Any],
    workspace_id: str,
) -> RawEvent | None:
    """Normalise inline pull_request_review_comment events."""
    if payload.get("action") != "created":
        return None

    comment = payload.get("comment", {})
    body = (comment.get("body") or "").strip()
    if not body:
        return None

    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    repo_name = repo.get("full_name", "unknown")
    pr_number = pr.get("number", 0)
    comment_id = comment.get("id", 0)
    author = (comment.get("user") or {}).get("login", "unknown")

    return RawEvent(
        source="github",
        source_id=f"{repo_name}:review_comment:{comment_id}",
        workspace_id=workspace_id,
        event_type="github:pull_request_review_comment:created",
        content=f"PR #{pr_number} review comment: {body[:800]}",
        author=author,
        channel=repo_name,
        timestamp=_parse_timestamp(comment.get("updated_at") or comment.get("created_at")),
        metadata={
            "pr_number": pr_number,
            "comment_id": comment_id,
            "path": comment.get("path", ""),
            "repo": repo_name,
        },
        schema_version=SCHEMA_VERSION,
    )


_NORMALISERS = {
    "pull_request": _normalise_pull_request,
    "pull_request_review": _normalise_pull_request_review,
    "pull_request_review_comment": _normalise_pull_request_review_comment,
    "issue_comment": _normalise_issue_comment,
    "push": _normalise_push,
    "issues": _normalise_issue,
}


def normalise_github_event(
    payload: dict[str, Any],
    event_type: str,
    workspace_id: str,
) -> RawEvent | None:
    """Route a GitHub webhook payload to the correct normaliser.

    Args:
        payload: Parsed webhook JSON body.
        event_type: Value of the X-GitHub-Event header.
        workspace_id: Cortex workspace identifier.

    Returns:
        RawEvent if processable, None otherwise.
    """
    if event_type not in _HANDLED_EVENTS:
        log.debug("github.event.skipped", event_type=event_type, reason="not_handled")
        return None

    normaliser = _NORMALISERS.get(event_type)
    if normaliser is None:
        return None

    try:
        return normaliser(payload, workspace_id)
    except (KeyError, ValidationError) as exc:
        log.error(
            "github.event.normalisation_failed",
            event_type=event_type,
            error=str(exc),
        )
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Kafka producer
# ─────────────────────────────────────────────────────────────────────────────


def _delivery_callback(err: Any, msg: Any) -> None:
    if err:
        log.error(
            "kafka.delivery.failed",
            topic=msg.topic(),
            error=str(err),
        )
    else:
        log.info(
            "kafka.delivery.success",
            topic=msg.topic(),
            partition=msg.partition(),
            offset=msg.offset(),
        )


class GitHubKafkaProducer:
    """Publishes normalised GitHub RawEvents to Kafka."""

    def __init__(self, bootstrap_servers: str | None = None) -> None:
        servers = bootstrap_servers or os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self._producer = Producer(
            {
                "bootstrap.servers": servers,
                "acks": "all",
                "retries": 5,
                "retry.backoff.ms": 300,
                "delivery.timeout.ms": 30000,
                "enable.idempotence": True,
                "compression.type": "snappy",
                "batch.size": 16384,
                "linger.ms": 100,
            }
        )
        log.info("github.producer.initialized", bootstrap_servers=servers)

    def publish(self, raw_event: RawEvent) -> None:
        key = f"{raw_event.workspace_id}:{raw_event.source_id}".encode()
        payload = raw_event.model_dump_json().encode("utf-8")
        try:
            self._producer.produce(
                topic=KAFKA_TOPIC,
                key=key,
                value=payload,
                callback=_delivery_callback,
            )
            self._producer.poll(0)
        except KafkaException as exc:
            log.error(
                "kafka.produce.failed",
                topic=KAFKA_TOPIC,
                event_id=raw_event.event_id,
                error=str(exc),
            )
            raise

        log.info(
            "github.event.published",
            event_id=raw_event.event_id,
            source_id=raw_event.source_id,
            event_type=raw_event.event_type,
        )

    def flush(self, timeout: float = 10.0) -> None:
        remaining = self._producer.flush(timeout)
        if remaining > 0:
            log.warning("kafka.flush.incomplete", remaining_messages=remaining)

    def close(self) -> None:
        self.flush()
        log.info("github.producer.closed")


# ─────────────────────────────────────────────────────────────────────────────
# GitHub connector
# ─────────────────────────────────────────────────────────────────────────────


class GitHubConnector:
    """Entry point for the GitHub connector.

    Instantiate once per process. Call handle_event() for every incoming
    GitHub webhook payload.
    """

    def __init__(
        self,
        workspace_id: str | None = None,
        bootstrap_servers: str | None = None,
        webhook_secret: str | None = None,
    ) -> None:
        self.workspace_id = workspace_id or os.environ.get(
            "CORTEX_WORKSPACE_ID", "local-dev"
        )
        self._webhook_secret = webhook_secret or os.environ.get(
            "GITHUB_WEBHOOK_SECRET", ""
        )
        self._producer = GitHubKafkaProducer(bootstrap_servers=bootstrap_servers)
        log.info(
            "github.connector.initialized",
            workspace_id=self.workspace_id,
            signature_verification=bool(self._webhook_secret),
        )

    def handle_event(
        self,
        payload: dict[str, Any],
        event_type: str,
        signature: str | None = None,
        raw_body: bytes | None = None,
    ) -> dict[str, str]:
        """Process an incoming GitHub webhook payload.

        Args:
            payload: Parsed JSON body.
            event_type: X-GitHub-Event header value.
            signature: X-Hub-Signature-256 header value (optional, for verification).
            raw_body: Raw request body bytes for signature verification.

        Returns:
            {"status": "ok", "event_id": ...} | {"status": "skipped", ...}
        """
        # When a secret is configured, verification is mandatory: a missing
        # signature or body must be rejected, not silently skipped.
        if self._webhook_secret and not (
            signature
            and raw_body
            and verify_github_signature(raw_body, signature, self._webhook_secret)
        ):
            log.warning("github.webhook.signature_invalid")
            return {"status": "error", "reason": "invalid_signature"}

        raw_event = normalise_github_event(payload, event_type, self.workspace_id)
        if raw_event is None:
            return {"status": "skipped", "reason": "not_processable"}

        self._producer.publish(raw_event)
        self._producer.flush(timeout=5.0)
        return {"status": "ok", "event_id": raw_event.event_id}

    def close(self) -> None:
        self._producer.close()
