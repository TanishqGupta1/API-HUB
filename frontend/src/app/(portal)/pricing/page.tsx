"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Loader2, Tag, CheckCircle2, XCircle } from "lucide-react";

interface MarkupRule {
  id: string;
  scope: string;
  markup_pct: number | null;
  markup_amount: number | null;
  min_margin: number | null;
  rounding: string | null;
  priority: number;
  is_active: boolean;
}

function fmt(val: number | null, suffix: string) {
  if (val === null || val === undefined) return "—";
  return `${val}${suffix}`;
}

function scopeLabel(scope: string) {
  if (scope === "all") return "All Products";
  if (scope.startsWith("supplier:")) return `Supplier: ${scope.replace("supplier:", "")}`;
  if (scope.startsWith("category:")) return `Category: ${scope.replace("category:", "")}`;
  if (scope.startsWith("product:")) return `Product: ${scope.replace("product:", "")}`;
  return scope;
}

export default function PortalPricing() {
  const [rules, setRules] = useState<MarkupRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api<MarkupRule[]>("/api/portal/markup-rules")
      .then(setRules)
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div>
        <h1 className="text-2xl font-black text-[#1e1e24] tracking-tight">Pricing Rules</h1>
        <p className="text-sm text-[#888894] font-medium mt-1">
          Markup rules applied to your storefront — managed by your administrator
        </p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-8 h-8 animate-spin text-[#1e4d92]" />
        </div>
      ) : !rules.length ? (
        <div className="text-center py-20 bg-white rounded-3xl border-2 border-dashed border-[#cfccc8]">
          <div className="w-14 h-14 rounded-2xl bg-[#f9f7f4] border border-[#cfccc8] flex items-center justify-center mx-auto mb-4">
            <Tag className="w-7 h-7 text-[#888894]" />
          </div>
          <h3 className="text-base font-black text-[#1e1e24] mb-1">No pricing rules configured</h3>
          <p className="text-sm text-[#888894]">Contact your administrator to set up markup rules.</p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-[#ebe9e6] overflow-hidden">
          {/* Header */}
          <div className="grid grid-cols-[1fr_100px_100px_90px_90px_60px] gap-4 px-6 py-3 border-b border-[#f2f0ed] bg-[#f9f7f4]">
            {["Scope", "Markup %", "Flat Amount", "Min Margin", "Rounding", "Active"].map((h) => (
              <div key={h} className="text-[10px] font-black uppercase tracking-widest text-[#888894]">{h}</div>
            ))}
          </div>

          <div className="divide-y divide-[#f2f0ed]">
            {rules.map((rule) => (
              <div
                key={rule.id}
                className={`grid grid-cols-[1fr_100px_100px_90px_90px_60px] gap-4 px-6 py-4 items-center ${
                  !rule.is_active ? "opacity-40" : ""
                }`}
              >
                {/* Scope */}
                <div>
                  <div className="text-sm font-bold text-[#1e1e24]">{scopeLabel(rule.scope)}</div>
                  <div className="text-[10px] text-[#888894] font-mono mt-0.5">Priority {rule.priority}</div>
                </div>

                {/* Markup % */}
                <div className="text-sm font-mono text-[#484852]">
                  {fmt(rule.markup_pct, "%")}
                </div>

                {/* Flat amount */}
                <div className="text-sm font-mono text-[#484852]">
                  {rule.markup_amount !== null ? `$${rule.markup_amount}` : "—"}
                </div>

                {/* Min margin */}
                <div className="text-sm font-mono text-[#484852]">
                  {fmt(rule.min_margin, "%")}
                </div>

                {/* Rounding */}
                <div className="text-sm font-mono text-[#484852]">
                  {rule.rounding ?? "—"}
                </div>

                {/* Active */}
                <div>
                  {rule.is_active
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    : <XCircle className="w-4 h-4 text-[#cfccc8]" />
                  }
                </div>
              </div>
            ))}
          </div>

          <div className="px-6 py-4 border-t border-[#f2f0ed] bg-[#f9f7f4]">
            <p className="text-[11px] text-[#888894]">
              Rules are applied in priority order (highest first). Contact your administrator to make changes.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
