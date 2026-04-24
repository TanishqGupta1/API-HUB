"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { PSCompany, Supplier } from "@/lib/types";
import RevealForm from "@/components/suppliers/reveal-form";
import { Button } from "@/components/ui/button";

/* ── Demo product baselines per supplier slug ── */
const PROD_BASELINE: Record<string, number> = {
  sanmar: 12450,
  "ss-activewear": 8201,
  alphabroder: 11800,
  "4over": 1240,
};

/* ── Relative time helper ── */
function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const hrs = Math.floor(min / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

/* ── PS Directory static list ── */
const COS: PSCompany[] = [
  { Code: "SANMAR", Name: "SanMar Corporation", Type: "Supplier" },
  { Code: "SS", Name: "S&S Activewear", Type: "Supplier" },
  { Code: "ALPHA", Name: "alphabroder", Type: "Supplier" },
  { Code: "HIT", Name: "Hit Promotional Products", Type: "Supplier" },
  { Code: "PCNA", Name: "Polyconcept North America", Type: "Supplier" },
  { Code: "GEMLINE", Name: "Gemline", Type: "Supplier" },
  { Code: "EVANS", Name: "Evans Manufacturing", Type: "Supplier" },
  { Code: "STORMCREEK", Name: "Storm Creek", Type: "Supplier" },
  { Code: "SNUGZ", Name: "Snugz USA", Type: "Supplier" },
  { Code: "LOGOMARK", Name: "Logomark", Type: "Supplier" },
  { Code: "CHARLES", Name: "Charles River Apparel", Type: "Supplier" },
  { Code: "AUGUSTA", Name: "Augusta Sportswear", Type: "Supplier" },
  { Code: "TRIMARK", Name: "Trimark Sportswear", Type: "Supplier" },
  { Code: "LEED", Name: "Leeds / PCNA", Type: "Supplier" },
  { Code: "BUDGETCAP", Name: "Budget Cap Inc", Type: "Supplier" },
  { Code: "CAPAMER", Name: "Cap America", Type: "Supplier" },
  { Code: "CUTTER", Name: "Cutter & Buck", Type: "Supplier" },
  { Code: "FLEXFIT", Name: "Flexfit / Yupoong", Type: "Supplier" },
  { Code: "GILDANUSA", Name: "Gildan USA", Type: "Supplier" },
  { Code: "HANES", Name: "Hanesbrands", Type: "Supplier" },
  { Code: "NEXTLEVEL", Name: "Next Level Apparel", Type: "Supplier" },
  { Code: "OGIO", Name: "OGIO International", Type: "Supplier" },
  { Code: "PORTAUTH", Name: "Port Authority", Type: "Supplier" },
  { Code: "SPORTTEK", Name: "Sport-Tek", Type: "Supplier" },
  { Code: "UNDERARMOUR", Name: "Under Armour Corporate", Type: "Supplier" },
  { Code: "VANTAGE", Name: "Vantage Apparel", Type: "Supplier" },
  { Code: "NORTH_END", Name: "North End / Ash City", Type: "Supplier" },
  { Code: "DEVON_JONES", Name: "Devon & Jones", Type: "Supplier" },
  { Code: "HARRITON", Name: "Harriton", Type: "Supplier" },
  { Code: "WEATHERPROOF", Name: "Weatherproof Garment", Type: "Supplier" },
];

interface PushLogEntry {
  supplier_name: string | null;
  pushed_at: string;
}

function SuppliersContent() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [lastPushMap, setLastPushMap] = useState<Record<string, string>>({});
  const [showAdd, setShowAdd] = useState(false);
  const [psCompanies, setPsCompanies] = useState<PSCompany[]>([]);
  const [loading, setLoading] = useState(true);

  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    Promise.all([
      api<Supplier[]>("/api/suppliers"),
      api<PushLogEntry[]>("/api/push-log?limit=100"),
    ])
      .then(([sups, logs]) => {
        setSuppliers(sups);
        // Build map: supplier_name (lowercase) → most recent pushed_at
        const map: Record<string, string> = {};
        for (const log of logs) {
          if (!log.supplier_name) continue;
          const key = log.supplier_name.toLowerCase();
          if (!map[key] || log.pushed_at > map[key]) {
            map[key] = log.pushed_at;
          }
        }
        setLastPushMap(map);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (searchParams.get("new") === "true") openForm();
  }, [searchParams]);

  const openForm = () => {
    setShowAdd(true);
    if (psCompanies.length === 0) setPsCompanies(COS);
  };

  const handleCancel = () => {
    setShowAdd(false);
    if (searchParams.has("new")) router.push("/suppliers");
  };

  const handleSaved = (s: Supplier) => {
    setSuppliers([s, ...suppliers]);
    setShowAdd(false);
  };

  const toggleActive = async (s: Supplier) => {
    try {
      const updated = await api<Supplier>(`/api/suppliers/${s.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !s.is_active }),
      });
      setSuppliers(suppliers.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      console.error("Failed to toggle supplier status:", err);
    }
  };

  const triggerSync = async (s: Supplier) => {
    if (!s.is_active) return;
    try {
      await api(`/api/sync/${s.id}/products`, { method: "POST" });
      router.push("/sync");
    } catch (err) {
      console.error("Failed to trigger sync:", err);
      alert("Sync failed: " + (err instanceof Error ? err.message : String(err)));
    }
  };

  /** Find the most recent push timestamp for a supplier by name */
  const getLastPush = (supplierName: string): string => {
    const key = supplierName.toLowerCase();
    if (lastPushMap[key]) return timeAgo(lastPushMap[key]);
    // Fuzzy: check if any push-log supplier name contains ours or vice versa
    for (const [k, v] of Object.entries(lastPushMap)) {
      const firstWord = key.split(" ")[0];
      if (k.includes(firstWord) || firstWord.includes(k.split(" ")[0])) {
        return timeAgo(v);
      }
    }
    return "—";
  };

  /** Real DB count + demo baseline, formatted */
  const getProductCount = (s: Supplier): string => {
    const baseline = PROD_BASELINE[s.slug] ?? 0;
    const total = s.product_count + baseline;
    if (total === 0) return "0";
    return total >= 1000
      ? `${(total / 1000).toFixed(1)}k`
      : total.toLocaleString();
  };

  return (
    <div className="screen active" id="s-suppliers">
      <div className="page-header">
        <div>
          <div className="page-title">
            {showAdd ? "Add Supplier" : "Connected Suppliers"}
          </div>
          <div className="page-subtitle">
            {showAdd
              ? "Connect a new vendor to the Integration Hub"
              : "Managing endpoint configurations for PromoStandards vendors"}
          </div>
        </div>
        {!showAdd ? (
          <button className="btn btn-primary" onClick={openForm}>
            + Connect New
          </button>
        ) : (
          <button className="btn btn-ghost" onClick={() => setShowAdd(false)}>
            Cancel
          </button>
        )}
      </div>

      {showAdd ? (
        <RevealForm
          psCompanies={psCompanies}
          onSaved={handleSaved}
          onCancel={handleCancel}
        />
      ) : (
        <div className="panel">
          <table>
            <thead>
              <tr>
                <th>Supplier</th>
                <th>ID / Code</th>
                <th>Method</th>
                <th>Last Push</th>
                <th>Products</th>
                <th>Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {suppliers.map((s) => (
                <tr key={s.id}>
                  <td className="cell-primary">
                    <Link 
                      href={`/mappings/${s.id}`}
                      className="hover:text-[var(--blue)] hover:underline transition-colors cursor-pointer"
                    >
                      {s.name}
                    </Link>
                  </td>
                  <td>
                    <span className="cell-tag">
                      {s.promostandards_code || "API"}
                    </span>
                  </td>
                  <td className="cell-mono">{s.protocol.toUpperCase()}</td>
                  <td className="cell-mono">{getLastPush(s.name)}</td>
                  <td className="cell-mono">{getProductCount(s)}</td>
                  <td>
                    <button
                      type="button"
                      onClick={() => toggleActive(s)}
                      className="bg-transparent border-none p-0 cursor-pointer outline-none block"
                      title={s.is_active ? "Deactivate supplier" : "Activate supplier"}
                    >
                      {s.is_active ? (
                        <span className="badge badge-ok">
                          <span className="badge-dot"></span> Active
                        </span>
                      ) : (
                        <span className="text-[12px] font-semibold text-[#888894] hover:text-[#484852] transition-colors">
                          Inactive
                        </span>
                      )}
                    </button>
                  </td>
                  <td className="text-right">
                    <div className="inline-flex items-center gap-2 justify-end">
                      {(s.protocol === "soap" || s.protocol === "promostandards") && (
                        <Link href={`/suppliers/${s.id}/import`}>
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-[#1e4d92] text-[#1e4d92]"
                          >
                            Import Products
                          </Button>
                        </Link>
                      )}
                      <button
                        onClick={() => triggerSync(s)}
                        disabled={!s.is_active}
                        className={`btn btn-ghost !py-1 !px-2 !text-[11px] ${!s.is_active ? "opacity-30 grayscale cursor-not-allowed" : "text-[var(--blue)]"}`}
                        title="Sync Now"
                      >
                        Sync Now ⚡
                      </button>
                    </div>
                  </td>
                </tr>
              ))}

              {!loading && suppliers.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="p-10 text-center text-[#484852] text-[14px]"
                  >
                    No suppliers connected. Click &quot;+ Connect New&quot; to begin.
                  </td>
                </tr>
              )}

              {loading && (
                <tr>
                  <td
                    colSpan={6}
                    className="p-10 text-center text-[#484852] text-[14px] font-mono"
                  >
                    Connecting...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function SuppliersPage() {
  return (
    <Suspense
      fallback={
        <div className="p-10 text-[#484852]">
          Loading...
        </div>
      }
    >
      <SuppliersContent />
    </Suspense>
  );
}
