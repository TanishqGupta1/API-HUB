import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { PriceTierTable } from "@/components/storefront/price-tier-table";

describe("PriceTierTable", () => {
  it("renders the qty bands with currency", () => {
    render(
      <PriceTierTable
        tiers={[
          { group_name: "MSRP", qty_min: 1, qty_max: 11, price: "24.98", currency: "USD" },
          { group_name: "MSRP", qty_min: 12, qty_max: 2147483647, price: "19.98", currency: "USD" },
        ]}
      />,
    );
    expect(screen.getByText("1 – 11")).toBeInTheDocument();
    expect(screen.getByText("12+")).toBeInTheDocument();
    expect(screen.getByText("$24.98")).toBeInTheDocument();
    expect(screen.getByText("$19.98")).toBeInTheDocument();
  });

  it("renders nothing when no tiers", () => {
    const { container } = render(<PriceTierTable tiers={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
