import { resolveApiBase } from "./api-base";

const API_BASE = resolveApiBase();

export class ApiError extends Error {
  status: number;
  /** Parsed JSON body from the backend, if the response was JSON. */
  envelope?: unknown;
  constructor(status: number, message: string, envelope?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.envelope = envelope;
  }
}

/** Extra options on top of standard fetch RequestInit. */
export interface ApiOptions extends RequestInit {
  /**
   * When true, a 401 response will NOT redirect the browser to /login.
   * Useful for tools that intentionally probe authenticated endpoints
   * (e.g. the API Registry's "Test Endpoint" button) where a 401 is
   * a *result to display*, not a session-expired signal.
   *
   * Defaults to false — every other caller keeps the normal behavior.
   */
  skipAuthRedirect?: boolean;
}

export async function api<T>(path: string, options?: ApiOptions): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };

  const { skipAuthRedirect, ...fetchOptions } = options ?? {};

  const res = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers,
    credentials: "include",
  });

  if (res.status === 401) {
    if (
      !skipAuthRedirect &&
      typeof window !== "undefined" &&
      !window.location.pathname.startsWith("/login") &&
      !window.location.pathname.startsWith("/setup")
    ) {
      window.location.href = "/login";
    }
    // For skipAuthRedirect callers, fall through to the normal error path
    // below so they get the real backend error message (not just
    // "Session expired"). For everyone else, preserve existing behavior.
    if (!skipAuthRedirect) {
      throw new ApiError(401, "Session expired");
    }
  }

  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    let message: string;
    let envelope: unknown;
    if (contentType.includes("application/json")) {
      const json = await res.json().catch(() => null);
      const detail = json?.detail ?? json;
      message = typeof detail === "string" ? detail : JSON.stringify(detail);
      envelope = detail;
    } else {
      message = await res.text().catch(() => res.statusText);
      // Truncate HTML responses to avoid flooding the UI
      if (message.length > 200) message = message.slice(0, 200) + "…";
    }
    throw new ApiError(res.status, message, envelope);
  }

  if (res.status === 204) {
    return {} as T;
  }

  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return (await res.text()) as any as T;
  }

  const text = await res.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}
