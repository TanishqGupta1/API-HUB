import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  serverExternalPackages: ["isomorphic-dompurify", "jsdom"],
  images: {
    // /_next/image will only proxy URLs whose host matches one of these
    // patterns. Keep this list tight — every entry is an SSRF/exfil vector
    // for the optimiser. http:// is intentionally omitted; SVG is left off
    // (Next default) so attacker-controlled markup can't execute.
    remotePatterns: [
      { protocol: "https", hostname: "*.sanmar.com" },
      { protocol: "https", hostname: "cdn.ssactivewear.com" },
      { protocol: "https", hostname: "*.alphabroder.com" },
      { protocol: "https", hostname: "*.4over.com" },
      { protocol: "https", hostname: "dei4q67dwezeh.cloudfront.net" },
      // placehold.co — placeholder images used only by SEED/demo products.
      // Real products use the supplier CDNs above. Dev/demo convenience.
      { protocol: "https", hostname: "placehold.co" },
      // Pin the project CDN to its specific distribution. Avoid `*.cloudfront.net`
      // — that allows ANY CloudFront distribution, including ones the attacker
      // controls. Set NEXT_PUBLIC_CDN_HOST in env when the CDN is provisioned.
      ...(process.env.NEXT_PUBLIC_CDN_HOST
        ? [{ protocol: "https" as const, hostname: process.env.NEXT_PUBLIC_CDN_HOST }]
        : []),
    ],
    // placehold.co serves SVG. Allow it, but sandbox the markup + block scripts
    // via CSP so an SVG can't execute anything (mitigates dangerouslyAllowSVG).
    dangerouslyAllowSVG: true,
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
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
