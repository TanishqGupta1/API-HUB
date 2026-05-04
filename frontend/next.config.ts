import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // isomorphic-dompurify uses jsdom on the server, which reads CSS files via
  // __dirname. Webpack loses the real __dirname when bundling, causing ENOENT.
  // Marking both as external keeps them out of the bundle so __dirname resolves correctly.
  serverExternalPackages: ["isomorphic-dompurify", "jsdom"],
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
      { protocol: "http", hostname: "**" },
    ],
  },
  output: "standalone",
};

export default nextConfig;
