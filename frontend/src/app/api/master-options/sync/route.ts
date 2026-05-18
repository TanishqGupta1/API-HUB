import { NextResponse } from "next/server";

import { SERVER_API_BASE } from "@/lib/env";

const INGEST_SECRET = process.env.INGEST_SHARED_SECRET ?? "";

export async function POST() {
  if (!INGEST_SECRET) {
    return NextResponse.json(
      { detail: "INGEST_SHARED_SECRET not set in frontend environment" },
      { status: 500 },
    );
  }

  const upstream = await fetch(`${SERVER_API_BASE}/api/master-options/sync`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Ingest-Secret": INGEST_SECRET,
    },
    body: "{}",
  });

  const text = await upstream.text();
  const contentType = upstream.headers.get("content-type") ?? "application/json";
  return new NextResponse(text, {
    status: upstream.status,
    headers: { "content-type": contentType },
  });
}
