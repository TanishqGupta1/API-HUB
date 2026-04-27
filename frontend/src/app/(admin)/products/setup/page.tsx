"use client";

import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import type { Product, Customer } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function ProductSetupPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [productId, setProductId] = useState("");
  const [productSearch, setProductSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [c, p] = await Promise.all([
          api<Customer[]>("/api/customers"),
          api<Product[]>("/api/products?limit=200"),
        ]);
        setCustomers(c);
        setProducts(p);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const filteredProducts = useMemo(() => {
    if (!productSearch.trim()) return products;
    return products.filter((p) =>
      p.product_name.toLowerCase().includes(productSearch.toLowerCase()) ||
      p.supplier_sku?.toLowerCase().includes(productSearch.toLowerCase())
    );
  }, [products, productSearch]);

  const chosenCustomer = customers.find((c) => c.id === customerId);
  const chosenProduct = products.find((p) => p.id === productId);
  const isReady = !!customerId && !!productId;

  if (loading) return (
    <div className="flex items-center justify-center h-[60vh] flex-col gap-4">
      <div className="w-8 h-8 border-[3px] border-[#1e4d92] border-t-transparent rounded-full animate-spin" />
      <p className="text-sm text-[#888894]">Loading setup tools...</p>
    </div>
  );

  return (
    <div className="p-8 max-w-5xl mx-auto flex flex-col gap-8">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-[#1e1e24] tracking-tight">Product Setup</h1>
        <p className="text-sm text-[#888894] mt-1">
          Map supplier products to your OPS storefront categories and pricing rules.
        </p>
      </div>

      {/* Step 1 + 2 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Step 1 — Storefront */}
        <div className="flex flex-col gap-2">
          <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
            Step 1 · Target Storefront
          </label>
          <Select value={customerId} onValueChange={setCustomerId}>
            <SelectTrigger className="h-11 bg-white border-[#cfccc8] text-[13px]">
              <SelectValue placeholder="Select a storefront..." />
            </SelectTrigger>
            <SelectContent className="w-[var(--radix-select-trigger-width)]">
              {customers.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Step 2 — Product with search filter */}
        <div className="flex flex-col gap-2">
          <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
            Step 2 · Product to Configure
          </label>
          <Input
            placeholder="Filter products by name or SKU..."
            value={productSearch}
            onChange={(e) => { setProductSearch(e.target.value); setProductId(""); }}
            className="h-8 text-[12px] bg-white border-[#cfccc8] mb-1"
          />
          <Select value={productId} onValueChange={setProductId}>
            <SelectTrigger className="h-11 bg-white border-[#cfccc8] text-[13px]">
              <SelectValue placeholder="Select a product..." />
            </SelectTrigger>
            <SelectContent className="w-[var(--radix-select-trigger-width)]">
              {filteredProducts.length === 0 ? (
                <div className="px-4 py-3 text-xs text-[#888894]">No products match your search.</div>
              ) : (
                filteredProducts.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.product_name} ({p.supplier_sku})
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Config Panel — only shown when both are selected */}
      {isReady ? (
        <div className="flex flex-col gap-6">

          {/* Product banner */}
          <div className="flex items-center gap-4 bg-white border border-[#cfccc8] rounded-xl px-6 py-4">
            <div className="w-11 h-11 rounded-lg bg-[#1e4d92] text-white font-extrabold text-lg flex items-center justify-center shrink-0">
              {chosenProduct?.product_name?.[0]}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-base font-bold text-[#1e1e24] truncate">{chosenProduct?.product_name}</div>
              <div className="text-xs text-[#888894]">
                Configuring for <span className="text-[#1e4d92] font-semibold">{chosenCustomer?.name}</span>
              </div>
            </div>
            <Button variant="outline" className="border-[#cfccc8] text-[13px]">Discard</Button>
            <Button className="bg-[#1e4d92] hover:bg-[#173d74] text-[13px]">Finalize Setup</Button>
          </div>

          {/* 3-card config grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">

            {/* Category */}
            <Card className="border-[#cfccc8] overflow-hidden">
              <div className="bg-[#f9f7f4] border-b border-[#ebe8e3] px-5 py-3 text-[12px] font-bold text-[#1e4d92]">
                📂 Storefront Category
              </div>
              <div className="p-5 flex flex-col gap-4">
                <p className="text-xs text-[#888894]">Where will this product appear in the VG catalog?</p>
                <Select>
                  <SelectTrigger className="h-9 border-[#cfccc8] text-[13px]">
                    <SelectValue placeholder="Select category..." />
                  </SelectTrigger>
                  <SelectContent className="w-[var(--radix-select-trigger-width)]">
                    <SelectItem value="apparel-tee">Apparel › T-Shirts</SelectItem>
                    <SelectItem value="apparel-hoodie">Apparel › Hoodies</SelectItem>
                    <SelectItem value="apparel-polo">Apparel › Polo</SelectItem>
                    <SelectItem value="infant">Infant &amp; Toddler</SelectItem>
                  </SelectContent>
                </Select>
                <div className="bg-blue-50 border border-blue-100 rounded-lg px-3 py-2 text-[11px] text-[#1e4d92]">
                  ℹ️ Currently: <span className="font-bold">Unassigned</span>
                </div>
              </div>
            </Card>

            {/* Option Mapping */}
            <Card className="border-[#cfccc8] overflow-hidden">
              <div className="bg-[#f9f7f4] border-b border-[#ebe8e3] px-5 py-3 text-[12px] font-bold text-[#1e4d92]">
                ⚙️ Option Mapping
              </div>
              <div className="p-5 flex flex-col gap-4">
                <p className="text-xs text-[#888894]">Connect supplier attributes to OPS master options.</p>
                <Button className="w-full bg-[#1e4d92] hover:bg-[#173d74] text-xs font-bold h-9">
                  Open Mapping Editor
                </Button>
                <div className="flex justify-between text-[11px] font-bold border-t border-dashed border-[#cfccc8] pt-3">
                  <span className="text-[#888894]">Mapped: 0</span>
                  <span className="text-[#1e4d92]">Pending: 2</span>
                </div>
              </div>
            </Card>

            {/* Pricing */}
            <Card className="border-[#cfccc8] bg-[#f9f7f4]">
              <div className="bg-[#ebe8e3] border-b border-[#d8d4cf] px-5 py-3 text-[12px] font-bold text-[#1e4d92]">
                💰 Pricing Outlook
              </div>
              <div className="p-5">
                <div className="bg-white rounded-lg border border-[#cfccc8] p-4 flex flex-col gap-3">
                  <div className="flex justify-between text-xs text-[#888894]">
                    <span>Wholesale Base</span>
                    <span className="font-mono font-bold text-[#1e1e24]">$3.99</span>
                  </div>
                  <div className="flex justify-between text-xs text-[#1e4d92]">
                    <span>Markup (45%)</span>
                    <span className="font-mono font-bold">+$1.80</span>
                  </div>
                  <div className="flex justify-between text-xs text-[#888894] border-b border-dashed border-[#cfccc8] pb-3">
                    <span>Rounding</span>
                    <span className="font-mono italic">Nearest .99</span>
                  </div>
                  <div className="flex justify-between items-end">
                    <span className="text-[10px] font-bold text-[#484852] uppercase tracking-wide">Customer Price</span>
                    <span className="text-xl font-extrabold text-[#1e4d92] font-mono leading-none">$5.99</span>
                  </div>
                </div>
              </div>
            </Card>

          </div>
        </div>
      ) : (
        <div className="border-2 border-dashed border-[#cfccc8] rounded-2xl p-24 text-center bg-[#fafaf8]">
          <div className="text-4xl mb-3">⚙️</div>
          <h3 className="text-base font-bold text-[#484852] mb-1">Setup Pending</h3>
          <p className="text-sm text-[#888894] max-w-sm mx-auto">
            Select a target storefront and a product above to access the configuration panel.
          </p>
        </div>
      )}
    </div>
  );
}
