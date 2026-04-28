"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import type { Supplier } from "@/lib/types";
import { SanMarMappingPanel } from "@/components/mappings/sanmar-mapping-panel";
import { OpsMappingPanel } from "@/components/mappings/ops-mapping-panel";
import { FourOverMappingPanel } from "@/components/mappings/fourover-mapping-panel";
import { ProductPreviewStrip } from "@/components/mappings/product-preview-strip";

const CANONICAL_FIELDS = [
  "product_name", "supplier_sku", "brand", "description",
  "product_type", "color", "size", "base_price", "inventory",
  "image_url", "warehouse",
];

interface Mapping { source: string; target: string }

const SAMPLE_PAYLOAD = `{
  "productName": "Essential Tee",
  "styleID": "PC61",
  "brandName": "Port & Company",
  "colorName": "Navy",
  "sizeName": "M",
  "price": 3.99,
  "qty": 120
}`;

function applyMapping(
  raw: Record<string, unknown>,
  active: Mapping[]
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const { source, target } of active) {
    if (!source) continue;
    if (source in raw) out[target] = raw[source];
  }
  return out;
}

export default function FieldMappingPage() {
  const { supplierId } = useParams<{ supplierId: string }>();
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [mappings, setMappings] = useState<Mapping[]>(
    CANONICAL_FIELDS.map((t) => ({ source: "", target: t }))
  );
  const [supplierSpecific, setSupplierSpecific] = useState<
    Record<string, string>
  >({});
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [sampleInput, setSampleInput] = useState(SAMPLE_PAYLOAD);
  const [sampleError, setSampleError] = useState<string | null>(null);
  const [testOutput, setTestOutput] = useState<string | null>(null);

  useEffect(() => {
    api<Supplier>(`/api/suppliers/${supplierId}`)
      .then((s) => {
        setSupplier(s);
        const raw = s.field_mappings ?? {};
        if (Object.keys(raw).length > 0) {
          // Split base source→target entries from supplier-specific namespaced keys
          const specific: Record<string, string> = {};
          const baseEntries: [string, string][] = [];
          for (const [k, v] of Object.entries(raw)) {
            if (k.includes(".")) {
              specific[k] = String(v);
            } else {
              baseEntries.push([k, String(v)]);
            }
          }
          setSupplierSpecific(specific);
          setMappings((prev) =>
            prev.map((m) => {
              const source =
                baseEntries.find(([, target]) => target === m.target)?.[0] ?? "";
              return { ...m, source };
            })
          );
        }
      })
      .catch(log.error);
  }, [supplierId]);

  const activeMappings = useMemo(
    () => mappings.filter((m) => m.source),
    [mappings]
  );

  const mappingPayload = useMemo(
    () => ({
      ...Object.fromEntries(activeMappings.map((m) => [m.source, m.target])),
      ...supplierSpecific,
    }),
    [activeMappings, supplierSpecific]
  );

  const jsonPreview = JSON.stringify(mappingPayload, null, 2);

  const updateSource = (target: string, source: string) => {
    setMappings((prev) =>
      prev.map((m) => (m.target === target ? { ...m, source } : m))
    );
    setSaved(false);
    setSaveError(null);
  };

  const handleSave = async () => {
    try {
      await api(`/api/suppliers/${supplierId}/mappings`, {
        method: "PUT",
        body: JSON.stringify({ mapping: mappingPayload }),
      });
      setSaved(true);
      setSaveError(null);
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : "Save failed");
    }
  };

  const handleTest = () => {
    setSampleError(null);
    setTestOutput(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(sampleInput);
    } catch (e) {
      setSampleError(e instanceof Error ? e.message : "Invalid JSON");
      return;
    }
    if (parsed == null || typeof parsed !== "object" || Array.isArray(parsed)) {
      setSampleError("Sample must be a JSON object");
      return;
    }
    const normalized = applyMapping(
      parsed as Record<string, unknown>,
      activeMappings
    );
    setTestOutput(JSON.stringify(normalized, null, 2));
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--ink)" }}>
        Data Configuration
      </h1>
      <p className="text-sm mb-6" style={{ color: "var(--ink-muted)" }}>
        {supplier
          ? `${supplier.name} — map supplier data to business schema`
          : "Loading…"}
      </p>

      {supplier && (
        <div className="my-4">
          <h2 className="text-sm font-bold uppercase tracking-[0.1em] text-[#888894] mb-2">
            Product preview
          </h2>
          <ProductPreviewStrip supplierId={supplier.id} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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

          <div className="flex gap-3 mt-4 items-center flex-wrap">
            <button
              onClick={handleSave}
              className="px-5 py-2 rounded-md text-sm font-semibold"
              style={{ background: "var(--blue)", color: "white" }}
            >
              Save Configuration
            </button>
            <button
              onClick={handleTest}
              disabled={activeMappings.length === 0}
              className="px-5 py-2 rounded-md text-sm font-semibold border"
              style={{
                borderColor: "var(--border)",
                background: "white",
                color: activeMappings.length === 0 ? "var(--ink-muted)" : "var(--ink)",
                cursor: activeMappings.length === 0 ? "not-allowed" : "pointer",
                opacity: activeMappings.length === 0 ? 0.6 : 1,
              }}
            >
              Test with Sample
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

        {/* Right column: JSON preview + sample tester */}
        <div className="flex flex-col gap-5">
          <div>
            <div
              className="text-xs font-semibold uppercase tracking-widest mb-2"
              style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}
            >
              Mapping JSON
            </div>
            <pre
              className="rounded-lg p-4 text-xs overflow-auto"
              style={{
                background: "var(--paper-warm)",
                border: "1px solid var(--border)",
                fontFamily: "var(--font-mono)",
                color: "var(--ink)",
                minHeight: 140,
              }}
            >
              {activeMappings.length > 0
                ? jsonPreview
                : "// Add mappings to preview JSON"}
            </pre>
          </div>

          <div>
            <div
              className="text-xs font-semibold uppercase tracking-widest mb-2"
              style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}
            >
              Sample supplier payload (paste to test)
            </div>
            <textarea
              value={sampleInput}
              onChange={(e) => {
                setSampleInput(e.target.value);
                setSampleError(null);
              }}
              rows={8}
              spellCheck={false}
              className="w-full rounded-lg p-3 text-xs outline-none"
              style={{
                background: "white",
                border: "1px solid var(--border)",
                fontFamily: "var(--font-mono)",
                color: "var(--ink)",
              }}
            />
            {sampleError && (
              <div
                className="text-xs mt-1"
                style={{ color: "var(--red)", fontFamily: "var(--font-mono)" }}
              >
                {sampleError}
              </div>
            )}
          </div>

          {testOutput && (
            <div>
              <div
                className="text-xs font-semibold uppercase tracking-widest mb-2"
                style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}
              >
                Normalized output
              </div>
              <pre
                className="rounded-lg p-4 text-xs overflow-auto"
                style={{
                  background: "var(--paper-warm)",
                  border: "1px solid var(--blue)",
                  fontFamily: "var(--font-mono)",
                  color: "var(--ink)",
                  minHeight: 140,
                }}
              >
                {testOutput}
              </pre>
            </div>
          )}
        </div>
      </div>

      {supplier && (
        <div className="mt-6">
          {supplier.protocol === "soap" ||
          supplier.protocol === "promostandards" ? (
            <SanMarMappingPanel
              supplierId={supplier.id}
              value={supplierSpecific}
              onChange={(next) => {
                setSupplierSpecific(next);
                setSaved(false);
                setSaveError(null);
              }}
            />
          ) : supplier.protocol === "ops_graphql" ? (
            <OpsMappingPanel supplier={supplier} />
          ) : supplier.protocol === "hmac" ||
            supplier.protocol === "rest_hmac" ? (
            <FourOverMappingPanel supplier={supplier} />
          ) : null}
        </div>
      )}
    </div>
  );
}
