import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OptionGroupedForm } from "@/components/storefront/option-grouped-form";
import type { ProductOption } from "@/lib/types";

const opt = (
  option_key: string,
  options_type: string,
  attrs: { id: string; title: string }[],
): ProductOption => ({
  id: `id-${option_key}`,
  option_key,
  title: option_key,
  options_type,
  sort_order: 0,
  master_option_id: null,
  ops_option_id: null,
  required: false,
  attributes: attrs.map((a, i) => ({
    id: a.id,
    title: a.title,
    sort_order: i,
    ops_attribute_id: null,
  })),
});

describe("OptionGroupedForm", () => {
  it("renders options under their section headers and emits selection", async () => {
    const onChange = vi.fn();
    render(
      <OptionGroupedForm
        options={[
          opt("substrateMaterial", "combo", [
            { id: "a1", title: "SAV" },
            { id: "a2", title: "Vinyl" },
          ]),
          opt("inkFinish", "radio", [
            { id: "a3", title: "Gloss" },
            { id: "a4", title: "Matte" },
          ]),
          opt("cutType", "radio", [
            { id: "a5", title: "Through Cut" },
            { id: "a6", title: "Kiss Cut" },
          ]),
        ]}
        selected={{}}
        onChange={onChange}
      />,
    );

    expect(screen.getByText("Material")).toBeInTheDocument();
    expect(screen.getByText("Cutting")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Matte" }));
    expect(onChange).toHaveBeenLastCalledWith({ "id-inkFinish": "a4" });
  });

  it("hides admin_only options", () => {
    render(
      <OptionGroupedForm
        options={[opt("file_prep", "admin_only", [{ id: "x", title: "x" }])]}
        selected={{}}
        onChange={() => {}}
      />,
    );
    expect(screen.queryByText("file_prep")).not.toBeInTheDocument();
  });
});
