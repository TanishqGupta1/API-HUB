"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import {
  TrendingUp,
  BarChart3,
  Users,
  CheckCircle2,
  AlertCircle,
  Clock,
  Tag,
  RefreshCw,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface CustomerMarginRow {
  customer_id: string;
  customer_name: string;
  is_active: boolean;
  active_rules: number;
  default_markup_pct: number | null;
  default_markup_amount: number | null;
  pushed_all_time: number;
  pushed_last_30d: number;
  push_success_rate: number | null;
  last_push_at: string | null;
  estimated_avg_markup_pct: number | null;
}

interface MarginSummary {
  total_customers: number;
  active_customers: number;
  customers_with_rules: number;
  total_active_rules: number;
  pushed_last_30d: number;
  pushed_all_time: number;
  overall_success_rate: number | null;
}

interface MarginsResponse {
  generated_at: string;
  summary: MarginSummary;
  customers: CustomerMarginRow[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(s: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleDateString(undefined, { dateStyle: "medium" });
}

function fmtRate(v: number | null) {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function SuccessBadge({ rate }: { rate: number | null }) {
  if (rate === null) return <span className="text-[#b4b4bc] text-[12px]">No pushes</span>;
  const pct = rate * 100;
  const colour =
    pct >= 90
      ? { bg: "#f0fdf4", text: "#16a34a", border: "#bbf7d0" }
      : pct >= 70
      ? { bg: "#fffbeb", text: "#d97706", border: "#fde68a" }
      : { bg: "#fef2f2", text: "#dc2626", border: "#fecaca" };
  return (
    <span
      className="inline-flex items-center gap-1 font-mono text-[11px] font-bold px-2 py-0.5 rounded-full"
      style={{ background: colour.bg, color: colour.text, border: `1px solid ${colour.border}` }}
    >
      {pct >= 90 ? <CheckCircle2 className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
      {fmtRate(rate)}
    </span>
  );
}

function StatCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="bg-white border border-[#cfccc8] rounded-2xl px-6 py-5">
      <div className="flex items-center gap-2 mb-3 text-[#888894]">{icon}</div>
      <div className="text-[28px] font-extrabold tracking-tight text-[#1e1e24] leading-none mb-1">
        {value}
      </div>
      <div className="text-[11px] font-black uppercase tracking-widest text-[#484852]">{label}</div>
      {sub && <div className="text-[11px] text-[#888894] mt-1">{sub}</div>}
    </div>
  );
}

// ─── Table row ────────────────────────────────────────────────────────────────

function CustomerRow({ row }: { row: CustomerMarginRow }) {
  const markupDisplay =
    row.estimated_avg_markup_pct !== null
      ? `~${row.estimated_avg_markup_pct.toFixed(1)}%`
      : row.default_markup_pct !== null
      ? `${row.default_markup_pct.toFixed(1)}%`
      : row.default_markup_amount !== null
      ? `+$${row.default_markup_amount.toFixed(2)}`
      : "—";

  const markupIsEstimate = row.estimated_avg_markup_pct !== null;

  return (
    <tr className="border-b border-[#f2f0ed] hover:bg-[#fafaf9] transition-colors">
      <td className="px-5 py-4">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-bold text-[#1e1e24]">{row.customer_name}</span>
          {!row.is_active && (
            <span className="font-mono text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-[#f2f0ed] text-[#888894] border border-[#cfccc8]">
              INACTIVE
            </span>
          )}
        </div>
      </td>

      <td className="px-5 py-4 text-center">
        {row.active_rules > 0 ? (
          <span className="inline-flex items-center gap-1 font-mono text-[12px] font-bold text-[#1e4d92]">
            <Tag className="w-3 h-3" />
            {row.active_rules}
          </span>
        ) : (
          <span className="text-[12px] text-[#b4b4bc]">0</span>
        )}
      </td>

      <td className="px-5 py-4 text-center">
        <div className="flex flex-col items-center gap-0.5">
          <span
            className="font-mono text-[13px] font-bold text-[#1e1e24]"
            title={markupIsEstimate ? "Weighted average across pushed variant prices" : "Default rule setting"}
          >
            {markupDisplay}
          </span>
          {markupIsEstimate && (
            <span className="text-[9px] text-[#888894] uppercase font-bold tracking-wide">est. avg</span>
          )}
        </div>
      </td>

      <td className="px-5 py-4 text-center">
        <div className="flex flex-col items-center gap-0.5">
          <span className="text-[13px] font-bold text-[#1e1e24]">{row.pushed_last_30d}</span>
          <span className="text-[9px] text-[#888894] uppercase font-bold tracking-wide">/ {row.pushed_all_time} total</span>
        </div>
      </td>

      <td className="px-5 py-4 text-center">
        <SuccessBadge rate={row.push_success_rate} />
      </td>

      <td className="px-5 py-4 text-right text-[12px] text-[#888894]">
        {fmtDate(row.last_push_at)}
      </td>
    </tr>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const [data, setData] = useState<MarginsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load(quiet = false) {
    if (!quiet) setLoading(true);
    else setRefreshing(true);
    try {
      const result = await api<MarginsResponse>("/api/analytics/margins");
      setData(result);
    } catch (err) {
      log.error("analytics/margins", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => { load(); }, []);

  const s = data?.summary;

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-end justify-between mb-10 pb-6 border-b-2 border-[#1e1e24]">
        <div>
          <div className="text-[32px] font-extrabold tracking-tight leading-none text-[#1e1e24]">
            Margin Analytics
          </div>
          <p className="text-[14px] text-[#888894] mt-3 max-w-xl leading-relaxed">
            Per-customer markup configuration, push volumes, and estimated margin
            percentages computed from variant wholesale prices.
          </p>
          {data && (
            <p className="text-[11px] text-[#b4b4bc] mt-1 font-mono">
              Generated {new Date(data.generated_at).toLocaleString()}
            </p>
          )}
        </div>
        <button
          onClick={() => load(true)}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 text-[12px] font-bold text-[#484852] border border-[#cfccc8] rounded-xl hover:bg-[#f9f7f4] transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="space-y-6 animate-pulse">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-28 bg-white border border-[#f2f0ed] rounded-2xl" />
            ))}
          </div>
          <div className="h-64 bg-white border border-[#f2f0ed] rounded-2xl" />
        </div>
      ) : data && s ? (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
            <StatCard
              icon={<Users className="w-4 h-4" />}
              label="Storefronts"
              value={s.active_customers}
              sub={`${s.total_customers} total`}
            />
            <StatCard
              icon={<Tag className="w-4 h-4" />}
              label="Active Rules"
              value={s.total_active_rules}
              sub={`${s.customers_with_rules} storefronts configured`}
            />
            <StatCard
              icon={<BarChart3 className="w-4 h-4" />}
              label="Pushed (30d)"
              value={s.pushed_last_30d}
              sub={`${s.pushed_all_time} all time`}
            />
            <StatCard
              icon={<TrendingUp className="w-4 h-4" />}
              label="Success Rate"
              value={s.overall_success_rate !== null ? `${(s.overall_success_rate * 100).toFixed(1)}%` : "—"}
              sub={s.overall_success_rate !== null ? "overall push pipeline" : "no pushes yet"}
            />
          </div>

          {/* Per-customer table */}
          {data.customers.length === 0 ? (
            <div className="text-center py-20">
              <BarChart3 className="w-12 h-12 text-[#cfccc8] mx-auto mb-4" />
              <p className="text-[15px] font-bold text-[#1e1e24] mb-1">No customers yet</p>
              <p className="text-[13px] text-[#888894]">
                Add storefronts and configure markup rules to see analytics here.
              </p>
            </div>
          ) : (
            <div className="bg-white border border-[#cfccc8] rounded-2xl overflow-hidden">
              <div className="px-6 py-4 border-b border-[#f2f0ed] flex items-center justify-between">
                <span className="text-[13px] font-extrabold text-[#1e1e24]">
                  Per-Storefront Breakdown
                </span>
                <span className="text-[11px] text-[#888894]">
                  {data.customers.length} storefront{data.customers.length !== 1 ? "s" : ""}
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-[#f2f0ed]">
                      {[
                        ["Storefront", "px-5 py-3 text-left"],
                        ["Rules", "px-5 py-3 text-center"],
                        ["Markup", "px-5 py-3 text-center"],
                        ["Pushed (30d)", "px-5 py-3 text-center"],
                        ["Success Rate", "px-5 py-3 text-center"],
                        ["Last Push", "px-5 py-3 text-right"],
                      ].map(([label, cls]) => (
                        <th key={label as string} className={`${cls} text-[10px] font-black uppercase tracking-widest text-[#888894]`}>
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.customers.map(row => (
                      <CustomerRow key={row.customer_id} row={row} />
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Legend */}
              <div className="px-6 py-3 bg-[#fafaf9] border-t border-[#f2f0ed] flex flex-wrap gap-6 text-[11px] text-[#888894]">
                <span>
                  <strong className="text-[#1e1e24]">Markup</strong> — shows estimated weighted-average markup across pushed
                  variant prices when available; falls back to default rule setting.
                </span>
                <span>
                  <strong className="text-[#1e1e24]">est. avg</strong> — calculated from actual wholesale variant prices × applied rule.
                </span>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="text-center py-20 text-[#888894]">
          Failed to load analytics. Check server logs.
        </div>
      )}
    </div>
  );
}
