"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Customer } from "@/lib/types";

// ─── helpers ─────────────────────────────────────────────────────────────────

function hostname(url: string) {
  try { return new URL(url).hostname; } catch { return url; }
}

function initials(name: string) {
  return name.split(" ").filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
}

function validateForm(f: FormState) {
  const errors: Partial<Record<keyof FormState, string>> = {};
  if (!f.name.trim()) errors.name = "Required";
  if (!f.ops_base_url.trim()) { errors.ops_base_url = "Required"; }
  else { try { new URL(f.ops_base_url); } catch { errors.ops_base_url = "Must be a valid URL"; } }
  if (!f.ops_token_url.trim()) { errors.ops_token_url = "Required"; }
  else { try { new URL(f.ops_token_url); } catch { errors.ops_token_url = "Must be a valid URL"; } }
  if (!f.ops_client_id.trim()) errors.ops_client_id = "Required";
  if (!f.ops_client_secret.trim()) errors.ops_client_secret = "Required";
  return errors;
}

// ─── types ───────────────────────────────────────────────────────────────────

type FormState = {
  name: string;
  ops_base_url: string;
  ops_token_url: string;
  ops_client_id: string;
  ops_client_secret: string;
};

const EMPTY_FORM: FormState = {
  name: "", ops_base_url: "", ops_token_url: "", ops_client_id: "", ops_client_secret: "",
};

// ─── Avatar ──────────────────────────────────────────────────────────────────

function Avatar({ name }: { name: string }) {
  return (
    <div style={{
      width: 36, height: 36, borderRadius: 8, flexShrink: 0,
      background: "var(--blue-pale)", color: "var(--blue)",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontWeight: 800, fontSize: 12, fontFamily: "var(--font-mono)",
      border: "1.5px solid var(--border)",
    }}>
      {initials(name)}
    </div>
  );
}

// ─── Field ───────────────────────────────────────────────────────────────────

function Field({
  label, value, onChange, placeholder, type = "text", error,
}: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: string; error?: string;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        style={{
          padding: "8px 12px", fontSize: 14, borderRadius: 6,
          border: `1.5px solid ${error ? "var(--red)" : "var(--border)"}`,
          background: "white", color: "var(--ink)", outline: "none",
          fontFamily: "var(--font-sans)",
        }}
      />
      {error && <span style={{ fontSize: 11, color: "var(--red)" }}>{error}</span>}
    </div>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [deactivating, setDeactivating] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    api<Customer[]>("/api/customers")
      .then(setCustomers)
      .catch((e: Error) => setFetchError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function setField(key: keyof FormState) {
    return (value: string) => {
      setForm((prev) => ({ ...prev, [key]: value }));
      setFormErrors((prev) => ({ ...prev, [key]: undefined }));
    };
  }

  async function handleAdd() {
    const errors = validateForm(form);
    if (Object.keys(errors).length) { setFormErrors(errors); return; }
    setSaving(true); setSaveError(null);
    try {
      const created = await api<Customer>("/api/customers", {
        method: "POST",
        body: JSON.stringify({
          name: form.name, ops_base_url: form.ops_base_url,
          ops_token_url: form.ops_token_url, ops_client_id: form.ops_client_id,
          ops_client_secret: form.ops_client_secret,
        }),
      });
      setCustomers((prev) => [created, ...prev]);
      setShowForm(false); setForm(EMPTY_FORM);
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : "Save failed");
    } finally { setSaving(false); }
  }

  async function handleDeactivate(customer: Customer) {
    setDeactivating(customer.id);
    try {
      const updated = await api<Customer>(`/api/customers/${customer.id}`, {
        method: "PATCH", body: JSON.stringify({ is_active: !customer.is_active }),
      });
      setCustomers((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to update");
    } finally { setDeactivating(null); }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this storefront? This cannot be undone.")) return;
    setDeleting(id);
    try {
      await api(`/api/customers/${id}`, { method: "DELETE" });
      setCustomers((prev) => prev.filter((c) => c.id !== id));
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Delete failed");
    } finally { setDeleting(null); }
  }

  return (
    <div className="screen active">

      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <div className="page-title">Storefronts</div>
          <div className="page-subtitle">
            Storefronts — each one is an independent instance
          </div>
        </div>
        {!showForm && (
          <button className="btn btn-primary" onClick={() => { setShowForm(true); setSaveError(null); setFormErrors({}); }}>
            + Add Storefront
          </button>
        )}
      </div>

      {/* ── Add form ── */}
      {showForm && (
        <div className="panel" style={{ marginBottom: 24 }}>
          <div className="panel-header">
            <span className="panel-title">New Storefront</span>
            <button className="btn btn-ghost" style={{ fontSize: 13, padding: "4px 12px" }}
              onClick={() => { setShowForm(false); setForm(EMPTY_FORM); setFormErrors({}); }}>
              Cancel
            </button>
          </div>
          <div style={{ padding: "20px 24px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <Field label="Store Name" value={form.name} onChange={setField("name")}
              placeholder="e.g., Acme Corp Store" error={formErrors.name} />
            <Field label="Storefront API URL" value={form.ops_base_url} onChange={setField("ops_base_url")}
              placeholder="https://acme.example.com/graphql" type="url" error={formErrors.ops_base_url} />
            <Field label="OAuth Token URL" value={form.ops_token_url} onChange={setField("ops_token_url")}
              placeholder="https://acme.example.com/oauth/token" type="url" error={formErrors.ops_token_url} />
            <Field label="Client ID" value={form.ops_client_id} onChange={setField("ops_client_id")}
              placeholder="Client ID" error={formErrors.ops_client_id} />
            <Field label="Client Secret" value={form.ops_client_secret} onChange={setField("ops_client_secret")}
              placeholder="••••••••" type="password" error={formErrors.ops_client_secret} />
          </div>
          <div style={{ padding: "0 24px 20px" }}>
            <p style={{ fontSize: 12, color: "var(--ink-muted)", marginBottom: 14 }}>
              Find credentials in your storefront admin under Settings › API.
              The client secret is encrypted and never exposed after saving.
            </p>
            {saveError && (
              <div style={{
                fontSize: 12, padding: "8px 12px", borderRadius: 6, marginBottom: 12,
                background: "var(--red-pale)", color: "var(--red)", fontFamily: "var(--font-mono)",
              }}>
                {saveError}
              </div>
            )}
            <div style={{ display: "flex", gap: 10 }}>
              <button className="btn btn-primary" onClick={handleAdd} disabled={saving}>
                {saving ? "Saving…" : "Save Storefront"}
              </button>
              <button className="btn btn-ghost"
                onClick={() => { setShowForm(false); setForm(EMPTY_FORM); setFormErrors({}); }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Fetch error ── */}
      {fetchError && (
        <div style={{
          padding: "12px 16px", borderRadius: 8, marginBottom: 20, fontSize: 13,
          border: "1.5px solid var(--red)", color: "var(--red)", background: "var(--red-pale)",
        }}>
          Failed to load storefronts: {fetchError}
        </div>
      )}

      {/* ── Table ── */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Storefront Directory</span>
          <span style={{ fontSize: 12, color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
            {!loading && `${customers.length} storefront${customers.length !== 1 ? "s" : ""}`}
          </span>
        </div>

        <table style={{ width: "100%" }}>
          <thead>
            <tr>
              <th>Storefront</th>
              <th>API Endpoint</th>
              <th>Status</th>
              <th>Products Pushed</th>
              <th>Pricing Rules</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {/* Loading skeleton */}
            {loading && [1, 2, 3].map((i) => (
              <tr key={i}>
                {[220, 160, 70, 90, 90, 130].map((w, j) => (
                  <td key={j}>
                    <div style={{
                      height: 12, width: w, borderRadius: 4,
                      background: "var(--paper-warm)",
                      animation: "pulse 1.5s ease-in-out infinite",
                    }} />
                  </td>
                ))}
              </tr>
            ))}

            {/* Rows */}
            {!loading && customers.map((c) => (
              <tr key={c.id}>

                {/* Name + avatar */}
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <Avatar name={c.name} />
                    <div>
                      <div className="cell-primary">{c.name}</div>
                      <div style={{ fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                        {c.ops_client_id}
                      </div>
                    </div>
                  </div>
                </td>

                {/* Storefront URL */}
                <td>
                  <a href={c.ops_base_url} target="_blank" rel="noopener noreferrer"
                    style={{ color: "var(--blue)", fontSize: 13, textDecoration: "none", fontWeight: 500 }}
                    onMouseOver={(e) => (e.currentTarget.style.textDecoration = "underline")}
                    onMouseOut={(e) => (e.currentTarget.style.textDecoration = "none")}
                  >
                    {hostname(c.ops_base_url)}
                  </a>
                  <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 2 }}>OAuth2</div>
                </td>

                {/* Status */}
                <td>
                  {c.is_active ? (
                    <span className="badge badge-ok">
                      <span className="badge-dot" style={{ background: "var(--green)" }} />
                      Active
                    </span>
                  ) : (
                    <span className="badge" style={{ background: "var(--paper)", color: "var(--ink-muted)", border: "1px solid var(--border)" }}>
                      <span className="badge-dot" style={{ background: "var(--ink-muted)" }} />
                      Inactive
                    </span>
                  )}
                </td>

                {/* Products pushed */}
                <td className="cell-mono">
                  {c.products_pushed > 0
                    ? c.products_pushed.toLocaleString()
                    : <span style={{ color: "var(--ink-faint)" }}>—</span>}
                </td>

                {/* Pricing rules */}
                <td>
                  {c.markup_rules_count > 0 ? (
                    <span className="cell-tag">
                      {c.markup_rules_count} {c.markup_rules_count === 1 ? "rule" : "rules"}
                    </span>
                  ) : (
                    <a href="/pricing-rules" style={{ fontSize: 12, color: "var(--blue)", textDecoration: "none", fontWeight: 600 }}>
                      + Add rules
                    </a>
                  )}
                </td>

                {/* Actions */}
                <td>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      onClick={() => handleDeactivate(c)}
                      disabled={deactivating === c.id}
                      style={{
                        fontSize: 12, fontWeight: 600, padding: "4px 10px",
                        border: "1.5px solid var(--border)", borderRadius: 5,
                        background: "white", color: "var(--ink-light)", cursor: "pointer",
                      }}
                    >
                      {deactivating === c.id ? "…" : c.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      onClick={() => handleDelete(c.id)}
                      disabled={deleting === c.id}
                      style={{
                        fontSize: 12, fontWeight: 600, padding: "4px 10px",
                        border: "1.5px solid transparent", borderRadius: 5,
                        background: "transparent", color: "var(--red)", cursor: "pointer",
                      }}
                    >
                      {deleting === c.id ? "…" : "Delete"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}

            {/* Empty state */}
            {!loading && customers.length === 0 && !fetchError && (
              <tr>
                <td colSpan={6} style={{ padding: "60px 24px", textAlign: "center" }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: 12, margin: "0 auto 16px",
                    background: "var(--blue-pale)", color: "var(--blue)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 22,
                  }}>
                    🏪
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", marginBottom: 6 }}>
                    No storefronts yet
                  </div>
                  <div style={{ fontSize: 13, color: "var(--ink-muted)", marginBottom: 20 }}>
                    Add your first storefront to start publishing products.
                  </div>
                  <button className="btn btn-primary"
                    onClick={() => { setShowForm(true); setSaveError(null); setFormErrors({}); }}>
                    + Add Storefront
                  </button>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
