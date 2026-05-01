import { describe, expect, it } from "vitest";
import type { Product, PriceQuote } from "@/lib/types";

describe("polymorphic Product types", () => {
  it("apparel product carries apparel_details + variant_prices", () => {
    const apparel: Product = {
      id: "p1",
      supplier_id: "s1",
      supplier_name: "SanMar",
      supplier_sku: "PC61",
      product_name: "Polo",
      brand: "Mercer+Mettle",
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
      variants: [
        {
          id: "v1",
          color: "Deep Black",
          size: "S",
          sku: "PC61-DB-S",
          base_price: 24.98,
          inventory: null,
          warehouse: null,
          part_id: "1878771",
          gtin: null,
          flags: { pms_color: "BLACK C", standard_color: "Deep Black" },
          prices: [
            { group_name: "MSRP", qty_min: 1, qty_max: 11, price: "24.98", currency: "USD" },
            { group_name: "MSRP", qty_min: 12, qty_max: 2147483647, price: "19.98", currency: "USD" },
          ],
        },
      ],
      images: [],
      options: [],
      apparel_details: {
        ps_part_id: "1878771",
        apparel_style: "Mens",
        is_closeout: false,
        is_hazmat: null,
        is_caution: false,
        caution_comment: null,
        is_on_demand: null,
        fabric_specs: { weight_oz: 8.1 },
        fob_points: null,
        keywords: null,
      },
      print_details: null,
      sizes: [],
    };
    expect(apparel.apparel_details?.apparel_style).toBe("Mens");
    expect(apparel.variants[0].prices[0].price).toBe("24.98");
  });

  it("PriceQuote breakdown is freeform JSON", () => {
    const quote: PriceQuote = {
      unit_price: "12.50",
      total: "625.00",
      currency: "USD",
      breakdown: { base: "8.00", area_multiplier: "6.00", setup_cost: "10.00" },
    };
    expect(quote.total).toBe("625.00");
  });
});
