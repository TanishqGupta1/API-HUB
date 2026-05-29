import { API_BASE } from "./env";



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

/**
 * Attempt to silently refresh the access token using the HttpOnly
 * refresh_token cookie.  Returns true if the refresh succeeded.
 * Only runs once per call — no infinite loops.
 */
let _refreshInFlight: Promise<boolean> | null = null;

async function _tryRefresh(): Promise<boolean> {
  if (_refreshInFlight) return _refreshInFlight;
  _refreshInFlight = fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
  })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      _refreshInFlight = null;
    });
  return _refreshInFlight;
}

async function _parseError(res: Response): Promise<ApiError> {
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
    if (message.length > 200) message = message.slice(0, 200) + "…";
  }
  return new ApiError(res.status, message, envelope);
}

export async function api<T>(path: string, options?: ApiOptions): Promise<T> {
  const method = (options?.method ?? "GET").toUpperCase();
  const needsContentType = ["POST", "PUT", "PATCH"].includes(method);
  const headers: Record<string, string> = {
    ...(needsContentType ? { "Content-Type": "application/json" } : {}),
    ...(options?.headers as Record<string, string>),
  };

  const { skipAuthRedirect, ...fetchOptions } = options ?? {};

  const doFetch = () =>
    fetch(`${API_BASE}${path}`, { ...fetchOptions, headers, credentials: "include" });

  let res = await doFetch();

  // ── 401 handling: try silent token refresh before giving up ──────────────
  if (res.status === 401 && !skipAuthRedirect) {
    const refreshed = await _tryRefresh();
    if (refreshed) {
      // Retry the original request with the new access token cookie
      res = await doFetch();
    }

    // If still 401 after refresh attempt, redirect to login
    if (res.status === 401) {
      if (
        typeof window !== "undefined" &&
        !window.location.pathname.startsWith("/login") &&
        !window.location.pathname.startsWith("/setup")
      ) {
        window.location.href = "/login";
      }
      throw new ApiError(401, "Session expired");
    }
  }

  if (!res.ok) {
    throw await _parseError(res);
  }

  if (res.status === 204) {
    // Return an empty object — callers that destructure the result (e.g.
    // `const { id } = await api(...)`) won't throw on a void response,
    // while callers that discard the result are unaffected.
    return {} as T;
  }

  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return (await res.text()) as any as T;
  }

  const text = await res.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}
