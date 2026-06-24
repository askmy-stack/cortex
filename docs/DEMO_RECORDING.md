# Demo recording checklist (Phase 7)

Use this when capturing the **~3 minute** portfolio demo and any **README GIF**.

## Before recording

1. **Docker Desktop** running; free ports: `5432`, `6379`, `7687`, `7474`, `9092`, `8000`, `3000`, `8080`.
2. From repo root: `cp .env.example .env` if you do not already have `.env`.
3. Run **`make demo`** or `bash scripts/demo.sh` and wait until the script prints **Demo stack is up** (first run can take many minutes while images build).
4. Confirm in browser:
   - [http://localhost:3000](http://localhost:3000) — dashboard loads, **API health** is green.
   - [http://localhost:8000/docs](http://localhost:8000/docs) — OpenAPI loads.

## Cloud demo script (Vercel + Railway)

Use this when recording for LinkedIn without running Docker locally.

| Time | Action |
|------|--------|
| 0:00 | Open https://frontend-ten-rouge-99.vercel.app — mention 24/7 Vercel + Railway stack. |
| 0:15 | **Ask** tab → confirm workspace **`local-dev`**. |
| 0:30 | Query *Why CockroachDB for payments?* — show results, trust scores, **coverage %**. |
| 1:00 | Switch workspace to **`oss-tiangolo-fastapi`** (if imported) — compare real OSS decisions. |
| 1:30 | **Explore** memory map; **Review** contradictions if seeded. |
| 2:00 | Show [MCP_SETUP.md](./MCP_SETUP.md) — wire Cursor in one JSON block. |
| 2:30 | GitHub README live demo link; close with organizational memory thesis. |

Custom domain steps: [CUSTOM_DOMAIN.md](./CUSTOM_DOMAIN.md).

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
