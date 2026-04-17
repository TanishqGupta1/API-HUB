"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Customer } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// ─── helpers ─────────────────────────────────────────────────────────────────

function hostname(url: string) {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function validateForm(f: FormState) {
  const errors: Partial<Record<keyof FormState, string>> = {};
  if (!f.name.trim()) errors.name = "Required";
  if (!f.ops_base_url.trim()) {
    errors.ops_base_url = "Required";
  } else {
    try { new URL(f.ops_base_url); } catch { errors.ops_base_url = "Must be a valid URL"; }
  }
  if (!f.ops_token_url.trim()) {
    errors.ops_token_url = "Required";
  } else {
    try { new URL(f.ops_token_url); } catch { errors.ops_token_url = "Must be a valid URL"; }
  }
  if (!f.ops_client_id.trim()) errors.ops_client_id = "Required";
  if (!f.ops_client_secret.trim()) errors.ops_client_secret = "Required";
  return errors;
}

function OAuth2Badge() {
  return (
    <Badge
      style={{
        background: "var(--blue-pale)",
        color: "var(--blue)",
        border: "none",
        fontFamily: "var(--font-mono)",
      }}
    >
      OAuth2
    </Badge>
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
  name: "",
  ops_base_url: "",
  ops_token_url: "",
  ops_client_id: "",
  ops_client_secret: "",
};

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
    if (Object.keys(errors).length) {
      setFormErrors(errors);
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const created = await api<Customer>("/api/customers", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          ops_base_url: form.ops_base_url,
          ops_token_url: form.ops_token_url,
          ops_client_id: form.ops_client_id,
          ops_client_secret: form.ops_client_secret,
        }),
      });
      setCustomers((prev) => [created, ...prev]);
      setShowForm(false);
      setForm(EMPTY_FORM);
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivate(customer: Customer) {
    setDeactivating(customer.id);
    try {
      const updated = await api<Customer>(`/api/customers/${customer.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !customer.is_active }),
      });
      setCustomers((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to update");
    } finally {
      setDeactivating(null);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this storefront? This cannot be undone.")) return;
    setDeleting(id);
    try {
      await api(`/api/customers/${id}`, { method: "DELETE" });
      setCustomers((prev) => prev.filter((c) => c.id !== id));
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: "var(--ink)" }}>
            Storefronts
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-muted)" }}>
            OnPrintShop storefront configurations
          </p>
        </div>
        {!showForm && (
          <Button
            onClick={() => {
              setShowForm(true);
              setSaveError(null);
              setFormErrors({});
            }}
          >
            + Add Storefront
          </Button>
        )}
      </div>

      <div className="mb-5" style={{ borderBottom: "1px solid var(--border)" }} />

      {/* Add Storefront form */}
      {showForm && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle
              className="text-xs font-semibold uppercase tracking-widest"
              style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}
            >
              New Storefront
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 mb-4">
              {/* Store Name */}
              <div className="flex flex-col gap-1">
                <label className="text-xs" style={{ color: "var(--ink-muted)" }}>
                  Store Name
                </label>
                <Input
                  placeholder="e.g., Acme Corp Store"
                  value={form.name}
                  onChange={(e) => setField("name")(e.target.value)}
                  className={formErrors.name ? "border-red-500" : ""}
                />
                {formErrors.name && (
                  <p className="text-xs" style={{ color: "var(--red)" }}>{formErrors.name}</p>
                )}
              </div>

              {/* OPS GraphQL URL */}
              <div className="flex flex-col gap-1">
                <label className="text-xs" style={{ color: "var(--ink-muted)" }}>
                  OPS GraphQL URL
                </label>
                <Input
                  type="url"
                  placeholder="e.g., https://acme.onprintshop.com/graphql"
                  value={form.ops_base_url}
                  onChange={(e) => setField("ops_base_url")(e.target.value)}
                  className={formErrors.ops_base_url ? "border-red-500" : ""}
                />
                {formErrors.ops_base_url && (
                  <p className="text-xs" style={{ color: "var(--red)" }}>{formErrors.ops_base_url}</p>
                )}
              </div>

              {/* OAuth Token URL */}
              <div className="flex flex-col gap-1">
                <label className="text-xs" style={{ color: "var(--ink-muted)" }}>
                  OAuth Token URL
                </label>
                <Input
                  type="url"
                  placeholder="e.g., https://acme.onprintshop.com/oauth/token"
                  value={form.ops_token_url}
                  onChange={(e) => setField("ops_token_url")(e.target.value)}
                  className={formErrors.ops_token_url ? "border-red-500" : ""}
                />
                {formErrors.ops_token_url && (
                  <p className="text-xs" style={{ color: "var(--red)" }}>{formErrors.ops_token_url}</p>
                )}
              </div>

              {/* Client ID */}
              <div className="flex flex-col gap-1">
                <label className="text-xs" style={{ color: "var(--ink-muted)" }}>
                  Client ID
                </label>
                <Input
                  placeholder="Client ID"
                  value={form.ops_client_id}
                  onChange={(e) => setField("ops_client_id")(e.target.value)}
                  className={formErrors.ops_client_id ? "border-red-500" : ""}
                />
                {formErrors.ops_client_id && (
                  <p className="text-xs" style={{ color: "var(--red)" }}>{formErrors.ops_client_id}</p>
                )}
              </div>

              {/* Client Secret */}
              <div className="flex flex-col gap-1">
                <label className="text-xs" style={{ color: "var(--ink-muted)" }}>
                  Client Secret
                </label>
                <Input
                  type="password"
                  placeholder="••••••••"
                  value={form.ops_client_secret}
                  onChange={(e) => setField("ops_client_secret")(e.target.value)}
                  className={formErrors.ops_client_secret ? "border-red-500" : ""}
                />
                {formErrors.ops_client_secret && (
                  <p className="text-xs" style={{ color: "var(--red)" }}>{formErrors.ops_client_secret}</p>
                )}
              </div>
            </div>

            {/* Help text */}
            <p className="text-xs mb-4" style={{ color: "var(--ink-muted)" }}>
              You can find these credentials in your OnPrintShop admin panel under Settings &gt; API.
            </p>

            {saveError && (
              <div
                className="text-xs mb-4 px-3 py-2 rounded"
                style={{
                  background: "rgba(185,50,50,0.08)",
                  color: "var(--red)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {saveError}
              </div>
            )}

            <div className="flex gap-3">
              <Button onClick={handleAdd} disabled={saving}>
                {saving ? "Saving…" : "Save Storefront"}
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setShowForm(false);
                  setForm(EMPTY_FORM);
                  setFormErrors({});
                }}
              >
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Fetch error */}
      {fetchError && (
        <div
          className="rounded-lg border px-4 py-3 mb-5 text-sm"
          style={{
            borderColor: "var(--red)",
            color: "var(--red)",
            background: "rgba(185,50,50,0.06)",
          }}
        >
          Failed to load storefronts: {fetchError}
        </div>
      )}

      {/* Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Store Name</TableHead>
              <TableHead>OPS URL</TableHead>
              <TableHead>Auth</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Products Pushed</TableHead>
              <TableHead>Pricing Rules</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            {/* Loading skeleton */}
            {loading &&
              [1, 2, 3].map((i) => (
                <TableRow key={i}>
                  {[200, 180, 70, 80, 100, 90, 120].map((w, j) => (
                    <TableCell key={j}>
                      <div
                        className="h-3 rounded animate-pulse"
                        style={{ width: w, background: "var(--paper-warm)" }}
                      />
                    </TableCell>
                  ))}
                </TableRow>
              ))}

            {/* Rows */}
            {!loading &&
              customers.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-semibold" style={{ color: "var(--ink)" }}>
                    {c.name}
                  </TableCell>

                  <TableCell>
                    <a
                      href={c.ops_base_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm hover:underline"
                      style={{ color: "var(--blue)" }}
                    >
                      {hostname(c.ops_base_url)}
                    </a>
                  </TableCell>

                  <TableCell>
                    <OAuth2Badge />
                  </TableCell>

                  <TableCell>
                    {c.is_active ? (
                      <Badge
                        className="gap-1"
                        style={{
                          background: "rgba(36,122,82,0.1)",
                          color: "var(--green)",
                          border: "none",
                        }}
                      >
                        <span
                          className="w-1.5 h-1.5 rounded-full inline-block"
                          style={{ background: "var(--green)" }}
                        />
                        Active
                      </Badge>
                    ) : (
                      <Badge variant="secondary">Inactive</Badge>
                    )}
                  </TableCell>

                  <TableCell style={{ fontFamily: "var(--font-mono)" }}>
                    {c.products_pushed > 0 ? c.products_pushed.toLocaleString() : "—"}
                  </TableCell>

                  <TableCell style={{ color: "var(--ink-muted)" }}>
                    {c.markup_rules_count === 0
                      ? "—"
                      : `${c.markup_rules_count} ${c.markup_rules_count === 1 ? "rule" : "rules"}`}
                  </TableCell>

                  <TableCell>
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={deactivating === c.id}
                        onClick={() => handleDeactivate(c)}
                        style={{ color: "var(--blue)" }}
                      >
                        {deactivating === c.id
                          ? "…"
                          : c.is_active
                          ? "Deactivate"
                          : "Activate"}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={deleting === c.id}
                        onClick={() => handleDelete(c.id)}
                        style={{ color: "var(--red)" }}
                      >
                        {deleting === c.id ? "…" : "Delete"}
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}

            {/* Empty state */}
            {!loading && customers.length === 0 && !fetchError && (
              <TableRow>
                <TableCell colSpan={7} className="py-16 text-center">
                  <div className="text-sm font-semibold mb-1" style={{ color: "var(--ink)" }}>
                    No storefronts added.
                  </div>
                  <div className="text-xs" style={{ color: "var(--ink-muted)" }}>
                    Add your OnPrintShop storefront to start publishing products.
                  </div>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
