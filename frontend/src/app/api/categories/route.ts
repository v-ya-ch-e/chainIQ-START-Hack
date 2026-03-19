import { NextResponse } from "next/server";

const backendBase = process.env.BACKEND_INTERNAL_URL;

export async function GET() {
  if (!backendBase) {
    return NextResponse.json(
      { error: "BACKEND_INTERNAL_URL is not configured." },
      { status: 500 },
    );
  }

  try {
    const response = await fetch(`${backendBase}/api/categories/`, {
      headers: { accept: "application/json" },
      cache: "no-store",
    });

    if (!response.ok) {
      const body = await response.text();
      return NextResponse.json(
        {
          error: "Failed to fetch categories from backend.",
          status: response.status,
          details: body.slice(0, 500),
        },
        { status: response.status },
      );
    }

    const payload = await response.json();
    return NextResponse.json(payload, { status: 200 });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown fetch error";
    return NextResponse.json(
      { error: "Categories proxy failed.", details: message },
      { status: 502 },
    );
  }
}
