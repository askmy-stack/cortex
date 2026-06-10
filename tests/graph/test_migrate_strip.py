"""Tests for graph.migrate statement chunk handling."""

from __future__ import annotations

from graph.migrate import _strip_leading_comments, get_migration_files


def test_v009_rbac_enforcement_migration_registered() -> None:
    versions = {version for version, _, _ in get_migration_files()}
    assert 9 in versions


def test_strip_leading_comments_preserves_create_after_header() -> None:
    chunk = """// V005 — header
// second line

CREATE INDEX foo IF NOT EXISTS FOR (n:Node) ON (n.x);
"""
    out = _strip_leading_comments(chunk)
    assert out.startswith("CREATE INDEX")


def test_strip_leading_comments_empty_when_only_comments() -> None:
    assert _strip_leading_comments("// only\n// comments\n") == ""


def test_strip_inline_comment_line_stays_inside_body() -> None:
    """Lines that are not solely leading comments are kept (inline // is rare in our migrations)."""
    body = _strip_leading_comments("RETURN 1 // trailing")
    assert "RETURN 1" in body
