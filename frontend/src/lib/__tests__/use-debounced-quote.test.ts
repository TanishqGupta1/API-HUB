import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useDebouncedQuote } from "@/lib/use-debounced-quote";

describe("useDebouncedQuote", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("posts request and returns the quote after the debounce window", async () => {
    const fakeFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        unit_price: "12.50",
        total: "625.00",
        currency: "USD",
        breakdown: { base: "8.00" },
      }),
      headers: new Headers({ "content-type": "application/json" }),
    });
    vi.stubGlobal("fetch", fakeFetch);

    const { result, rerender } = renderHook(
      (props: { qty: number }) =>
        useDebouncedQuote({ enabled: true, body: { product_id: "p1", qty: props.qty }, debounceMs: 250 }),
      { initialProps: { qty: 1 } },
    );

    expect(result.current.quote).toBeNull();
    expect(result.current.loading).toBe(false);

    rerender({ qty: 50 });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(260);
    });
    expect(result.current.quote?.total).toBe("625.00");
    expect(fakeFetch).toHaveBeenCalledTimes(1);
  });

  it("skips when disabled", async () => {
    const fakeFetch = vi.fn();
    vi.stubGlobal("fetch", fakeFetch);
    renderHook(() =>
      useDebouncedQuote({ enabled: false, body: { product_id: "p1", qty: 1 }, debounceMs: 250 }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(fakeFetch).not.toHaveBeenCalled();
  });
});
