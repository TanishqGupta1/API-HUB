"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { PSCompany, Supplier } from "@/lib/types";

interface Props {
  psCompanies: PSCompany[];
  onSaved: (s: Supplier) => void;
  onCancel: () => void;
}

const POPULAR_SUPPLIERS = [
  { name: "SanMar", code: "SANMAR", type: "ps" },
  { name: "S&S Activewear", code: "SSACT", type: "ps" },
  { name: "alphabroder", code: "ALPHA", type: "ps" },
  { name: "4Over", code: "4OVER", type: "custom" },
];

const SCHEDULE_MAP: Record<string, any> = {
  "Recommended (automatic)": { inv: "30min", price: "daily", prod: "daily", img: "weekly" },
  "Every 30 minutes": { inv: "30min", price: "30min", prod: "daily", img: "weekly" },
  "Every hour": { inv: "1hour", price: "1hour", prod: "daily", img: "weekly" },
  "Once a day": { inv: "daily", price: "daily", prod: "daily", img: "weekly" },
};

export default function RevealForm({ psCompanies, onSaved, onCancel }: Props) {
  const [step, setStep] = useState(1);
  const [search, setSearch] = useState("");
  const [isCustom, setIsCustom] = useState(false);

  // Form State
  const [selectedPS, setSelectedPS] = useState<PSCompany | null>(null);
  const [customName, setCustomName] = useState("");
  const [customUrl, setCustomUrl] = useState("");
  const [customType, setCustomType] = useState("Standard API"); // Maps to 'rest' or 'rest_hmac'
  
  const [creds, setCreds] = useState({ id: "", password: "" });
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "ok" | "fail">("idle");
  const [scheduleType, setScheduleType] = useState("Recommended (automatic)");
  
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const filtered = psCompanies.filter(
    (c) =>
      c.Name.toLowerCase().includes(search.toLowerCase()) ||
      c.Code.toLowerCase().includes(search.toLowerCase())
  );

  const handleTestConnection = async () => {
    setTestStatus("testing");
    await new Promise((r) => setTimeout(r, 1500));
    // Demo logic: succeed if both fields have content
    if (creds.id && creds.password) {
      setTestStatus("ok");
    } else {
      setTestStatus("fail");
    }
  };

  const handleActivate = async () => {
    setSaving(true);
    try {
      const isPS = !isCustom;
      
      // Fallback for demo if selectedPS is somehow null but we think it's a PS integration
      // (This can happen if the POPULAR_SUPPLIERS code isn't perfectly matched in psCompanies)
      const name = isPS ? (selectedPS?.Name || "Mock Supplier") : customName;
      const protocol = isPS 
        ? "promostandards"
        : (customType === "Secure API (signed requests)" ? "hmac" : "rest");
      const code = isPS ? (selectedPS?.Code || "MOCK") : customName.toUpperCase().replace(/[^A-Z0-9]+/g, "_");
      
      const supplier = await api<Supplier>("/api/suppliers", {
        method: "POST",
        body: JSON.stringify({
          name,
          slug: code.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
          protocol,
          promostandards_code: isPS ? code : null,
          base_url: isPS ? null : customUrl,
          auth_config: { 
            id: creds.id, 
            password: creds.password, 
            sync_schedule: SCHEDULE_MAP[scheduleType] 
          },
        }),
      });
      
      setSaveSuccess(true);
      setTimeout(() => {
        onSaved(supplier);
      }, 1500);
      
    } catch (e) {
      console.error(e);
      alert("Failed to activate supplier.");
    } finally {
      setSaving(false);
    }
  };

  const currentSupplierName = isCustom ? customName : selectedPS?.Name;

  return (
    <div className="wizard-shell">
      {/* STEP 1: Choose Storefront */}
      {step === 1 && (
        <div className="reveal-section">
          <div className="reveal-num">1</div>
          <div className="reveal-content">
            <div className="reveal-title font-bold text-xl mb-4">Choose your supplier</div>
            
            {!isCustom ? (
              <>
                <div className="mb-6">
                  <input
                    type="text"
                    className="input-control w-full p-3 border rounded-lg"
                    placeholder="Search 994+ suppliers..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>

                {search ? (
                  <div className="grid grid-cols-2 gap-2 max-h-[240px] overflow-y-auto mb-6 p-1">
                    {filtered.slice(0, 20).map((c) => (
                      <button
                        key={c.Code}
                        onClick={() => {
                          setSelectedPS(c);
                          setStep(2);
                        }}
                        className="flex flex-col items-start p-3 border rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all text-left"
                      >
                        <span className="text-xs font-mono font-bold text-blue-600 bg-blue-100 px-1.5 py-0.5 rounded mb-1">
                          {c.Code}
                        </span>
                        <span className="text-sm font-semibold truncate w-full">{c.Name}</span>
                      </button>
                    ))}
                    {filtered.length === 0 && (
                      <div className="col-span-2 py-4 text-center text-gray-500 text-sm italic">
                        No matching suppliers found.
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="mb-6">
                    <div className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-3">Popular Suppliers</div>
                    <div className="grid grid-cols-2 gap-3">
                      {POPULAR_SUPPLIERS.map((s) => (
                        <button
                          key={s.code}
                          onClick={() => {
                            if (s.type === "ps") {
                              const company = psCompanies.find(c => c.Code === s.code);
                              if (company) {
                                setSelectedPS(company);
                              } else {
                                // Fallback mock object if API doesn't return exactly this code
                                setSelectedPS({ Code: s.code, Name: s.name } as PSCompany);
                              }
                              setIsCustom(false);
                            } else {
                              setIsCustom(true);
                              setCustomName(s.name);
                              setCustomUrl("https://api.4over.com");
                              setCustomType("Secure API (signed requests)");
                            }
                            setStep(2);
                          }}
                          className="flex items-center justify-between p-4 border rounded-xl hover:border-blue-500 hover:bg-blue-50 transition-all group"
                        >
                          <div className="text-left">
                            <div className="font-bold text-sm text-gray-800">{s.name}</div>
                            <div className="text-[10px] text-gray-500 font-mono">{s.code}</div>
                          </div>
                          <div className="text-blue-400 group-hover:text-blue-600 transition-colors">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <button
                  onClick={() => setIsCustom(true)}
                  className="w-full py-3 text-sm font-semibold text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-colors border border-dashed border-blue-200"
                >
                  Can&apos;t find yours? Add a custom supplier
                </button>
              </>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-bold text-gray-500 uppercase mb-1 block">Supplier Name</label>
                  <input
                    type="text"
                    className="input-control w-full p-2.5 border rounded-lg text-sm"
                    placeholder="e.g. Acme Promo"
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-gray-500 uppercase mb-1 block">API Address</label>
                  <input
                    type="text"
                    className="input-control w-full p-2.5 border rounded-lg text-sm"
                    placeholder="https://api.example.com"
                    value={customUrl}
                    onChange={(e) => setCustomUrl(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-gray-500 uppercase mb-1 block">API Type</label>
                  <select
                    className="input-control w-full p-2.5 border rounded-lg text-sm bg-white"
                    value={customType}
                    onChange={(e) => setCustomType(e.target.value)}
                  >
                    <option>Standard API</option>
                    <option>Secure API (signed requests)</option>
                  </select>
                  <p className="mt-2 text-[11px] text-gray-400 leading-relaxed italic">
                    Not sure? Choose &apos;Standard API&apos; &mdash; your supplier&apos;s documentation will tell you if signed requests are needed.
                  </p>
                </div>
                <div className="flex gap-3 pt-2">
                  <button
                    onClick={() => setIsCustom(false)}
                    className="flex-1 py-3 text-sm font-semibold text-gray-500 hover:bg-gray-50 rounded-lg transition-colors"
                  >
                    Back to Search
                  </button>
                  <button
                    disabled={!customName || !customUrl}
                    onClick={() => setStep(2)}
                    className="flex-[2] py-3 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Continue
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* STEP 2: Connect account */}
      {step === 2 && (
        <div className="reveal-section">
          <div className="reveal-num">2</div>
          <div className="reveal-content">
            <div className="reveal-title font-bold text-xl mb-1">Connect your account</div>
            <div className="text-sm text-gray-500 mb-6">Linking to <span className="font-bold text-gray-700">{currentSupplierName}</span></div>
            
            <div className="space-y-4 mb-6">
              <div>
                <label className="text-xs font-bold text-gray-500 uppercase mb-1 block">API Username</label>
                <input
                  type="text"
                  className="input-control w-full p-2.5 border rounded-lg text-sm font-mono"
                  placeholder="Your API username"
                  value={creds.id}
                  onChange={(e) => {
                    setCreds({ ...creds, id: e.target.value });
                    setTestStatus("idle");
                  }}
                />
              </div>
              <div>
                <label className="text-xs font-bold text-gray-500 uppercase mb-1 block">API Password</label>
                <input
                  type="password"
                  className="input-control w-full p-2.5 border rounded-lg text-sm font-mono"
                  placeholder="••••••••"
                  value={creds.password}
                  onChange={(e) => {
                    setCreds({ ...creds, password: e.target.value });
                    setTestStatus("idle");
                  }}
                />
              </div>
              <p className="text-[11px] text-gray-400 leading-relaxed italic">
                Your supplier provides these when you sign up for API access. Contact <span className="font-bold">{currentSupplierName}</span> support if you don&apos;t have them.
              </p>
            </div>

            {testStatus === "testing" ? (
              <div className="py-6 flex flex-col items-center">
                <div className="w-full bg-gray-100 h-1.5 rounded-full overflow-hidden mb-3">
                  <div className="bg-blue-500 h-full animate-progress-fast" style={{ width: "100%" }}></div>
                </div>
                <div className="text-sm text-gray-500 font-medium">Verifying credentials...</div>
              </div>
            ) : testStatus === "ok" ? (
              <div className="p-4 bg-green-50 border border-green-200 rounded-xl mb-6">
                <div className="flex items-center gap-3 text-green-700 font-bold mb-1">
                  <div className="bg-green-500 text-white rounded-full p-1">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="4"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  </div>
                  Connected!
                </div>
                <p className="text-xs text-green-600">Successfully linked to <span className="font-bold">{currentSupplierName}</span> &mdash; ready to sync products.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {testStatus === "fail" && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs font-semibold text-red-600">
                    Could not connect. Please check your username and password.
                  </div>
                )}
                <button
                  onClick={handleTestConnection}
                  disabled={!creds.id || !creds.password}
                  className="w-full py-3 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Test Connection
                </button>
              </div>
            )}

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setStep(1)}
                className="flex-1 py-2.5 text-xs font-bold text-gray-400 hover:text-gray-600 uppercase tracking-wider"
              >
                Back
              </button>
              {testStatus === "ok" && (
                <button
                  onClick={() => setStep(3)}
                  className="flex-[2] py-2.5 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm"
                >
                  Continue to Activation
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* STEP 3: Activate */}
      {step === 3 && (
        <div className="reveal-section">
          <div className="reveal-num">3</div>
          <div className="reveal-content">
            <div className="reveal-title font-bold text-xl mb-4">Activate</div>
            
            <div className="bg-gray-50 border rounded-xl p-5 mb-8">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded-lg bg-blue-600 flex items-center justify-center text-white text-xl font-bold">
                  {currentSupplierName?.charAt(0)}
                </div>
                <div>
                  <div className="font-bold text-gray-900">{currentSupplierName}</div>
                  <div className="text-xs text-green-600 font-semibold flex items-center gap-1">
                    <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                    Connection Verified
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-gray-200">
                <label className="text-xs font-bold text-gray-500 uppercase mb-2 block">How often should we check for updates?</label>
                <select
                  className="input-control w-full p-3 border rounded-lg text-sm bg-white font-medium"
                  value={scheduleType}
                  onChange={(e) => setScheduleType(e.target.value)}
                >
                  <option>Recommended (automatic)</option>
                  <option>Every 30 minutes</option>
                  <option>Every hour</option>
                  <option>Once a day</option>
                </select>
                <p className="mt-3 text-[11px] text-gray-400 leading-relaxed italic">
                  We&apos;ll sync inventory, pricing, and product details according to this schedule. 
                  <span className="text-blue-500 font-semibold"> Recommended</span> ensures your stock levels stay accurate.
                </p>
              </div>
            </div>

            <button
              onClick={handleActivate}
              disabled={saving || saveSuccess}
              className={`w-full py-4 text-base font-bold text-white rounded-xl shadow-lg transition-all transform active:scale-[0.98] ${
                saveSuccess ? 'bg-green-500' : 'bg-blue-600 hover:bg-blue-700'
              }`}
            >
              {saving ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                  Activating...
                </span>
              ) : saveSuccess ? (
                "✓ Supplier Activated!"
              ) : (
                "Activate Supplier"
              )}
            </button>

            {!saveSuccess && (
              <button
                onClick={() => setStep(2)}
                className="w-full mt-4 py-2 text-xs font-bold text-gray-400 hover:text-gray-600 text-center uppercase tracking-wider"
              >
                Back to connection
              </button>
            )}
          </div>
        </div>
      )}

      {/* Tailwind animation keyframes added via a style tag for the loader-bar to work if not in globals.css */}
      <style jsx>{`
        @keyframes progress-fast {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(0%); }
        }
        .animate-progress-fast {
          animation: progress-fast 1.5s ease-out;
        }
      `}</style>
    </div>
  );
}
