"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ProductPushLogRead } from "@/lib/types";

interface Props {
  productId: string;
}

function fmt(iso: string) {
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function PushHistory({ productId }: Props) {
  const [rows, setRows] = useState<ProductPushLogRead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api<ProductPushLogRead[]>(`/api/push-log?product_id=${productId}&limit=20`)
      .then(setRows)
      .finally(() => setLoading(false));
  }, [productId]);

  if (loading) return <div className="text-[12px] text-[#888894] font-mono">Loading push history…</div>;
  if (rows.length === 0) return <div className="text-[12px] text-[#888894] font-mono">Never pushed.</div>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12px] border-collapse">
        <thead>
          <tr className="text-left text-[10px] font-bold uppercase tracking-[0.1em] text-[#888894] border-b border-[#ebe8e3]">
            <th className="pb-2 font-mono">When</th>
            <th className="pb-2 font-mono">Customer</th>
            <th className="pb-2 font-mono">Status</th>
            <th className="pb-2 font-mono">OPS ID</th>
            <th className="pb-2 font-mono">Error</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-[#ebe8e3] hover:bg-[#f9f7f4] transition-colors">
              <td className="py-2.5 font-mono text-[#484852]">{fmt(r.pushed_at)}</td>
              <td className="py-2.5 font-mono text-[#484852]">{r.customer_name ?? r.customer_id.slice(0, 8)}</td>
              <td className="py-2.5">
                <span
                  className={`inline-flex items-center px-2 py-[2px] rounded-full text-[10px] font-bold border ${
                    r.status === "pushed"
                      ? "bg-[#e6f3ec] text-[#247a52] border-[#c3e6d2]"
                      : r.status === "failed"
                        ? "bg-[#fdeded] text-[#b93232] border-[#f9d7d7]"
                        : "bg-[#f9f7f4] text-[#888894] border-[#ebe8e3]"
                  }`}
                >
                  <span className={`w-1 h-1 rounded-full mr-1.5 ${
                    r.status === "pushed" ? "bg-[#247a52]" : r.status === "failed" ? "bg-[#b93232]" : "bg-[#888894]"
                  }`} />
                  {r.status}
                </span>
              </td>
              <td className="py-2.5 font-mono text-[#484852]">{r.ops_product_id ?? "—"}</td>
              <td className="py-2.5 text-[#b93232] truncate max-w-[200px] font-sans" title={r.error ?? ""}>
                {r.error ?? ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
