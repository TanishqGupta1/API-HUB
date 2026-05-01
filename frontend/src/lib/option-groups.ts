import type { ProductOption } from "@/lib/types";

export type SectionName = "Material" | "Production" | "Cutting" | "Design" | "Other";

export const SECTION_ORDER: SectionName[] = [
  "Material",
  "Production",
  "Cutting",
  "Design",
  "Other",
];

const HIDDEN_TYPES = new Set(["admin_only", "textmp"]);

const SECTION_KEYS: Record<Exclude<SectionName, "Other">, ReadonlyArray<string>> = {
  Material: [
    "substrateMaterial",
    "substrateType",
    "substrateClass",
    "lamMaterial",
    "inkFinish",
    "inkType",
    "whiteInk",
    "panelType",
    "imageShape",
  ],
  Production: [
    "prodTime",
    "printSides",
    "printDevice",
    "printSurface",
    "printMode_Colorado",
    "printMode_FluidColor",
    "provideProof",
  ],
  Cutting: [
    "cutType",
    "cutting",
    "cutMasking",
    "cutComplexity",
    "kissCutDevice",
    "kissCutDeviceTool",
    "thruCutDevice",
    "thruCutDeviceTool_ThruCut",
    "weeding",
    "lamDevice",
    "rcRadius",
  ],
  Design: ["design", "designType", "designServices", "designComm", "designConsult"],
};

export function groupOptionsBySection(
  options: ProductOption[],
): Record<SectionName, ProductOption[]> {
  const out: Record<SectionName, ProductOption[]> = {
    Material: [],
    Production: [],
    Cutting: [],
    Design: [],
    Other: [],
  };
  for (const o of options) {
    if (HIDDEN_TYPES.has(o.options_type ?? "")) continue;
    const section = (Object.keys(SECTION_KEYS) as Array<Exclude<SectionName, "Other">>).find(
      (s) => SECTION_KEYS[s].includes(o.option_key),
    );
    out[section ?? "Other"].push(o);
  }
  return out;
}
