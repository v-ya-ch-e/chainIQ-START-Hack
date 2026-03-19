import type { NextConfig } from "next";

const apiBase = process.env.BACKEND_INTERNAL_URL;
if (!apiBase) {
  throw new Error("BACKEND_INTERNAL_URL is required for frontend rewrites.");
}
const logicalApiBase =
  process.env.LOGICAL_BACKEND_INTERNAL_URL || apiBase.replace(":8000", ":8080");

// #region agent log
console.log(`[DEBUG-105a7f] next.config.ts loaded: apiBase=${apiBase}, logicalApiBase=${logicalApiBase}, LOGICAL_BACKEND_INTERNAL_URL=${process.env.LOGICAL_BACKEND_INTERNAL_URL ?? "(unset)"}`);
// #endregion

const nextConfig: NextConfig = {
  transpilePackages: ["@assistant-ui/react", "@assistant-ui/react-markdown", "@assistant-ui/react-ai-sdk"],
  // Keep trailing-slash API paths untouched so rewrites don't trigger
  // redirect chains that expose internal container hostnames to browsers.
  skipTrailingSlashRedirect: true,
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
