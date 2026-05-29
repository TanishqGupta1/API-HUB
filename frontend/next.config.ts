import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  serverExternalPackages: ["isomorphic-dompurify", "jsdom"],
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
      { protocol: "http", hostname: "**" },
    ],
  },
  output: "standalone",
  async redirects() {
    return [
      // Typo guard: /privew → /preview
      {
        source: "/products/:id/privew",
        destination: "/products/:id/preview",
        permanent: false,
      },
    ];
  },
};

export default withSentryConfig(nextConfig, {
  silent: true,
  // Sentry is opt-in — if SENTRY_DSN / NEXT_PUBLIC_SENTRY_DSN are unset
  // the SDK initialises as a no-op so local dev is unaffected.
  webpack: {
    treeshake: {
      removeDebugLogging: true,
    },
  },
});
