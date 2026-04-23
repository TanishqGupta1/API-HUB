"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Customer, MarkupRule, MarkupRuleCreate } from "@/lib/types";

/* ─── Helpers ─────────────────────────────────────────────────────────────── */

function parseScope(scope: string): { type: string; target: string } {
  if (scope === "all") return { type: "Global", target: "—" };
  const colonIdx = scope.indexOf(":");
  if (colonIdx === -1) return { type: "Global", target: scope };
  const prefix = scope.slice(0, colonIdx);
  const target = scope.slice(colonIdx + 1);
  if (prefix === "category") return { type: "Category", target };
  if (prefix === "product")  return { type: "Product",  target };
  if (prefix === "supplier") return { type: "Supplier", target };
  return { type: "Global", target: scope };
}

function roundingLabel(rounding: string): string {
  switch (rounding) {
    case "nearest_99":     return "nearest $0.99";
    case "nearest_dollar": return "round up";
    default:               return "none";
  }
}

function applyRounding(price: number, rounding: string): number {
  switch (rounding) {
    case "nearest_99":     return Math.ceil(price) - 0.01;
    case "nearest_dollar": return Math.ceil(price);
    default:               return Math.round(price * 100) / 100;
  }
}

function fmt(n: number): string {
  return `$${n.toFixed(2)}`;
}

/* ─── Component ───────────────────────────────────────────────────────────── */

const SCOPE_TYPES = [
  { label: "Global",   value: "all" },
  { label: "Category", value: "category" },
  { label: "Product",  value: "product" },
  { label: "Supplier", value: "supplier" },
];

const ROUNDING_OPTIONS = [
  { label: "None",          value: "none" },
  { label: "Nearest $0.99", value: "nearest_99" },
  { label: "Round Up",      value: "nearest_dollar" },
];

export default function MarkupPage() {
  /* ── Data state ── */
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);
  const [rules, setRules] = useState<MarkupRule[]>([]);

  /* ── Loading / error ── */
  const [customersLoading, setCustomersLoading] = useState(true);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* ── Pricing preview ── */
  const [previewBasePrice, setPreviewBasePrice] = useState("3.68");

  /* ── Modal / form ── */
  const [showModal, setShowModal] = useState(false);
  const [formScopeType, setFormScopeType] = useState("all");
  const [formScopeTarget, setFormScopeTarget] = useState("");
  const [formMarkupPct, setFormMarkupPct] = useState("");
  const [formMinMargin, setFormMinMargin] = useState("");
  const [formRounding, setFormRounding] = useState("nearest_99");
  const [formPriority, setFormPriority] = useState("1");
  const [formSaving, setFormSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  /* ── Fetch customers on mount ── */
  useEffect(() => {
    api<Customer[]>("/api/customers")
      .then((data) => {
        setCustomers(data);
        if (data.length > 0) setSelectedCustomerId(data[0].id);
      })
      .catch(() => setError("Failed to load customers."))
      .finally(() => setCustomersLoading(false));
  }, []);

  /* ── Fetch rules when customer changes ── */
  useEffect(() => {
    if (!selectedCustomerId) return;
    setRulesLoading(true);
    setRules([]);
    api<MarkupRule[]>(`/api/markup-rules/${selectedCustomerId}`)
      .then(setRules)
      .catch(() => setError("Failed to load markup rules."))
      .finally(() => setRulesLoading(false));
  }, [selectedCustomerId]);

  const fetchRules = () => {
    if (!selectedCustomerId) return;
    api<MarkupRule[]>(`/api/markup-rules/${selectedCustomerId}`).then(setRules);
  };

  /* ── Delete rule ── */
  const handleDelete = async (ruleId: string) => {
    if (!window.confirm("Delete this markup rule?")) return;
    await api(`/api/markup-rules/${ruleId}`, { method: "DELETE" });
    fetchRules();
  };

  /* ── Submit new rule ── */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustomerId) return;
    setFormSaving(true);
    setFormError(null);
    const scope = formScopeType === "all" ? "all" : `${formScopeType}:${formScopeTarget}`;
    const body: MarkupRuleCreate = {
      customer_id: selectedCustomerId,
      scope,
      markup_pct: parseFloat(formMarkupPct),
      min_margin: formMinMargin ? parseFloat(formMinMargin) : null,
      rounding: formRounding,
      priority: parseInt(formPriority, 10),
    };
    try {
      await api("/api/markup-rules", { method: "POST", body: JSON.stringify(body) });
      setShowModal(false);
      resetForm();
      fetchRules();
    } catch {
      setFormError("Failed to save rule. Check your inputs and try again.");
    } finally {
      setFormSaving(false);
    }
  };

  const resetForm = () => {
    setFormScopeType("all");
    setFormScopeTarget("");
    setFormMarkupPct("");
    setFormMinMargin("");
    setFormRounding("nearest_99");
    setFormPriority("1");
    setFormError(null);
  };

  const selectedCustomer = customers.find((c) => c.id === selectedCustomerId);
  const base = parseFloat(previewBasePrice) || 0;

  /* ── Render ── */
  return (
    <div className="screen active" id="s-markup">

      {/* PAGE HEADER */}
      <div className="page-header">
        <div>
          <div className="page-title">Pricing Rules</div>
          <div className="page-subtitle">
            {selectedCustomer
              ? `Pricing configuration for ${selectedCustomer.name}`
              : "Select a customer to view rules"}
          </div>
        </div>
        <div className="flex gap-2.5 items-center">
          {customersLoading ? (
            <span className="text-[13px] text-[#888894]">Loading…</span>
          ) : (
            <select
              value={selectedCustomerId ?? ""}
              onChange={(e) => setSelectedCustomerId(e.target.value)}
              className="px-3.5 py-[9px] border-[1.5px] border-[#cfccc8] rounded-[5px] font-bold text-[13px] bg-white cursor-pointer"
            >
              {customers.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          )}
          <button
            className="btn btn-primary"
            onClick={() => { resetForm(); setShowModal(true); }}
            disabled={!selectedCustomerId}
          >
            + Add Rule
          </button>
        </div>
      </div>

      {/* PANEL 1: ACTIVE RULES TABLE */}
      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">Active Rules (highest priority first)</div>
        </div>

        {error && (
          <div className="p-6 text-[#b93232] text-[13px]">{error}</div>
        )}

        {rulesLoading && (
          <div className="py-12 px-6 text-center text-[#888894] text-[13px]">
            Loading rules…
          </div>
        )}

        {!rulesLoading && !error && rules.length === 0 && (
          <div className="py-12 px-6 text-center text-[#888894]">
            <div className="text-[32px] mb-3">$</div>
            <div className="font-bold mb-1.5">No pricing rules configured</div>
            <div className="text-[13px]">
              Select a storefront and add pricing rules to control margins.
            </div>
          </div>
        )}

        {!rulesLoading && !error && rules.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Priority</th>
                <th>Scope</th>
                <th>Target</th>
                <th>Markup %</th>
                <th>Min Margin</th>
                <th>Rounding</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule, index) => {
                const { type: scopeType, target } = parseScope(rule.scope);
                const isFirst = index === 0;
                const isLast  = index === rules.length - 1 && rules.length > 1;
                return (
                  <tr key={rule.id}>
                    <td>
                      <span className="font-mono text-[12px] font-bold text-[#1e4d92]">
                        {index + 1}
                      </span>
                      {isFirst && (
                        <span className="text-[10px] text-[#cfccc8] ml-1">highest</span>
                      )}
                      {isLast && (
                        <span className="text-[10px] text-[#cfccc8] ml-1">lowest</span>
                      )}
                    </td>
                    <td><span className="cell-tag">{scopeType}</span></td>
                    <td className="cell-primary">{target}</td>
                    <td className="cell-mono font-bold">{rule.markup_pct}%</td>
                    <td className="cell-mono">{rule.min_margin != null ? `${rule.min_margin}%` : "—"}</td>
                    <td className="cell-mono">{roundingLabel(rule.rounding)}</td>
                    <td>
                      <button
                        className="btn btn-ghost px-2.5 py-1 text-[12px]"
                        onClick={() => handleDelete(rule.id)}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* PANEL 2: PRICING PREVIEW */}
      {rules.length > 0 && (
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">Pricing Preview</div>
            <div className="flex items-center gap-2.5">
              <span className="text-[12px] text-[#888894]">Base price:</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={previewBasePrice}
                onChange={(e) => setPreviewBasePrice(e.target.value)}
                className="w-20 px-2 py-1 border-[1.5px] border-[#cfccc8] rounded font-mono text-[13px]"
              />
            </div>
          </div>
          <div className="p-6 grid gap-2.5">
            {rules.map((rule, index) => {
              const isApplied = index === 0;
              const markedUp  = base * (1 + rule.markup_pct / 100);
              const rounded   = applyRounding(markedUp, rule.rounding);
              const { type: scopeType } = parseScope(rule.scope);
              const label = `${scopeType} (${rule.markup_pct}%)`;

              return (
                <div
                  key={rule.id}
                  className={`flex items-center gap-4 py-3.5 px-[18px] rounded-lg border-[1.5px] ${
                    isApplied 
                      ? "bg-[#eef4fb] border-[#1e4d92]/20 opacity-100" 
                      : "bg-[#f2f0ed] border-[#cfccc8] opacity-50"
                  }`}
                >
                  <span className={`font-bold text-[13px] min-w-[130px] ${
                    isApplied ? "text-[#1e4d92]" : "text-[#888894]"
                  }`}>
                    {label}
                  </span>
                  <span className={`font-mono text-[13px] ${
                    isApplied ? "text-[#1e1e24]" : "text-[#888894]"
                  }`}>
                    {fmt(base)} &rarr; {fmt(markedUp)} &rarr;{" "}
                    <strong className={isApplied ? "text-[15px] text-[#1e4d92]" : ""}>
                      {fmt(rounded)}
                    </strong>
                  </span>
                  {isApplied && (
                    <span className="ml-auto text-[11px] font-bold text-[#2e7d32] bg-[#edf7ed] px-2.5 py-[3px] rounded">
                      ✓ Applied
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ADD RULE MODAL */}
      {showModal && (
        <div className="fixed inset-0 bg-[#1e1e24]/40 flex items-center justify-center z-[100]">
          <div className="panel w-[480px] m-0 max-h-[90vh] overflow-y-auto">
            <div className="panel-header">
              <div className="panel-title">Add Pricing Rule</div>
              <button
                className="btn btn-ghost px-3 py-1 text-[12px]"
                onClick={() => setShowModal(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 grid gap-4">

              {/* Scope type */}
              <div className="grid gap-1.5">
                <label className="text-[12px] font-bold text-[#888894]">Scope</label>
                <select
                  value={formScopeType}
                  onChange={(e) => setFormScopeType(e.target.value)}
                  className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]"
                >
                  {SCOPE_TYPES.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {/* Scope target — hidden for Global */}
              {formScopeType !== "all" && (
                <div className="grid gap-1.5">
                  <label className="text-[12px] font-bold text-[#888894]">
                    {formScopeType === "category" ? "Category Name" : formScopeType === "product" ? "Product SKU" : "Supplier Name"}
                  </label>
                  <input
                    required
                    type="text"
                    value={formScopeTarget}
                    onChange={(e) => setFormScopeTarget(e.target.value)}
                    placeholder={formScopeType === "category" ? "e.g. T-Shirts" : formScopeType === "product" ? "e.g. PC61" : "e.g. SanMar"}
                    className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]"
                  />
                </div>
              )}

              {/* Markup % */}
              <div className="grid gap-1.5">
                <label className="text-[12px] font-bold text-[#888894]">Markup %</label>
                <input
                  required
                  type="number"
                  step="0.01"
                  min="0"
                  value={formMarkupPct}
                  onChange={(e) => setFormMarkupPct(e.target.value)}
                  placeholder="e.g. 45"
                  className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]"
                />
              </div>

              {/* Min Margin % */}
              <div className="grid gap-1.5">
                <label className="text-[12px] font-bold text-[#888894]">Min Margin % <span className="font-normal text-[#888894]">(optional)</span></label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formMinMargin}
                  onChange={(e) => setFormMinMargin(e.target.value)}
                  placeholder="e.g. 25"
                  className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]"
                />
              </div>

              {/* Rounding */}
              <div className="grid gap-1.5">
                <label className="text-[12px] font-bold text-[#888894]">Rounding</label>
                <select
                  value={formRounding}
                  onChange={(e) => setFormRounding(e.target.value)}
                  className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]"
                >
                  {ROUNDING_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {/* Priority */}
              <div className="grid gap-1.5">
                <label className="text-[12px] font-bold text-[#888894]">
                  Priority <span className="font-normal text-[#888894]">(higher number = higher priority)</span>
                </label>
                <input
                  required
                  type="number"
                  min="1"
                  step="1"
                  value={formPriority}
                  onChange={(e) => setFormPriority(e.target.value)}
                  className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-[5px] text-[13px]"
                />
              </div>

              {formError && (
                <div className="text-[13px] text-[#b93232]">{formError}</div>
              )}

              <div className="flex gap-2.5 justify-end">
                <button type="button" className="btn btn-ghost" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={formSaving}>
                  {formSaving ? "Saving…" : "Save Rule"}
                </button>
              </div>

            </form>
          </div>
        </div>
      )}
    </div>
  );
}
