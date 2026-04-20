"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Supplier } from "@/lib/types";
import { EmptyState } from "@/components/ui/empty-state";

export default function MappingsIndexPage() {
  const router = useRouter();
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
      <h1 className="text-3xl font-bold mb-1" style={{ color: "var(--ink)" }}>
        Data Configuration
      </h1>
      <p className="text-sm mb-8" style={{ color: "var(--ink-muted)" }}>
        Define source field mappings and transformation rules for each data provider.
      </p>

      {loading && (
        <p className="text-sm" style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
          Initializing registry…
        </p>
      )}

      {error && (
        <div
          className="rounded-lg px-4 py-3 text-sm mb-6"
          style={{ background: "var(--red-pale)", color: "var(--red)", border: "1px solid var(--red)" }}
        >
          {error}
        </div>
      )}

      {!loading && !error && suppliers.length === 0 && (
        <div style={{ maxWidth: 640 }}>
          <EmptyState
            title="No Sources Found"
            description="You need to connect at least one supplier before you can configure data transformation rules."
            action={{
              label: "Go to Suppliers",
              onClick: () => router.push("/suppliers"),
            }}
            icon={
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
              </svg>
            }
          />
        </div>
      )}

      <div className="flex flex-col gap-3" style={{ maxWidth: 640 }}>
        {suppliers.map((s) => (
          <div
            key={s.id}
            className="rounded-lg flex items-center justify-between px-6 py-5 transition-all hover:bg-vellum"
            style={{
              background: "white",
              border: "1px solid var(--border)",
              boxShadow: "0 1px 4px var(--shadow)",
            }}
          >
            <div>
              <div className="font-semibold text-base" style={{ color: "var(--ink)" }}>
                {s.name}
              </div>
              <div
                className="text-xs mt-1"
                style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}
              >
                {s.protocol.toUpperCase()} PROTOCOL {s.promostandards_code ? `· ${s.promostandards_code}` : ""}
              </div>
            </div>

            <Link
              href={`/mappings/${s.id}`}
              className="px-5 py-2 rounded-md text-xs font-bold uppercase tracking-wide"
              style={{ background: "var(--blue)", color: "white", textDecoration: "none" }}
            >
              Configure Logic
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
