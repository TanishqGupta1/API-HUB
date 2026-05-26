"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { clearCachedUser } from "@/lib/auth";
import { API_BASE } from "@/lib/env";

export default function SetupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/setup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => null);
        if (res.status === 409) {
          router.push("/login");
          return;
        }
        throw new Error(j?.detail ?? "Setup failed");
      }
      clearCachedUser();
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        width: "100%",
        maxWidth: "400px",
        padding: "40px",
        background: "var(--paper)",
        border: "1px solid var(--border)",
        borderRadius: "4px",
      }}
    >
      <div style={{ marginBottom: "32px" }}>
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            fontWeight: 700,
            color: "var(--blue)",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            marginBottom: "8px",
          }}
        >
          API-HUB
        </div>
        <h1
          style={{
            fontSize: "20px",
            fontWeight: 700,
            color: "var(--ink)",
            margin: 0,
          }}
        >
          First-run setup
        </h1>
        <p style={{ marginTop: "8px", marginBottom: 0, color: "var(--ink-muted)", fontSize: 13 }}>
          Create the first VG admin account. Available only before any user exists.
        </p>
      </div>

      <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div>
          <label
            htmlFor="email"
            style={{
              display: "block",
              fontSize: "11px",
              fontWeight: 700,
              color: "var(--ink-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: "6px",
            }}
          >
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{
              width: "100%",
              padding: "8px 12px",
              border: "1px solid var(--border)",
              borderRadius: "3px",
              background: "#fff",
              color: "var(--ink)",
              fontSize: "14px",
              boxSizing: "border-box",
            }}
          />
        </div>

        <div>
          <label
            htmlFor="password"
            style={{
              display: "block",
              fontSize: "11px",
              fontWeight: 700,
              color: "var(--ink-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: "6px",
            }}
          >
            Password (min 12 chars)
          </label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{
              width: "100%",
              padding: "8px 12px",
              border: "1px solid var(--border)",
              borderRadius: "3px",
              background: "#fff",
              color: "var(--ink)",
              fontSize: "14px",
              boxSizing: "border-box",
            }}
          />
        </div>

        {error && (
          <div
            style={{
              padding: "10px 12px",
              background: "rgba(220,38,38,0.08)",
              border: "1px solid rgba(220,38,38,0.3)",
              borderRadius: "3px",
              fontSize: "13px",
              color: "#dc2626",
            }}
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            padding: "10px 16px",
            background: "var(--blue)",
            color: "#fff",
            border: "none",
            borderRadius: "3px",
            fontSize: "13px",
            fontWeight: 700,
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading ? 0.7 : 1,
          }}
        >
          {loading ? "Creating…" : "Create admin"}
        </button>
      </form>
    </div>
  );
}
