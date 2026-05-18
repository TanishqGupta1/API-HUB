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

export const API_BASE = RAW_API_URL ?? "http://localhost:8000";
export const N8N_BASE = RAW_N8N_URL ?? "http://localhost:5678";
