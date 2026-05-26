// Cookie-based session. The `auth_token` cookie is HttpOnly + Secure, set by
// the backend on /api/auth/login. The client cannot read or write it.
// User info comes from /api/auth/me.

export interface AuthUser {
  id: string;
  email: string;
  role: "vg_admin" | "customer_admin";
  customer_id: string | null;
}

import { API_BASE } from "./env";



let cachedUser: AuthUser | null | undefined = undefined;

export async function fetchUser(): Promise<AuthUser | null> {
  if (cachedUser !== undefined) return cachedUser;
  try {
    const res = await fetch(`${API_BASE}/api/auth/me`, { credentials: "include" });
    if (!res.ok) {
      cachedUser = null;
      return null;
    }
    cachedUser = (await res.json()) as AuthUser;
    return cachedUser;
  } catch {
    cachedUser = null;
    return null;
  }
}

export function clearCachedUser(): void {
  cachedUser = undefined;
}

export function getCachedUser(): AuthUser | null {
  return cachedUser ?? null;
}

export async function isVGAdmin(): Promise<boolean> {
  const u = await fetchUser();
  return u?.role === "vg_admin";
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } finally {
    clearCachedUser();
  }
}
