/**
 * Humanize OPS master option keys + attribute keys into display names.
 *
 * OPS stores attributes as `attribute_key` which can be:
 *   "Gloss"                  → "Gloss"
 *   "Rectangle|1"            → "Rectangle"       (strip |id suffix)
 *   "None_lamMaterial"       → "None"            (None_ prefix + opt key suffix)
 *   "true_proof"             → "Yes"
 *   "false_proof"            → "No"
 *   "hourly_designType"      → "Hourly"          (strip opt-key suffix)
 *   "standard_weeding"       → "Standard"
 *   "Through Cut_Knife|2"    → "Through Cut"     (strip |id + _suffix)
 *   "36degBlade"             → "36 Deg Blade"    (camelCase split)
 *   "1" / "2" / "3" / "7"    → "1" / "2" / "3" / "7"  (leave numbers)
 *
 * Master options: `title` is often empty → fall back to humanized `option_key`:
 *   "lamMaterial"    → "Laminate Material"
 *   "inkFinish"      → "Ink Finish"
 *   "substrateClass" → "Substrate Class"
 */

const KNOWN_OPTION_KEYS: Record<string, string> = {
  lamMaterial: "Laminate Material",
  lamDevice: "Lamination Device",
  inkFinish: "Ink Finish",
  inkType: "Ink Type",
  whiteInk: "White Ink",
  printSides: "Print Sides",
  printDevice: "Print Device",
  printSurface: "Print Surface",
  substrateMaterial: "Substrate Material",
  substrateClass: "Substrate Class",
  substrateType: "Substrate Type",
  imageShape: "Graphic Shape",
  cutType: "Cut Type",
  cutMasking: "Cut Masking",
  cutComplexity: "Cut Complexity",
  cutting: "Cutting",
  kissCutDevice: "Kiss-Cut Device",
  kissCutDeviceTool: "Kiss-Cut Tool",
  thruCutDevice: "Through-Cut Device",
  thruCutDeviceTool_ThruCut: "Through-Cut Tool",
  weeding: "Weeding",
  rcRadius: "Corner Radius",
  specialSign: "Special Sign",
  prodTime: "Production Time",
  designTime: "Design Time",
  designType: "Design Type",
  designServices: "Design Services",
  designComm: "Design Communication",
  designConsult: "Design Consult",
  design: "Design Service",
  panelType: "Panel Type",
  provideProof: "Proof",
  printMode_Colorado: "Print Mode (Colorado)",
  printMode_FluidColor: "Print Mode (FluidColor)",
  file_prep: "File Prep",
  "file_processing_(rip)": "File Processing (RIP)",
};

/** Split camelCase (`lamMaterial` → `"Lam Material"`) and snake_case. */
function splitIdentifier(s: string): string {
  return s
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
    .replace(/_+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function titleCase(s: string): string {
  return s
    .toLowerCase()
    .split(" ")
    .map((w) => (w.length > 0 ? w[0].toUpperCase() + w.slice(1) : ""))
    .join(" ");
}

/**
 * Turn an OPS master option `option_key` + `title` into a display name.
 * Prefer non-empty `title`; otherwise humanize `option_key`.
 */
export function humanizeOptionName(
  title: string | null | undefined,
  option_key: string | null | undefined,
): string {
  if (title && title.trim().length > 0) return title.trim();
  if (!option_key) return "Option";
  const known = KNOWN_OPTION_KEYS[option_key];
  if (known) return known;
  return titleCase(splitIdentifier(option_key));
}

/**
 * Turn an OPS `attribute_key` (e.g. `"Rectangle|1"`, `"None_lamMaterial"`,
 * `"true_proof"`, `"hourly_designType"`) into a clean display label.
 * Prefers non-empty `title` if the ingest provided one.
 */
export function humanizeAttributeName(
  title: string | null | undefined,
  attribute_key: string | null | undefined,
): string {
  if (title && title.trim().length > 0 && !looksLikeAttributeKey(title)) {
    return title.trim();
  }
  const raw = (attribute_key || title || "").trim();
  if (!raw) return "—";

  // Strip |id suffix: "Rectangle|1" → "Rectangle", "Through Cut_Knife|2" → "Through Cut_Knife"
  let s = raw.replace(/\|[^|]*$/, "");

  // Boolean-style prefixes
  if (/^true[_\s]/i.test(s) || /^true$/i.test(s)) return "Yes";
  if (/^false[_\s]/i.test(s) || /^false$/i.test(s)) return "No";
  if (/^none[_\s]/i.test(s)) return "None";

  // Trailing option_key suffix: "hourly_designType" → "hourly", "standard_weeding" → "standard"
  // Heuristic: if last underscore segment is camelCase-looking (has uppercase mid-word), drop it.
  const lastUnderscore = s.lastIndexOf("_");
  if (lastUnderscore > 0) {
    const tail = s.slice(lastUnderscore + 1);
    if (/[A-Z]/.test(tail) && tail.length > 2) {
      s = s.slice(0, lastUnderscore);
    }
  }

  // Minute shorthands: "15min" → "15 min", "30min" → "30 min"
  s = s.replace(/^(\d+)min$/i, "$1 min");

  // If it's still just a number, leave it
  if (/^\d+(\.\d+)?$/.test(s)) return s;

  // If it's an angle/measurement prefix: "36degBlade" → "36 deg blade"
  s = s.replace(/(\d+)deg/i, "$1 deg ");

  // camelCase + snake split + title case
  return titleCase(splitIdentifier(s));
}

/** If title looks like a raw attribute_key (has `_`, `|`, or is camelCase), prefer humanizing. */
function looksLikeAttributeKey(s: string): boolean {
  return /[|_]/.test(s) || /^[a-z]+[A-Z]/.test(s);
}
