"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Customer } from "@/lib/types";

// ─── helpers ─────────────────────────────────────────────────────────────────

function validateForm(f: FormState) {
  const err: Partial<Record<keyof FormState, string>> = {};
  if (!f.name.trim())            err.name            = "Required";
  if (!f.ops_base_url.trim())    err.ops_base_url    = "Required";
  else { try { new URL(f.ops_base_url); } catch { err.ops_base_url = "Must be a valid URL"; } }
  if (!f.ops_token_url.trim())   err.ops_token_url   = "Required";
  else { try { new URL(f.ops_token_url); } catch { err.ops_token_url = "Must be a valid URL"; } }
  if (!f.ops_client_id.trim())   err.ops_client_id   = "Required";
  if (!f.ops_client_secret.trim()) err.ops_client_secret = "Required";
  return err;
}

function hostname(url: string) {
  try { return new URL(url).hostname; } catch { return url; }
}

// ─── sub-components ──────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <tr style={{ borderTop: "1px solid var(--border)" }}>
      {[160, 180, 70, 80, 90, 70].map((w, i) => (
        <td key={i} className="px-5 py-4">
          <div className="h-3 rounded animate-pulse" style={{ width: w, background: "var(--paper-warm)" }} />
        </td>
      ))}
    </tr>
  );
}

function OAuth2Badge() {
  return (
    <span
      className="text-xs font-semibold px-2 py-0.5 rounded"
      style={{ background: "var(--blue-pale)", color: "var(--blue)", fontFamily: "var(--font-mono)" }}
    >
      OAuth2
    </span>
  );
}

function Field({
  label, field, type = "text", placeholder, value, onChange, error,
}: {
  label: string;
  field: string;
  type?: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
}) {
  return (
    <div>
      <label className="text-xs mb-1 block" style={{ color: "var(--ink-muted)" }}>{label}</label>
      <input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 rounded-md text-sm outline-none"
        style={{
          border: `1px solid ${error ? "var(--red)" : "var(--border)"}`,
          background: "var(--paper)",
          fontFamily: type === "password" ? "var(--font-mono)" : undefined,
        }}
      />
      {error && <p className="text-xs mt-1" style={{ color: "var(--red)" }}>{error}</p>}
    </div>
  );
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

// ─── page ────────────────────────────────────────────────────────────────────

export default function CustomersPage() {
  const [customers, setCustomers]   = useState<Customer[]>([]);
  const [loading, setLoading]       = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [showAdd, setShowAdd]       = useState(false);
  const [form, setForm]             = useState<FormState>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [saving, setSaving]         = useState(false);
  const [saveError, setSaveError]   = useState<string | null>(null);

  const [toggling, setToggling]     = useState<string | null>(null);
  const [deleting, setDeleting]     = useState<string | null>(null);

  useEffect(() => {
    api<Customer[]>("/api/customers")
      .then(setCustomers)
      .catch((e: Error) => setFetchError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function setField(key: keyof FormState) {
    return (v: string) => {
      setForm((f) => ({ ...f, [key]: v }));
      setFormErrors((e) => ({ ...e, [key]: undefined }));
    };
  }

  async function handleSave() {
    const errs = validateForm(form);
    if (Object.keys(errs).length) { setFormErrors(errs); return; }
    setSaving(true); setSaveError(null);
    try {
      const c = await api<Customer>("/api/customers", { method: "POST", body: JSON.stringify(form) });
      setCustomers((prev) => [c, ...prev]);
      setShowAdd(false);
      setForm(EMPTY_FORM);
    } catch (e: any) {
      setSaveError(e.message ?? "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(c: Customer) {
    setToggling(c.id);
    try {
      const updated = await api<Customer>(`/api/customers/${c.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !c.is_active }),
      });
      setCustomers((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch (e: any) { alert(e.message ?? "Failed"); }
    finally { setToggling(null); }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this customer?")) return;
    setDeleting(id);
    try {
      await api(`/api/customers/${id}`, { method: "DELETE" });
      setCustomers((prev) => prev.filter((c) => c.id !== id));
    } catch (e: any) { alert(e.message ?? "Delete failed"); }
    finally { setDeleting(null); }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: "var(--ink)" }}>Customers</h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-muted)" }}>OPS storefront configurations</p>
        </div>
        {!showAdd && (
          <button
            onClick={() => { setShowAdd(true); setSaveError(null); setFormErrors({}); }}
            className="px-5 py-2.5 rounded-md text-sm font-semibold text-white"
            style={{ backgroundColor: "#1e4d92" }}
          >
            + Add Customer
          </button>
        )}
      </div>

      {/* Divider */}
      <div className="mb-5" style={{ borderBottom: "1px solid var(--border)" }} />

      {/* Add form */}
      {showAdd && (
        <div className="rounded-lg border p-6 mb-6" style={{ borderColor: "var(--border)", background: "white" }}>
          <div className="text-xs font-semibold uppercase tracking-widest mb-5"
            style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
            New Customer — OAuth2
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <Field label="Store Name"      field="name"             placeholder="Acme Corp"                    value={form.name}             onChange={setField("name")}             error={formErrors.name} />
            <Field label="OPS Base URL"    field="ops_base_url"     placeholder="https://acme.onprintshop.com" value={form.ops_base_url}    onChange={setField("ops_base_url")}    error={formErrors.ops_base_url} type="url" />
            <Field label="Token URL"       field="ops_token_url"    placeholder="https://acme.onprintshop.com/oauth/token" value={form.ops_token_url}   onChange={setField("ops_token_url")}   error={formErrors.ops_token_url} type="url" />
            <Field label="Client ID"       field="ops_client_id"    placeholder="client_id"                    value={form.ops_client_id}   onChange={setField("ops_client_id")}   error={formErrors.ops_client_id} />
            <Field label="Client Secret"   field="ops_client_secret" placeholder="••••••••"                   value={form.ops_client_secret} onChange={setField("ops_client_secret")} error={formErrors.ops_client_secret} type="password" />
          </div>

          {saveError && (
            <div className="text-xs mb-4 px-3 py-2 rounded"
              style={{ background: "rgba(185,50,50,0.08)", color: "var(--red)", fontFamily: "var(--font-mono)" }}>
              {saveError}
            </div>
          )}

          <div className="flex gap-3">
            <button onClick={handleSave} disabled={saving}
              className="px-5 py-2 rounded-md text-sm font-semibold text-white"
              style={{ backgroundColor: "#1e4d92", opacity: saving ? 0.6 : 1 }}>
              {saving ? "Saving…" : "Save Customer"}
            </button>
            <button onClick={() => setShowAdd(false)} className="text-sm px-4 py-2"
              style={{ color: "var(--ink-muted)" }}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Fetch error */}
      {fetchError && (
        <div className="rounded-lg border px-4 py-3 mb-5 text-sm"
          style={{ borderColor: "var(--red)", color: "var(--red)", background: "rgba(185,50,50,0.06)" }}>
          Failed to load customers: {fetchError}
        </div>
      )}

      {/* Table */}
      <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--border)", background: "white" }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Name", "OPS Base URL", "Auth", "Products Pushed", "Markup Rules", "Status"].map((h) => (
                <th key={h} className="text-left px-5 py-3 text-xs font-semibold uppercase tracking-wide"
                  style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                  {h}
                </th>
              ))}
              <th className="px-5 py-3" />
            </tr>
          </thead>

          <tbody>
            {loading && [1, 2, 3].map((i) => <SkeletonRow key={i} />)}

            {!loading && customers.map((c) => (
              <tr
                key={c.id}
                style={{ borderTop: "1px solid var(--border)" }}
                className="group"
              >
                {/* Name */}
                <td className="px-5 py-4 font-semibold" style={{ color: "var(--ink)" }}>
                  {c.name}
                </td>

                {/* OPS Base URL */}
                <td className="px-5 py-4">
                  <a href={c.ops_base_url} target="_blank" rel="noopener noreferrer"
                    className="text-sm hover:underline" style={{ color: "var(--blue)" }}>
                    {hostname(c.ops_base_url)}
                  </a>
                </td>

                {/* Auth */}
                <td className="px-5 py-4">
                  <OAuth2Badge />
                </td>

                {/* Products Pushed */}
                <td className="px-5 py-4 text-sm" style={{ color: "var(--ink)", fontFamily: "var(--font-mono)" }}>
                  {c.products_pushed.toLocaleString()}
                </td>

                {/* Markup Rules */}
                <td className="px-5 py-4 text-sm" style={{ color: "var(--ink-muted)" }}>
                  {c.markup_rules_count === 0
                    ? <span style={{ color: "var(--ink-muted)" }}>—</span>
                    : `${c.markup_rules_count} ${c.markup_rules_count === 1 ? "rule" : "rules"}`}
                </td>

                {/* Status */}
                <td className="px-5 py-4">
                  {c.is_active ? (
                    <span className="flex items-center gap-1.5 text-sm font-medium" style={{ color: "var(--green)" }}>
                      <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: "var(--green)" }} />
                      Active
                    </span>
                  ) : (
                    <span className="text-sm" style={{ color: "var(--ink-muted)" }}>Inactive</span>
                  )}
                </td>

                {/* Actions */}
                <td className="px-5 py-4">
                  <div className="flex gap-3 opacity-0 group-hover:opacity-100 transition-opacity items-center">
                    <button
                      onClick={() => handleToggle(c)}
                      disabled={toggling === c.id}
                      className="text-xs"
                      style={{ color: "var(--blue)", opacity: toggling === c.id ? 0.5 : 1 }}
                    >
                      {toggling === c.id ? "…" : c.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <span style={{ color: "var(--border)" }}>·</span>
                    <button
                      onClick={() => handleDelete(c.id)}
                      disabled={deleting === c.id}
                      className="text-xs"
                      style={{ color: "var(--red)", opacity: deleting === c.id ? 0.5 : 1 }}
                    >
                      {deleting === c.id ? "…" : "Delete"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}

            {!loading && customers.length === 0 && !fetchError && (
              <tr>
                <td colSpan={7} className="px-5 py-16 text-center">
                  <div className="text-3xl mb-3">🏪</div>
                  <div className="text-sm font-semibold mb-1" style={{ color: "var(--ink)" }}>
                    No customers configured
                  </div>
                  <div className="text-xs" style={{ color: "var(--ink-muted)" }}>
                    Add an OnPrintShop storefront to start pushing products.
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
