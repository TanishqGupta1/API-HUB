"use client";
import { createContext, useContext, useState, type ReactNode } from "react";

interface SearchCtx {
  query: string;
  setQuery: (q: string) => void;
}

const Ctx = createContext<SearchCtx | null>(null);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [query, setQuery] = useState("");
  return <Ctx.Provider value={{ query, setQuery }}>{children}</Ctx.Provider>;
}

export function useSearch() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSearch used outside SearchProvider");
  return ctx;
}
