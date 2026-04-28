"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import type { PSCompany, Supplier } from "@/lib/types";

interface Props {
  psCompanies: PSCompany[];
  onSaved: (s: Supplier) => void;
  onCancel: () => void;
}


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
  const [customType, setCustomType] = useState("Standard API");

  const [creds, setCreds] = useState({ id: "", password: "" });
  const [customerNumber, setCustomerNumber] = useState("");
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
    try {
      const isPS = !isCustom;
      const protocol = isPS
        ? "promostandards"
        : (customType === "Secure API (signed requests)" ? "hmac" : "rest");

      const res = await api<any>("/api/suppliers/test", {
        method: "POST",
        body: JSON.stringify({
          protocol,
          promostandards_code: isPS ? selectedPS?.Code : null,
          auth_config: { id: creds.id, password: creds.password }
        })
      });

      if (res.ok) {
        setTestStatus("ok");
      } else {
        setTestStatus("fail");
      }
    } catch (err) {
      log.error("Test connection failed:", err);
      setTestStatus("fail");
    }
  };

  const handleActivate = async () => {
    setSaving(true);
    try {
      const isPS = !isCustom;

      const name = isPS ? selectedPS!.Name : customName;
      const protocol = isPS
        ? "promostandards"
        : (customType === "Secure API (signed requests)" ? "hmac" : "rest");
      const code = isPS ? selectedPS!.Code : customName.toUpperCase().replace(/[^A-Z0-9]+/g, "_");

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
            ...(customerNumber ? { customer_number: customerNumber } : {}),
            sync_schedule: SCHEDULE_MAP[scheduleType]
          },
        }),
      });

      setSaveSuccess(true);
      setTimeout(() => {
        onSaved(supplier);
      }, 1500);

    } catch (e) {
      log.error("Test connection failed", e);
      alert("Failed to activate supplier.");
    } finally {
      setSaving(false);
    }
  };

  const currentSupplierName = isCustom ? customName : selectedPS?.Name;

  /* ── shared input class ── */
  const inputCls = "w-full px-4 py-[11px] bg-white border-2 border-[#cfccc8] rounded-lg text-[14px] font-sans text-[#1e1e24] outline-none transition-all focus:border-[#1e4d92] focus:shadow-[0_0_0_4px_#eef4fb] placeholder:text-[#b4b4bc]";
  const selectCls = "w-full px-4 py-[11px] bg-white border-2 border-[#cfccc8] rounded-lg text-[14px] font-sans text-[#1e1e24] outline-none transition-all focus:border-[#1e4d92] focus:shadow-[0_0_0_4px_#eef4fb] appearance-none cursor-pointer";
  const labelCls = "block text-[11px] font-bold uppercase tracking-[0.08em] text-[#888894] mb-[6px]";
  const primaryBtn = "w-full py-[13px] text-[14px] font-bold text-white bg-[#1e4d92] hover:bg-[#173d74] rounded-lg shadow-[0_3px_0_#143566] active:shadow-none active:translate-y-[2px] transition-all disabled:opacity-40 disabled:cursor-not-allowed";
  const ghostBtn = "py-[10px] text-[12px] font-bold text-[#888894] hover:text-[#484852] uppercase tracking-wider transition-colors";

  return (
    <div className="wizard-shell">

      {/* ── STEP 1: Choose Supplier ────────────────────── */}
      {step === 1 && (
        <div className="reveal-section">
          <div className="reveal-num">1</div>
          <div className="reveal-content">
            <div className="reveal-title mb-5">Choose your supplier</div>

            {!isCustom ? (
              <>
                <div className="mb-5">
                  <input
                    type="text"
                    className={inputCls}
                    placeholder="Search 994+ suppliers..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>

                {search ? (
                  <div className="grid grid-cols-2 gap-2 max-h-[240px] overflow-y-auto mb-5 pr-1">
                    {filtered.slice(0, 20).map((c) => (
                      <button
                        key={c.Code}
                        onClick={() => { setSelectedPS(c); setStep(2); }}
                        className="flex flex-col items-start p-3 border-2 border-[#cfccc8] rounded-lg hover:border-[#1e4d92] hover:bg-[#eef4fb] transition-all text-left"
                      >
                        <span className="text-[10px] font-mono font-bold text-[#1e4d92] bg-[#eef4fb] px-1.5 py-0.5 rounded mb-1">
                          {c.Code}
                        </span>
                        <span className="text-[13px] font-semibold text-[#1e1e24] truncate w-full">{c.Name}</span>
                      </button>
                    ))}
                    {filtered.length === 0 && (
                      <div className="col-span-2 py-6 text-center text-[#888894] text-[13px]">
                        No matching suppliers found.
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="mb-5">
                    <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#888894] mb-3">Popular Suppliers</div>
                    <div className="grid grid-cols-2 gap-3">
                      {psCompanies.slice(0, 4).map((s) => (
                        <button
                          key={s.Code}
                          onClick={() => { setSelectedPS(s); setIsCustom(false); setStep(2); }}
                          className="flex items-center justify-between p-4 border-2 border-[#cfccc8] rounded-xl hover:border-[#1e4d92] hover:bg-[#eef4fb] transition-all group"
                        >
                          <div className="text-left">
                            <div className="font-bold text-[13px] text-[#1e1e24]">{s.Name}</div>
                            <div className="text-[10px] text-[#888894] font-mono mt-0.5">{s.Code}</div>
                          </div>
                          <svg className="text-[#cfccc8] group-hover:text-[#1e4d92] transition-colors" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="9 18 15 12 9 6" />
                          </svg>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <button
                  onClick={() => setIsCustom(true)}
                  className="w-full py-3 text-[13px] font-semibold text-[#1e4d92] hover:bg-[#eef4fb] rounded-lg transition-colors border-2 border-dashed border-[#1e4d92]/30 hover:border-[#1e4d92]"
                >
                  Can&apos;t find yours? Add a custom supplier
                </button>
              </>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className={labelCls}>Supplier Name</label>
                  <input
                    type="text"
                    className={inputCls}
                    placeholder="e.g. Acme Promo"
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                  />
                </div>
                <div>
                  <label className={labelCls}>API Address</label>
                  <input
                    type="text"
                    className={`${inputCls} font-mono`}
                    placeholder="https://api.example.com"
                    value={customUrl}
                    onChange={(e) => setCustomUrl(e.target.value)}
                  />
                </div>
                <div>
                  <label className={labelCls}>API Type</label>
                  <div className="relative">
                    <select
                      className={selectCls}
                      value={customType}
                      onChange={(e) => setCustomType(e.target.value)}
                    >
                      <option>Standard API</option>
                      <option>Secure API (signed requests)</option>
                    </select>
                    <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[#888894]">▾</span>
                  </div>
                  <p className="mt-2 text-[11px] text-[#888894] leading-relaxed">
                    Not sure? Choose &apos;Standard API&apos; — your supplier&apos;s documentation will tell you if signed requests are needed.
                  </p>
                </div>
                <div className="flex gap-3 pt-2">
                  <button onClick={() => setIsCustom(false)} className={`flex-1 ${ghostBtn}`}>
                    ← Back to Search
                  </button>
                  <button
                    disabled={!customName || !customUrl}
                    onClick={() => setStep(2)}
                    className={`flex-[2] ${primaryBtn}`}
                  >
                    Continue →
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── STEP 2: Connect account ───────────────────── */}
      {step === 2 && (
        <div className="reveal-section">
          <div className="reveal-num">2</div>
          <div className="reveal-content">
            <div className="reveal-title mb-1">Connect your account</div>
            <div className="text-[13px] text-[#888894] mb-6">
              Linking to <span className="font-bold text-[#1e1e24]">{currentSupplierName}</span>
            </div>

            <div className="space-y-4 mb-6">
              <div>
                <label className={labelCls}>API Username</label>
                <input
                  type="text"
                  className={`${inputCls} font-mono`}
                  placeholder="Your API username"
                  value={creds.id}
                  onChange={(e) => { setCreds({ ...creds, id: e.target.value }); setTestStatus("idle"); }}
                />
              </div>
              <div>
                <label className={labelCls}>API Password</label>
                <input
                  type="password"
                  className={`${inputCls} font-mono`}
                  placeholder="••••••••"
                  value={creds.password}
                  onChange={(e) => { setCreds({ ...creds, password: e.target.value }); setTestStatus("idle"); }}
                />
              </div>
              {!isCustom && (
                <div>
                  <label className={labelCls}>
                    Customer / Account Number
                    <span className="ml-2 text-[10px] font-normal text-[#888894] normal-case">
                      (required for SanMar; optional for others)
                    </span>
                  </label>
                  <input
                    type="text"
                    className={`${inputCls} font-mono`}
                    placeholder="e.g. 12345678"
                    value={customerNumber}
                    onChange={(e) => { setCustomerNumber(e.target.value); setTestStatus("idle"); }}
                  />
                </div>
              )}
              <p className="text-[11px] text-[#888894] leading-relaxed bg-[#f9f7f4] border border-[#cfccc8] rounded-lg px-4 py-3">
                Your supplier provides these when you sign up for API access. Contact{" "}
                <span className="font-bold text-[#484852]">{currentSupplierName}</span> support if you don&apos;t have them.
              </p>
            </div>

            {testStatus === "testing" ? (
              <div className="py-5 flex flex-col items-center">
                <div className="w-full bg-[#ebe8e3] h-1.5 rounded-full overflow-hidden mb-3">
                  <div className="bg-[#1e4d92] h-full animate-progress-fast" style={{ width: "100%" }} />
                </div>
                <div className="text-[13px] text-[#888894] font-medium">Verifying credentials...</div>
              </div>
            ) : testStatus === "ok" ? (
              <div className="p-4 bg-[#f0f9f4] border border-[#247a52]/30 rounded-xl mb-6">
                <div className="flex items-center gap-2 text-[#247a52] font-bold text-[13px] mb-1">
                  <span className="w-5 h-5 bg-[#247a52] text-white rounded-full flex items-center justify-center text-[10px]">✓</span>
                  Connected!
                </div>
                <p className="text-[12px] text-[#247a52]">
                  Successfully linked to <span className="font-bold">{currentSupplierName}</span> — ready to sync products.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {testStatus === "fail" && (
                  <div className="p-3 bg-[#fdf2f2] border border-[#b93232]/30 rounded-lg text-[12px] font-semibold text-[#b93232]">
                    Could not connect. Please check your username and password.
                  </div>
                )}
                <button
                  onClick={handleTestConnection}
                  disabled={!creds.id || !creds.password}
                  className={primaryBtn}
                >
                  Test Connection
                </button>
              </div>
            )}

            <div className="flex gap-3 mt-5">
              <button onClick={() => setStep(1)} className={`flex-1 ${ghostBtn}`}>
                ← Back
              </button>
              {testStatus === "ok" && (
                <button onClick={() => setStep(3)} className={`flex-[2] ${primaryBtn}`}>
                  Continue to Activation →
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── STEP 3: Activate ─────────────────────────── */}
      {step === 3 && (
        <div className="reveal-section">
          <div className="reveal-num">3</div>
          <div className="reveal-content">
            <div className="reveal-title mb-5">Activate</div>

            <div className="bg-[#f9f7f4] border border-[#cfccc8] rounded-xl p-5 mb-8">
              <div className="flex items-center gap-4 mb-5">
                <div className="w-12 h-12 rounded-lg bg-[#1e4d92] flex items-center justify-center text-white text-xl font-bold shadow-[0_3px_0_#143566]">
                  {currentSupplierName?.charAt(0)}
                </div>
                <div>
                  <div className="font-bold text-[14px] text-[#1e1e24]">{currentSupplierName}</div>
                  <div className="text-[12px] text-[#247a52] font-semibold flex items-center gap-1 mt-0.5">
                    <span className="w-1.5 h-1.5 bg-[#247a52] rounded-full" />
                    Connection Verified
                  </div>
                </div>
              </div>

              <div className="pt-5 border-t border-[#cfccc8]">
                <label className={labelCls}>How often should we check for updates?</label>
                <div className="relative">
                  <select
                    className={selectCls}
                    value={scheduleType}
                    onChange={(e) => setScheduleType(e.target.value)}
                  >
                    <option>Recommended (automatic)</option>
                    <option>Every 30 minutes</option>
                    <option>Every hour</option>
                    <option>Once a day</option>
                  </select>
                  <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[#888894]">▾</span>
                </div>
                <p className="mt-3 text-[11px] text-[#888894] leading-relaxed">
                  We&apos;ll sync inventory, pricing, and product details on this schedule.{" "}
                  <span className="text-[#1e4d92] font-semibold">Recommended</span> keeps stock levels accurate automatically.
                </p>
              </div>
            </div>

            <button
              onClick={handleActivate}
              disabled={saving || saveSuccess}
              className={`w-full py-[14px] text-[15px] font-bold text-white rounded-xl shadow-[0_4px_0_#143566] active:shadow-none active:translate-y-[3px] transition-all ${
                saveSuccess ? "bg-[#247a52] shadow-[0_4px_0_#1a5c3e]" : "bg-[#1e4d92] hover:bg-[#173d74]"
              } disabled:opacity-40 disabled:cursor-not-allowed`}
            >
              {saving ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Activating...
                </span>
              ) : saveSuccess ? "✓ Supplier Activated!" : "Activate Supplier"}
            </button>

            {!saveSuccess && (
              <button onClick={() => setStep(2)} className={`w-full mt-4 text-center ${ghostBtn}`}>
                ← Back to connection
              </button>
            )}
          </div>
        </div>
      )}

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
