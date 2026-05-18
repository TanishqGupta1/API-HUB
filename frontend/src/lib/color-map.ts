/**
 * Maps common apparel color names → approximate hex for visual swatches.
 * Covers standard names + Comfort Colors, SanMar, Port & Company, Richardson
 * brand-specific abbreviated codes.
 */
const COLOR_MAP: Record<string, string> = {
  // ── Neutrals ──
  white: "#ffffff", black: "#1a1a1a", natural: "#e8dcc8", cream: "#f5f0e0",
  ivory: "#f4eed8", tan: "#d2b48c", khaki: "#c3b091", sand: "#c2b280",
  grey: "#9e9e9e", gray: "#9e9e9e", charcoal: "#4a4a4a", smoke: "#8a8a8a",
  heather: "#b0adb5", silver: "#c0c0c0", slate: "#708090", ash: "#b2b2b2",
  pepper: "#2e2e2e", graphite: "#555555", cement: "#8c8c8c",
  oatmeal: "#d4c5a9", linen: "#e8dcc8", antique: "#c8b89a",

  // ── Blues ──
  navy: "#1a2f5e", blue: "#2563eb", royal: "#4169e1", cobalt: "#0047ab",
  ocean: "#006994", sky: "#87ceeb", "light blue": "#add8e6", denim: "#1560bd",
  sapphire: "#0f52ba", indigo: "#4b0082", teal: "#008080",
  chambray: "#6495ed", "true navy": "#1a2f5e", steel: "#4682b4",
  periwinkle: "#ccccff", bluejean: "#5b7fa6", "blue jean": "#5b7fa6",
  aqua: "#00bcd4", turquoise: "#40e0d0", seafoam: "#93e9be",
  carolina: "#4b9cd3", columbia: "#9bddff",

  // ── Greens ──
  green: "#2d6a2d", forest: "#228b22", olive: "#808000", lime: "#32cd32",
  mint: "#98ff98", sage: "#b2ac88", fern: "#4f7942", moss: "#8a9a5b",
  kelly: "#4cbb17", hunter: "#355e3b", jade: "#00a86b",
  military: "#4a5240", camo: "#78866b", loden: "#6b7c45",

  // ── Reds & Pinks ──
  red: "#cc0000", cardinal: "#c41e3a", crimson: "#dc143c", maroon: "#800000",
  burgundy: "#800020", wine: "#722f37", cranberry: "#9b1b30",
  pink: "#ff69b4", "light pink": "#ffb6c1", coral: "#ff7f50", salmon: "#fa8072",
  rose: "#e8567a", mauve: "#c8849a", blush: "#f4a7b4",
  watermelon: "#fc6c85", berry: "#8b1a4a", cherry: "#de3163",
  peachy: "#ffb085", peach: "#ffb085",

  // ── Yellows & Oranges ──
  yellow: "#ffd700", gold: "#d4a017", citrine: "#e4d00a", lemon: "#fff44f",
  orange: "#ff8c00", tangerine: "#f28500", amber: "#ffbf00",
  butter: "#ffe680", banana: "#ffe135",

  // ── Purples ──
  purple: "#800080", violet: "#7f00ff", lavender: "#c8a8d8",
  amethyst: "#9966cc", orchid: "#da70d6", plum: "#dda0dd", eggplant: "#614051",
  lilac: "#c8a2c8", grape: "#6f2da8",
  vio: "#8b5cf6",       // catches NeonVio, UltraVio, etc.
  hydrangea: "#b09ec0",

  // ── Browns ──
  brown: "#795548", chocolate: "#7b3f00", mocha: "#967117", espresso: "#4b3832",
  caramel: "#c68642", rust: "#b7410e", clay: "#b66a50", brick: "#cb4154",
  sienna: "#a0522d", cinnamon: "#d2691e",
  buck: "#d4a96a",      // buckskin — Richardson hats
  khaki2: "#c3b091",

  // ── Brand abbreviations (Richardson, SanMar codes) ──
  // 3-4 char keys matched inside compound codes like "GrnCamo/Wh"
  grn: "#4a7c4e",       // Grn → green
  blk: "#1a1a1a",       // Blk → black
  wht: "#f5f5f5",       // Wht → white
  brn: "#795548",       // Brn → brown
  brwn: "#795548",      // Brwn → brown
  nvy: "#1a2f5e",       // Nvy → navy
  gry: "#9e9e9e",       // Gry → gray
  org: "#ff8c00",       // Org → orange
  pnk: "#ff69b4",       // Pnk → pink
  prp: "#800080",       // Prp → purple
  dsrt: "#c2a882",      // Dsrt → desert (sandy tan)
  bliz: "#e8e8e8",      // Bliz / Blz → blizzard (near white)
  blz: "#e8e8e8",
  tmber: "#8b6914",     // Tmbr / Timber → tan-brown
  tmbr: "#8b6914",
  ltgn: "#6aad6a",      // LtGn → light green
  ltan: "#d2b48c",      // LTan / LTn → light tan
  ltn: "#d2b48c",
  // 2-char codes — only used for "/" segment matching (see getColorHex)
  bk: "#1a1a1a",        // Bk → black
  br: "#795548",        // Br → brown
  ld: "#6b7c45",        // Ld → loden (olive-green)
  wh: "#f5f5f5",        // Wh / W → white
  lg: "#6aad6a",        // LG → light green

  // ── Neon / Brights ──
  neon: "#39ff14",
  "neon green": "#39ff14", "neon yellow": "#ffff00",
  "neon pink": "#ff44cc",  "neon orange": "#ff6600",
  bright: "#ff4500",

  // ── Textures / finishes treated as color hints ──
  "color blast": "#c080a0",
  washed: "#9ab0c8",
  vintage: "#b09a7a",
  pigment: "#a07898",
};

const SORTED_KEYS = Object.keys(COLOR_MAP).sort((a, b) => b.length - a.length);

function matchPartial(lower: string, minLen: number): string | null {
  const k = SORTED_KEYS.find((k) => k.length >= minLen && lower.includes(k));
  return k ? COLOR_MAP[k] : null;
}

export function getColorHex(name: string): string | null {
  if (!name) return null;
  const lower = name.toLowerCase().trim();

  // 1. Exact match
  if (COLOR_MAP[lower]) return COLOR_MAP[lower];

  // 2. Compound "/" codes — e.g. "GrnCamo/Wh", "RTTmbr/Blk"
  //    Try each segment with a 2-char minimum (Richardson uses "Bk", "Br", "Ld", "Wh")
  if (lower.includes("/")) {
    for (const part of lower.split("/")) {
      const p = part.trim();
      if (!p) continue;
      if (COLOR_MAP[p]) return COLOR_MAP[p];           // exact segment match
      const hit = matchPartial(p, 2);                  // partial with min 2
      if (hit) return hit;
    }
  }

  // 3. Direct partial match on the full name — min 3 chars to avoid false positives
  const hit = matchPartial(lower, 3);
  if (hit) return hit;

  // 4. No match → return null (caller hides the dot)
  return null;
}
