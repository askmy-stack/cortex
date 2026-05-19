# Connector validation (Slack / GitHub / Jira)

End-to-end checks require **real tokens** in `.env` (never commit secrets). Cortex does not ship OAuth callbacks in-repo for all providers; use provider consoles and webhooks as documented below.

## Preconditions

- `docker compose up -d` core stack + `docker compose --profile api up -d api pipeline-worker kafka` (or `make demo` for a seeded graph).
- `python -m graph.migrate` applied (through **V007** if upgrading an older volume).
- Kafka UI: [http://localhost:8080](http://localhost:8080) — confirm topics exist after first publish.

## GitHub (webhook → API → Kafka)

1. In GitHub repo **Settings → Webhooks**, add `http://<your-host>:8000/webhooks/github` (use [smee.io](https://smee.io) or Tailscale if localhost is not reachable).
2. Set `GITHUB_WEBHOOK_SECRET` in `.env` to match the secret configured on the webhook.
3. Trigger a test delivery; in Kafka UI, look for messages on **`cortex.raw.github.events`** (topic name per D-013 / `connectors/github/producer.py`).
4. Confirm `pipeline-worker` logs show consumption (no errors connecting with `KAFKA_BOOTSTRAP_SERVERS=kafka:29092` inside Compose).

## Slack

1. Create a Slack app; install to workspace; set **Bot token** as `SLACK_BOT_TOKEN` in `.env`.
2. Configure **Event Subscriptions** to POST to `https://<public-url>/webhooks/slack` (same tunneling note as GitHub).
3. Subscribe to `message.channels` (or per product requirements); send a test message; verify **`cortex.raw.slack.messages`** (or configured topic) receives payloads.

## Jira

1. Register webhook in Jira pointing at `/webhooks/jira` on the API.
2. Set any shared secrets / auth headers your `api/webhooks.py` expects (see repo for exact env names).
3. Fire a test issue event; inspect **`cortex.raw.jira.events`**.

## Neo4j graph confirmation

After worker processes an event (requires extractor + scorer pipeline configured):

```text
MATCH (d:Decision) RETURN d.id, d.content LIMIT 5;
```

If nothing appears, check worker logs, importance/trust thresholds, and that `RawEvent` messages match the consumer group subscription.
