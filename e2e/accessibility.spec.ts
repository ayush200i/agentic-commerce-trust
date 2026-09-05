import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("keyboard access and WCAG AA checks", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByText("Local API online")).toBeVisible();
  for (const view of [
    "Control room",
    "Merchant catalog",
    "Session receipts",
    "Connections",
  ]) {
    await page.getByRole("button", { name: view, exact: true }).click();
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    await testInfo.attach(`accessibility-${view}.json`, {
      body: JSON.stringify(result.violations, null, 2),
      contentType: "application/json",
    });
    expect(
      result.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.map((n) => ({
          target: n.target,
          summary: n.failureSummary,
        })),
      })),
    ).toEqual([]);
  }
  await page.getByRole("button", { name: "Control room", exact: true }).click();
  await page.getByLabel("What should the buyer find?").focus();
  await expect(page.getByLabel("What should the buyer find?")).toBeFocused();
  expect(
    await page
      .getByLabel("What should the buyer find?")
      .evaluate((el) => getComputedStyle(el).outlineStyle),
  ).not.toBe("none");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Agent execution")).toBeFocused();
});
