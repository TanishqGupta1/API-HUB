"use client";

import { useMemo, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { PriceQuote, PriceQuoteRequest } from "@/lib/types";

interface UseDebouncedQuoteArgs {
  enabled: boolean;
  body: PriceQuoteRequest;
  debounceMs?: number;
}

interface UseDebouncedQuoteResult {
  quote: PriceQuote | null;
  loading: boolean;
  error: string | null;
}

export function useDebouncedQuote(
  { enabled, body, debounceMs = 250 }: UseDebouncedQuoteArgs,
): UseDebouncedQuoteResult {
  const [quote, setQuote] = useState<PriceQuote | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  // Serialize once per distinct body value (M4). Callers should pass a
  // stable body reference (useMemo at the call site) so this only reruns
  // when the pricing inputs actually change.
  const serialized = useMemo(() => JSON.stringify(body), [body]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    const myId = ++requestId.current;
    const handle = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await api<PriceQuote>("/api/pricing/quote", {
          method: "POST",
          body: serialized,
        });
        if (myId === requestId.current) {
          setQuote(result);
        }
      } catch (err) {
        if (myId === requestId.current) {
          setError(err instanceof Error ? err.message : String(err));
          setQuote(null);
        }
      } finally {
        if (myId === requestId.current) setLoading(false);
      }
    }, debounceMs);

    return () => clearTimeout(handle);
  }, [enabled, serialized, debounceMs]);

  return { quote, loading, error };
}
