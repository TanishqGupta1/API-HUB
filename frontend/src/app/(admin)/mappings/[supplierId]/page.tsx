"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import type { Supplier } from "@/lib/types";
import { toast } from "sonner";
import { SanMarMappingPanel } from "@/components/mappings/sanmar-mapping-panel";
import { OpsMappingPanel } from "@/components/mappings/ops-mapping-panel";
import { FourOverMappingPanel } from "@/components/mappings/fourover-mapping-panel";
import { ProductPreviewStrip } from "@/components/mappings/product-preview-strip";

export default function FieldMappingPage() {
  const { supplierId } = useParams<{ supplierId: string }>();
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [supplierSpecific, setSupplierSpecific] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    api<Supplier>(`/api/suppliers/${supplierId}`)
      .then((s) => {
        setSupplier(s);
        const raw = s.field_mappings ?? {};
        const specific: Record<string, string> = {};
        for (const [k, v] of Object.entries(raw)) {
          if (k.includes(".")) {
            specific[k] = String(v);
          }
        }
        setSupplierSpecific(specific);
      })
      .catch(log.error);
  }, [supplierId]);

  const handleSave = async (nextSpecific?: Record<string, string>) => {
    const payload = nextSpecific ?? supplierSpecific;
    setSaving(true);
    try {
      await api(`/api/suppliers/${supplierId}/mappings`, {
        method: "PUT",
        body: JSON.stringify({ mapping: payload }),
      });
      toast.success("Configuration saved");
    } catch (e) {
      toast.error("Failed to save configuration");
    } finally {
      setSaving(false);
    }
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
          <ProductPreviewStrip key={refreshKey} supplierId={supplier.id} />
        </div>
      )}

      {/* Protocol Specific Configuration (SanMar/OPS/etc) */}

      {supplier && (
        <div className="mt-6">
          {supplier.protocol === "soap" ||
          supplier.protocol === "promostandards" ? (
            <SanMarMappingPanel
              supplierId={supplier.id}
              value={supplierSpecific}
              onChange={(next) => {
                setSupplierSpecific(next);
                handleSave(next);
              }}
              onSyncComplete={() => {
                setRefreshKey((prev) => prev + 1);
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
