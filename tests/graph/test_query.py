"""Tests for graph/query.py — mocked Neo4j async driver."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from graph.query import GraphQueryService


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
