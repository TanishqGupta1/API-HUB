"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { clearCachedUser } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<"checking" | "open" | "closed">("checking");

  useEffect(() => {
    fetch(`${API_BASE}/api/auth/signup-status`, { credentials: "include" })
      .then((r) => r.json())
      .then((j: { open: boolean }) => setStatus(j.open ? "open" : "closed"))
      .catch(() => setStatus("closed"));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Enter a valid email address");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    if (password.trim().length < 12) {
      setError("Password must be at least 12 non-whitespace characters");
      return;
    }

    setLoading(true);
    try {
      // /api/auth/users is a VGAdmin-only endpoint — this page requires
      // an authenticated admin session (middleware enforces it).
      const res = await fetch(`${API_BASE}/api/auth/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password, role: "vg_admin" }),
      });

      if (!res.ok) {
        const json = await res.json().catch(() => null);
        throw new Error(json?.detail ?? "Registration failed");
      }

      clearCachedUser();
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  if (status === "closed") {
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
        <div style={{ marginBottom: "16px" }}>
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
          <h1 style={{ fontSize: "20px", fontWeight: 700, color: "var(--ink)", margin: 0 }}>
            Registration closed
          </h1>
        </div>
        <p style={{ fontSize: "13px", color: "var(--ink-muted)", marginBottom: "20px" }}>
          Public signup is currently disabled. Contact an administrator for access.
        </p>
        <Link
          href="/login"
          style={{ color: "var(--blue)", textDecoration: "none", fontWeight: 600, fontSize: "13px" }}
        >
          Sign in instead →
        </Link>
      </div>
    );
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
          Create account
        </h1>
      </div>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
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
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            required
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
          <div
            style={{
              fontSize: "11px",
              color: "var(--ink-muted)",
              marginTop: "4px",
            }}
          >
            Minimum 12 characters
          </div>
        </div>

        <div>
          <label
            htmlFor="confirm"
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
            Confirm Password
          </label>
          <input
            id="confirm"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
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
          {loading ? "Creating account…" : "Create account"}
        </button>

        <div
          style={{
            textAlign: "center",
            fontSize: "13px",
            color: "var(--ink-muted)",
          }}
        >
          Already have an account?{" "}
          <Link
            href="/login"
            style={{ color: "var(--blue)", textDecoration: "none", fontWeight: 600 }}
          >
            Sign in
          </Link>
        </div>
      </form>
    </div>
  );
}
