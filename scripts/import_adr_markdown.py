#!/usr/bin/env python3
"""Import Architecture Decision Records from markdown files into Neo4j.

Parses common MADR-style ADR markdown and writes Decision nodes via the same
scoring pipeline as ``seed_demo.py`` (no Kafka / LLM extraction).

Usage:
  python scripts/import_adr_markdown.py --path ./vendor/adr --workspace oss-adr-fastapi --dry-run
  python scripts/import_adr_markdown.py --path docs/adr --glob '*.md'
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv

from shared.models import DecisionEvent, Provenance

SECTION_HEADING = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)


def adr_uuid(path_key: str) -> str:
    """Deterministic id for idempotent MERGE on re-import."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cortex.adr:{path_key}"))


def parse_adr_markdown(text: str, *, path_key: str) -> dict[str, str | list[str]] | None:
    """Extract title, status, context, decision, consequences from MADR-like markdown."""
    lines = text.strip().splitlines()
    if not lines:
        return None

    title = lines[0].lstrip("#").strip()
    if not title:
        return None

    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, current
        if current and buf:
            sections[current] = "\n".join(buf).strip()
        buf = []

    for line in lines[1:]:
        m = SECTION_HEADING.match(line)
        if m:
            flush()
            current = m.group(1).strip().lower()
        elif current:
            buf.append(line)
    flush()

    decision_text = (
        sections.get("decision")
        or sections.get("decision outcome")
        or sections.get("decision outcome / rationale")
        or ""
    )
    context = sections.get("context") or sections.get("issue") or ""
    consequences = sections.get("consequences") or sections.get("consequences / implications") or ""

    content_parts = [title]
    if decision_text:
        content_parts.append(decision_text)
    elif context:
        content_parts.append(context[:500])
    content = ". ".join(p for p in content_parts if p)

    rationale: list[str] = []
    if context:
        rationale.append(context[:400])
    if consequences:
        rationale.append(consequences[:400])

    status_raw = (sections.get("status") or "accepted").lower()
    event_type = "update" if "supersed" in status_raw or "deprecated" in status_raw else "decision"

    return {
        "title": title,
        "content": content[:4000],
        "rationale": rationale,
        "status": status_raw,
        "event_type": event_type,
        "path_key": path_key,
    }


def build_decision_from_adr(
    parsed: dict[str, str | list[str]],
    workspace_id: str,
    *,
    channel: str,
) -> DecisionEvent:
    """Materialize parsed ADR fields into a DecisionEvent."""
    now = datetime.now(UTC)
    path_key = str(parsed["path_key"])
    event_id = adr_uuid(path_key)
    raw_id = adr_uuid(f"raw-{path_key}")

    importance = 0.82 if parsed["event_type"] == "decision" else 0.72
    trust = 0.85

    return DecisionEvent(
        event_id=event_id,
        source_raw_event_id=raw_id,
        workspace_id=workspace_id,
        event_type=str(parsed["event_type"]),  # type: ignore[arg-type]
        content=str(parsed["content"]),
        made_by=["adr-import"],
        affects=[channel.split("/")[0] if "/" in channel else "architecture"],
        rationale=list(parsed["rationale"]),  # type: ignore[arg-type]
        extraction_confidence=0.95,
        importance_score=importance,
        trust_score=trust,
        provenance=Provenance(
            source="manual",
            channel=channel,
            original_timestamp=now,
            extractor_version="adr-import-1.0",
            extractor_model="markdown-parser",
            verified_by=[],
            raw_event_id=raw_id,
        ),
        extracted_at=now,
        status="active" if "accept" in str(parsed["status"]) else "under_review",
    )


def collect_adr_files(root: Path, glob_pattern: str) -> list[Path]:
    """Return markdown files under root matching glob."""
    if root.is_file():
        return [root] if root.suffix.lower() in {".md", ".markdown"} else []
    return sorted(root.rglob(glob_pattern))


def write_decisions(decisions: list[DecisionEvent]) -> tuple[int, int]:
    """Score and persist decisions; return (written, skipped)."""
    from graph.writer import GraphWriter
    from memory.quarantine import persist_quarantine
    from scoring.write_pipeline import DecisionScoringPipeline, write_reject_reason

    scoring = DecisionScoringPipeline()
    writer = GraphWriter()
    written = 0
    skipped = 0
    try:
        for decision in decisions:
            scoring.score(decision)
            reject = write_reject_reason(decision)
            if reject is not None:
                persist_quarantine(decision, reject)
                skipped += 1
                continue
            writer.write(decision)
            written += 1
    finally:
        writer.close()
    return written, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Import ADR markdown into Neo4j")
    parser.add_argument("--path", type=Path, required=True, help="ADR file or directory")
    parser.add_argument("--glob", default="*.md", help="Glob under directory (default: *.md)")
    parser.add_argument("--workspace", default=None, help="Cortex workspace id")
    parser.add_argument(
        "--channel",
        default=None,
        help="Provenance channel label (default: adr/<path>)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse only; do not write")
    args = parser.parse_args()

    load_dotenv(_REPO / ".env")
    workspace = args.workspace or os.environ.get("CORTEX_WORKSPACE_ID", "oss-adr")

    files = collect_adr_files(args.path, args.glob)
    if not files:
        print(f"No ADR files found under {args.path}", file=sys.stderr)
        return 1

    decisions: list[DecisionEvent] = []
    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        rel = file_path.relative_to(args.path) if args.path.is_dir() else file_path.name
        path_key = str(rel)
        parsed = parse_adr_markdown(text, path_key=path_key)
        if parsed is None:
            continue
        channel = args.channel or f"adr/{path_key}"
        decisions.append(build_decision_from_adr(parsed, workspace, channel=channel))

    print(f"Parsed {len(decisions)} ADR(s) from {len(files)} file(s) → workspace={workspace!r}")

    if args.dry_run:
        for d in decisions[:3]:
            print(f"  - {d.event_id}: {d.content[:80]}…")
        if len(decisions) > 3:
            print(f"  … and {len(decisions) - 3} more")
        return 0

    written, skipped = write_decisions(decisions)
    print(f"ADR import complete: wrote {written}, skipped {skipped} (quarantine/importance)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
