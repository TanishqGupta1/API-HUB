"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MasterOption, MasterOptionsSyncStatus } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { humanizeOptionName, humanizeAttributeName } from "@/lib/humanize-options";

export default function MasterOptionsCatalogPage() {
  const [options, setOptions] = useState<MasterOption[]>([]);
  const [status, setStatus] = useState<MasterOptionsSyncStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

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

  useEffect(() => { load(); }, []);

  const triggerSync = async () => {
    setSyncing(true);
    try {
      const res = await fetch("/api/master-options/sync", { method: "POST" });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`Sync failed: ${res.status} ${body.slice(0, 200)}`);
      }
      await new Promise((r) => setTimeout(r, 3000));
      await load();
    } catch (e) {
      console.error(e);
      alert("Sync failed. Check n8n at http://localhost:5678.");
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#1e1e24]">Master Options Catalog</h1>
          <p className="text-sm text-[#888894] mt-1">
            Global option templates synced from OPS. Attach them to individual products via Configure Options.
          </p>
          {status && (
            <p className="text-xs text-[#888894] mt-2 font-mono">
              {status.total} synced
              {status.last_synced_at ? ` · last ${new Date(status.last_synced_at).toLocaleString()}` : " · never synced"}
            </p>
          )}
        </div>
        <Button onClick={triggerSync} disabled={syncing}>
          {syncing ? "Syncing..." : "Sync from OPS"}
        </Button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-40 bg-white rounded-[10px] border border-[#cfccc8] animate-pulse" />
          ))}
        </div>
      ) : options.length === 0 ? (
        <div className="bg-white rounded-[10px] border border-[#cfccc8] p-10 text-center">
          <div className="text-[15px] font-semibold text-[#1e1e24] mb-2">No master options synced yet</div>
          <p className="text-sm text-[#888894] mb-4">Click Sync from OPS to pull master options from your OPS account.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {options.map((mo) => (
            <div key={mo.id}
                 className="bg-white rounded-[10px] border border-[#cfccc8] shadow-[4px_5px_0_rgba(30,77,146,0.08)] p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="font-bold text-[#1e4d92]">{humanizeOptionName(mo.title, mo.option_key)}</div>
                <span className="text-[10px] font-mono text-[#888894]">#{mo.ops_master_option_id}</span>
              </div>
              <div className="text-xs text-[#888894] mb-3">
                {mo.options_type || "—"} · {mo.attributes.length} attributes
              </div>
              <div className="flex flex-wrap gap-1">
                {mo.attributes.slice(0, 6).map((a) => (
                  <span key={a.id} className="text-[10px] px-2 py-0.5 bg-[#ebe8e3] rounded">
                    {humanizeAttributeName(a.title, (a as any).attribute_key ?? null)}
                  </span>
                ))}
                {mo.attributes.length > 6 && (
                  <span className="text-[10px] text-[#888894]">+{mo.attributes.length - 6}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
