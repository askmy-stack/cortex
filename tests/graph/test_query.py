"""Tests for graph/query.py — mocked Neo4j async driver."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from graph.query import GraphQueryService, _causal_chain_query


def _decision_node(
    *,
    event_id: str = "d-1",
    access_policy: str | None = None,
) -> MagicMock:
    node = MagicMock()
    policy = access_policy or (
        '{"roles": ["authenticated"], "deny": [], '
        '"classification": "internal", "gdpr_subject": false}'
    )
    node.get = lambda key, default=None: {
        "id": event_id,
        "event_type": "decision",
        "content": "Use CockroachDB",
        "importance_score": 0.9,
        "trust_score": 0.8,
        "extraction_confidence": 0.95,
        "source": "slack",
        "channel": "C-engineering",
        "extracted_at": "2026-05-11T12:00:00+00:00",
        "status": "active",
        "access_policy": policy,
    }.get(key, default)
    return node


@pytest.mark.asyncio
async def test_find_decisions_by_system_filters_rbac() -> None:
    service = GraphQueryService()
    record = {
        "d": _decision_node(),
        "made_by": ["alice"],
        "affects": ["payments"],
        "rationale": ["scale"],
    }

    async def fake_run(*_args: object, **_kwargs: object) -> AsyncMock:
        result = AsyncMock()

        async def agen() -> object:
            yield record

        result.__aiter__ = lambda self: agen()
        return result

    mock_session = MagicMock()
    mock_session.run = AsyncMock(side_effect=fake_run)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session

    with patch.object(service, "_driver_instance", AsyncMock(return_value=mock_driver)):
        rows = await service.find_decisions_by_system(
            system_id="payments",
            workspace_id="ws-1",
            limit=5,
            caller_roles=["authenticated"],
        )

    assert len(rows) == 1
    assert rows[0]["event_id"] == "d-1"
    assert rows[0]["affects"] == ["payments"]


@pytest.mark.asyncio
async def test_find_decisions_by_system_denies_without_role() -> None:
    service = GraphQueryService()
    policy = (
        '{"roles": ["admin"], "deny": [], '
        '"classification": "confidential", "gdpr_subject": false}'
    )
    record = {
        "d": _decision_node(access_policy=policy),
        "made_by": [],
        "affects": [],
        "rationale": [],
    }

    async def fake_run(*_args: object, **_kwargs: object) -> AsyncMock:
        result = AsyncMock()

        async def agen() -> object:
            yield record

        result.__aiter__ = lambda self: agen()
        return result

    mock_session = MagicMock()
    mock_session.run = AsyncMock(side_effect=fake_run)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session

    with patch.object(service, "_driver_instance", AsyncMock(return_value=mock_driver)):
        rows = await service.find_decisions_by_system(
            system_id="payments",
            workspace_id="ws-1",
            limit=5,
            caller_roles=["authenticated"],
        )

    assert rows == []


def test_causal_chain_query_inlines_depth() -> None:
    """Variable-length depth must be a literal in the rendered Cypher."""
    rendered = _causal_chain_query(3)
    assert "[:SUPERSEDES*1..3]" in rendered
    assert "$max_depth" not in rendered


def test_causal_chain_query_clamps_depth_bounds() -> None:
    """Depth is clamped to ``1..8`` to keep paths bounded."""
    assert "[:SUPERSEDES*1..1]" in _causal_chain_query(0)
    assert "[:SUPERSEDES*1..1]" in _causal_chain_query(-7)
    assert "[:SUPERSEDES*1..8]" in _causal_chain_query(99)


@pytest.mark.asyncio
async def test_trace_causal_chain_uses_inlined_query() -> None:
    service = GraphQueryService()
    record = {
        "d": _decision_node(event_id="d-root"),
        "made_by": ["alice"],
        "affects": ["payments"],
        "rationale": ["scale"],
        "supersedes_ids": ["d-old"],
        "triggered_by_id": None,
    }

    async def fake_run(query: str, **_kwargs: object) -> AsyncMock:
        assert "[:SUPERSEDES*1..4]" in query
        assert "$max_depth" not in query
        result = AsyncMock()

        async def agen() -> object:
            yield record

        result.__aiter__ = lambda self: agen()
        return result

    mock_session = MagicMock()
    mock_session.run = AsyncMock(side_effect=fake_run)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session

    with patch.object(service, "_driver_instance", AsyncMock(return_value=mock_driver)):
        rows = await service.trace_causal_chain(
            decision_id="d-root",
            workspace_id="ws-1",
            max_depth=4,
            caller_roles=["authenticated"],
        )

    assert len(rows) == 1
    assert rows[0]["event_id"] == "d-root"
    assert rows[0]["supersedes_ids"] == ["d-old"]


@pytest.mark.asyncio
async def test_list_pending_contradictions_filters_rbac() -> None:
    service = GraphQueryService()
    policy_open = (
        '{"roles": ["authenticated"], "deny": [], '
        '"classification": "internal", "gdpr_subject": false}'
    )
    policy_locked = (
        '{"roles": ["admin"], "deny": [], '
        '"classification": "confidential", "gdpr_subject": false}'
    )

    class Row(dict):
        def get(self, key: str, default: object = None) -> object:
            return super().get(key, default)

    visible = Row(
        id="c-1",
        score=0.7,
        explanation="overlap",
        access_policy=policy_open,
        new_id="d-new",
        prior_id="d-old",
        status="pending",
    )
    hidden = Row(
        id="c-2",
        score=0.5,
        explanation="locked",
        access_policy=policy_locked,
        new_id="d-x",
        prior_id="d-y",
        status="pending",
    )

    async def fake_run(*_args: object, **_kwargs: object) -> AsyncMock:
        result = AsyncMock()

        async def agen() -> object:
            yield visible
            yield hidden

        result.__aiter__ = lambda self: agen()
        return result

    mock_session = MagicMock()
    mock_session.run = AsyncMock(side_effect=fake_run)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session

    with patch.object(service, "_driver_instance", AsyncMock(return_value=mock_driver)):
        rows = await service.list_pending_contradictions(
            workspace_id="ws-1",
            caller_roles=["authenticated"],
        )

    assert [row["id"] for row in rows] == ["c-1"]
    assert rows[0]["new_decision_id"] == "d-new"
