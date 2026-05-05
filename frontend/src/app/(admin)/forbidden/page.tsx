import Link from "next/link";

export default function ForbiddenPage() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        gap: "20px",
        textAlign: "center",
        padding: "40px",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "10px",
          fontWeight: 700,
          color: "#d97706",
          textTransform: "uppercase",
          letterSpacing: "0.12em",
        }}
      >
        403 — Forbidden
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
        Access denied
      </h1>
      <p style={{ fontSize: "13px", color: "var(--ink-muted)", maxWidth: "380px", margin: 0 }}>
        You don&apos;t have permission to view this page. If you believe this is
        a mistake, contact your administrator.
      </p>
      <Link
        href="/"
        style={{
          padding: "8px 20px",
          background: "var(--blue)",
          color: "#fff",
          borderRadius: "3px",
          fontSize: "13px",
          fontWeight: 700,
          textDecoration: "none",
        }}
      >
        Go to Dashboard
      </Link>
    </div>
  );
}
