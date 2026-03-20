import { NextRequest } from "next/server";

import { proxyToOrgBackend } from "@/app/api/requests/proxy";

const ROUTE_LABEL = "/api/requests/[requestId]";

function normalizeRequestId(value: string) {
  return encodeURIComponent(value.trim());
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ requestId: string }> },
) {
  const { requestId } = await params
  return proxyToOrgBackend({
    routeLabel: ROUTE_LABEL,
    upstreamPath: `/api/requests/${normalizeRequestId(requestId)}`,
    request,
  });
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ requestId: string }> },
) {
  const { requestId } = await params
  return proxyToOrgBackend({
    routeLabel: ROUTE_LABEL,
    upstreamPath: `/api/requests/${normalizeRequestId(requestId)}`,
    request,
  });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ requestId: string }> },
) {
  const { requestId } = await params
  return proxyToOrgBackend({
    routeLabel: ROUTE_LABEL,
    upstreamPath: `/api/requests/${normalizeRequestId(requestId)}`,
    request,
  });
}
