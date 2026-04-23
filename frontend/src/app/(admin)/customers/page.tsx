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
    <div className="w-9 h-9 rounded-lg shrink-0 bg-[#eef4fb] text-[#1e4d92] flex items-center justify-center font-extrabold text-[12px] font-mono border-[1.5px] border-[#cfccc8]">
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
    <div className="flex flex-col gap-1">
      <label className="text-[12px] font-semibold text-[#484852] font-mono">
        {label}
      </label>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={`px-3 py-2 text-[14px] rounded-md border-[1.5px] bg-white text-[#1e1e24] outline-none font-sans ${
          error ? "border-[#b93232]" : "border-[#cfccc8]"
        } focus:border-[#1e4d92]`}
      />
      {error && <span className="text-[11px] text-[#b93232]">{error}</span>}
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
        <div className="panel mb-6">
          <div className="panel-header">
            <span className="panel-title">New Storefront</span>
            <button className="btn btn-ghost text-[13px] px-3 py-1"
              onClick={() => { setShowForm(false); setForm(EMPTY_FORM); setFormErrors({}); }}>
              Cancel
            </button>
          </div>
          <div className="px-6 py-5 grid grid-cols-2 gap-4">
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
          <div className="px-6 pb-5">
            <p className="text-[12px] text-[#484852] mb-3.5">
              Find credentials in your storefront admin under Settings › API.
              The client secret is encrypted and never exposed after saving.
            </p>
            {saveError && (
              <div className="text-[12px] px-3 py-2 rounded-md mb-3 bg-[#fdf2f2] text-[#b93232] font-mono">
                {saveError}
              </div>
            )}
            <div className="flex gap-2.5">
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
        <div className="px-4 py-3 rounded-lg mb-5 text-[13px] border-[1.5px] border-[#b93232] text-[#b93232] bg-[#fdf2f2]">
          Failed to load storefronts: {fetchError}
        </div>
      )}

      {/* ── Table ── */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Storefront Directory</span>
          <span className="text-[12px] text-[#484852] font-mono">
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
                    <div
                      className="h-3 rounded bg-[#f2f0ed] animate-pulse"
                      style={{ width: w }}
                    />
                  </td>
                ))}
              </tr>
            ))}

            {/* Rows */}
            {!loading && customers.map((c) => (
              <tr key={c.id}>

                {/* Name + avatar */}
                <td>
                  <div className="flex items-center gap-2.5">
                    <Avatar name={c.name} />
                    <div>
                      <div className="cell-primary">{c.name}</div>
                      <div className="text-[11px] text-[#484852] font-mono">
                        {c.ops_client_id}
                      </div>
                    </div>
                  </div>
                </td>

                {/* Storefront URL */}
                <td>
                  <a href={c.ops_base_url} target="_blank" rel="noopener noreferrer"
                    className="text-[#1e4d92] text-[13px] font-medium no-underline hover:underline"
                  >
                    {hostname(c.ops_base_url)}
                  </a>
                  <div className="text-[11px] text-[#484852] mt-0.5">OAuth2</div>
                </td>

                {/* Status */}
                <td>
                  {c.is_active ? (
                    <span className="badge badge-ok">
                      <span className="badge-dot bg-[#2e8b57]" />
                      Active
                    </span>
                  ) : (
                    <span className="badge bg-[#f9f7f4] text-[#484852] border border-[#cfccc8]">
                      <span className="badge-dot bg-[#484852]" />
                      Inactive
                    </span>
                  )}
                </td>

                {/* Products pushed */}
                <td className="cell-mono">
                  {c.products_pushed > 0
                    ? c.products_pushed.toLocaleString()
                    : <span className="text-[#888894]">—</span>}
                </td>

                {/* Pricing rules */}
                <td>
                  {c.markup_rules_count > 0 ? (
                    <span className="cell-tag">
                      {c.markup_rules_count} {c.markup_rules_count === 1 ? "rule" : "rules"}
                    </span>
                  ) : (
                    <a href="/pricing-rules" className="text-[12px] text-[#1e4d92] no-underline font-semibold hover:underline">
                      + Add rules
                    </a>
                  )}
                </td>

                {/* Actions */}
                <td>
                  <div className="flex gap-1.5">
                    <button
                      onClick={() => handleDeactivate(c)}
                      disabled={deactivating === c.id}
                      className="text-[12px] font-semibold px-2.5 py-1 border-[1.5px] border-[#cfccc8] rounded-md bg-white text-[#484852] cursor-pointer hover:bg-[#f9f7f4]"
                    >
                      {deactivating === c.id ? "…" : c.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      onClick={() => handleDelete(c.id)}
                      disabled={deleting === c.id}
                      className="text-[12px] font-semibold px-2.5 py-1 border-none rounded-md bg-transparent text-[#b93232] cursor-pointer hover:bg-[#fdf2f2]"
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
                <td colSpan={6} className="px-6 py-16 text-center">
                  <div className="w-12 h-12 rounded-xl mx-auto mb-4 bg-[#eef4fb] text-[#1e4d92] flex items-center justify-center text-[22px]">
                    🏪
                  </div>
                  <div className="text-[14px] font-semibold text-[#1e1e24] mb-1.5">
                    No storefronts yet
                  </div>
                  <div className="text-[13px] text-[#484852] mb-5">
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
