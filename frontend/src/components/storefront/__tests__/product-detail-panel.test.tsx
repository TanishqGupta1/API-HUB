import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Product } from "@/lib/types";
import { ProductDetailPanel } from "@/components/storefront/product-detail-panel";

vi.mock("@/components/storefront/apparel-detail-panel", () => ({
  ApparelDetailPanel: () => <div data-testid="apparel-panel" />,
}));
vi.mock("@/components/storefront/print-detail-panel", () => ({
  PrintDetailPanel: () => <div data-testid="print-panel" />,
}));

const baseProduct: Product = {
  id: "p1",
  supplier_id: "s1",
  supplier_name: "x",
  supplier_has_decoration_overlay: false,
  supplier_sku: "x",
  product_name: "x",
  brand: null,
  category: null,
  category_id: null,
  description: null,
  product_type: "apparel",
  pricing_method: "tiered_variants",
  image_url: null,
  ops_product_id: null,
  external_catalogue: null,
  last_synced: null,
  archived_at: null,
  variants: [],
  images: [],
  options: [],
  apparel_details: null,
  print_details: null,
  sizes: [],
};

describe("ProductDetailPanel", () => {
  it("renders apparel panel for apparel product", () => {
    render(<ProductDetailPanel product={{ ...baseProduct, product_type: "apparel" }} />);
    expect(screen.getByTestId("apparel-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("print-panel")).toBeNull();
  });

  it("renders print panel for print product", () => {
    render(<ProductDetailPanel product={{ ...baseProduct, product_type: "print" }} />);
    expect(screen.getByTestId("print-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("apparel-panel")).toBeNull();
  });

  it("falls back to apparel for unknown product_type", () => {
    render(
      <ProductDetailPanel
        product={{ ...baseProduct, product_type: "promo" as Product["product_type"] }}
      />,
    );
    expect(screen.getByTestId("apparel-panel")).toBeInTheDocument();
  });
});
