"""Tests for graph/rbac.py."""

from __future__ import annotations

from graph.rbac import can_access, normalize_access_policy, serialize_access_policy


def test_normalize_json_policy() -> None:
    policy = serialize_access_policy({"roles": ["admin"], "deny": [], "classification": "internal"})
    assert normalize_access_policy(policy)["roles"] == ["admin"]


def test_can_access_allows_authenticated_role() -> None:
    assert can_access({"roles": ["authenticated"], "deny": []}, ["viewer"])


def test_can_access_respects_deny_list() -> None:
    policy = {"roles": ["authenticated"], "deny": ["contractor"]}
    assert not can_access(policy, ["contractor"])
