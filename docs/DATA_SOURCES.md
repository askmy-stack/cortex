# Cortex data workspaces

Cortex isolates organizational memory by **`workspace_id`**. Use separate workspaces for synthetic demo data vs real open-source imports.

## Workspace naming

| Workspace | Source | How to populate |
|-----------|--------|-----------------|
| `local-dev` | Synthetic demo catalog | `make demo` or `python scripts/seed_demo.py --workspace local-dev` |
| `oss-<org>-<repo>` | Real GitHub merged PRs | `python scripts/import_github_org.py --org tiangolo --repo fastapi` |
| `oss-adr` / `oss-adr-<project>` | ADR markdown files | `python scripts/import_adr_markdown.py --path docs/adr` |

## Path A — GitHub (full pipeline)

Exercises Kafka → extractor → importance/trust → Neo4j.

```bash
# Preview without Kafka
python scripts/import_github_org.py --org tiangolo --repo fastapi --dry-run

# Publish (requires Kafka + pipeline-worker)
python scripts/import_github_org.py \
  --org tiangolo \
  --repo fastapi \
  --workspace oss-tiangolo-fastapi \
  --limit 30

# Optional: GITHUB_TOKEN in .env for higher rate limits
```

After import, wait for `pipeline-worker` to process, then:

```bash
python scripts/dual_workspace_smoke.py --workspaces local-dev,oss-tiangolo-fastapi
```

## Path B — ADR markdown (direct graph write)

High-quality decisions without LLM extraction variance. Uses the same scoring loop as `seed_demo.py`.

```bash
python scripts/import_adr_markdown.py --path /path/to/docs/adr --workspace oss-adr-myproject --dry-run
python scripts/import_adr_markdown.py --path /path/to/docs/adr --workspace oss-adr-myproject
```

Supports common MADR sections: Context, Decision, Consequences, Status.

## Compare workspaces

```bash
make seed-dev          # local-dev only
make verify-dual       # query local-dev vs oss-tiangolo-fastapi
```

Dashboard presets: **local-dev**, **oss-tiangolo-fastapi**, **oss-adr** (Connection bar).

## Open data sources (future)

| Source | Maps to | Notes |
|--------|---------|-------|
| GitHub REST API | `RawEvent` via `normalise_github_event` | Implemented |
| ADR markdown repos | `DecisionEvent` direct | Implemented |
| Kaggle GitHub issues CSV | Custom CSV → `RawEvent` | Not yet shipped |
| GH Archive | Batch JSON → inject script | Not yet shipped |

## Licenses and ethics

- Only import **public** repositories and datasets.
- Do not import private Slack exports or employee PII without GDPR review.
- Document dataset provenance in PR descriptions when used for portfolio demos.
