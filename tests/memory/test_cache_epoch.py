"""Unit tests for workspace query-cache epoch helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from memory.cache_epoch import (
    bump_workspace_cache_epoch,
    workspace_cache_epoch_key,
)


def test_workspace_cache_epoch_key() -> None:
    assert workspace_cache_epoch_key("ws-1") == "cortex:ws:ws-1:cache_epoch"


def test_bump_with_client_increments() -> None:
    client = MagicMock()
    client.incr.return_value = 3
    epoch = bump_workspace_cache_epoch("ws-1", redis_client=client)
    assert epoch == 3
    client.incr.assert_called_once_with("cortex:ws:ws-1:cache_epoch")


def test_bump_empty_workspace_noop() -> None:
    assert bump_workspace_cache_epoch("", redis_client=MagicMock()) is None


def test_bump_connects_when_client_omitted() -> None:
    fake = MagicMock()
    fake.incr.return_value = 1
    with patch("memory.cache_epoch._connect_redis", return_value=fake):
        assert bump_workspace_cache_epoch("ws-x") == 1
