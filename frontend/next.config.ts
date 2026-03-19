import type { NextConfig } from "next";

const apiBase = process.env.BACKEND_INTERNAL_URL;
if (!apiBase) {
  throw new Error("BACKEND_INTERNAL_URL is required for frontend rewrites.");
}
const logicalApiBase =
  process.env.LOGICAL_BACKEND_INTERNAL_URL ??
  apiBase.replace(":8000", ":8080");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/pipeline/:path*",
        destination: `${logicalApiBase}/api/pipeline/:path*`,
      },
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
