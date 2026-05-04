import Link from "next/link";

export default function AdminNotFound() {
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
          color: "var(--ink-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.12em",
        }}
      >
        404 — Not Found
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
        Page not found
      </h1>
      <p style={{ fontSize: "13px", color: "var(--ink-muted)", maxWidth: "360px", margin: 0 }}>
        The page you&apos;re looking for doesn&apos;t exist or was moved.
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
