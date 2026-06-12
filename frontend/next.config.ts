import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Fully client-side app: static export so Render can serve it as a static
  // site (no Node server, no cold starts). Build output lands in out/.
  output: "export",
};

export default nextConfig;
