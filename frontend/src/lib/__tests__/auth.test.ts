import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearCachedUser,
  fetchUser,
  getCachedUser,
  isVGAdmin,
  logout,
  type AuthUser,
} from "@/lib/auth";

// Plan ref: 2026-06-02-production-readiness.md, Phase 3 — "Frontend: ...
// auth-flow ... tests". Covers the cookie-session helpers in lib/auth:
// /api/auth/me caching, failure → null, role check, and logout.

const VG_ADMIN: AuthUser = { id: "u1", email: "a@vg.com", role: "vg_admin", customer_id: null };
const CUST_ADMIN: AuthUser = { id: "u2", email: "c@x.com", role: "customer_admin", customer_id: "cust-1" };

function jsonOk(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as unknown as Response;
}
function notOk(status = 401): Response {
  return { ok: false, status, json: async () => ({}) } as unknown as Response;
}

beforeEach(() => {
  clearCachedUser();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("fetchUser", () => {
  it("returns the user and caches it (no second network call)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonOk(VG_ADMIN));
    vi.stubGlobal("fetch", fetchMock);

    expect(await fetchUser()).toEqual(VG_ADMIN);
    expect(await fetchUser()).toEqual(VG_ADMIN); // served from cache
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toContain("/api/auth/me");
  });

  it("returns null and caches null on a non-OK response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(notOk(401));
    vi.stubGlobal("fetch", fetchMock);

    expect(await fetchUser()).toBeNull();
    expect(await fetchUser()).toBeNull(); // cached null — no re-fetch
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("returns null when the request throws (network error)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    expect(await fetchUser()).toBeNull();
  });
});

describe("cache controls", () => {
  it("clearCachedUser forces a re-fetch", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonOk(VG_ADMIN));
    vi.stubGlobal("fetch", fetchMock);

    await fetchUser();
    clearCachedUser();
    await fetchUser();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("getCachedUser returns null before any fetch, then the cached user", async () => {
    expect(getCachedUser()).toBeNull();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonOk(CUST_ADMIN)));
    await fetchUser();
    expect(getCachedUser()).toEqual(CUST_ADMIN);
  });
});

describe("isVGAdmin", () => {
  it("is true for a vg_admin and false for a customer_admin", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonOk(VG_ADMIN)));
    expect(await isVGAdmin()).toBe(true);

    clearCachedUser();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonOk(CUST_ADMIN)));
    expect(await isVGAdmin()).toBe(false);
  });
});

describe("logout", () => {
  it("POSTs to logout and clears the cached user", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonOk(VG_ADMIN))   // initial fetchUser
      .mockResolvedValueOnce(jsonOk({}))          // logout POST
      .mockResolvedValueOnce(jsonOk(CUST_ADMIN)); // re-fetch after logout
    vi.stubGlobal("fetch", fetchMock);

    await fetchUser();
    expect(getCachedUser()).toEqual(VG_ADMIN);

    await logout();
    expect(getCachedUser()).toBeNull(); // cache cleared

    const logoutCall = fetchMock.mock.calls[1];
    expect(logoutCall[0]).toContain("/api/auth/logout");
    expect((logoutCall[1] as RequestInit).method).toBe("POST");

    // cache was cleared → next fetchUser hits the network again
    expect(await fetchUser()).toEqual(CUST_ADMIN);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
