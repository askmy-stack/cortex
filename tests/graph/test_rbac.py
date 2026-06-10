"""Tests for graph/rbac.py."""

from __future__ import annotations

from graph.rbac import can_access, can_erase, is_gdpr_subject, normalize_access_policy, serialize_access_policy


def test_normalize_json_policy() -> None:
    policy = serialize_access_policy({"roles": ["admin"], "deny": [], "classification": "internal"})
    assert normalize_access_policy(policy)["roles"] == ["admin"]


def test_can_access_allows_authenticated_role() -> None:
    assert can_access({"roles": ["authenticated"], "deny": []}, ["viewer"])


def test_can_access_respects_deny_list() -> None:
    policy = {"roles": ["authenticated"], "deny": ["contractor"]}
    assert not can_access(policy, ["contractor"])


def test_can_access_requires_explicit_role_when_not_authenticated() -> None:
    policy = {"roles": ["admin", "legal"], "deny": []}
    assert can_access(policy, ["admin"])
    assert not can_access(policy, ["viewer"])


def test_can_erase_allows_privileged_roles() -> None:
    assert can_erase(["admin"])
    assert can_erase(["gdpr_officer"])
    assert can_erase(["legal"])
    assert not can_erase(["viewer"])
    assert not can_erase(["authenticated"])


def test_is_gdpr_subject_reads_policy_flag() -> None:
    assert is_gdpr_subject({"roles": ["authenticated"], "gdpr_subject": True})
    assert not is_gdpr_subject({"roles": ["authenticated"], "gdpr_subject": False})
    assert not is_gdpr_subject(None)
