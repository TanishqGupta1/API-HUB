"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SupplierCategoryBrowse } from "@/lib/types";

interface Props {
  supplierId: string;
  value: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
}

/** SanMar-specific mapping panel — category default + image opts. */
export function SanMarMappingPanel({ supplierId, value, onChange }: Props) {
  const [categories, setCategories] = useState<SupplierCategoryBrowse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const cats = await api<SupplierCategoryBrowse[]>(
          `/api/suppliers/${supplierId}/categories`,
        );
        setCategories(cats);
      } catch {
        /* OK if not fetchable — panel stays useful without preview */
      } finally {
        setLoading(false);
      }
    })();
  }, [supplierId]);

  const defaultCategory = value["sanmar.default_category"] || "";
  const includeImages = value["sanmar.include_images"] === "true";

  return (
    <div className="bg-white rounded-[10px] border border-[#cfccc8] shadow-[4px_5px_0_rgba(30,77,146,0.08)] p-5 flex flex-col gap-4">
      <div>
        <h3 className="font-bold text-[#1e4d92] text-sm flex items-center gap-2">
          <span className="w-1 h-4 bg-[#1e4d92]" />
          SanMar-specific settings
        </h3>
        <p className="text-xs text-[#888894] mt-1">
          Configure how SanMar data flows into the hub beyond the base field mappings.
        </p>
      </div>

      <div>
        <label className="block text-[11px] font-bold uppercase tracking-[0.1em] text-[#484852] mb-2">
          Default category for imports
        </label>
        <select
          value={defaultCategory}
          onChange={(e) =>
            onChange({ ...value, "sanmar.default_category": e.target.value })
          }
          className="w-full h-9 px-3 text-sm border border-[#cfccc8] rounded bg-white"
          disabled={loading}
        >
          <option value="">— None (choose per import) —</option>
          {categories.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeImages}
            onChange={(e) =>
              onChange({
                ...value,
                "sanmar.include_images": e.target.checked ? "true" : "false",
              })
            }
          />
          Fetch images from Media Content service during import
        </label>
        <p className="text-[11px] text-[#888894] mt-1 ml-6">
          Adds an extra SOAP call per product but populates image_url + variant
          image arrays from SanMar's Media service.
        </p>
      </div>
    </div>
  );
}
