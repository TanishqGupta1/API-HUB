import type { NextConfig } from "next";

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

export default nextConfig;
