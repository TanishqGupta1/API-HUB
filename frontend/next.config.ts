import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  serverExternalPackages: ["isomorphic-dompurify", "jsdom"],
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "*.sanmar.com" },
      { protocol: "https", hostname: "cdn.ssactivewear.com" },
      { protocol: "https", hostname: "*.alphabroder.com" },
      { protocol: "https", hostname: "images.alphabroder.com" },
      { protocol: "https", hostname: "*.4over.com" },
      { protocol: "https", hostname: "*.cloudfront.net" },
      // Add project CDN/S3/R2 host here when configured
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
