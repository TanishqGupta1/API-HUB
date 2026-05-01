import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProductTypeFilter } from "@/components/storefront/product-type-filter";

describe("ProductTypeFilter", () => {
  it("renders an All pill plus one pill per available type", async () => {
    const onChange = vi.fn();
    render(
      <ProductTypeFilter available={["apparel", "print"]} value={null} onChange={onChange} />,
    );
    expect(screen.getByRole("button", { name: /all/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /apparel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /print/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /print/i }));
    expect(onChange).toHaveBeenLastCalledWith("print");
  });

  it("clicking the active pill clears the filter", async () => {
    const onChange = vi.fn();
    render(
      <ProductTypeFilter available={["apparel", "print"]} value="apparel" onChange={onChange} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /apparel/i }));
    expect(onChange).toHaveBeenLastCalledWith(null);
  });
});
