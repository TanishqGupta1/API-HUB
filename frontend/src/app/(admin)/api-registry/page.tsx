"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

// --- Components ---

function APIEntry({ method, path, desc, blueprint }: { method: string; path: string; desc: string; blueprint: string }) {
  const [response, setResponse] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function testEndpoint() {
    setLoading(true);
    setResponse(null);
    try {
      let finalPath = path;

      // --- Placeholder Resolution ---
      // If path has {supplier_id}, find the first supplier
      if (path.includes("{supplier_id}") || path.includes("{id}")) {
        try {
          const suppliers = await api<any[]>("/api/suppliers");
          if (suppliers.length > 0) {
            const sid = suppliers[0].id;
            finalPath = path.replace("{supplier_id}", sid).replace("{id}", sid);
          }
        } catch (e) {
          console.warn("Failed to fetch fallback ID for placeholder", e);
        }
      }

      const data = await api<any>(finalPath, { method });
      setResponse(JSON.stringify(data, null, 2));
    } catch (err: any) {
      // If it's a 422 or other JSON error, try to stringify the body
      if (err.body) {
        setResponse(`Error ${err.status}:\n${JSON.stringify(err.body, null, 2)}`);
      } else {
        setResponse(`Error: ${err.message || String(err)}`);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="api-entry">
      <div className="api-head">
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span className={`method m-${method.toLowerCase()}`}>
            {method.toUpperCase()}
          </span>
          <span className="path">
            {path}
          </span>
        </div>
        <button 
          onClick={testEndpoint}
          disabled={loading}
          className="btn btn-ghost"
          style={{ 
            fontSize: "10px", 
            padding: "4px 10px", 
            textTransform: "uppercase", 
            fontWeight: "bold",
            background: loading ? "var(--paper-warm)" : "transparent",
            color: "var(--blue)"
          }}
        >
          {loading ? "Calling..." : "Test Endpoint ⚡"}
        </button>
      </div>
      <div className="api-desc">
        {desc}
      </div>
      <div className="api-blueprint" style={{ position: "relative" }}>
        <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
          {response || blueprint}
        </pre>
        <div className="api-blueprint-label" style={{ 
          color: response ? "var(--green)" : "var(--ink-faint)",
          fontWeight: response ? "bold" : "normal"
        }}>
          {response ? "Live Response" : "Sample Response"}
        </div>
      </div>
    </div>
  );
}

// --- Main Page ---

export default function APIRegistryPage() {
  return (
    <div className="screen active" id="s-api">
      <div className="page-header">
        <div>
          <div className="page-title">API Registry</div>
          <div className="page-subtitle">Modular Monolith Endpoint Schema & Documentation</div>
        </div>
        <div className="connected-badge"
          style={{ 
            background: "var(--blue-pale)", 
            padding: "6px 12px", 
            borderRadius: "4px", 
            border: "1px solid var(--blue)" 
          }}>
          <span style={{ 
            fontFamily: "var(--font-mono)", 
            color: "var(--blue)", 
            fontSize: "11px" 
          }}>
            API_HOST: {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
          </span>
        </div>
      </div>

      <div className="api-list">
        <div>
          <div className="api-category">Authentication & Security</div>
          <div style={{ display: "grid", gap: "16px" }}>
            <APIEntry 
              method="GET" 
              path="/health" 
              desc="Public health check. No auth required." 
              blueprint='{ "status": "ok" }' 
            />
            <div className="api-entry" style={{ borderLeft: "4px solid var(--red)" }}>
              <div className="api-desc" style={{ padding: "10px", fontSize: "11px", color: "var(--red)", fontWeight: "bold" }}>
                🔒 SECURE ENDPOINTS REQUIRE: X-Ingest-Secret header
              </div>
            </div>
          </div>
        </div>

        <div>
          <div className="api-category">Supplier Sync (Triggered)</div>
          <div style={{ display: "grid", gap: "16px" }}>
            <APIEntry 
              method="POST" 
              path="/api/sync/{supplier_id}/products" 
              desc="Trigger a background product sync. Requires Secret." 
              blueprint='{ "job_id": "uuid", "status": "queued" }' 
            />
            <APIEntry 
              method="GET" 
              path="/api/sync/{supplier_id}/status" 
              desc="Get the status of the latest sync job for a supplier." 
              blueprint='{ "status": "completed", "records_processed": 1250 }' 
            />
          </div>
        </div>

        <div>
          <div className="api-category">System & Health</div>
          <div style={{ display: "grid", gap: "16px" }}>
            <APIEntry 
              method="GET" 
              path="/api/stats" 
              desc="Aggregated metrics for dashboard visualization." 
              blueprint='{ "suppliers": 4, "products": 32451, "variants": 187000 }' 
            />
          </div>
        </div>

        <div>
          <div className="api-category">Supplier Management</div>
          <div style={{ display: "grid", gap: "16px" }}>
            <APIEntry 
              method="GET" 
              path="/api/suppliers" 
              desc="List all connected suppliers with product counts." 
              blueprint='[ { "id": "uuid", "name": "SanMar", "protocol": "promostandards", "product_count": 12450 } ]' 
            />
          </div>
        </div>

        <div>
          <div className="api-category">Product Catalog</div>
          <div style={{ display: "grid", gap: "16px" }}>
            <APIEntry 
              method="GET" 
              path="/api/products?limit=10" 
              desc="Search normalized product catalog with pagination." 
              blueprint='{ "total": 32000, "products": [...] }' 
            />
          </div>
        </div>
      </div>
    </div>
  );
}
