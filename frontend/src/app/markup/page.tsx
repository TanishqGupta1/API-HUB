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
          <div className="page-title">Markup Rules</div>
          <div className="page-subtitle">
            {selectedCustomer
              ? `Pricing configuration for ${selectedCustomer.name}`
              : "Select a customer to view rules"}
          </div>
        </div>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          {customersLoading ? (
            <span style={{ fontSize: "13px", color: "var(--ink-muted)" }}>Loading…</span>
          ) : (
            <select
              value={selectedCustomerId ?? ""}
              onChange={(e) => setSelectedCustomerId(e.target.value)}
              style={{
                padding: "9px 14px",
                border: "1.5px solid var(--border)",
                borderRadius: "5px",
                fontFamily: "var(--font-head)",
                fontSize: "13px",
                fontWeight: 600,
                background: "white",
                cursor: "pointer",
              }}
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
          <div style={{ padding: "24px", color: "var(--red)", fontSize: "13px" }}>{error}</div>
        )}

        {rulesLoading && (
          <div style={{ padding: "48px 24px", textAlign: "center", color: "var(--ink-muted)", fontSize: "13px" }}>
            Loading rules…
          </div>
        )}

        {!rulesLoading && !error && rules.length === 0 && (
          <div style={{ padding: "48px 24px", textAlign: "center", color: "var(--ink-muted)" }}>
            <div style={{ fontSize: "32px", marginBottom: "12px" }}>$</div>
            <div style={{ fontWeight: 600, marginBottom: "6px" }}>No markup rules configured</div>
            <div style={{ fontSize: "13px" }}>
              Select a customer and add markup rules to control pricing margins.
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
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", fontWeight: 700, color: "var(--blue)" }}>
                        {index + 1}
                      </span>
                      {isFirst && (
                        <span style={{ fontSize: "10px", color: "var(--ink-faint)", marginLeft: "4px" }}>highest</span>
                      )}
                      {isLast && (
                        <span style={{ fontSize: "10px", color: "var(--ink-faint)", marginLeft: "4px" }}>lowest</span>
                      )}
                    </td>
                    <td><span className="cell-tag">{scopeType}</span></td>
                    <td className="cell-primary">{target}</td>
                    <td className="cell-mono" style={{ fontWeight: 600 }}>{rule.markup_pct}%</td>
                    <td className="cell-mono">{rule.min_margin != null ? `${rule.min_margin}%` : "—"}</td>
                    <td className="cell-mono">{roundingLabel(rule.rounding)}</td>
                    <td>
                      <button
                        className="btn btn-ghost"
                        style={{ padding: "4px 10px", fontSize: "12px" }}
                        onClick={() => handleDelete(rule.id)}
                      >
                        Delete
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
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "12px", color: "var(--ink-muted)" }}>Base price:</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={previewBasePrice}
                onChange={(e) => setPreviewBasePrice(e.target.value)}
                style={{
                  width: "80px",
                  padding: "4px 8px",
                  border: "1.5px solid var(--border)",
                  borderRadius: "4px",
                  fontFamily: "var(--font-mono)",
                  fontSize: "13px",
                }}
              />
            </div>
          </div>
          <div style={{ padding: "24px", display: "grid", gap: "10px" }}>
            {rules.map((rule, index) => {
              const isApplied = index === 0;
              const markedUp  = base * (1 + rule.markup_pct / 100);
              const rounded   = applyRounding(markedUp, rule.rounding);
              const { type: scopeType } = parseScope(rule.scope);
              const label = `${scopeType} (${rule.markup_pct}%)`;

              return (
                <div
                  key={rule.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "16px",
                    padding: "14px 18px",
                    borderRadius: "8px",
                    background: isApplied ? "var(--blue-pale)" : "var(--vellum)",
                    border: isApplied
                      ? "1.5px solid rgba(30,77,146,0.2)"
                      : "1.5px solid var(--border)",
                    opacity: isApplied ? 1 : 0.5,
                  }}
                >
                  <span style={{
                    fontWeight: isApplied ? 700 : 600,
                    fontSize: "13px",
                    color: isApplied ? "var(--blue)" : "var(--ink-light)",
                    minWidth: "130px",
                  }}>
                    {label}
                  </span>
                  <span style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "13px",
                    color: isApplied ? "var(--ink)" : "var(--ink-muted)",
                  }}>
                    {fmt(base)} &rarr; {fmt(markedUp)} &rarr;{" "}
                    <strong style={isApplied ? { fontSize: "15px", color: "var(--blue)" } : {}}>
                      {fmt(rounded)}
                    </strong>
                  </span>
                  {isApplied && (
                    <span style={{
                      marginLeft: "auto",
                      fontSize: "11px",
                      fontWeight: 700,
                      color: "var(--green)",
                      background: "var(--green-pale)",
                      padding: "3px 10px",
                      borderRadius: "4px",
                    }}>
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
        <div style={{
          position: "fixed", inset: 0,
          background: "rgba(30,30,36,0.4)",
          display: "flex", alignItems: "center", justifyContent: "center",
          zIndex: 100,
        }}>
          <div className="panel" style={{ width: "480px", margin: 0, maxHeight: "90vh", overflowY: "auto" }}>
            <div className="panel-header">
              <div className="panel-title">Add Markup Rule</div>
              <button
                className="btn btn-ghost"
                style={{ padding: "4px 12px", fontSize: "12px" }}
                onClick={() => setShowModal(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleSubmit} style={{ padding: "24px", display: "grid", gap: "16px" }}>

              {/* Scope type */}
              <div style={{ display: "grid", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--ink-light)" }}>Scope</label>
                <select
                  value={formScopeType}
                  onChange={(e) => setFormScopeType(e.target.value)}
                  style={{ padding: "8px 12px", border: "1.5px solid var(--border)", borderRadius: "5px", fontSize: "13px" }}
                >
                  {SCOPE_TYPES.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {/* Scope target — hidden for Global */}
              {formScopeType !== "all" && (
                <div style={{ display: "grid", gap: "6px" }}>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--ink-light)" }}>
                    {formScopeType === "category" ? "Category Name" : formScopeType === "product" ? "Product SKU" : "Supplier Name"}
                  </label>
                  <input
                    required
                    type="text"
                    value={formScopeTarget}
                    onChange={(e) => setFormScopeTarget(e.target.value)}
                    placeholder={formScopeType === "category" ? "e.g. T-Shirts" : formScopeType === "product" ? "e.g. PC61" : "e.g. SanMar"}
                    style={{ padding: "8px 12px", border: "1.5px solid var(--border)", borderRadius: "5px", fontSize: "13px" }}
                  />
                </div>
              )}

              {/* Markup % */}
              <div style={{ display: "grid", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--ink-light)" }}>Markup %</label>
                <input
                  required
                  type="number"
                  step="0.01"
                  min="0"
                  value={formMarkupPct}
                  onChange={(e) => setFormMarkupPct(e.target.value)}
                  placeholder="e.g. 45"
                  style={{ padding: "8px 12px", border: "1.5px solid var(--border)", borderRadius: "5px", fontSize: "13px" }}
                />
              </div>

              {/* Min Margin % */}
              <div style={{ display: "grid", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--ink-light)" }}>Min Margin % <span style={{ fontWeight: 400, color: "var(--ink-muted)" }}>(optional)</span></label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formMinMargin}
                  onChange={(e) => setFormMinMargin(e.target.value)}
                  placeholder="e.g. 25"
                  style={{ padding: "8px 12px", border: "1.5px solid var(--border)", borderRadius: "5px", fontSize: "13px" }}
                />
              </div>

              {/* Rounding */}
              <div style={{ display: "grid", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--ink-light)" }}>Rounding</label>
                <select
                  value={formRounding}
                  onChange={(e) => setFormRounding(e.target.value)}
                  style={{ padding: "8px 12px", border: "1.5px solid var(--border)", borderRadius: "5px", fontSize: "13px" }}
                >
                  {ROUNDING_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {/* Priority */}
              <div style={{ display: "grid", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--ink-light)" }}>
                  Priority <span style={{ fontWeight: 400, color: "var(--ink-muted)" }}>(higher number = higher priority)</span>
                </label>
                <input
                  required
                  type="number"
                  min="1"
                  step="1"
                  value={formPriority}
                  onChange={(e) => setFormPriority(e.target.value)}
                  style={{ padding: "8px 12px", border: "1.5px solid var(--border)", borderRadius: "5px", fontSize: "13px" }}
                />
              </div>

              {formError && (
                <div style={{ fontSize: "13px", color: "var(--red)" }}>{formError}</div>
              )}

              <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
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
