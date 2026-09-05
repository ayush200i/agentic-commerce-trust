import { test, expect } from "@playwright/test";
import { verify } from "./verify";
import AxeBuilder from "@axe-core/playwright";

test("recorded rehearsal: recover stock, approve, capture and verify receipt", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByText("Local API online")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("control-room.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Start negotiation" }).click();
  await expect(
    page.getByText("Needs your approval", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/Simulated stock change: Arc 75 keyboard/),
  ).toBeVisible();
  await expect(page.getByText(/Switching to Forma 75 keyboard/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Complete payment" }),
  ).toHaveCount(0);
  const approvalAccessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    approvalAccessibility.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
  await page.getByRole("button", { name: /Approve ₹/ }).click();
  await expect(
    page.getByRole("button", { name: "Complete payment" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Complete payment" }).click();
  await expect(
    page.getByText("Simulation complete", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Simulated payment captured. No real money moved."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Verify chain" }).click();
  await expect(page.getByRole("status")).toContainText("Verified");
  const completedAccessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    completedAccessibility.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
  const href = await page
    .getByRole("link", { name: "Export receipt" })
    .getAttribute("href");
  const response = await page.request.get(href!);
  const receipt = await response.json();
  expect(verify(receipt)).toBe(true);
  expect(
    receipt.entries.filter((e: any) => e.action === "payment_captured"),
  ).toHaveLength(1);
  await testInfo.attach("audit-receipt.json", {
    body: JSON.stringify(receipt, null, 2),
    contentType: "application/json",
  });
  await page.screenshot({
    path: testInfo.outputPath("completed-receipt.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Session receipts", exact: true })
    .click();
  await page
    .getByRole("button")
    .filter({ hasText: "#" + receipt.session_id.slice(0, 8) })
    .click();
  await expect(
    page.getByText("Simulation complete", { exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("rejection leaves no payment and catalog/connections navigation works", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start negotiation" }).click();
  await page.getByRole("button", { name: "Reject quote" }).click();
  await expect(
    page.getByText("Quote rejected", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Complete payment" }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Merchant catalog", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Arc 75 keyboard" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Connections", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Razorpay MCP" }),
  ).toBeVisible();
});

test("policy failure remains readable and stops checkout", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Maximum spend").fill("1");
  await page.getByRole("button", { name: "Start negotiation" }).click();
  await expect(page.getByText("Stopped safely", { exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "No in-stock product fits",
  );
  await expect(
    page.getByRole("button", { name: "Complete payment" }),
  ).toHaveCount(0);
});
