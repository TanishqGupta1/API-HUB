import { test, expect } from "@playwright/test";
import printProduct from "./fixtures/print-product.json";
import quote from "./fixtures/quote-response.json";

test.describe("Print PDP", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/products/00000000-0000-0000-0000-0000000000b1", (r) =>
      r.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(printProduct),
      }),
    );
    await page.route("**/api/products/00000000-0000-0000-0000-0000000000b1/options-config", (r) =>
      r.fulfill({ status: 404, contentType: "application/json", body: "{}" }),
    );
    await page.route("**/api/categories/**", (r) =>
      r.fulfill({ status: 404, contentType: "application/json", body: "{}" }),
    );
  });

  test("renders dimension input + options + live quote", async ({ page }) => {
    let quoteCalls = 0;
    await page.route("**/api/pricing/quote", async (route) => {
      quoteCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(quote),
      });
    });

    await page.goto("/storefront/vg/product/00000000-0000-0000-0000-0000000000b1");
    await expect(page.getByRole("heading", { name: "Decals - General Performance" })).toBeVisible();

    // Placeholder until dimensions filled.
    await expect(page.getByText(/enter dimensions/i)).toBeVisible();
    expect(quoteCalls).toBe(0);

    // Fill width + height; quote should be requested.
    await page.getByLabel("Width").fill("24");
    await page.getByLabel("Height").fill("36");
    await expect(page.getByText("$625.00")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/12\.50 per unit/)).toBeVisible();
    await expect(page.getByText("Material", { exact: true })).toBeVisible();

    // Selecting an option also re-requests.
    const before = quoteCalls;
    await page.getByRole("button", { name: "Matte" }).click();
    await expect.poll(() => quoteCalls).toBeGreaterThan(before);
  });
});
