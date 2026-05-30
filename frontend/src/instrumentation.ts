import * as Sentry from "@sentry/nextjs";

export async function register() {
  const dsn = process.env.SENTRY_DSN;
  if (!dsn) return;

  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { init } = await import("@sentry/nextjs");
    init({ dsn, environment: process.env.NODE_ENV, tracesSampleRate: 0.2 });
  }

  if (process.env.NEXT_RUNTIME === "edge") {
    const { init } = await import("@sentry/nextjs");
    init({ dsn, environment: process.env.NODE_ENV, tracesSampleRate: 0.2 });
  }
}

export const onRequestError = Sentry.captureRequestError;
