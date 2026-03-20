import { NextRequest, NextResponse } from "next/server";

type ProxyContext = {
  routeLabel: string;
  upstreamPath: string;
  request: NextRequest;
};

function getOrgBackendBase(): string | null {
  const base = process.env.BACKEND_INTERNAL_URL?.trim();
  if (!base) return null;
  return base.replace(/\/$/, "");
}

function formatInboundPath(request: NextRequest) {
  return `${request.nextUrl.pathname}${request.nextUrl.search}`;
}

function withQuery(path: string, request: NextRequest): string {
  const query = request.nextUrl.search;
  if (!query) return path;
  return `${path}${query}`;
}

function copyForwardHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  const accepted = request.headers.get("accept");
  const contentType = request.headers.get("content-type");
  const authorization = request.headers.get("authorization");

  if (accepted) headers.set("accept", accepted);
  if (contentType) headers.set("content-type", contentType);
  if (authorization) headers.set("authorization", authorization);

  return headers;
}

function copyResponseHeaders(upstream: Response): Headers {
  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  headers.set("cache-control", "no-store");
  return headers;
}

function extractCauseCode(error: unknown): string | null {
  if (!(error instanceof Error)) return null;
  const cause = (error as Error & { cause?: unknown }).cause;
  if (!cause || typeof cause !== "object") return null;
  const code = (cause as { code?: unknown }).code;
  return typeof code === "string" && code.trim() ? code : null;
}

export async function proxyToOrgBackend({
  routeLabel,
  upstreamPath,
  request,
}: ProxyContext) {
  const backendBase = getOrgBackendBase();
  if (!backendBase) {
    console.error(`[${routeLabel}] missing backend configuration`, {
      method: request.method,
      inboundPath: formatInboundPath(request),
      envVar: "BACKEND_INTERNAL_URL",
    });
    return NextResponse.json(
      {
        detail:
          "BACKEND_INTERNAL_URL is not configured for requests proxy.",
      },
      { status: 500 },
    );
  }

  const upstreamUrl = `${backendBase}${withQuery(upstreamPath, request)}`;
  const inboundPath = formatInboundPath(request);

  try {
    const method = request.method.toUpperCase();
    const hasBody = method !== "GET" && method !== "HEAD";
    const body = hasBody ? await request.arrayBuffer() : undefined;

    const upstreamResponse = await fetch(upstreamUrl, {
      method,
      headers: copyForwardHeaders(request),
      body,
      cache: "no-store",
      redirect: "manual",
    });

    console.info(`[${routeLabel}] upstream response`, {
      method,
      inboundPath,
      upstreamUrl,
      status: upstreamResponse.status,
    });

    const responseHeaders = copyResponseHeaders(upstreamResponse);
    if (upstreamResponse.status === 204) {
      return new NextResponse(null, {
        status: upstreamResponse.status,
        headers: responseHeaders,
      });
    }

    const responseBody = await upstreamResponse.text();
    return new NextResponse(responseBody, {
      status: upstreamResponse.status,
      headers: responseHeaders,
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown proxy error";
    const errorClass =
      error instanceof Error ? error.name : "UnknownError";
    const causeCode = extractCauseCode(error);

    console.error(`[${routeLabel}] upstream fetch failed`, {
      method: request.method,
      inboundPath,
      upstreamUrl,
      errorClass,
      message,
      causeCode,
    });

    return NextResponse.json(
      {
        detail:
          "Requests proxy failed to reach organisational backend.",
        upstream_url: upstreamUrl,
        error_class: errorClass,
        error: message,
        cause_code: causeCode,
      },
      { status: 502 },
    );
  }
}
