"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Customer } from "@/lib/types";

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ 
    name: "", 
    ops_base_url: "https://ops.acme.com/api", 
    ops_token_url: "https://auth.acme.com/token",
    ops_client_id: "",
    ops_client_secret: ""
  });

  const fetchCustomers = () => {
    setLoading(true);
    api<Customer[]>("/api/customers")
      .then(setCustomers)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
        await api("/api/customers", {
            method: "POST",
            body: JSON.stringify(form)
        });
        setShowAdd(false);
        fetchCustomers();
    } catch (e) {
        alert("Failed to create customer.");
    }
  };

  return (
    <div className="screen active">
      <div className="page-header">
        <div>
          <div className="page-title">OPS Environments</div>
          <div className="page-subtitle">Configuring target destinations for product and inventory synchronizations</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowAdd(!showAdd)}>
            {showAdd ? "Cancel" : "+ Add Environment"}
        </button>
      </div>

      {showAdd && (
        <div className="panel" style={{ padding: "24px", maxWidth: "600px", marginBottom: "32px", animation: "slideUp 0.3s ease-out" }}>
          <div className="panel-title" style={{ marginBottom: "20px" }}>Connect New Storefront</div>
          <form onSubmit={handleSave} style={{ display: "grid", gap: "16px" }}>
            <div>
              <label className="field-label">Organization Name</label>
              <input 
                type="text" 
                className="input-control" 
                placeholder="e.g. Acme Corp (Production)" 
                required 
                value={form.name}
                onChange={e => setForm({...form, name: e.target.value})}
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div>
                    <label className="field-label">OPS Base URL</label>
                    <input 
                        type="text" 
                        className="input-control" 
                        value={form.ops_base_url}
                        onChange={e => setForm({...form, ops_base_url: e.target.value})}
                    />
                </div>
                <div>
                    <label className="field-label">Client ID</label>
                    <input 
                        type="text" 
                        className="input-control" 
                        placeholder="OAuth2 Client ID"
                        value={form.ops_client_id}
                        onChange={e => setForm({...form, ops_client_id: e.target.value})}
                    />
                </div>
            </div>
            <div>
              <label className="field-label">Client Secret</label>
              <input 
                type="password" 
                className="input-control" 
                placeholder="••••••••••••••••"
                value={form.ops_client_secret}
                onChange={e => setForm({...form, ops_client_secret: e.target.value})}
              />
            </div>
            <button className="btn btn-primary" style={{ width: "100%", padding: "14px" }}>Authorize Connection</button>
          </form>
        </div>
      )}

      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">Connected Environments ({customers.length})</div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Customer / Store</th>
              <th>Base URL</th>
              <th>Client ID</th>
              <th>Created</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {customers.map((c) => (
              <tr key={c.id}>
                <td className="cell-primary">{c.name}</td>
                <td className="cell-mono">{c.ops_base_url}</td>
                <td className="cell-mono">{c.ops_client_id}</td>
                <td className="cell-mono">{new Date(c.created_at).toLocaleDateString()}</td>
                <td>
                  <span className="badge badge-ok">
                    <span className="badge-dot"></span> Active
                  </span>
                </td>
                <td>
                  <button className="btn btn-ghost" style={{ padding: "4px 8px", fontSize: "11px" }}>Manage</button>
                </td>
              </tr>
            ))}
            {!loading && customers.length === 0 && (
                <tr>
                    <td colSpan={6} style={{ padding: "40px", textAlign: "center", color: "var(--ink-muted)", fontSize: "14px" }}>
                        No environments configured. Add a target storefront to enable "Push to OPS".
                    </td>
                </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
