"""Graph query edge cases — empty data, failures, malformed RBAC."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from graph.query import GraphQueryService, _causal_chain_query


@pytest.mark.asyncio
async def test_search_returns_empty_list_when_no_matches() -> None:
    service = GraphQueryService()

    async def empty_run(*_args: object, **_kwargs: object) -> AsyncMock:
        result = AsyncMock()

        async def agen() -> object:
            if False:  # noqa: SIM115 — empty async iterator
                yield None

        result.__aiter__ = lambda self: agen()
        return result

    mock_session = MagicMock()
    mock_session.run = AsyncMock(side_effect=empty_run)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session

    with patch.object(service, "_driver_instance", AsyncMock(return_value=mock_driver)):
        rows = await service.search_decisions(
            query="nonexistent topic xyz",
            workspace_id="empty-ws",
            limit=10,
            min_importance=0.0,
            min_trust=0.0,
            event_types=[],
            caller_roles=["authenticated"],
        )

    assert rows == []


def test_causal_chain_query_aggregates_triggers_separately() -> None:
    """Regression: Neo4j 5 rejects mixing collect() with bare trigger in one WITH."""
    cypher = _causal_chain_query(3)
    assert "collect(DISTINCT trigger)" in cypher
    assert cypher.count("WITH") >= 2


@pytest.mark.asyncio
async def test_causal_chain_propagates_driver_errors() -> None:
    service = GraphQueryService()
    mock_session = MagicMock()
    mock_session.run = AsyncMock(side_effect=RuntimeError("neo4j timeout"))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session

    with patch.object(service, "_driver_instance", AsyncMock(return_value=mock_driver)):
        with pytest.raises(RuntimeError, match="neo4j timeout"):
            await service.trace_causal_chain(
                decision_id="d-1",
                workspace_id="ws-1",
                max_depth=3,
                caller_roles=["authenticated"],
            )
