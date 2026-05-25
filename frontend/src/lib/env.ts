/**
 * Centralized public env access.
 *
 * Background: Next.js inlines NEXT_PUBLIC_* env vars at build time. If the
 * Docker image is built without `NEXT_PUBLIC_API_URL` set, the fallback
 * `http://localhost:8000` is baked in — which makes login fail for any
 * browser that isn't on the same host as the API.
 *
 * One source of truth here. Adjust here, every consumer follows.
 */

const RAW_API_URL = process.env.NEXT_PUBLIC_API_URL;
const RAW_N8N_URL = process.env.NEXT_PUBLIC_N8N_URL;
// Server-only URL — used by Next.js API routes (route handlers) that proxy to
// the backend from inside the same Docker network. In dev compose this points
// to http://api:8000; in the browser this var is never read (Next.js strips
// non-PUBLIC env vars from the client bundle).
const RAW_SERVER_API_URL = process.env.API_BASE_URL;
const NODE_ENV = process.env.NODE_ENV;

if (NODE_ENV === "production" && !RAW_API_URL) {
  // Surface the misconfiguration loudly at module load instead of letting
  // login silently 401 from a localhost call that never reaches the API.
  throw new Error(
    "NEXT_PUBLIC_API_URL is not set. Pass it as --build-arg to the frontend " +
      "Docker build (or set it in CI vars / .env.local) before running " +
      "`next build`.",
  );
}

/**
 * Auto-upgrade `http://` to `https://` when the page is loaded over HTTPS.
 *
 * Why: in some deployments `NEXT_PUBLIC_API_URL` is baked at build time to
 * a raw ALB hostname over HTTP (e.g. `http://apihub-dev-alb-...amazonaws.com`).
 * When the frontend is served over HTTPS, the browser blocks those fetches
 * as Mixed Content and login fails with "Failed to fetch". Forcing HTTPS
 * client-side keeps login working even when the env var is misconfigured.
 *
 * No-op on the server (window is undefined) and in plain-HTTP local dev.
 */
function upgradeToHttpsIfNeeded(url: string): string {
  if (typeof window === "undefined") return url;
  if (window.location.protocol !== "https:") return url;
  if (!url.startsWith("http://")) return url;
  return "https://" + url.slice("http://".length);
}

export const API_BASE = upgradeToHttpsIfNeeded(RAW_API_URL ?? "http://localhost:8000");
export const N8N_BASE = upgradeToHttpsIfNeeded(RAW_N8N_URL ?? "http://localhost:5678");
// Server-side: prefer API_BASE_URL (e.g. http://api:8000 inside Docker),
// fall back to the public URL, then to localhost for non-Docker dev.
export const SERVER_API_BASE = RAW_SERVER_API_URL ?? RAW_API_URL ?? "http://127.0.0.1:8000";
