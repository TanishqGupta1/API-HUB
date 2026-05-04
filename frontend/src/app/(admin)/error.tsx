"use client";

import { useEffect } from "react";

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        gap: "24px",
        textAlign: "center",
        padding: "40px",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "10px",
          fontWeight: 700,
          color: "#dc2626",
          textTransform: "uppercase",
          letterSpacing: "0.12em",
        }}
      >
        500 — Server Error
      </div>
      <h1
        style={{
          fontSize: "22px",
          fontWeight: 800,
          color: "var(--ink)",
          margin: 0,
          letterSpacing: "-0.02em",
        }}
      >
        Something went wrong
      </h1>
      <p style={{ fontSize: "13px", color: "var(--ink-muted)", maxWidth: "400px", margin: 0 }}>
        An unexpected error occurred. If this keeps happening, check the API logs.
      </p>
      {error.digest && (
        <code
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            color: "var(--ink-muted)",
            background: "var(--paper)",
            border: "1px solid var(--border)",
            padding: "4px 10px",
            borderRadius: "3px",
          }}
        >
          {error.digest}
        </code>
      )}
      <button
        onClick={reset}
        style={{
          padding: "8px 20px",
          background: "var(--blue)",
          color: "#fff",
          border: "none",
          borderRadius: "3px",
          fontSize: "13px",
          fontWeight: 700,
          cursor: "pointer",
        }}
      >
        Try again
      </button>
    </div>
  );
}
