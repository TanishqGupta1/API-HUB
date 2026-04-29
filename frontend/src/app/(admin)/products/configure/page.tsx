"use client";

import { useEffect, useMemo, useState } from "react";
import DOMPurify from "isomorphic-dompurify";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import type { MasterOption, MasterOptionsSyncStatus } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { humanizeOptionName, humanizeAttributeName } from "@/lib/humanize-options";

export default function MasterOptionsCatalogPage() {
  const [options, setOptions] = useState<MasterOption[]>([]);
  const [status, setStatus] = useState<MasterOptionsSyncStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [opts, st] = await Promise.all([
        api<MasterOption[]>("/api/master-options"),
        api<MasterOptionsSyncStatus>("/api/master-options/sync-status"),
      ]);
      setOptions(opts);
      setStatus(st);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const triggerSync = async () => {
    setSyncing(true);
    try {
      await api("/api/master-options/sync", { method: "POST" });
      await new Promise((r) => setTimeout(r, 3000));
      await load();
    } catch (e) {
      log.error("Sync failed", e);
      const n8nUrl = process.env.NEXT_PUBLIC_N8N_URL || "http://localhost:5678";
      alert(`Sync failed. Check n8n at ${n8nUrl}.`);
    } finally {
      setSyncing(false);
    }
  };

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const expandAll = () => setExpanded(new Set(options.map((o) => o.id)));
  const collapseAll = () => setExpanded(new Set());

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return options;
    return options.filter((mo) => {
      const title = humanizeOptionName(mo.title, mo.option_key).toLowerCase();
      const key = (mo.option_key || "").toLowerCase();
      if (title.includes(q) || key.includes(q)) return true;
      return mo.attributes.some((a) =>
        humanizeAttributeName(a.title, (a as any).attribute_key ?? null)
          .toLowerCase()
          .includes(q),
      );
    });
  }, [options, search]);

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#1e1e24]">Master Options Catalog</h1>
          <p className="text-sm text-[#888894] mt-1">
            Global option templates synced from OPS. Click any card to inspect
            attributes. Attach to individual products via Configure Options.
          </p>
          {status && (
            <p className="text-xs text-[#888894] mt-2 font-mono">
              {status.total} synced
              {status.last_synced_at
                ? ` · last ${new Date(status.last_synced_at).toLocaleString()}`
                : " · never synced"}
            </p>
          )}
        </div>
        <Button onClick={triggerSync} disabled={syncing}>
          {syncing ? "Syncing..." : "Sync from OPS"}
        </Button>
      </div>

      {!loading && options.length > 0 && (
        <div className="flex items-center gap-3">
          <Input
            placeholder="Search master options or attributes..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-sm"
          />
          <Button variant="ghost" size="sm" onClick={expandAll}>
            Expand all
          </Button>
          <Button variant="ghost" size="sm" onClick={collapseAll}>
            Collapse all
          </Button>
          <span className="text-xs text-[#888894] ml-auto">
            {filtered.length} / {options.length} shown
          </span>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-40 bg-white rounded-[10px] border border-[#cfccc8] animate-pulse"
            />
          ))}
        </div>
      ) : options.length === 0 ? (
        <div className="bg-white rounded-[10px] border border-[#cfccc8] p-10 text-center">
          <div className="text-[15px] font-semibold text-[#1e1e24] mb-2">
            No master options synced yet
          </div>
          <p className="text-sm text-[#888894] mb-4">
            Click Sync from OPS to pull master options from your OPS account.
          </p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white rounded-[10px] border border-[#cfccc8] p-10 text-center text-[#888894]">
          No matches for &quot;{search}&quot;.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 items-start">
          {filtered.map((mo) => {
            const isOpen = expanded.has(mo.id);
            const displayName = humanizeOptionName(mo.title, mo.option_key);
            const activeAttrs = mo.attributes.filter((a) => (a as any).status === undefined || (a as any).status === 1);
            return (
              <div
                key={mo.id}
                className={`bg-white rounded-[10px] border shadow-[4px_5px_0_rgba(30,77,146,0.08)] overflow-hidden transition-all ${
                  isOpen ? "border-[#1e4d92]" : "border-[#cfccc8] hover:border-[#1e4d92]"
                }`}
              >
                <button
                  type="button"
                  onClick={() => toggle(mo.id)}
                  className="w-full text-left cursor-pointer"
                  aria-expanded={isOpen}
                >
                  <div className="px-5 py-4 border-b border-[#cfccc8] bg-[#ebe8e3] flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-1 h-5 bg-[#1e4d92]" />
                      <span className="font-bold text-[#1e4d92] text-[14px]">
                        {displayName}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-[10px]">
                      <span className="font-mono text-[#888894]">
                        #{mo.ops_master_option_id}
                      </span>
                      <span
                        className={`transition-transform ${
                          isOpen ? "rotate-90" : ""
                        } text-[#1e4d92] font-bold`}
                      >
                        ›
                      </span>
                    </div>
                  </div>
                  <div className="px-5 pt-3 flex flex-wrap gap-2 text-[11px] text-[#484852]">
                    {mo.options_type && (
                      <span className="px-2 py-0.5 bg-[#ebe8e3] rounded font-mono">
                        {mo.options_type}
                      </span>
                    )}
                    {mo.pricing_method && (
                      <span className="px-2 py-0.5 bg-[#ebe8e3] rounded font-mono">
                        {mo.pricing_method}
                      </span>
                    )}
                    <span className="px-2 py-0.5 bg-[#ebe8e3] rounded font-mono">
                      {mo.attributes.length} attribute{mo.attributes.length === 1 ? "" : "s"}
                    </span>
                    {mo.option_key && (
                      <span className="px-2 py-0.5 bg-[#f9f7f4] rounded font-mono text-[#888894]">
                        {mo.option_key}
                      </span>
                    )}
                  </div>
                  {!isOpen && mo.attributes.length > 0 && (
                    <div className="px-5 pt-2 pb-4 flex flex-wrap gap-1">
                      {mo.attributes.slice(0, 6).map((a) => (
                        <span
                          key={a.id}
                          className="text-[10px] px-2 py-0.5 bg-white border border-[#cfccc8] rounded text-[#484852]"
                        >
                          {humanizeAttributeName(a.title, (a as any).attribute_key ?? null)}
                        </span>
                      ))}
                      {mo.attributes.length > 6 && (
                        <span className="text-[10px] text-[#888894] px-2 py-0.5">
                          +{mo.attributes.length - 6} more
                        </span>
                      )}
                    </div>
                  )}
                </button>

                {isOpen && (
                  <div className="px-5 pb-5 pt-2 border-t border-dashed border-[#ebe8e3] flex flex-col gap-3">
                    {mo.description && (
                      <div 
                        className="text-[12px] text-[#484852] bg-[#f9f7f4] p-3 rounded border border-[#ebe8e3] prose-storefront"
                        dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(mo.description) }}
                      />
                    )}
                    {mo.attributes.length === 0 ? (
                      <div className="text-sm text-[#888894] italic py-4 text-center">
                        No attributes defined for this option.
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse text-[12px]">
                          <thead>
                            <tr className="border-b border-[#cfccc8]">
                              <th className="text-left px-2 py-2 font-bold text-[10px] uppercase tracking-wider text-[#888894]">
                                Attribute
                              </th>
                              <th className="text-left px-2 py-2 font-bold text-[10px] uppercase tracking-wider text-[#888894]">
                                Key
                              </th>
                              <th className="text-right px-2 py-2 font-bold text-[10px] uppercase tracking-wider text-[#888894]">
                                Default $
                              </th>
                              <th className="text-right px-2 py-2 font-bold text-[10px] uppercase tracking-wider text-[#888894]">
                                Sort
                              </th>
                              <th className="text-right px-2 py-2 font-bold text-[10px] uppercase tracking-wider text-[#888894]">
                                OPS ID
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {[...mo.attributes]
                              .sort((a, b) => a.sort_order - b.sort_order)
                              .map((a) => {
                                const attrKey = (a as any).attribute_key ?? null;
                                return (
                                  <tr
                                    key={a.id}
                                    className="border-b border-[#f9f7f4] last:border-b-0 hover:bg-[rgba(30,77,146,0.03)]"
                                  >
                                    <td className="px-2 py-2 text-[#1e1e24]">
                                      {humanizeAttributeName(a.title, attrKey)}
                                    </td>
                                    <td className="px-2 py-2 font-mono text-[10px] text-[#888894]">
                                      {attrKey || a.title || "—"}
                                    </td>
                                    <td className="px-2 py-2 font-mono text-right text-[#484852]">
                                      {a.default_price != null
                                        ? `$${Number(a.default_price).toFixed(2)}`
                                        : "—"}
                                    </td>
                                    <td className="px-2 py-2 font-mono text-right text-[#888894]">
                                      {a.sort_order}
                                    </td>
                                    <td className="px-2 py-2 font-mono text-right text-[10px] text-[#888894]">
                                      #{a.ops_attribute_id}
                                    </td>
                                  </tr>
                                );
                              })}
                          </tbody>
                        </table>
                      </div>
                    )}
                    <div className="text-[11px] text-[#888894] pt-1">
                      Attach this option to a specific product from{" "}
                      <span className="font-semibold">/products/[id]/options</span>.
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
