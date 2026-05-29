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
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
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
    <div className="w-full max-w-sm p-10 bg-[var(--paper)] border border-[var(--border)] rounded">
      <div className="mb-8">
        <p className="font-mono text-[11px] font-bold text-[var(--blue)] uppercase tracking-widest mb-2">
          API-HUB
        </p>
        <h1 className="text-xl font-bold text-[var(--ink)] m-0">Create account</h1>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label
            htmlFor="email"
            className="block text-[11px] font-bold text-[var(--ink-muted)] uppercase tracking-wide mb-1.5"
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
            className="w-full px-3 py-2 border border-[var(--border)] rounded-sm bg-white text-[var(--ink)] text-sm"
          />
        </div>

        <div>
          <label
            htmlFor="password"
            className="block text-[11px] font-bold text-[var(--ink-muted)] uppercase tracking-wide mb-1.5"
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
            className="w-full px-3 py-2 border border-[var(--border)] rounded-sm bg-white text-[var(--ink)] text-sm"
          />
          <p className="text-[11px] text-[var(--ink-muted)] mt-1">Minimum 12 characters</p>
        </div>

        <div>
          <label
            htmlFor="confirm"
            className="block text-[11px] font-bold text-[var(--ink-muted)] uppercase tracking-wide mb-1.5"
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
            className="w-full px-3 py-2 border border-[var(--border)] rounded-sm bg-white text-[var(--ink)] text-sm"
          />
        </div>

        {error && (
          <div className="px-3 py-2.5 bg-red-50 border border-red-200 rounded-sm text-sm text-red-600">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2.5 bg-[var(--blue)] text-white border-none rounded-sm text-sm font-bold cursor-pointer disabled:opacity-70 disabled:cursor-not-allowed"
        >
          {loading ? "Creating account…" : "Create account"}
        </button>

        <p className="text-center text-sm text-[var(--ink-muted)]">
          Already have an account?{" "}
          <Link href="/login" className="text-[var(--blue)] no-underline font-semibold">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
