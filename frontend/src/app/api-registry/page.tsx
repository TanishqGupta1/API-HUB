"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

// --- Components ---

function APIEntry({ method, path, desc, blueprint }: { method: string; path: string; desc: string; blueprint: string }) {
  return (
    <div className="api-entry">
      <div className="api-head">
        <span className={`method m-${method.toLowerCase()}`}>
          {method.toUpperCase()}
        </span>
        <span className="path">
          {path}
        </span>
      </div>
      <div className="api-desc">
        {desc}
      </div>
      <div className="api-blueprint">
        {blueprint}
        <div className="api-blueprint-label">
          Sample Response
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
            BASE_URL: http://localhost:8000
          </span>
        </div>
      </div>

      <div className="api-list">
        <div>
          <div className="api-category">System & Health</div>
          <div style={{ display: "grid", gap: "16px" }}>
            <APIEntry 
              method="GET" 
              path="/health" 
              desc="Service heartbeat and uptime verification." 
              blueprint='{ "status": "healthy", "service": "api-hub" }' 
            />
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
            <APIEntry 
              method="POST" 
              path="/api/suppliers" 
              desc="Register a new supplier. Encrypts auth_config at rest." 
              blueprint='Request: { "name": "...", "promostandards_code": "...", "auth_config": {...} }' 
            />
          </div>
        </div>

        <div>
          <div className="api-category">PromoStandards Directory</div>
          <div style={{ display: "grid", gap: "16px" }}>
            <APIEntry 
              method="GET" 
              path="/api/ps-directory/companies" 
              desc="Fetch the global registry of 1800+ PromoStandards members." 
              blueprint='[ { "Code": "SANMAR", "Name": "SanMar Corporation", "Type": "Supplier" } ]' 
            />
          </div>
        </div>

        <div>
          <div className="api-category">Product Catalog</div>
          <div style={{ display: "grid", gap: "16px" }}>
            <APIEntry 
              method="GET" 
              path="/api/products" 
              desc="Search normalized product catalog with pagination." 
              blueprint='Params: ?search=tee&limit=50&brand=Gildan' 
            />
          </div>
        </div>
      </div>
    </div>
  );
}
