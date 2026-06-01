"use client";
import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Customer, MarkupRule, MarkupRuleCreate } from "@/lib/types";

/* ── helpers ── */
function parseScope(s: string) {
  if (s === "all") return { type: "Global", target: "—" };
  const i = s.indexOf(":");
  if (i === -1) return { type: "Global", target: s };
  const prefix = s.slice(0, i), target = s.slice(i + 1);
  const map: Record<string, string> = { category: "Category", product: "Product", supplier: "Supplier" };
  return { type: map[prefix] ?? "Global", target };
}
function roundLabel(r: string) {
  return r === "nearest_99" ? "→ $X.99" : r === "nearest_dollar" ? "→ $X.00" : "none";
}
function applyMarkup(base: number, rule: MarkupRule): number {
  let price = rule.markup_amount != null ? base + rule.markup_amount : base * (1 + (rule.markup_pct ?? 0) / 100);
  if (rule.min_margin != null) price = Math.max(price, base * (1 + rule.min_margin / 100));
  if (rule.rounding === "nearest_99") price = Math.floor(price) + 0.99;
  else if (rule.rounding === "nearest_dollar") price = Math.round(price);
  if (rule.min_price != null) price = Math.max(price, rule.min_price);
  if (rule.max_price != null) price = Math.min(price, rule.max_price);
  return Math.round(price * 100) / 100;
}
function fmt(n: number) { return `$${n.toFixed(2)}`; }
function isLive(rule: MarkupRule) {
  if (!rule.is_active) return false;
  const now = Date.now();
  if (rule.effective_from && new Date(rule.effective_from).getTime() > now) return false;
  if (rule.effective_until && new Date(rule.effective_until).getTime() < now) return false;
  return true;
}
function statusBadge(rule: MarkupRule) {
  if (!rule.is_active) return <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#f2f0ed] text-[#888894]">Paused</span>;
  const now = Date.now();
  if (rule.effective_from && new Date(rule.effective_from).getTime() > now)
    return <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#fff8e1] text-[#b8860b]">Scheduled</span>;
  if (rule.effective_until && new Date(rule.effective_until).getTime() < now)
    return <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#fdecea] text-[#b93232]">Expired</span>;
  return <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#edf7ed] text-[#2e7d32]">Active</span>;
}
/** Convert an ISO datetime string to the "YYYY-MM-DDTHH:MM" format required by datetime-local inputs. */
function toLocalInputValue(iso: string | null | undefined): string {
  if (!iso) return "";
  // Slice to minute precision — datetime-local doesn't accept seconds or Z suffix
  return iso.replace("Z", "").slice(0, 16);
}

const SCOPE_TYPES = [
  { label: "Global (all products)", value: "all" },
  { label: "Category", value: "category" },
  { label: "Product SKU", value: "product" },
  { label: "Supplier", value: "supplier" },
];
const ROUNDING = [
  { label: "None", value: "none" },
  { label: "Nearest $0.99", value: "nearest_99" },
  { label: "Round to dollar", value: "nearest_dollar" },
];

/* ── component ── */
export default function MarkupPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [cid, setCid] = useState<string | null>(null);
  const [rules, setRules] = useState<MarkupRule[]>([]);
  const [cLoading, setCLoading] = useState(true);
  const [rLoading, setRLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [previewBase, setPreviewBase] = useState("10.00");
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fErr, setFErr] = useState<string | null>(null);

  /** The rule being edited; null means "create new". */
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);

  /* form fields */
  const [fScope, setFScope] = useState("all");
  const [fTarget, setFTarget] = useState("");
  const [fMarkupType, setFMarkupType] = useState<"pct" | "amt">("pct");
  const [fMarkupPct, setFMarkupPct] = useState("");
  const [fMarkupAmt, setFMarkupAmt] = useState("");
  const [fMinMargin, setFMinMargin] = useState("");
  const [fMinPrice, setFMinPrice] = useState("");
  const [fMaxPrice, setFMaxPrice] = useState("");
  const [fRounding, setFRounding] = useState("nearest_99");
  const [fPriority, setFPriority] = useState("1");
  const [fFrom, setFFrom] = useState("");
  const [fUntil, setFUntil] = useState("");

  const resetForm = () => {
    setEditingRuleId(null);
    setFScope("all"); setFTarget(""); setFMarkupType("pct");
    setFMarkupPct(""); setFMarkupAmt(""); setFMinMargin("");
    setFMinPrice(""); setFMaxPrice(""); setFRounding("nearest_99");
    setFPriority("1"); setFFrom(""); setFUntil(""); setFErr(null);
  };

  /** Populate form fields from an existing rule and open the modal for editing. */
  function openEdit(rule: MarkupRule) {
    setEditingRuleId(rule.id);

    // Parse compound scope string (e.g. "category:Apparel" → scope="category", target="Apparel")
    if (rule.scope === "all") {
      setFScope("all");
      setFTarget("");
    } else {
      const colonIdx = rule.scope.indexOf(":");
      if (colonIdx !== -1) {
        setFScope(rule.scope.slice(0, colonIdx));
        setFTarget(rule.scope.slice(colonIdx + 1));
      } else {
        setFScope("all");
        setFTarget("");
      }
    }

    if (rule.markup_amount != null) {
      setFMarkupType("amt");
      setFMarkupAmt(String(rule.markup_amount));
      setFMarkupPct("");
    } else {
      setFMarkupType("pct");
      setFMarkupPct(rule.markup_pct != null ? String(rule.markup_pct) : "");
      setFMarkupAmt("");
    }

    setFMinMargin(rule.min_margin != null ? String(rule.min_margin) : "");
    setFMinPrice(rule.min_price != null ? String(rule.min_price) : "");
    setFMaxPrice(rule.max_price != null ? String(rule.max_price) : "");
    setFRounding(rule.rounding ?? "none");
    setFPriority(String(rule.priority));
    setFFrom(toLocalInputValue(rule.effective_from as string | null));
    setFUntil(toLocalInputValue(rule.effective_until as string | null));
    setFErr(null);
    setShowModal(true);
  }

  useEffect(() => {
    api<Customer[]>("/api/customers")
      .then(d => { setCustomers(d); if (d.length) setCid(d[0].id); })
      .catch(() => setErr("Failed to load customers."))
      .finally(() => setCLoading(false));
  }, []);

  const fetchRules = (id: string) => {
    setRLoading(true); setRules([]);
    api<MarkupRule[]>(`/api/markup-rules/${id}`)
      .then(setRules).catch(() => setErr("Failed to load rules."))
      .finally(() => setRLoading(false));
  };

  useEffect(() => { if (cid) fetchRules(cid); }, [cid]);

  const toggleActive = async (rule: MarkupRule) => {
    await api(`/api/markup-rules/${rule.id}`, {
      method: "PATCH", body: JSON.stringify({ is_active: !rule.is_active }),
    });
    if (cid) fetchRules(cid);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this pricing rule?")) return;
    await api(`/api/markup-rules/${id}`, { method: "DELETE" });
    if (cid) fetchRules(cid);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cid) return;
    setSaving(true); setFErr(null);
    const scope = fScope === "all" ? "all" : `${fScope}:${fTarget}`;
    const fields = {
      scope,
      rounding: fRounding,
      priority: parseInt(fPriority, 10),
      markup_pct: fMarkupType === "pct" && fMarkupPct ? parseFloat(fMarkupPct) : null,
      markup_amount: fMarkupType === "amt" && fMarkupAmt ? parseFloat(fMarkupAmt) : null,
      min_margin: fMinMargin ? parseFloat(fMinMargin) : null,
      min_price: fMinPrice ? parseFloat(fMinPrice) : null,
      max_price: fMaxPrice ? parseFloat(fMaxPrice) : null,
      effective_from: fFrom || null,
      effective_until: fUntil || null,
    };
    try {
      if (editingRuleId) {
        // Edit mode — PATCH existing rule
        await api(`/api/markup-rules/${editingRuleId}`, {
          method: "PATCH",
          body: JSON.stringify(fields),
        });
      } else {
        // Create mode — POST new rule
        const body: MarkupRuleCreate = { customer_id: cid, ...fields };
        await api("/api/markup-rules", { method: "POST", body: JSON.stringify(body) });
      }
      setShowModal(false);
      resetForm();
      if (cid) fetchRules(cid);
    } catch { setFErr("Failed to save. Check your inputs."); }
    finally { setSaving(false); }
  };

  const customer = customers.find(c => c.id === cid);
  const base = parseFloat(previewBase) || 0;
  const liveRule = rules.find(r => isLive(r));

  return (
    <div className="screen active" id="s-markup">
      {/* header */}
      <div className="page-header">
        <div>
          <div className="page-title">Pricing Rules</div>
          <div className="page-subtitle">
            {customer ? `Non-destructive margin rules for ${customer.name}` : "Select a storefront"}
          </div>
        </div>
        <div className="flex gap-2.5 items-center">
          {cLoading ? <span className="text-[13px] text-[#888894]">Loading…</span> : (
            <select value={cid ?? ""} onChange={e => setCid(e.target.value)}
              className="px-3.5 py-[9px] border-[1.5px] border-[#cfccc8] rounded-[5px] font-bold text-[13px] bg-white cursor-pointer">
              {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
          <button className="btn btn-primary" onClick={() => { resetForm(); setShowModal(true); }} disabled={!cid}>
            + Add Rule
          </button>
        </div>
      </div>

      {/* rules table */}
      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">Rules — highest priority first</div>
          <span className="text-[12px] text-[#888894]">{rules.length} rule{rules.length !== 1 ? "s" : ""}</span>
        </div>
        {err && <div className="p-6 text-[#b93232] text-[13px]">{err}</div>}
        {rLoading && <div className="py-12 text-center text-[#888894] text-[13px]">Loading rules…</div>}
        {!rLoading && !err && rules.length === 0 && (
          <div className="py-14 px-6 text-center text-[#888894]">
            <div className="text-[36px] mb-3">$</div>
            <div className="font-bold mb-1.5">No pricing rules yet</div>
            <div className="text-[13px]">Add rules to control margins per customer — changes are always reversible.</div>
          </div>
        )}
        {!rLoading && rules.length > 0 && (
          <table>
            <thead><tr>
              <th>Priority</th><th>Status</th><th>Scope</th><th>Target</th>
              <th>Markup</th><th>Floor / Ceiling</th><th>Rounding</th><th>Effective</th><th></th>
            </tr></thead>
            <tbody>
              {rules.map((rule, i) => {
                const { type, target } = parseScope(rule.scope);
                const live = isLive(rule);
                return (
                  <tr key={rule.id} style={{ opacity: live ? 1 : 0.6 }}>
                    <td><span className="font-mono text-[12px] font-bold text-[#1e4d92]">{i + 1}</span></td>
                    <td>{statusBadge(rule)}</td>
                    <td><span className="cell-tag">{type}</span></td>
                    <td className="cell-primary">{target}</td>
                    <td className="cell-mono font-bold">
                      {rule.markup_amount != null ? `+${fmt(rule.markup_amount)}` : `${rule.markup_pct ?? 0}%`}
                    </td>
                    <td className="cell-mono text-[12px]">
                      {rule.min_price != null ? `≥ ${fmt(rule.min_price)}` : ""}
                      {rule.min_price != null && rule.max_price != null ? " · " : ""}
                      {rule.max_price != null ? `≤ ${fmt(rule.max_price)}` : ""}
                      {rule.min_price == null && rule.max_price == null ? "—" : ""}
                    </td>
                    <td className="cell-mono">{roundLabel(rule.rounding)}</td>
                    <td className="text-[11px] text-[#888894] font-mono">
                      {rule.effective_from ? new Date(rule.effective_from).toLocaleDateString() : ""}
                      {rule.effective_from && rule.effective_until ? " → " : ""}
                      {rule.effective_until ? new Date(rule.effective_until).toLocaleDateString() : ""}
                      {!rule.effective_from && !rule.effective_until ? "Always" : ""}
                    </td>
                    <td>
                      <div className="flex gap-1.5">
                        <button
                          className="btn btn-ghost px-2.5 py-1 text-[12px]"
                          onClick={() => openEdit(rule)}
                          title="Edit rule"
                        >
                          Edit
                        </button>
                        <button
                          className="btn btn-ghost px-2.5 py-1 text-[12px]"
                          onClick={() => toggleActive(rule)}
                          title={rule.is_active ? "Pause rule" : "Activate rule"}
                        >
                          {rule.is_active ? "Pause" : "Activate"}
                        </button>
                        <button className="btn btn-ghost px-2.5 py-1 text-[12px]" onClick={() => handleDelete(rule.id)}>
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* pricing preview */}
      {rules.length > 0 && (
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">Live Pricing Preview</div>
            <div className="flex items-center gap-2.5">
              <span className="text-[12px] text-[#888894]">Base price:</span>
              <input type="number" step="0.01" min="0" value={previewBase}
                onChange={e => setPreviewBase(e.target.value)}
                className="w-24 px-2 py-1 border-[1.5px] border-[#cfccc8] rounded font-mono text-[13px]" />
            </div>
          </div>
          <div className="p-6 grid gap-2.5">
            {liveRule ? (
              <div className="flex items-center gap-4 py-3.5 px-[18px] rounded-lg border-[1.5px] bg-[#eef4fb] border-[#1e4d92]/20">
                <span className="font-bold text-[13px] text-[#1e4d92] min-w-[160px]">
                  {parseScope(liveRule.scope).type}
                  {liveRule.markup_amount != null ? ` +${fmt(liveRule.markup_amount)}` : ` ${liveRule.markup_pct ?? 0}%`}
                </span>
                <span className="font-mono text-[13px] text-[#1e1e24]">
                  {fmt(base)} → <strong className="text-[15px] text-[#1e4d92]">{fmt(applyMarkup(base, liveRule))}</strong>
                </span>
                <span className="ml-auto text-[11px] font-bold text-[#2e7d32] bg-[#edf7ed] px-2.5 py-[3px] rounded">✓ Applied</span>
              </div>
            ) : (
              <div className="py-6 text-center text-[#888894] text-[13px]">No active rules match right now.</div>
            )}
            <div className="mt-2 grid gap-1.5">
              {rules.filter(r => !isLive(r)).map(rule => {
                const { type } = parseScope(rule.scope);
                return (
                  <div key={rule.id} className="flex items-center gap-4 py-2.5 px-[18px] rounded-lg border border-[#cfccc8] bg-[#f9f7f4] opacity-50">
                    <span className="font-bold text-[12px] text-[#888894] min-w-[160px]">
                      {type} · {!rule.is_active ? "Paused" : "Inactive"}
                    </span>
                    <span className="font-mono text-[12px] text-[#888894]">
                      {fmt(base)} → {fmt(applyMarkup(base, rule))}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* add / edit rule modal */}
      {showModal && (
        <div className="fixed inset-0 bg-[#1e1e24]/40 flex items-center justify-center z-[100]">
          <div className="panel w-[520px] m-0 max-h-[90vh] overflow-y-auto">
            <div className="panel-header">
              <div className="panel-title">{editingRuleId ? "Edit Pricing Rule" : "Add Pricing Rule"}</div>
              <button className="btn btn-ghost px-3 py-1 text-[12px]" onClick={() => { setShowModal(false); resetForm(); }}>✕</button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 grid gap-4">

              {/* scope */}
              <div className="grid gap-1.5">
                <label className="text-[12px] font-bold text-[#888894]">Scope</label>
                <select value={fScope} onChange={e => setFScope(e.target.value)}
                  className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]">
                  {SCOPE_TYPES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              {fScope !== "all" && (
                <div className="grid gap-1.5">
                  <label className="text-[12px] font-bold text-[#888894]">
                    {fScope === "category" ? "Category Name" : fScope === "product" ? "Product SKU" : "Supplier Slug"}
                  </label>
                  <input required type="text" value={fTarget} onChange={e => setFTarget(e.target.value)}
                    placeholder={fScope === "category" ? "e.g. Apparel" : fScope === "product" ? "e.g. PC61" : "e.g. sanmar"}
                    className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]" />
                </div>
              )}

              {/* markup type toggle */}
              <div className="grid gap-1.5">
                <label className="text-[12px] font-bold text-[#888894]">Markup Type</label>
                <div className="flex border border-[#cfccc8] rounded-[5px] overflow-hidden">
                  {[{ v: "pct" as const, l: "% Percentage" }, { v: "amt" as const, l: "$ Fixed Amount" }].map(({ v, l }) => (
                    <button key={v} type="button" onClick={() => setFMarkupType(v)}
                      className={`flex-1 py-2 text-[13px] font-bold transition-colors ${fMarkupType === v ? "bg-[#1e4d92] text-white" : "bg-white text-[#484852] hover:bg-[#f2f0ed]"}`}>
                      {l}
                    </button>
                  ))}
                </div>
              </div>

              {fMarkupType === "pct" ? (
                <div className="grid gap-1.5">
                  <label className="text-[12px] font-bold text-[#888894]">Markup %</label>
                  <input required type="number" step="0.01" min="0" value={fMarkupPct}
                    onChange={e => setFMarkupPct(e.target.value)} placeholder="e.g. 45"
                    className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]" />
                </div>
              ) : (
                <div className="grid gap-1.5">
                  <label className="text-[12px] font-bold text-[#888894]">Fixed Markup ($)</label>
                  <input required type="number" step="0.01" min="0" value={fMarkupAmt}
                    onChange={e => setFMarkupAmt(e.target.value)} placeholder="e.g. 5.00"
                    className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]" />
                </div>
              )}

              {/* live mini preview */}
              {(fMarkupPct || fMarkupAmt) && (
                <div className="px-3 py-2 bg-[#eef4fb] rounded-[5px] text-[13px] font-mono text-[#1e4d92]">
                  Preview: {fmt(base)} → <strong>
                    {fmt(fMarkupType === "pct"
                      ? base * (1 + parseFloat(fMarkupPct || "0") / 100)
                      : base + parseFloat(fMarkupAmt || "0"))}
                  </strong> <span className="text-[11px] text-[#888894]">(base: ${previewBase})</span>
                </div>
              )}

              {/* optional fields */}
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-1.5">
                  <label className="text-[12px] font-bold text-[#888894]">Min Margin % <span className="font-normal">(opt)</span></label>
                  <input type="number" step="0.01" min="0" value={fMinMargin}
                    onChange={e => setFMinMargin(e.target.value)} placeholder="e.g. 20"
                    className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]" />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[12px] font-bold text-[#888894]">Rounding</label>
                  <select value={fRounding} onChange={e => setFRounding(e.target.value)}
                    className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]">
                    {ROUNDING.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[12px] font-bold text-[#888894]">Floor Price $ <span className="font-normal">(opt)</span></label>
                  <input type="number" step="0.01" min="0" value={fMinPrice}
                    onChange={e => setFMinPrice(e.target.value)} placeholder="e.g. 9.99"
                    className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]" />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[12px] font-bold text-[#888894]">Ceiling Price $ <span className="font-normal">(opt)</span></label>
                  <input type="number" step="0.01" min="0" value={fMaxPrice}
                    onChange={e => setFMaxPrice(e.target.value)} placeholder="e.g. 99.99"
                    className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]" />
                </div>
              </div>

              {/* effective dates */}
              <div className="grid gap-1.5">
                <label className="text-[12px] font-bold text-[#888894]">Effective Window <span className="font-normal">(opt — leave blank = always active)</span></label>
                <div className="grid grid-cols-2 gap-3">
                  <input type="datetime-local" value={fFrom} onChange={e => setFFrom(e.target.value)}
                    className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]" />
                  <input type="datetime-local" value={fUntil} onChange={e => setFUntil(e.target.value)}
                    className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]" />
                </div>
                <div className="text-[11px] text-[#888894]">From · Until</div>
              </div>

              {/* priority */}
              <div className="grid gap-1.5">
                <label className="text-[12px] font-bold text-[#888894]">Priority <span className="font-normal">(higher = wins over lower)</span></label>
                <input required type="number" min="1" step="1" value={fPriority}
                  onChange={e => setFPriority(e.target.value)}
                  className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]" />
              </div>

              {fErr && <div className="text-[13px] text-[#b93232]">{fErr}</div>}

              <div className="flex gap-2.5 justify-end pt-1">
                <button type="button" className="btn btn-ghost" onClick={() => { setShowModal(false); resetForm(); }}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? "Saving…" : editingRuleId ? "Save Changes" : "Save Rule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
