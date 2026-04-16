"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { Supplier } from "@/lib/types";

const CANONICAL_FIELDS = [
  "product_name", "supplier_sku", "brand", "description",
  "product_type", "color", "size", "base_price", "inventory",
  "image_url", "warehouse",
];

interface Mapping { source: string; target: string }

export default function FieldMappingPage() {
  const { supplierId } = useParams<{ supplierId: string }>();
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [mappings, setMappings] = useState<Mapping[]>(
    CANONICAL_FIELDS.map((t) => ({ source: "", target: t }))
  );
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    api<Supplier>(`/api/suppliers/${supplierId}`)
      .then(setSupplier)
      .catch(console.error);
  }, [supplierId]);

  const updateSource = (target: string, source: string) => {
    setMappings((prev) =>
      prev.map((m) => (m.target === target ? { ...m, source } : m))
    );
    setSaved(false);
    setSaveError(null);
  };

  const handleSave = async () => {
    const mapping = Object.fromEntries(
      mappings.filter((m) => m.source).map((m) => [m.source, m.target])
    );
    try {
      await api(`/api/suppliers/${supplierId}/mappings`, {
        method: "PUT",
        body: JSON.stringify({ mapping }),
      });
      setSaved(true);
      setSaveError(null);
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : "Save failed");
    }
  };

  const activeMappings = mappings.filter((m) => m.source);
  const jsonPreview = JSON.stringify(
    Object.fromEntries(activeMappings.map((m) => [m.source, m.target])),
    null,
    2
  );

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--ink)" }}>
        Field Mappings
      </h1>
      <p className="text-sm mb-6" style={{ color: "var(--ink-muted)" }}>
        {supplier
          ? `${supplier.name} — map supplier fields to canonical schema`
          : "Loading…"}
      </p>

      <div className="grid grid-cols-2 gap-6">
        {/* Mapping editor */}
        <div>
          <div
            className="rounded-lg border overflow-hidden"
            style={{ borderColor: "var(--border)", background: "white" }}
          >
            <div
              className="grid grid-cols-2 px-4 py-2.5 border-b text-xs font-semibold uppercase tracking-wide"
              style={{
                borderColor: "var(--border)",
                color: "var(--ink-muted)",
                fontFamily: "var(--font-mono)",
              }}
            >
              <span>Source (Supplier)</span>
              <span>Target (Canonical)</span>
            </div>

            {mappings.map((m) => (
              <div
                key={m.target}
                className="grid grid-cols-2 items-center gap-3 px-4 py-2 border-b last:border-0"
                style={{ borderColor: "var(--border)" }}
              >
                <input
                  type="text"
                  value={m.source}
                  placeholder="supplier field name"
                  onChange={(e) => updateSource(m.target, e.target.value)}
                  className="px-2 py-1.5 rounded text-xs outline-none w-full"
                  style={{
                    border: "1px solid var(--border)",
                    background: "var(--paper)",
                    fontFamily: "var(--font-mono)",
                  }}
                />
                <span
                  className="text-xs font-semibold"
                  style={{ color: "var(--blue)", fontFamily: "var(--font-mono)" }}
                >
                  {m.target}
                </span>
              </div>
            ))}
          </div>

          <div className="flex gap-3 mt-4 items-center">
            <button
              onClick={handleSave}
              className="px-5 py-2 rounded-md text-sm font-semibold"
              style={{ background: "var(--blue)", color: "white" }}
            >
              Save Mappings
            </button>
            {saved && (
              <span
                className="text-sm"
                style={{ color: "var(--green)", fontFamily: "var(--font-mono)" }}
              >
                Saved ✓
              </span>
            )}
            {saveError && (
              <span
                className="text-xs"
                style={{ color: "var(--red)", fontFamily: "var(--font-mono)" }}
              >
                {saveError}
              </span>
            )}
          </div>
        </div>

        {/* JSON preview */}
        <div>
          <div
            className="text-xs font-semibold uppercase tracking-widest mb-2"
            style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}
          >
            JSON Preview
          </div>
          <pre
            className="rounded-lg p-4 text-xs overflow-auto"
            style={{
              background: "var(--paper-warm)",
              border: "1px solid var(--border)",
              fontFamily: "var(--font-mono)",
              color: "var(--ink)",
              minHeight: 200,
            }}
          >
            {activeMappings.length > 0
              ? jsonPreview
              : "// Add mappings to preview JSON"}
          </pre>
        </div>
      </div>
    </div>
  );
}
