"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Search, Building2, Globe, ArrowRight, ShieldCheck, Activity } from "lucide-react";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import type { Customer } from "@/lib/types";

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<Customer[]>("/api/customers")
      .then(setCustomers)
      .catch(log.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = customers.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Page Header */}
      <div className="flex items-end justify-between mb-10 pb-6 border-b-2 border-[#1e1e24]">
        <div>
          <div className="text-[32px] font-extrabold tracking-tight leading-none text-[#1e1e24]">
            Storefront Directory
          </div>
          <p className="text-[14px] text-[#888894] mt-3 max-w-xl leading-relaxed">
            Manage your OnPrintShop (OPS) instances. Connected storefronts can receive products, 
            inventory updates, and custom price markups from the hub.
          </p>
        </div>
        <Link
          href="/customers/new"
          className="flex items-center gap-2 px-6 py-3 bg-[#1e4d92] text-white text-[13px] font-bold rounded-xl shadow-[0_4px_0_#143566] hover:bg-[#173d74] active:shadow-none active:translate-y-1 transition-all"
        >
          <Plus className="w-4 h-4" />
          Register Storefront
        </Link>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-4 mb-8">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#b4b4bc]" />
          <input
            type="text"
            placeholder="Filter by storefront name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-11 pr-4 h-12 bg-white border border-[#cfccc8] rounded-xl text-[14px] font-medium text-[#1e1e24] placeholder:text-[#b4b4bc] outline-none focus:border-[#1e4d92] transition-colors shadow-sm"
          />
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-[#f9f7f4] border border-[#cfccc8] rounded-lg">
          <Activity className="w-3.5 h-3.5 text-emerald-600" />
          <span className="text-[11px] font-black uppercase tracking-widest text-[#484852]">
            {customers.length} Active Nodes
          </span>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-pulse">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-64 bg-white border border-[#f2f0ed] rounded-2xl" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-24 text-center border-2 border-dashed border-[#cfccc8] rounded-3xl bg-[#fcfbf9]">
          <div className="w-16 h-16 bg-white border border-[#cfccc8] rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-sm">
            <Building2 className="w-8 h-8 text-[#b4b4bc]" />
          </div>
          <div className="text-[16px] font-bold text-[#1e1e24]">No storefronts found</div>
          <p className="text-[13px] text-[#888894] mt-1 mb-6">Start by registering your first OPS instance.</p>
          <Link
            href="/customers/new"
            className="text-[13px] font-bold text-[#1e4d92] hover:underline"
          >
            Create registration →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((customer) => (
            <Link
              key={customer.id}
              href={`/customers/${customer.id}`}
              className="group bg-white border border-[#cfccc8] rounded-2xl p-6 hover:border-[#1e4d92] hover:shadow-xl hover:shadow-blue-900/5 transition-all relative overflow-hidden"
            >
              <div className="flex items-start justify-between mb-6">
                <div className="w-12 h-12 rounded-xl bg-[#eef4fb] text-[#1e4d92] flex items-center justify-center group-hover:bg-[#1e4d92] group-hover:text-white transition-colors shadow-sm">
                  <Globe className="w-6 h-6" />
                </div>
                {customer.is_active ? (
                  <span className="flex items-center gap-1 text-[10px] font-black bg-emerald-50 text-emerald-700 px-2.5 py-1 rounded-full border border-emerald-100 uppercase tracking-wider">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Online
                  </span>
                ) : (
                  <span className="text-[10px] font-black bg-[#f9f7f4] text-[#888894] px-2.5 py-1 rounded-full border border-[#ebe8e3] uppercase tracking-wider">
                    Offline
                  </span>
                )}
              </div>

              <h3 className="text-[20px] font-extrabold text-[#1e1e24] mb-1 group-hover:text-[#1e4d92] transition-colors tracking-tight">
                {customer.name}
              </h3>
              <div className="text-[12px] font-mono text-[#888894] mb-6 truncate opacity-70">
                {customer.ops_base_url}
              </div>

              <div className="grid grid-cols-2 gap-4 pt-6 border-t border-[#f2f0ed]">
                <div>
                  <div className="text-[10px] font-black text-[#888894] uppercase tracking-widest mb-0.5">Products</div>
                  <div className="text-[16px] font-bold text-[#1e1e24]">{customer.products_pushed}</div>
                </div>
                <div>
                  <div className="text-[10px] font-black text-[#888894] uppercase tracking-widest mb-0.5">Markup Rules</div>
                  <div className="text-[16px] font-bold text-[#1e1e24]">{customer.markup_rules_count}</div>
                </div>
              </div>

              <div className="absolute bottom-6 right-6 opacity-0 group-hover:opacity-100 transition-opacity">
                <div className="w-8 h-8 rounded-full bg-[#1e4d92] text-white flex items-center justify-center shadow-lg">
                  <ArrowRight className="w-4 h-4" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Footer / Trust Badge */}
      <div className="mt-16 pt-8 border-t border-[#f2f0ed] flex items-center justify-center gap-8 opacity-50 grayscale">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4" />
          <span className="text-[11px] font-bold uppercase tracking-widest">OPS Certified Connector</span>
        </div>
        <div className="flex items-center gap-2">
          <Lock className="w-4 h-4" />
          <span className="text-[11px] font-bold uppercase tracking-widest">OAuth2 Security</span>
        </div>
      </div>
    </div>
  );
}
