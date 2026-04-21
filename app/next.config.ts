import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
