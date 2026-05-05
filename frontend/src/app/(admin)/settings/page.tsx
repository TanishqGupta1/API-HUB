"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fetchUser, type AuthUser } from "@/lib/auth";

interface Customer {
  id: string;
  name: string;
  ops_base_url: string;
  ops_token_url: string;
  ops_client_id: string;
  is_active: boolean;
}

interface UserRecord {
  id: string;
  email: string;
  role: string;
  customer_id: string | null;
  is_active: boolean;
}

export default function SettingsPage() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetchUser().then((u) => {
      setUser(u);
      setLoaded(true);
    });
  }, []);

  if (!loaded) {
    return (
      <div className="page-container">
        <div className="page-header"><h1 className="page-title">Settings</h1></div>
        <div style={{ color: "var(--ink-muted)", fontSize: 13 }}>Loading…</div>
      </div>
    );
  }

  const isAdmin = user?.role === "vg_admin";

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
        {isAdmin ? <UserManagement /> : <OPSSettings customerId={user?.customer_id ?? null} />}
        {isAdmin && <SystemUsers user={user} />}
      </div>
    </div>
  );
}

function OPSSettings({ customerId }: { customerId: string | null }) {
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [form, setForm] = useState({
    ops_base_url: "",
    ops_token_url: "",
    ops_client_id: "",
    ops_client_secret: "",
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!customerId) return;
    api<Customer>(`/api/customers/${customerId}`).then((c) => {
      setCustomer(c);
      setForm({
        ops_base_url: c.ops_base_url,
        ops_token_url: c.ops_token_url,
        ops_client_id: c.ops_client_id,
        ops_client_secret: "",
      });
    });
  }, [customerId]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!customerId) return;
    setSaving(true);
    setError(null);
    try {
      const body: Record<string, string> = {
        ops_base_url: form.ops_base_url,
        ops_token_url: form.ops_token_url,
        ops_client_id: form.ops_client_id,
      };
      if (form.ops_client_secret) body.ops_client_secret = form.ops_client_secret;
      await api(`/api/customers/${customerId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!customerId) return <div style={{ color: "var(--ink-muted)" }}>No storefront linked to this account.</div>;

  return (
    <section>
      <h2 style={{ fontSize: "14px", fontWeight: 700, color: "var(--ink)", marginBottom: "16px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        OPS Storefront Connection
      </h2>
      {customer && (
        <div style={{ marginBottom: "16px", fontSize: "13px", color: "var(--ink-muted)" }}>
          Storefront: <strong style={{ color: "var(--ink)" }}>{customer.name}</strong>
        </div>
      )}
      <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: "14px", maxWidth: "480px" }}>
        {(
          [
            { id: "ops_base_url", label: "OPS Base URL", type: "url" },
            { id: "ops_token_url", label: "Token URL", type: "url" },
            { id: "ops_client_id", label: "Client ID", type: "text" },
            { id: "ops_client_secret", label: "Client Secret (leave blank to keep)", type: "password" },
          ] as const
        ).map(({ id, label, type }) => (
          <div key={id}>
            <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "var(--ink-muted)", textTransform: "uppercase", marginBottom: "5px" }}>
              {label}
            </label>
            <input
              type={type}
              value={form[id]}
              onChange={(e) => setForm((f) => ({ ...f, [id]: e.target.value }))}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "3px", background: "var(--paper)", color: "var(--ink)", fontSize: "13px", boxSizing: "border-box" }}
            />
          </div>
        ))}
        {error && <div style={{ color: "#dc2626", fontSize: "13px" }}>{error}</div>}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <button
            type="submit"
            disabled={saving}
            style={{ padding: "8px 16px", background: "var(--blue)", color: "#fff", border: "none", borderRadius: "3px", fontSize: "13px", fontWeight: 700, cursor: saving ? "not-allowed" : "pointer", opacity: saving ? 0.7 : 1 }}
          >
            {saving ? "Saving…" : "Save"}
          </button>
          {saved && <span style={{ fontSize: "13px", color: "var(--green)" }}>Saved</span>}
        </div>
      </form>
    </section>
  );
}

function UserManagement() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [form, setForm] = useState({ email: "", password: "", role: "vg_admin", customer_id: "" });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    api<Customer[]>("/api/customers").then(setCustomers).catch(() => {});
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    setSuccess(null);
    try {
      const body: Record<string, string> = { email: form.email, password: form.password, role: form.role };
      if (form.role === "customer_admin" && form.customer_id) body.customer_id = form.customer_id;
      await api("/api/auth/users", { method: "POST", body: JSON.stringify(body) });
      setSuccess(`User ${form.email} created.`);
      setForm({ email: "", password: "", role: "vg_admin", customer_id: "" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setCreating(false);
    }
  }

  return (
    <section>
      <h2 style={{ fontSize: "14px", fontWeight: 700, color: "var(--ink)", marginBottom: "16px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        Add User
      </h2>
      <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: "14px", maxWidth: "480px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
          <div>
            <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "var(--ink-muted)", textTransform: "uppercase", marginBottom: "5px" }}>Email</label>
            <input type="email" required value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} style={{ width: "100%", padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "3px", background: "var(--paper)", color: "var(--ink)", fontSize: "13px", boxSizing: "border-box" }} />
          </div>
          <div>
            <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "var(--ink-muted)", textTransform: "uppercase", marginBottom: "5px" }}>Password</label>
            <input type="password" required value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} style={{ width: "100%", padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "3px", background: "var(--paper)", color: "var(--ink)", fontSize: "13px", boxSizing: "border-box" }} />
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
          <div>
            <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "var(--ink-muted)", textTransform: "uppercase", marginBottom: "5px" }}>Role</label>
            <select value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))} style={{ width: "100%", padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "3px", background: "var(--paper)", color: "var(--ink)", fontSize: "13px", boxSizing: "border-box" }}>
              <option value="vg_admin">VG Admin</option>
              <option value="customer_admin">Customer Admin</option>
            </select>
          </div>
          {form.role === "customer_admin" && (
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "var(--ink-muted)", textTransform: "uppercase", marginBottom: "5px" }}>Storefront</label>
              <select value={form.customer_id} onChange={(e) => setForm((f) => ({ ...f, customer_id: e.target.value }))} style={{ width: "100%", padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "3px", background: "var(--paper)", color: "var(--ink)", fontSize: "13px", boxSizing: "border-box" }}>
                <option value="">Select storefront</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          )}
        </div>
        {error && <div style={{ color: "#dc2626", fontSize: "13px" }}>{error}</div>}
        {success && <div style={{ color: "var(--green)", fontSize: "13px" }}>{success}</div>}
        <div>
          <button type="submit" disabled={creating} style={{ padding: "8px 16px", background: "var(--blue)", color: "#fff", border: "none", borderRadius: "3px", fontSize: "13px", fontWeight: 700, cursor: creating ? "not-allowed" : "pointer", opacity: creating ? 0.7 : 1 }}>
            {creating ? "Creating…" : "Create user"}
          </button>
        </div>
      </form>
    </section>
  );
}

function SystemUsers({ user: me }: { user: AuthUser | null }) {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<UserRecord[]>("/api/auth/users")
      .then(setUsers)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(id: string) {
    if (!confirm("Delete this user?")) return;
    await api(`/api/auth/users/${id}`, { method: "DELETE" });
    setUsers((u) => u.filter((x) => x.id !== id));
  }

  return (
    <section>
      <h2 style={{ fontSize: "14px", fontWeight: 700, color: "var(--ink)", marginBottom: "16px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        Users
      </h2>
      {loading ? (
        <div style={{ color: "var(--ink-muted)", fontSize: "13px" }}>Loading…</div>
      ) : (
        <table style={{ width: "100%", maxWidth: "640px", borderCollapse: "collapse", fontSize: "13px" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Email", "Role", ""].map((h) => (
                <th key={h} style={{ textAlign: "left", padding: "6px 10px", fontSize: "11px", fontWeight: 700, color: "var(--ink-muted)", textTransform: "uppercase" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} style={{ borderBottom: "1px solid var(--border-light, var(--border))" }}>
                <td style={{ padding: "8px 10px", color: "var(--ink)" }}>{u.email}</td>
                <td style={{ padding: "8px 10px", color: "var(--ink-muted)", fontFamily: "var(--font-mono)", fontSize: "11px" }}>{u.role}</td>
                <td style={{ padding: "8px 10px", textAlign: "right" }}>
                  {me?.id !== u.id && (
                    <button onClick={() => handleDelete(u.id)} style={{ fontSize: "11px", color: "#dc2626", background: "none", border: "none", cursor: "pointer" }}>
                      Remove
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
