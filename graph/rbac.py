"""Graph-level RBAC helpers for Cortex memory reads and writes."""

from __future__ import annotations

import json
from typing import Any

_DEFAULT_POLICY: dict[str, Any] = {
    "roles": ["authenticated"],
    "deny": [],
    "classification": "internal",
    "gdpr_subject": False,
}

_GDPR_ERASURE_ROLES = frozenset({"admin", "gdpr_officer", "legal"})


def normalize_access_policy(policy: Any) -> dict[str, Any]:
    """Coerce stored access_policy values into a dict."""
    if policy is None:
        return dict(_DEFAULT_POLICY)
    if isinstance(policy, dict):
        return policy
    if isinstance(policy, str):
        try:
            loaded = json.loads(policy)
        except json.JSONDecodeError:
            return dict(_DEFAULT_POLICY)
        if isinstance(loaded, dict):
            return loaded
    return dict(_DEFAULT_POLICY)


def can_access(policy: Any, caller_roles: list[str]) -> bool:
    """Return True when caller_roles satisfy the node access policy."""
    normalized = normalize_access_policy(policy)
    deny = {str(role) for role in normalized.get("deny", [])}
    if deny.intersection(caller_roles):
        return False

    allowed_roles = {str(role) for role in normalized.get("roles", ["authenticated"])}
    if "authenticated" in allowed_roles:
        return True
    return bool(allowed_roles.intersection(caller_roles))


def can_erase(caller_roles: list[str]) -> bool:
    """Return True when caller may invoke GDPR Right to Erasure."""
    return bool(_GDPR_ERASURE_ROLES.intersection(caller_roles))


def is_gdpr_subject(policy: Any) -> bool:
    """Return True when a node access policy marks GDPR-subject data."""
    normalized = normalize_access_policy(policy)
    return bool(normalized.get("gdpr_subject", False))


def serialize_access_policy(policy: dict[str, Any] | None) -> str:
    """Serialize access policy for Neo4j storage."""
    payload = policy or _DEFAULT_POLICY
    return json.dumps(payload, sort_keys=True)
