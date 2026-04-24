import { NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const INGEST_SECRET = process.env.INGEST_SHARED_SECRET ?? "";

export async function POST() {
  if (!INGEST_SECRET) {
    return NextResponse.json(
      { detail: "INGEST_SHARED_SECRET not set in frontend environment" },
      { status: 500 },
    );
  }

  const upstream = await fetch(`${API_BASE}/api/master-options/sync`, {
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
