import type { NextConfig } from "next";

/**
 * Static export — the whole site compiles to plain HTML/CSS/JS in `out/`.
 * This is the portability guarantee the owner asked for: the site can move
 * from Vercel to ANY host later by copying `out/` and flipping DNS.
 * No server features are used (no DB, no API routes, no Vercel-specific APIs).
 */
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  // Allows a verification build into a scratch distDir while `next dev` holds .next
  distDir: process.env.NEXT_DIST_DIR || ".next",
  turbopack: { root: __dirname },
};

export default nextConfig;
