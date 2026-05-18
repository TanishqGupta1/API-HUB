import Link from "next/link";

export default function GlobalNotFound() {
  return (
    <html>
      <body
        style={{
          margin: 0,
          fontFamily: "system-ui, sans-serif",
          background: "#f9f7f4",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
        }}
      >
        <div style={{ textAlign: "center", padding: "40px" }}>
          <div
            style={{
              fontFamily: "monospace",
              fontSize: "10px",
              fontWeight: 700,
              color: "#888894",
              textTransform: "uppercase",
              letterSpacing: "0.12em",
              marginBottom: "12px",
            }}
          >
            404
          </div>
          <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#1e1e24", margin: "0 0 12px" }}>
            Page not found
          </h1>
          <p style={{ fontSize: "13px", color: "#888894", margin: "0 0 24px" }}>
            This URL doesn&apos;t exist.
          </p>
          <Link
            href="/"
            style={{
              padding: "8px 20px",
              background: "#1e4d92",
              color: "#fff",
              borderRadius: "3px",
              fontSize: "13px",
              fontWeight: 700,
              textDecoration: "none",
            }}
          >
            Back to app
          </Link>
        </div>
      </body>
    </html>
  );
}
