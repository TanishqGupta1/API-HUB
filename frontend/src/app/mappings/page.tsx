"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Supplier } from "@/lib/types";

export default function MappingsIndexPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Supplier[]>("/api/suppliers")
      .then(setSuppliers)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--ink)" }}>
        Data Configuration
      </h1>
      <p className="text-sm mb-6" style={{ color: "var(--ink-muted)" }}>
        Select a supplier to configure how its data maps to the business schema.
      </p>

      {loading && (
        <p className="text-sm" style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
          Loading suppliers…
        </p>
      )}

      {error && (
        <div
          className="rounded-lg px-4 py-3 text-sm"
          style={{ background: "var(--red-pale)", color: "var(--red)", border: "1px solid var(--red)" }}
        >
          {error}
        </div>
      )}

      {!loading && !error && suppliers.length === 0 && (
        <p className="text-sm" style={{ color: "var(--ink-muted)" }}>
          No suppliers found. Add a supplier first.
        </p>
      )}

      <div className="flex flex-col gap-3" style={{ maxWidth: 640 }}>
        {suppliers.map((s) => (
          <div
            key={s.id}
            className="rounded-lg flex items-center justify-between px-5 py-4"
            style={{
              background: "white",
              border: "1px solid var(--border)",
              boxShadow: "0 1px 4px var(--shadow)",
            }}
          >
            <div>
              <div className="font-semibold text-sm" style={{ color: "var(--ink)" }}>
                {s.name}
              </div>
              <div
                className="text-xs mt-0.5"
                style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}
              >
                {s.slug} · {s.protocol.toUpperCase()}
                {s.promostandards_code ? ` · ${s.promostandards_code}` : ""}
              </div>
            </div>

            <Link
              href={`/mappings/${s.id}`}
              className="px-4 py-2 rounded-md text-xs font-semibold"
              style={{ background: "var(--blue)", color: "white", textDecoration: "none" }}
            >
              Configure Data
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
