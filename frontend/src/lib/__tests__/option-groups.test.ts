import { describe, expect, it } from "vitest";
import { groupOptionsBySection } from "@/lib/option-groups";
import type { ProductOption } from "@/lib/types";

const opt = (option_key: string, options_type: string | null = "combo"): ProductOption => ({
  id: `id-${option_key}`,
  option_key,
  title: option_key,
  options_type,
  sort_order: 0,
  master_option_id: null,
  ops_option_id: null,
  required: false,
  attributes: [],
});

describe("groupOptionsBySection", () => {
  it("buckets known OPS keys into Material / Production / Cutting / Design", () => {
    const groups = groupOptionsBySection([
      opt("substrateMaterial"),
      opt("lamMaterial"),
      opt("inkType"),
      opt("prodTime"),
      opt("printSides"),
      opt("printDevice"),
      opt("cutType"),
      opt("kissCutDevice"),
      opt("rcRadius"),
      opt("design"),
      opt("designType"),
      opt("designServices"),
    ]);
    expect(groups.Material.map((o) => o.option_key)).toEqual([
      "substrateMaterial",
      "lamMaterial",
      "inkType",
    ]);
    expect(groups.Production.map((o) => o.option_key)).toEqual([
      "prodTime",
      "printSides",
      "printDevice",
    ]);
    expect(groups.Cutting.map((o) => o.option_key)).toEqual([
      "cutType",
      "kissCutDevice",
      "rcRadius",
    ]);
    expect(groups.Design.map((o) => o.option_key)).toEqual([
      "design",
      "designType",
      "designServices",
    ]);
  });

  it("drops admin_only and textmp options", () => {
    const groups = groupOptionsBySection([
      opt("file_prep", "admin_only"),
      opt("designTime", "textmp"),
      opt("inkFinish", "combo"),
    ]);
    expect(groups.Other.map((o) => o.option_key)).toEqual([]);
    expect(groups.Material.map((o) => o.option_key)).toEqual(["inkFinish"]);
  });

  it("falls back to Other for unknown keys", () => {
    const groups = groupOptionsBySection([opt("specialSign"), opt("zogZog")]);
    expect(groups.Other.map((o) => o.option_key).sort()).toEqual(["specialSign", "zogZog"]);
  });
});
