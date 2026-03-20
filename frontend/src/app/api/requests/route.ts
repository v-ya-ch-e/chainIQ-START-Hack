import { NextRequest } from "next/server";

import { proxyToOrgBackend } from "@/app/api/requests/proxy";

const ROUTE_LABEL = "/api/requests";

export async function GET(request: NextRequest) {
  return proxyToOrgBackend({
    routeLabel: ROUTE_LABEL,
    upstreamPath: "/api/requests/",
    request,
  });
}

export async function POST(request: NextRequest) {
  return proxyToOrgBackend({
    routeLabel: ROUTE_LABEL,
    upstreamPath: "/api/requests/",
    request,
  });
}
