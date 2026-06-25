import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { dismissOnboarding, installApiMocks } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await dismissOnboarding(page);
  await installApiMocks(page);
});

test.describe("Accessibility audit", () => {
  test("home view has no serious axe violations", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("main#main")).toBeVisible();
    // Let entrance animations finish so axe does not sample faded text.
    await page.waitForTimeout(700);

    const results = await new AxeBuilder({ page }).analyze();

    const serious = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );
    expect(serious).toEqual([]);
  });
});
