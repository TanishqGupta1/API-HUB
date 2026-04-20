"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { PSCompany, Supplier } from "@/lib/types";
import RevealForm from "@/components/suppliers/reveal-form";
import { EmptyState } from "@/components/ui/empty-state";

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
              </tr>
            </thead>
            <tbody>
              {suppliers.map((s) => (
                <tr key={s.id}>
                  <td className="cell-primary">{s.name}</td>
                  <td>
                    <span className="cell-tag">
                      {s.promostandards_code || "API"}
                    </span>
                  </td>
                  <td className="cell-mono">{s.protocol.toUpperCase()}</td>
                  <td className="cell-mono">{getLastPush(s.name)}</td>
                  <td className="cell-mono">{getProductCount(s)}</td>
                  <td>
                    {s.is_active ? (
                      <span className="badge badge-ok">
                        <span className="badge-dot"></span> Active
                      </span>
                    ) : (
                      <span
                        style={{
                          color: "var(--ink-faint)",
                          fontSize: "12px",
                          fontWeight: 600,
                        }}
                      >
                        Inactive
                      </span>
                    )}
                  </td>
                </tr>
              ))}

              {!loading && suppliers.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-16">
                    <EmptyState
                      title="No Suppliers Connected"
                      description="Connect your first supplier (SanMar, S&S, 4Over) to start indexing product data into your catalog."
                      action={{
                        label: "Connect New Supplier",
                        onClick: openForm,
                      }}
                      icon={
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="16 16 12 12 8 16" />
                          <line x1="12" y1="12" x2="12" y2="21" />
                          <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
                          <polyline points="16 16 12 12 8 16" />
                        </svg>
                      }
                    />
                  </td>
                </tr>
              )}

              {loading && (
                <tr>
                  <td
                    colSpan={6}
                    style={{
                      padding: "40px",
                      textAlign: "center",
                      color: "var(--ink-muted)",
                      fontSize: "14px",
                      fontFamily: "var(--font-mono)",
                    }}
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
        <div style={{ padding: "40px", color: "var(--ink-muted)" }}>
          Loading...
        </div>
      }
    >
      <SuppliersContent />
    </Suspense>
  );
}
