import { expect, test } from "@playwright/test";
import { dismissOnboarding, installApiMocks, SAMPLE_CHAIN_NODE, SAMPLE_DECISION } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await dismissOnboarding(page);
  await installApiMocks(page);
});

test.describe("Critical user journeys", () => {
  test("bug report section is visible with GitHub and email links", async ({ page }) => {
    await page.goto("/");
    const section = page.getByRole("heading", { name: /report a bug or issue/i });
    await section.scrollIntoViewIfNeeded();
    await expect(section).toBeVisible();
    await expect(page.getByRole("link", { name: /file on github/i })).toHaveAttribute(
      "href",
      /github\.com\/askmy-stack\/cortex\/issues/,
    );
    await expect(page.getByRole("link", { name: /email report/i })).toHaveAttribute(
      "href",
      /^mailto:/,
    );
  });

  test("Assist panel opens and accepts a mocked search", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await page.locator(".mobile-nav__item--assist").click();
    await expect(page.getByRole("complementary", { name: /cortex assist/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /cortex assist/i })).toBeVisible();

    const input = page.getByRole("textbox", { name: /message cortex assist/i });
    await input.fill("Why CockroachDB for payments?");
    await page.getByRole("button", { name: /^send$/i }).click();
    await expect(page.getByText(/cockroachdb/i).first()).toBeVisible({ timeout: 10_000 });
  });

  test("lineage tab renders causal chain without 503", async ({ page }) => {
    await page.goto("/#ask");
    await page.getByLabel(/your question/i).fill("Why CockroachDB for payments?");
    await page.getByRole("button", { name: /search memory/i }).click();
    await expect(page.getByRole("heading", { name: /1 shown/i })).toBeVisible({
      timeout: 10_000,
    });

    await page.getByRole("button", { name: /open memory map/i }).click();
    await expect(page.getByRole("heading", { name: /memory map/i })).toBeVisible();

    await page.getByRole("tab", { name: /lineage/i }).click();
    await expect(page.getByText(SAMPLE_CHAIN_NODE.content)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/couldn't trace lineage/i)).not.toBeVisible();
  });

  test("accessibility landmarks and skip link", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("main#main")).toBeVisible();
    const skip = page.getByRole("link", { name: /skip to content/i });
    await skip.focus();
    await expect(skip).toBeFocused();
  });

  test("demo journey: ask search, explore, connection panel", async ({ page }) => {
    await page.goto("/#ask");
    await expect(page.getByRole("heading", { name: /ask your organization/i })).toBeVisible();

    await page.getByLabel(/your question/i).fill("Why CockroachDB for payments?");
    await page.getByRole("button", { name: /search memory/i }).click();
    await expect(page.getByText(/1 shown/i)).toBeVisible({ timeout: 10_000 });

    await page.getByRole("button", { name: /open memory map/i }).click();
    await expect(page.getByRole("heading", { name: /memory map/i })).toBeVisible();

    await page.getByRole("button", { name: "Connection", exact: true }).click();
    await expect(page.getByLabel(/^api key$/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /test connection/i })).toBeVisible();
  });
});
