import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DimensionInput } from "@/components/storefront/dimension-input";

describe("DimensionInput", () => {
  it("emits width and height changes", async () => {
    const onChange = vi.fn();
    render(
      <DimensionInput
        width={null}
        height={null}
        widthMin={1}
        widthMax={96}
        heightMin={1}
        heightMax={96}
        onChange={onChange}
      />,
    );
    const w = screen.getByLabelText(/width/i);
    const h = screen.getByLabelText(/height/i);
    await userEvent.type(w, "24");
    await userEvent.type(h, "36");
    expect(onChange).toHaveBeenLastCalledWith({ width: 24, height: 36 });
  });

  it("flags out-of-range values", async () => {
    render(
      <DimensionInput
        width={120}
        height={36}
        widthMin={1}
        widthMax={96}
        heightMin={1}
        heightMax={96}
        onChange={() => {}}
      />,
    );
    expect(screen.getByText(/width must be between/i)).toBeInTheDocument();
  });
});
