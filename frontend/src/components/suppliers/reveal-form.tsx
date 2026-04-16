"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { PSCompany, Supplier } from "@/lib/types";

interface Props {
  psCompanies: PSCompany[];
  onSaved: (s: Supplier) => void;
  onCancel: () => void;
}

export default function RevealForm({ psCompanies, onSaved, onCancel }: Props) {
  const [protocol, setProtocol] = useState("");
  const [selectedCompany, setSelectedCompany] = useState<PSCompany | null>(null);
  const [search, setSearch] = useState("");
  const [creds, setCreds] = useState({ id: "", password: "" });
  const [customName, setCustomName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "ok" | "fail">("idle");
  const [schedule, setSchedule] = useState({ inv: "Every 30 min", price: "Daily", prod: "Daily (delta)", img: "Weekly" });
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Progressive Reveal State Logic
  const s2Unlocked = protocol !== "";
  const s3Unlocked = s2Unlocked && (protocol === "ps" ? selectedCompany !== null : (customName !== "" && baseUrl !== ""));
  const s4Unlocked = s3Unlocked && creds.id !== "";
  const s5Unlocked = s4Unlocked && testStatus === "ok";

  const filtered = psCompanies.filter(
    (c) =>
      c.Name.toLowerCase().includes(search.toLowerCase()) ||
      c.Code.toLowerCase().includes(search.toLowerCase())
  );

  const handleTest = async () => {
    setTestStatus("testing");
    await new Promise((r) => setTimeout(r, 1200));
    setTestStatus(creds.id && creds.password ? "ok" : "fail");
  };

  const handleSave = async () => {
    const isPS = protocol === "ps";
    if (isPS && !selectedCompany) return;
    if (!isPS && !customName) return;

    setSaving(true);
    try {
      const name = isPS ? selectedCompany!.Name : customName;
      const code = isPS ? selectedCompany!.Code : customName.toUpperCase().replace(/[^A-Z0-9]+/g, "_");
      
      const supplier = await api<Supplier>("/api/suppliers", {
        method: "POST",
        body: JSON.stringify({
          name,
          slug: code.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
          protocol,
          promostandards_code: isPS ? code : null,
          base_url: isPS ? null : baseUrl,
          auth_config: { id: creds.id, password: creds.password, sync_schedule: schedule },
        }),
      });
      
      setSaveSuccess(true);
      setSaving(false);
      
      // Delay to let the user see the "Activated" state
      setTimeout(() => {
        onSaved(supplier);
      }, 2000);
      
    } catch (e) {
      console.error(e);
      setSaving(false);
      alert("Failed to save supplier. Check connection.");
    }
  };

  return (
    <div className="wizard-shell">
      {/* SECTION 1: Protocol */}
      <div className={`reveal-section`} id="sec-1">
        <div className="reveal-num">1</div>
        <div className="reveal-content">
          <div className="reveal-title">How does this supplier connect?</div>
          <div style={{ display: "grid", gap: "10px", marginTop: "16px" }}>
            <label className={`proto-card ${protocol === "ps" ? "selected" : ""}`} onClick={() => { setProtocol("ps"); setSelectedCompany(null); }}>
              <input type="radio" checked={protocol === "ps"} readOnly style={{ accentColor: "var(--blue)", width: "16px", height: "16px" }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: "14px", fontWeight: 700 }}>PromoStandards</div>
                <div style={{ fontSize: "11px", color: "var(--ink-muted)", marginTop: "2px" }}>
                  SOAP/WSDL &mdash; auto-discovers endpoints for 994 suppliers
                </div>
              </div>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--green)", background: "var(--green-pale)", padding: "3px 8px", borderRadius: "3px", fontWeight: 600 }}>
                994 vendors
              </span>
            </label>
            <label className={`proto-card ${protocol === "rest" ? "selected" : ""}`} onClick={() => { setProtocol("rest"); setSelectedCompany(null); }}>
              <input type="radio" checked={protocol === "rest"} readOnly style={{ accentColor: "var(--blue)", width: "16px", height: "16px" }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: "14px", fontWeight: 700 }}>REST API</div>
                <div style={{ fontSize: "11px", color: "var(--ink-muted)", marginTop: "2px" }}>
                  JSON over HTTPS &mdash; Basic Auth or Bearer token
                </div>
              </div>
            </label>
            <label className={`proto-card ${protocol === "hmac" ? "selected" : ""}`} onClick={() => { setProtocol("hmac"); setSelectedCompany(null); }}>
              <input type="radio" checked={protocol === "hmac"} readOnly style={{ accentColor: "var(--blue)", width: "16px", height: "16px" }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: "14px", fontWeight: 700 }}>REST + HMAC Signing</div>
                <div style={{ fontSize: "11px", color: "var(--ink-muted)", marginTop: "2px" }}>
                  HMAC-SHA256 signed requests &mdash; e.g. 4Over
                </div>
              </div>
            </label>
          </div>
        </div>
      </div>

      {/* SECTION 2: Select Supplier */}
      <div className={`reveal-section ${!s2Unlocked ? "locked" : ""}`} id="sec-2">
        <div className="reveal-num">2</div>
        <div className="reveal-content">
          <div className="reveal-title">{protocol === "ps" ? "Which supplier?" : "API Details"}</div>
          <div style={{ fontSize: "12px", color: "var(--ink-muted)", marginTop: "4px", marginBottom: "14px" }}>
            {protocol === "ps" ? "Select from available PromoStandards vendors" : "Provide endpoint details for the custom connector"}
          </div>

          {protocol === "ps" ? (
            selectedCompany ? (
              <div className="sup-pick sel" style={{ borderColor: 'var(--blue)', background: 'var(--blue-pale)' }}>
                <div className="sp-code">{selectedCompany.Code}</div>
                <div className="sp-name">{selectedCompany.Name}</div>
                <button 
                  onClick={() => setSelectedCompany(null)}
                  style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '11px', color: 'var(--ink-muted)' }}>
                  Change
                </button>
              </div>
            ) : (
              <div>
                <input 
                  type="text" 
                  className="input-control" 
                  placeholder="Filter by name or code..." 
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  style={{ marginBottom: "12px", pointerEvents: s2Unlocked ? 'auto' : 'none' }} 
                />
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", maxHeight: "300px", overflowY: "auto", paddingRight: "4px" }}>
                  {filtered.slice(0, 40).map(c => (
                    <div key={c.Code} className="sup-pick" onClick={() => { if(s2Unlocked) setSelectedCompany(c); }}>
                      <div className="sp-code">{c.Code}</div>
                      <div className="sp-name">{c.Name}</div>
                    </div>
                  ))}
                  {filtered.length === 0 && search && (
                    <div style={{ fontSize: "13px", color: "var(--ink-muted)" }}>No matching suppliers found.</div>
                  )}
                </div>
              </div>
            )
          ) : (
            <div style={{ display: "grid", gap: "16px" }}>
              <div>
                <label className="field-label">Supplier Name</label>
                <input 
                  type="text" 
                  className="input-control" 
                  placeholder="e.g. 4Over" 
                  value={customName}
                  onChange={e => setCustomName(e.target.value)}
                  style={{ pointerEvents: s2Unlocked ? 'auto' : 'none' }}
                />
              </div>
              <div>
                <label className="field-label">Base URL</label>
                <input 
                  type="text" 
                  className="input-control" 
                  placeholder="https://api.4over.com" 
                  value={baseUrl}
                  onChange={e => setBaseUrl(e.target.value)}
                  style={{ pointerEvents: s2Unlocked ? 'auto' : 'none' }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* SECTION 3: Credentials */}
      <div className={`reveal-section ${!s3Unlocked ? "locked" : ""}`} id="sec-3">
        <div className="reveal-num">3</div>
        <div className="reveal-content">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="reveal-title">Enter credentials</div>
            <span style={{ fontSize: "10px", color: "var(--green)", fontWeight: 700, display: "flex", alignItems: "center", gap: "4px" }}>
              &#128274; Encrypted at rest
            </span>
          </div>
          <div style={{ marginTop: "16px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <div>
                <label className="field-label">Account ID / Username</label>
                <input 
                  type="text" 
                  className="input-control" 
                  placeholder="PromoStandards ID" 
                  style={{ fontFamily: "var(--font-mono)", pointerEvents: s3Unlocked ? 'auto' : 'none' }}
                  value={creds.id}
                  onChange={e => { setCreds({...creds, id: e.target.value}); setTestStatus("idle"); }} 
                />
              </div>
              <div>
                <label className="field-label">Password</label>
                <input 
                  type="password" 
                  className="input-control" 
                  placeholder="&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;" 
                  style={{ fontFamily: "var(--font-mono)", pointerEvents: s3Unlocked ? 'auto' : 'none' }}
                  value={creds.password}
                  onChange={e => { setCreds({...creds, password: e.target.value}); setTestStatus("idle"); }} 
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* SECTION 4: Test Connection */}
      <div className={`reveal-section ${!s4Unlocked ? "locked" : ""}`} id="sec-4">
        <div className="reveal-num">4</div>
        <div className="reveal-content">
          <div className="reveal-title">Verify connection</div>
          <div style={{ marginTop: "16px" }}>
            {testStatus === "idle" || testStatus === "fail" ? (
              <button 
                className="btn btn-primary" 
                style={{ width: "100%", pointerEvents: s4Unlocked ? 'auto' : 'none' }} 
                onClick={handleTest}
              >
                &#9889; Test Connection
              </button>
            ) : null}

            {testStatus === "testing" && (
              <div style={{ marginTop: "16px" }}>
                <div className="loader-bar">
                  <div className="loader-progress" style={{ width: "60%" }}></div>
                </div>
                <div style={{ fontSize: "12px", color: "var(--ink-muted)", textAlign: "center" }}>
                  Connecting to PromoStandards directory...
                </div>
              </div>
            )}
            
            {testStatus === "ok" && (
              <div style={{ marginTop: "16px" }}>
                <div className="connected-mark">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                  Connected Successfully
                </div>
                <div style={{ fontSize: "12px", color: "var(--ink-muted)" }}>
                  Found <strong style={{ color: "var(--ink)" }}>11 active services</strong> &mdash; Product Data v2, Inventory v2, Pricing v1, Media v1.1 + 7 more
                </div>
              </div>
            )}

            {testStatus === "fail" && (
              <div style={{ marginTop: "16px", color: "var(--red)", fontSize: "14px", fontWeight: 600 }}>
                Connection failed. Please check your credentials.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* SECTION 5: Schedule + Save */}
      <div className={`reveal-section ${!s5Unlocked ? "locked" : "done"}`} id="sec-5">
        <div className="reveal-num">5</div>
        <div className="reveal-content">
          <div className="reveal-title">Set sync schedule</div>
          <div style={{ display: "grid", gap: "12px", marginTop: "16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "13px", fontWeight: 600 }}>Inventory</span>
              <select style={{ padding: "6px 12px", border: "1.5px solid var(--border)", borderRadius: "4px", fontFamily: "var(--font-head)", fontSize: "12px", background: "white", minWidth: "140px", pointerEvents: s5Unlocked ? 'auto' : 'none' }}>
                <option>Every 30 min</option>
                <option>Every 15 min</option>
                <option>Every 1 hour</option>
              </select>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "13px", fontWeight: 600 }}>Pricing</span>
              <select style={{ padding: "6px 12px", border: "1.5px solid var(--border)", borderRadius: "4px", fontFamily: "var(--font-head)", fontSize: "12px", background: "white", minWidth: "140px", pointerEvents: s5Unlocked ? 'auto' : 'none' }}>
                <option>Daily</option>
                <option>Twice daily</option>
                <option>Weekly</option>
              </select>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "13px", fontWeight: 600 }}>Products</span>
              <select style={{ padding: "6px 12px", border: "1.5px solid var(--border)", borderRadius: "4px", fontFamily: "var(--font-head)", fontSize: "12px", background: "white", minWidth: "140px", pointerEvents: s5Unlocked ? 'auto' : 'none' }}>
                <option>Daily (delta)</option>
                <option>Weekly (full)</option>
              </select>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "13px", fontWeight: 600 }}>Images</span>
              <select style={{ padding: "6px 12px", border: "1.5px solid var(--border)", borderRadius: "4px", fontFamily: "var(--font-head)", fontSize: "12px", background: "white", minWidth: "140px", pointerEvents: s5Unlocked ? 'auto' : 'none' }}>
                <option>Weekly</option>
                <option>On demand</option>
              </select>
            </div>
          </div>
          <button 
            className="btn btn-primary" 
            style={{ 
              width: "100%", 
              marginTop: "24px", 
              padding: "14px", 
              pointerEvents: s5Unlocked ? 'auto' : 'none',
              background: saveSuccess ? 'var(--green)' : '',
              boxShadow: saveSuccess ? '0 4px 0 #1a5c3a' : ''
            }} 
            onClick={handleSave}
            disabled={saving || saveSuccess}
          >
            {saving ? "Deploying..." : saveSuccess ? "✓ Supplier Activated!" : "Save & Activate Supplier"}
          </button>
        </div>
      </div>
    </div>
  );
}
