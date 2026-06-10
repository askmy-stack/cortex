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

    const results = await new AxeBuilder({ page })
      .disableRules(["color-contrast"])
      .analyze();

    const serious = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );
    expect(serious).toEqual([]);
  });
});
