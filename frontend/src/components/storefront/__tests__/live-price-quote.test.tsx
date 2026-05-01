import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { LivePriceQuote } from "@/components/storefront/live-price-quote";

vi.mock("@/lib/use-debounced-quote", () => ({
  useDebouncedQuote: vi.fn(),
}));
import { useDebouncedQuote } from "@/lib/use-debounced-quote";

describe("LivePriceQuote", () => {
  it("renders a placeholder when not ready", () => {
    (useDebouncedQuote as unknown as { mockReturnValue: (v: unknown) => void }).mockReturnValue({
      quote: null,
      loading: false,
      error: null,
    });
    render(
      <LivePriceQuote
        productId="p1"
        qty={1}
        width={null}
        height={null}
        selectedAttributeIds={[]}
      />,
    );
    expect(screen.getByText(/enter dimensions/i)).toBeInTheDocument();
  });

  it("renders unit price + breakdown when quote arrives", () => {
    (useDebouncedQuote as unknown as { mockReturnValue: (v: unknown) => void }).mockReturnValue({
      quote: {
        unit_price: "12.50",
        total: "625.00",
        currency: "USD",
        breakdown: { base: "8.00", area_multiplier: "6.00", setup_cost: "10.00" },
      },
      loading: false,
      error: null,
    });
    render(
      <LivePriceQuote
        productId="p1"
        qty={50}
        width={24}
        height={36}
        selectedAttributeIds={["a1", "a2"]}
      />,
    );
    expect(screen.getByText(/\$625\.00/)).toBeInTheDocument();
    expect(screen.getByText(/12\.50/)).toBeInTheDocument();
    expect(screen.getByText(/setup_cost/i)).toBeInTheDocument();
  });

  it("renders the error message when the quote endpoint fails", () => {
    (useDebouncedQuote as unknown as { mockReturnValue: (v: unknown) => void }).mockReturnValue({
      quote: null,
      loading: false,
      error: "API 400: width is required",
    });
    render(
      <LivePriceQuote
        productId="p1"
        qty={50}
        width={24}
        height={36}
        selectedAttributeIds={[]}
      />,
    );
    expect(screen.getByText(/width is required/i)).toBeInTheDocument();
  });
});
