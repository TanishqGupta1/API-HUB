"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { clearCachedUser } from "@/lib/auth";
import { API_BASE } from "@/lib/env";

type ValidationError = { loc: (string | number)[]; msg: string; type: string };

function formatApiError(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const fieldMsg = (detail as ValidationError[])
      .map((e) => {
        const field = e.loc?.filter((p) => p !== "body").join(".") ?? "input";
        return `${field}: ${e.msg}`;
      })
      .join("; ");
    if (fieldMsg) return fieldMsg;
  }
  if (status === 401) return "Invalid credentials";
  if (status === 422) return "Please check the email and password fields";
  return "Login failed";
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password, remember_me: rememberMe }),
      });

      if (!res.ok) {
        const json = await res.json().catch(() => null);
        throw new Error(formatApiError(json?.detail, res.status));
      }

      const user = await res.json().catch(() => null);
      clearCachedUser();

      // Role-based redirect
      const next = searchParams.get("next");
      if (next) {
        router.push(next);
      } else if (user?.role === "customer_admin") {
        router.push("/dashboard");
      } else {
        router.push("/");
      }
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      width: "100%",
      maxWidth: "400px",
      background: "var(--paper)",
      border: "1px solid var(--border)",
      borderRadius: "4px",
      overflow: "hidden",
    }}>
      <div style={{ padding: "32px 40px 40px" }}>
        {/* Header */}
        <div style={{ marginBottom: "28px" }}>
          <div style={{
            fontFamily: "var(--font-mono)",
            fontSize: "10px",
            fontWeight: 700,
            color: "var(--blue)",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            marginBottom: "6px",
          }}>
            API-HUB
          </div>
          <h1 style={{ fontSize: "20px", fontWeight: 700, color: "var(--ink)", margin: "0 0 4px" }}>
            Sign in
          </h1>
          <p style={{ fontSize: "12px", color: "var(--ink-muted)", margin: 0 }}>
            Manage suppliers, catalog, storefronts and OPS push pipeline.
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>

          <div>
            <label htmlFor="email" style={labelStyle}>Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={inputStyle}
            />
          </div>

          <div>
            <label htmlFor="password" style={labelStyle}>Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={inputStyle}
            />
          </div>

          <label style={{
            display: "flex", alignItems: "center", gap: "8px",
            fontSize: "13px", color: "var(--ink-muted)", cursor: "pointer", userSelect: "none",
          }}>
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              style={{ width: "14px", height: "14px", cursor: "pointer" }}
            />
            Keep me signed in for 18 hours
          </label>

          {error && (
            <div style={{
              padding: "10px 12px",
              background: "rgba(220,38,38,0.08)",
              border: "1px solid rgba(220,38,38,0.3)",
              borderRadius: "3px",
              fontSize: "13px",
              color: "#dc2626",
            }}>
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
              transition: "background 0.15s",
            }}
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>

          <div
            style={{
              textAlign: "center",
              fontSize: "13px",
              color: "var(--ink-muted)",
            }}
          >
            Need an account?{" "}
            <Link
              href="/signup"
              style={{ color: "var(--blue)", textDecoration: "none", fontWeight: 600 }}
            >
              Create one
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "11px",
  fontWeight: 700,
  color: "var(--ink-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  marginBottom: "6px",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 12px",
  border: "1px solid var(--border)",
  borderRadius: "3px",
  background: "#fff",
  color: "var(--ink)",
  fontSize: "14px",
  boxSizing: "border-box",
};
