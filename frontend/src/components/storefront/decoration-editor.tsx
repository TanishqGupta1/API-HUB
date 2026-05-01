"use client";

import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface MasterOptionAttribute {
  id: string;
  ops_attribute_id: number;
  title: string;
  sort_order: number;
}

interface MasterOption {
  id: string;
  ops_master_option_id: number;
  title: string;
  option_key: string | null;
  options_type: string | null;
  sort_order: number;
  attributes: MasterOptionAttribute[];
}

interface Props {
  customerId: string;
  productId: string;
}

export function DecorationEditor({ customerId, productId }: Props) {
  const [masterOptions, setMasterOptions] = useState<MasterOption[]>([]);
  const [selected, setSelected] = useState<Record<string, number[]>>({});
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setLoadingOptions(true);
    Promise.all([
      api<MasterOption[]>("/api/master-options"),
      api<{ decoration_options: { option_key: string; attributes: { master_attribute_id?: number }[] }[] }>(
        `/api/customers/${customerId}/products/${productId}/decorations`
      ).catch(() => null),
    ]).then(([opts, existing]) => {
      setMasterOptions(opts.filter((o) => (o.attributes ?? []).length > 0));
      if (existing) {
        const init: Record<string, number[]> = {};
        for (const opt of existing.decoration_options) {
          if (opt.option_key) {
            init[opt.option_key] = opt.attributes
              .map((a) => a.master_attribute_id)
              .filter((id): id is number => id != null);
          }
        }
        setSelected(init);
      }
    }).finally(() => setLoadingOptions(false));
  }, [customerId, productId]);

  const toggle = useCallback((optionKey: string, attrId: number) => {
    setSelected((prev) => {
      const cur = prev[optionKey] ?? [];
      return {
        ...prev,
        [optionKey]: cur.includes(attrId)
          ? cur.filter((id) => id !== attrId)
          : [...cur, attrId],
      };
    });
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const decoration_options = masterOptions
        .filter((o) => o.option_key && (selected[o.option_key] ?? []).length > 0)
        .map((o) => ({
          option_key: o.option_key!,
          title: o.title,
          options_type: o.options_type ?? "checkbox",
          sort_order: o.sort_order,
          required: false,
          master_option_id: o.ops_master_option_id,
          attributes: o.attributes
            .filter((a) => (selected[o.option_key!] ?? []).includes(a.ops_attribute_id))
            .map((a, i) => ({
              title: a.title,
              sort_order: i,
              master_attribute_id: a.ops_attribute_id,
            })),
        }));

      if (decoration_options.length === 0) {
        await api(`/api/customers/${customerId}/products/${productId}/decorations`, {
          method: "DELETE",
        }).catch(() => null);
      } else {
        await api(`/api/customers/${customerId}/products/${productId}/decorations`, {
          method: "PUT",
          body: JSON.stringify({ decoration_options }),
        });
      }

      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  if (loadingOptions) {
    return (
      <div className="space-y-3 animate-pulse">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-16 bg-[#ebe8e3] rounded-lg" />
        ))}
      </div>
    );
  }

  if (masterOptions.length === 0) {
    return (
      <p className="text-[13px] text-[#888894] py-4">
        No master options configured. Sync from OPS first.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <p className="text-[13px] text-[#888894]">
        Select the decoration options that apply to this product for this customer. These will be
        merged with the base apparel options when pushed to OPS.
      </p>

      {masterOptions.map((opt) => {
        const key = opt.option_key ?? opt.id;
        const picked = selected[key] ?? [];
        return (
          <div key={opt.id}>
            <p className="text-[12px] font-bold text-[#1e1e24] uppercase tracking-wide mb-2">
              {opt.title}
            </p>
            <div className="flex flex-wrap gap-2">
              {opt.attributes.map((attr) => {
                const active = picked.includes(attr.ops_attribute_id);
                return (
                  <button
                    key={attr.id}
                    type="button"
                    onClick={() => toggle(key, attr.ops_attribute_id)}
                    className={`rounded-md border px-3 py-1.5 text-[12px] font-medium transition-colors ${
                      active
                        ? "border-[#1e4d92] bg-[#eef4fb] text-[#1e4d92]"
                        : "border-[#cfccc8] bg-white text-[#484852] hover:border-[#1e4d92]"
                    }`}
                  >
                    {attr.title}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}

      <div className="pt-2 flex items-center gap-3">
        <Button onClick={save} disabled={saving} size="sm" className="bg-[#1e4d92] hover:bg-[#173d74]">
          {saving ? "Saving…" : saved ? "Saved ✓" : "Save Decoration"}
        </Button>
        {saved && (
          <span className="text-[12px] text-[#247a52] font-medium">Changes saved</span>
        )}
      </div>
    </div>
  );
}
