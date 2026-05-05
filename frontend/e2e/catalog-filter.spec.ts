import { test, expect } from "@playwright/test";

const items = [
  {
    id: "00000000-0000-0000-0000-0000000000a1",
    supplier_id: "s1",
    supplier_name: "SanMar",
    supplier_sku: "PC61",
    product_name: "Apparel One",
    brand: "Mercer+Mettle",
    category_id: null,
    product_type: "apparel",
    pricing_method: "tiered_variants",
    image_url: null,
    ops_product_id: null,
    external_catalogue: null,
    variant_count: 4,
    price_min: 19.98,
    price_max: 24.98,
    total_inventory: 1000,
    archived_at: null,
  },
  {
    id: "00000000-0000-0000-0000-0000000000b1",
    supplier_id: "s1",
    supplier_name: "VG OPS",
    supplier_sku: "131",
    product_name: "Decals - General",
    brand: null,
    category_id: null,
    product_type: "print",
    pricing_method: "formula",
    image_url: null,
    ops_product_id: "131",
    external_catalogue: 1,
    variant_count: 0,
    price_min: null,
    price_max: null,
    total_inventory: 0,
    archived_at: null,
  },
];

test("catalog filter narrows the list by product_type", async ({ page }) => {
  await page.route("**/api/products*", (r) =>
    r.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(items),
    }),
  );
  await page.route("**/api/categories*", (r) =>
    r.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );

  await page.goto("/storefront/vg");
  await expect(page.getByText("Apparel One")).toBeVisible();
  await expect(page.getByText("Decals - General")).toBeVisible();

  await page.getByRole("button", { name: "Print" }).click();
  await expect(page.getByText("Decals - General")).toBeVisible();
  await expect(page.getByText("Apparel One")).not.toBeVisible();

  // Click the active pill clears the filter.
  await page.getByRole("button", { name: "Print" }).click();
  await expect(page.getByText("Apparel One")).toBeVisible();
});
