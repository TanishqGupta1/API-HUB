/**
 * Resolves the API base URL.
 *
 * If the page is loaded over HTTPS but NEXT_PUBLIC_API_URL is set to an
 * `http://` URL (a common deployment misconfig where the env points at a
 * raw ALB hostname), browsers block the fetch as Mixed Content. To keep
 * the UI working in that case, we upgrade the scheme to `https://`
 * on the client side.
 */
export function resolveApiBase(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  if (typeof window !== "undefined" && window.location.protocol === "https:") {
    if (raw.startsWith("http://")) {
      return "https://" + raw.slice("http://".length);
    }
  }

  return raw;
}
