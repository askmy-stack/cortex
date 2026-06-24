# Custom domain for the Cortex dashboard (Vercel)

Replace `frontend-ten-rouge-99.vercel.app` with a branded URL (e.g. `cortex.askmy-stack.dev`).

## 1. Add domain in Vercel

1. Vercel → Project **frontend** → **Settings** → **Domains**.
2. Add your domain (apex or subdomain).
3. Follow Vercel’s DNS instructions (CNAME to `cname.vercel-dns.com` or A records for apex).

## 2. Keep API proxy working

No change to `CORTEX_API_ORIGIN` — middleware still proxies `/query` and `/health` to Railway.

Ensure **Environment Variables** include:

```env
CORTEX_API_ORIGIN=https://cortex-api-production-fbd5.up.railway.app
```

Apply to **Production** (and Preview if you use preview URLs).

## 3. Optional: API subdomain

If you want `api.cortex.example.com` instead of middleware-only:

1. Deploy API with public URL (Railway custom domain or Render).
2. Set `CORTEX_API_ORIGIN` to that URL **or** set `VITE_API_URL` (requires rebuild — prefer middleware).

Recommended for portfolio: **dashboard on custom domain, API stays on Railway**, proxy via middleware (no CORS).

## 4. Update links

After DNS propagates, update:

- [README.md](../README.md) live demo badge
- [docs/PORTFOLIO_DEMO.md](./PORTFOLIO_DEMO.md)
- LinkedIn / portfolio site

## 5. Verify

```bash
curl -s https://your-domain.example/health | jq .
curl -s -X POST https://your-domain.example/query \
  -H 'content-type: application/json' \
  -d '{"query":"Why CockroachDB for payments?","workspace_id":"local-dev","limit":3}'
```

Both should return JSON from the Railway API.
