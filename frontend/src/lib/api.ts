const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };

  const secret = process.env.NEXT_PUBLIC_INGEST_SECRET;
  if (secret) {
    headers["X-Ingest-Secret"] = secret;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    let message: string;
    if (contentType.includes("application/json")) {
      const json = await res.json().catch(() => null);
      message = json?.detail ?? JSON.stringify(json) ?? res.statusText;
    } else {
      message = await res.text().catch(() => res.statusText);
      // Truncate HTML responses to avoid flooding the UI
      if (message.length > 200) message = message.slice(0, 200) + "…";
    }
    throw new Error(`API ${res.status}: ${message}`);
  }

  return res.json() as Promise<T>;
}
