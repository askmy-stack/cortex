import assert from "node:assert/strict";
import { test } from "node:test";

import { resolveMcpAuth } from "./auth.js";

test("production without an API key is blocked", () => {
  const auth = resolveMcpAuth({ ENVIRONMENT: "production" });
  assert.equal(auth.blocked, true);
});

test("production with an API key is not blocked", () => {
  const auth = resolveMcpAuth({ ENVIRONMENT: "production", CORTEX_API_KEY: "sk_test" });
  assert.equal(auth.blocked, false);
});

test("development without an API key is not blocked (legacy role header allowed)", () => {
  const auth = resolveMcpAuth({ ENVIRONMENT: "development" });
  assert.equal(auth.blocked, false);
});

test("unset ENVIRONMENT defaults to development and is not blocked", () => {
  const auth = resolveMcpAuth({});
  assert.equal(auth.environment, "development");
  assert.equal(auth.blocked, false);
});

test("ENVIRONMENT is case-insensitive", () => {
  const auth = resolveMcpAuth({ ENVIRONMENT: "Production" });
  assert.equal(auth.blocked, true);
});
