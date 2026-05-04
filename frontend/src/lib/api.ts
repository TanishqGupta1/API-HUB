import { clearSession, getToken } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearSession();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    let message: string;
    if (contentType.includes("application/json")) {
      const json = await res.json().catch(() => null);
      const detail = json?.detail ?? json;
      message = typeof detail === "string" ? detail : JSON.stringify(detail);
    } else {
      message = await res.text().catch(() => res.statusText);
      if (message.length > 200) message = message.slice(0, 200) + "…";
    }
    throw new Error(`API ${res.status}: ${message}`);
  }

  return res.json() as Promise<T>;
}
