export type SortKey = "name" | "price_asc" | "price_desc" | "newest" | "variants";
export type StockFilter = "in" | null;

export interface StorefrontFilters {
  category: string | null;
  q: string;
  stock: StockFilter;
  sort: SortKey;
}

export function readFilters(sp: URLSearchParams): StorefrontFilters {
  const rawSort = sp.get("sort");
  const sort: SortKey =
    rawSort === "price_asc" ||
    rawSort === "price_desc" ||
    rawSort === "newest" ||
    rawSort === "variants"
      ? rawSort
      : "name";
  return {
    category: sp.get("category"),
    q: sp.get("q") ?? "",
    stock: sp.get("stock") === "in" ? "in" : null,
    sort,
  };
}

export function writeFilters(base: URLSearchParams, next: Partial<StorefrontFilters>): URLSearchParams {
  const out = new URLSearchParams(base.toString());
  if ("category" in next) next.category ? out.set("category", next.category) : out.delete("category");
  if ("q" in next) next.q ? out.set("q", next.q) : out.delete("q");
  if ("stock" in next) next.stock === "in" ? out.set("stock", "in") : out.delete("stock");
  if ("sort" in next) next.sort && next.sort !== "name" ? out.set("sort", next.sort) : out.delete("sort");
  return out;
}

export function countActive(f: StorefrontFilters): number {
  let n = 0;
  if (f.stock === "in") n++;
  if (f.sort !== "name") n++;
  return n;
}
