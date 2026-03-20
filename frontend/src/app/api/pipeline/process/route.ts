import { NextRequest, NextResponse } from "next/server";

const PIPELINE_TIMEOUT_MS = 120_000; // 2 minutes for LLM-heavy pipeline

function deriveLogicalUrlFromOrg(orgUrl: string): string {
  try {
    const parsed = new URL(orgUrl);
    if (parsed.port === "8000") {
      parsed.port = "8080";
      return parsed.toString().replace(/\/$/, "");
    }
    return `${parsed.protocol}//${parsed.hostname}:8080`;
  } catch {
    return orgUrl.replace(":8000", ":8080").replace(/\/$/, "");
  }
}

export async function POST(request: NextRequest) {
  const orgLayerUrl = process.env.BACKEND_INTERNAL_URL;
  const logicalLayerUrl =
    process.env.LOGICAL_BACKEND_INTERNAL_URL ||
    (orgLayerUrl ? deriveLogicalUrlFromOrg(orgLayerUrl) : undefined);
  if (!logicalLayerUrl) {
    return NextResponse.json(
      { detail: "Logical backend URL is not configured" },
      { status: 500 }
    );
  }

  const url = `${logicalLayerUrl.replace(/\/$/, "")}/api/pipeline/process`;
  let body: string;
  try {
    body = await request.text();
  } catch {
    return NextResponse.json(
      { detail: "Invalid request body" },
      { status: 400 }
    );
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), PIPELINE_TIMEOUT_MS);

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: body || undefined,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    const contentType = res.headers.get("content-type") ?? "";
    const data =
      contentType.includes("application/json")
        ? await res.json().catch(() => ({}))
        : { detail: await res.text().catch(() => "Unknown error") };
    return NextResponse.json(data, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    clearTimeout(timeoutId);
    const message =
      err instanceof Error
        ? err.name === "AbortError"
          ? "Pipeline timed out (120s limit)"
          : err.message
        : "Pipeline request failed";
    return NextResponse.json(
      { detail: message },
      { status: 500 }
    );
  }
}
