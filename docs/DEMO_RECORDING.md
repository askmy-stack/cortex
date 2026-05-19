# Demo recording checklist (Phase 7)

Use this when capturing the **~3 minute** portfolio demo and any **README GIF**.

## Before recording

1. **Docker Desktop** running; free ports: `5432`, `6379`, `7687`, `7474`, `9092`, `8000`, `3000`, `8080`.
2. From repo root: `cp .env.example .env` if you do not already have `.env`.
3. Run **`make demo`** or `bash scripts/demo.sh` and wait until the script prints **Demo stack is up** (first run can take many minutes while images build).
4. Confirm in browser:
   - [http://localhost:3000](http://localhost:3000) — dashboard loads, **API health** is green.
   - [http://localhost:8000/docs](http://localhost:8000/docs) — OpenAPI loads.

## Suggested script (voiceover optional)

| Time | Action |
|------|--------|
| 0:00 | One-sentence thesis: organizational memory for agents; decisions not documents. |
| 0:20 | Show `make demo` or already-running stack; mention Kafka + Neo4j + API. |
| 0:45 | Dashboard: workspace `local-dev`, query *Why CockroachDB for payments?* — show JSON results. |
| 1:30 | Open **Swagger** → `POST /query` with same body; or show **Kafka UI** at [http://localhost:8080](http://localhost:8080). |
| 2:15 | Mention **MCP** line from README (one JSON block). |
| 2:45 | Close: GitHub link, open-source, “memory infrastructure not model failure.” |

## README GIF (short loop)

- Record **10–20 s**: dashboard query + first result expanded or health + query tab in Swagger.
- Convert with **ffmpeg** (example): `ffmpeg -i demo.mov -vf "fps=10,scale=960:-1:flags=lanczos" -loop 0 demo.gif`
- Keep file size small (< ~5 MB); host in repo or link to asset in release.

## After recording

- [ ] Upload to YouTube or Loom (unlisted is fine); add link to README **Quickstart** or top badge.
- [ ] Add GIF path to README if committed to repo.

You cannot automate good audio or hosting from CI; this checklist is the remaining **Phase 7** work that stays manual.
