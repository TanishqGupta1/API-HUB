"use client";
import { createContext, useContext, useCallback, useMemo, type ReactNode } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { readFilters, writeFilters, type StorefrontFilters } from "@/lib/storefront-url";

interface SearchCtx {
  filters: StorefrontFilters;
  setFilter: <K extends keyof StorefrontFilters>(key: K, value: StorefrontFilters[K]) => void;
  clearAll: () => void;
  // legacy alias so old callers keep compiling
  query: string;
  setQuery: (q: string) => void;
}

const Ctx = createContext<SearchCtx | null>(null);

export function SearchProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const filters = useMemo(() => readFilters(sp), [sp]);

  const push = useCallback(
    (next: Partial<StorefrontFilters>) => {
      const params = writeFilters(sp, next);
      const qs = params.toString();
      router.push(qs ? `${pathname}?${qs}` : pathname);
    },
    [router, pathname, sp]
  );

  const setFilter: SearchCtx["setFilter"] = useCallback(
    (key, value) => push({ [key]: value } as Partial<StorefrontFilters>),
    [push]
  );

  const clearAll = useCallback(() => router.push(pathname), [router, pathname]);

  return (
    <Ctx.Provider
      value={{
        filters,
        setFilter,
        clearAll,
        query: filters.q,
        setQuery: (q: string) => push({ q }),
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useSearch() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSearch used outside SearchProvider");
  return ctx;
}
