import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";

// Plan ref: 2026-06-02-production-readiness.md, Phase 3 — "Frontend: API-client
// layer (lib/api), error-state tests; ... error states untested today".
//
// Covers the api() fetch wrapper: success parsing, POST content-type,
// error-envelope → ApiError, and the 401 silent-refresh / retry / session-
// expired path (the riskiest auth logic).

interface MakeResp {
  status: number;
  ok?: boolean;
  contentType?: string;
  body?: unknown;
  text?: string;
}

function makeResponse({ status, ok, contentType = "application/json", body = null, text }: MakeResp): Response {
  return {
    ok: ok ?? (status >= 200 && status < 300),
    status,
    headers: { get: (k: string) => (k.toLowerCase() === "content-type" ? contentType : null) },
    json: async () => body,
    text: async () => (text !== undefined ? text : body === null ? "" : JSON.stringify(body)),
  } as unknown as Response;
}

beforeEach(() => {
  window.history.pushState({}, "", "/dashboard");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("api() success paths", () => {
  it("parses a JSON body and sends credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse({ status: 200, body: { id: "abc" } }));
    vi.stubGlobal("fetch", fetchMock);

    const r = await api<{ id: string }>("/api/thing");
    expect(r).toEqual({ id: "abc" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/thing");
    expect((init as RequestInit).credentials).toBe("include");
  });

  it("sets Content-Type: application/json on POST", async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse({ status: 200, body: {} }));
    vi.stubGlobal("fetch", fetchMock);

    await api("/api/thing", { method: "POST", body: JSON.stringify({ a: 1 }) });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("returns {} on 204 No Content", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(makeResponse({ status: 204 })));
    expect(await api("/api/thing", { method: "DELETE" })).toEqual({});
  });

  it("returns raw text for non-JSON responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      makeResponse({ status: 200, contentType: "text/plain", text: "plain body" }),
    ));
    expect(await api<string>("/api/thing")).toBe("plain body");
  });
});

describe("api() error handling", () => {
  it("throws ApiError with parsed JSON detail + envelope", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      makeResponse({ status: 422, ok: false, body: { detail: "bad field" } }),
    ));
    let err: unknown;
    try { await api("/api/thing"); } catch (e) { err = e; }
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(422);
    expect((err as ApiError).message).toBe("bad field");
    expect((err as ApiError).envelope).toBe("bad field");
  });

  it("throws ApiError from a non-JSON error body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      makeResponse({ status: 500, ok: false, contentType: "text/plain", text: "server boom" }),
    ));
    let err: unknown;
    try { await api("/api/thing"); } catch (e) { err = e; }
    expect((err as ApiError).status).toBe(500);
    expect((err as ApiError).message).toBe("server boom");
  });
});

describe("api() 401 handling", () => {
  it("refreshes the token then retries the original request on success", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(makeResponse({ status: 401, ok: false, body: { detail: "expired" } }))
      .mockResolvedValueOnce(makeResponse({ status: 200, ok: true, body: {} }))      // /api/auth/refresh
      .mockResolvedValueOnce(makeResponse({ status: 200, body: { id: "after-refresh" } }));
    vi.stubGlobal("fetch", fetchMock);

    const r = await api<{ id: string }>("/api/thing");
    expect(r).toEqual({ id: "after-refresh" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toContain("/api/auth/refresh");
  });

  it("throws 'Session expired' when refresh also fails (no redirect from /login)", async () => {
    window.history.pushState({}, "", "/login"); // redirect branch is skipped here
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(makeResponse({ status: 401, ok: false, body: { detail: "x" } }))
      .mockResolvedValueOnce(makeResponse({ status: 401, ok: false, body: { detail: "x" } })); // refresh fails
    vi.stubGlobal("fetch", fetchMock);

    let err: unknown;
    try { await api("/api/thing"); } catch (e) { err = e; }
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(401);
    expect((err as ApiError).message).toBe("Session expired");
    expect(fetchMock).toHaveBeenCalledTimes(2); // initial + refresh, no retry
  });

  it("redirects to /login when refresh fails and not already on an auth page", async () => {
    const realLoc = window.location;
    const fakeLoc = { pathname: "/dashboard", href: "/dashboard" };
    Object.defineProperty(window, "location", { configurable: true, value: fakeLoc });
    try {
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(makeResponse({ status: 401, ok: false, body: { detail: "x" } }))
        .mockResolvedValueOnce(makeResponse({ status: 401, ok: false, body: { detail: "x" } })); // refresh fails
      vi.stubGlobal("fetch", fetchMock);

      let err: unknown;
      try { await api("/api/thing"); } catch (e) { err = e; }
      expect((err as ApiError).status).toBe(401);
      expect(fakeLoc.href).toBe("/login"); // redirect was attempted
    } finally {
      Object.defineProperty(window, "location", { configurable: true, value: realLoc });
    }
  });

  it("skipAuthRedirect surfaces the 401 as a result without refreshing", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      makeResponse({ status: 401, ok: false, body: { detail: "unauthorized probe" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    let err: unknown;
    try { await api("/api/probe", { skipAuthRedirect: true }); } catch (e) { err = e; }
    expect((err as ApiError).status).toBe(401);
    expect((err as ApiError).message).toBe("unauthorized probe"); // parsed body, not "Session expired"
    expect(fetchMock).toHaveBeenCalledTimes(1); // no refresh attempt
  });
});
