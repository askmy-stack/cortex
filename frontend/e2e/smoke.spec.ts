import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("cortex_onboarding_v1", "done");
  });
});

test.describe("Cortex dashboard smoke", () => {
  test("loads overview and navigates to search", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /see what your team decided/i })).toBeVisible();
    await page.getByRole("button", { name: /ask a question/i }).click();
    await expect(page.getByRole("heading", { name: /ask your organization anything/i })).toBeVisible();
  });

  test("mobile nav switches views", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/#ask");
    await page.getByRole("button", { name: "Overview", exact: true }).click();
    await expect(page.getByRole("heading", { name: /see what your team decided/i })).toBeVisible();
  });
});
