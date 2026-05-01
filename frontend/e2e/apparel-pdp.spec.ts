import { test, expect } from "@playwright/test";
import apparel from "./fixtures/apparel-product.json";

test.describe("Apparel PDP", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/products/00000000-0000-0000-0000-0000000000a1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(apparel),
      });
    });
    // Block other backend calls so the test does not require a running backend.
    await page.route("**/api/products/00000000-0000-0000-0000-0000000000a1/options-config", (r) =>
      r.fulfill({ status: 404, contentType: "application/json", body: "{}" }),
    );
    await page.route("**/api/categories/**", (r) =>
      r.fulfill({ status: 404, contentType: "application/json", body: "{}" }),
    );
  });

  test("renders the variant picker and updates the tier table on selection", async ({ page }) => {
    await page.goto("/storefront/vg/product/00000000-0000-0000-0000-0000000000a1");
    await expect(page.getByRole("heading", { name: "Heavyweight Polo" })).toBeVisible();

    // Variant picker buttons
    await expect(page.getByRole("button", { name: "Deep Black" })).toBeVisible();
    const sButton = page.getByRole("button", { name: "S", exact: true });
    await expect(sButton).toBeVisible();

    // Default = first variant; tier table shows two bands.
    await expect(page.getByText("1 – 11")).toBeVisible();
    await expect(page.getByText("12+")).toBeVisible();

    // Pick size M → tier table collapses to one band (per fixture).
    await page.getByRole("button", { name: "M", exact: true }).click();
    await expect(page.getByText("1 – 11")).toBeVisible();
    await expect(page.getByText("12+")).not.toBeVisible();

    // Apparel meta shows Mens badge.
    await expect(page.getByText("Mens")).toBeVisible();
  });
});
