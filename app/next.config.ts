import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  outputFileTracingRoot: path.join(__dirname),
  typescript: {
    // Next 15.5 typed-routes validator can mis-resolve `src/app/page.tsx` on Windows (false positive).
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Needed for deck.gl / maplibre-gl which rely on browser globals
  webpack: (config) => {
    config.resolve.fallback = { fs: false, path: false };
    return config;
  },
};

export default nextConfig;
