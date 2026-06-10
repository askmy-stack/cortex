/**
 * k6 load test for Cortex POST /query.
 *
 * Prerequisites: k6 installed (https://k6.io/docs/get-started/installation/)
 *
 *   k6 run scripts/load/k6_query.js
 *   CORTEX_URL=http://staging:8000 k6 run scripts/load/k6_query.js
 *   k6 run --vus 20 --duration 60s scripts/load/k6_query.js
 */
import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.CORTEX_URL || "http://localhost:8000";
const WORKSPACE = __ENV.CORTEX_WORKSPACE || "local-dev";

export const options = {
  vus: Number(__ENV.K6_VUS || 10),
  duration: __ENV.K6_DURATION || "30s",
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: [`p(95)<${Number(__ENV.K6_P95_MS || 2000)}`],
  },
};

export default function queryLoad() {
  const payload = JSON.stringify({
    query: "Why CockroachDB for payments?",
    workspace_id: WORKSPACE,
    limit: 10,
  });

  const res = http.post(`${BASE_URL}/query`, payload, {
    headers: { "Content-Type": "application/json" },
    tags: { name: "query" },
  });

  check(res, {
    "status is 200": (r) => r.status === 200,
    "has results": (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.results);
      } catch {
        return false;
      }
    },
  });

  sleep(Number(__ENV.K6_SLEEP || 0.5));
}
