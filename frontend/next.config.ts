import type { NextConfig } from "next";

const apiBase = process.env.BACKEND_INTERNAL_URL;
if (!apiBase) {
  throw new Error("BACKEND_INTERNAL_URL is required for frontend rewrites.");
}

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${apiBase}/health`,
      },
    ];
  },
};

export default nextConfig;
