"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  ChevronLeft,
  Copy,
  Settings2,
  GripVertical,
  ArrowUpDown,
  Trash2,
  Save,
  ChevronDown,
  ChevronUp,
  Layers,
  Package,
  Store,
  CheckCircle2,
  Sliders,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { log } from "@/lib/log";

// ─── Component: OptionCard ──────────────────────────────────────────────────

const VISIBLE_LIMIT = 6;

function OptionCard({
  option,
  productId,
  onUpdateAttr,
  onToggle,
  onRefresh,
}: {
  option: any;
  productId: string;
  onUpdateAttr: (attrId: string, field: string, value: any) => void;
  onToggle: (enabled: boolean) => void;
  onRefresh: () => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const sortedAttrs = useMemo(
    () => [...option.attributes].sort((a: any, b: any) => a.sort_order - b.sort_order),
    [option.attributes]
  );

  const visible = showAll ? sortedAttrs : sortedAttrs.slice(0, VISIBLE_LIMIT);
  const hasMore = sortedAttrs.length > VISIBLE_LIMIT;
  const enabledCount = sortedAttrs.filter((a: any) => a.enabled).length;

  const handleSaveCard = async () => {
    setIsSaving(true);
    try {
      await api(`/api/products/${productId}/options/${option.id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: option.enabled }),
      });
      await Promise.all(
        option.attributes.map((attr: any) =>
          api(`/api/products/${productId}/options/${option.id}/attributes/${attr.id}`, {
            method: "PATCH",
            body: JSON.stringify({
              price: attr.price,
              sort_order: attr.sort_order,
              enabled: attr.enabled,
            }),
          })
        )
      );
      toast.success("Option saved");
    } catch (e: any) {
      toast.error(`Save failed: ${e.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteCard = async () => {
    if (!confirm("Delete this option group entirely?")) return;
    setIsDeleting(true);
    try {
      await api(`/api/products/${productId}/options/${option.id}`, { method: "DELETE" });
      toast.success("Option deleted");
      onRefresh();
    } catch (e: any) {
      toast.error(`Delete failed: ${e.message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div
      className={`bg-white border flex flex-col rounded-2xl overflow-hidden transition-all duration-200 hover:shadow-lg hover:shadow-blue-900/5 ${
        option.enabled ? "border-[#cfccc8]" : "border-[#e8e5e2] opacity-60"
      }`}
    >
      {/* Card Header */}
      <div className="px-4 py-3 flex items-center justify-between border-b border-[#f2f0ed] bg-[#f9f7f4]">
        <div className="flex items-center gap-2.5 min-w-0">
          <GripVertical className="w-4 h-4 text-[#b4b4bc] shrink-0 cursor-grab" />
          <div className="min-w-0">
            <div className="text-[11px] font-black text-[#1e1e24] uppercase tracking-widest truncate">
              {option.title}
            </div>
            <div className="text-[10px] text-[#888894] font-medium mt-0.5">
              {enabledCount}/{sortedAttrs.length} active
            </div>
          </div>
        </div>
        <Switch
          checked={option.enabled}
          onCheckedChange={onToggle}
          className="data-[state=checked]:bg-[#1e4d92] data-[state=unchecked]:bg-[#cfccc8]"
        />
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-[28px_1fr_88px_64px] text-[9px] font-black uppercase tracking-widest text-[#888894] border-b border-[#f2f0ed] bg-[#fcfbf9]">
        <div className="flex justify-center py-1.5 border-r border-[#f2f0ed]">✓</div>
        <div className="px-3 py-1.5 border-r border-[#f2f0ed]">Attribute</div>
        <div className="px-2 py-1.5 border-r border-[#f2f0ed] text-right">Price</div>
        <div className="px-2 py-1.5 text-right">Order</div>
      </div>

      {/* Attribute rows */}
      <div className="flex-1 overflow-y-auto min-h-[180px] max-h-[320px]">
        {visible.map((attr: any) => (
          <div
            key={attr.id}
            className={`grid grid-cols-[28px_1fr_88px_64px] items-center border-b border-[#f2f0ed] last:border-0 transition-colors ${
              attr.enabled ? "hover:bg-[#f9f7f4]" : "opacity-50 hover:bg-[#f9f7f4]"
            }`}
          >
            <div className="flex justify-center py-2 border-r border-[#f2f0ed] h-full items-center">
              <Checkbox
                checked={attr.enabled}
                onCheckedChange={(v) => onUpdateAttr(attr.id, "enabled", !!v)}
                className="rounded border-[#cfccc8] data-[state=checked]:bg-[#1e4d92] data-[state=checked]:border-[#1e4d92]"
              />
            </div>
            <span className="px-3 text-[12px] font-medium text-[#1e1e24] truncate border-r border-[#f2f0ed] py-2 h-full flex items-center">
              {attr.title}
            </span>
            <div className="flex items-center px-2 gap-1 border-r border-[#f2f0ed] h-full">
              <span className="text-[10px] font-bold text-[#b4b4bc]">$</span>
              <Input
                type="number"
                step="0.01"
                value={attr.price ?? 0}
                onChange={(e) => onUpdateAttr(attr.id, "price", parseFloat(e.target.value) || 0)}
                className="h-7 w-full p-1 text-[11px] font-mono border-[#e8e5e2] rounded-lg text-right focus-visible:ring-1 focus-visible:ring-[#1e4d92] focus-visible:ring-offset-0 bg-white"
              />
            </div>
            <div className="flex items-center px-2 gap-1 h-full">
              <ArrowUpDown className="w-3 h-3 text-[#b4b4bc] shrink-0" />
              <Input
                type="number"
                value={attr.sort_order ?? 0}
                onChange={(e) => onUpdateAttr(attr.id, "sort_order", parseInt(e.target.value) || 0)}
                className="h-7 w-full p-1 text-[11px] font-mono border-[#e8e5e2] rounded-lg text-right focus-visible:ring-1 focus-visible:ring-[#1e4d92] focus-visible:ring-offset-0 bg-white"
              />
            </div>
          </div>
        ))}
        {visible.length === 0 && (
          <div className="px-3 py-10 text-center text-[12px] text-[#888894] font-medium">
            No attributes available
          </div>
        )}
      </div>

      {/* Card Footer */}
      <div className="border-t border-[#f2f0ed] px-4 py-2.5 flex items-center justify-between bg-white">
        {hasMore ? (
          <button
            onClick={() => setShowAll((v) => !v)}
            className="text-[10px] font-black text-[#1e4d92] hover:underline flex items-center gap-1 uppercase tracking-widest"
          >
            {showAll ? (
              <><ChevronUp className="w-3 h-3" /> Show Less</>
            ) : (
              <><ChevronDown className="w-3 h-3" /> +{sortedAttrs.length - VISIBLE_LIMIT} More</>
            )}
          </button>
        ) : (
          <span />
        )}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            disabled={isDeleting}
            onClick={handleDeleteCard}
            className="h-7 px-2.5 text-[#b4b4bc] hover:text-red-500 hover:bg-red-50 text-[10px] font-bold rounded-lg"
          >
            <Trash2 className="w-3 h-3" />
          </Button>
          <Button
            size="sm"
            disabled={isSaving}
            onClick={handleSaveCard}
            className="h-7 px-3 bg-[#1e4d92] hover:bg-[#173d74] text-white text-[10px] font-black uppercase tracking-widest rounded-lg"
          >
            <Save className="w-3 h-3 mr-1" />
            {isSaving ? "…" : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────

export default function ProductOptionsPage() {
  const router = useRouter();
  const [options, setOptions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [tag, setTag] = useState("all");
  const [savingAll, setSavingAll] = useState(false);
  const [customerId, setCustomerId] = useState<string>("");
  const [productId, setProductId] = useState<string>("");
  const [customers, setCustomers] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [productsList, setProductsList] = useState<any[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [supplierId, setSupplierId] = useState<string>("all");

  const fetchOptions = async (pid: string) => {
    try {
      const data = await api<any>(`/api/products/${pid}`);
      setOptions(data.options || []);
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const [c, s] = await Promise.all([
          api<any[]>("/api/customers"),
          api<any[]>("/api/suppliers"),
        ]);
        setCustomers(c);
        setSuppliers(s);
      } catch (e: any) {
        toast.error(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!customerId || customers.length === 0 || suppliers.length === 0) return;
    setProductsList([]);
    setProductsLoading(true);
    (async () => {
      try {
        const params = new URLSearchParams({ limit: "500" });
        if (supplierId && supplierId !== "all") {
          params.set("supplier_id", supplierId);
        } else {
          params.set("customer_id", customerId);
        }
        const p = await api<any[]>(`/api/products?${params.toString()}`);
        setProductsList(p);
      } catch (e: any) {
        log.error("Failed to fetch products", e);
        toast.error(e.message);
      } finally {
        setProductsLoading(false);
      }
    })();
  }, [customerId, supplierId, customers, suppliers]);

  useEffect(() => {
    if (!productId || !customerId) {
      setOptions([]);
      return;
    }
    fetchOptions(productId);
  }, [productId, customerId]);

  const selectedProduct = productsList.find((p) => p.id === productId);
  const selectedCustomer = customers.find((c) => c.id === customerId);

  const filteredOptions = useMemo(() => {
    let result = options;

    if (selectedProduct) {
      const pName = (selectedProduct.product_name || "").toLowerCase();
      const pType = (selectedProduct.product_type || "").toLowerCase();
      const isApparel =
        pName.includes("shirt") ||
        pName.includes("tee") ||
        pName.includes("hoodie") ||
        pName.includes("toddler") ||
        pName.includes("infant") ||
        pType.includes("apparel") ||
        (selectedProduct.supplier_name || "").toLowerCase().includes("sanmar");

      if (isApparel) {
        const signageKeywords = ["laminate", "substrate", "ink", "finish", "packaging", "binding", "paper"];
        result = result.filter((o) => {
          const t = (o.title || o.option_key || "").toLowerCase();
          return !signageKeywords.some((kw) => t.includes(kw));
        });
      }
    }

    if (!search.trim() && tag === "all") return result;
    return result
      .map((opt) => {
        const filteredAttrs = opt.attributes.filter((a: any) =>
          a.title.toLowerCase().includes(search.toLowerCase())
        );
        if (search.trim() && filteredAttrs.length === 0) return null;
        return { ...opt, attributes: search.trim() ? filteredAttrs : opt.attributes };
      })
      .filter(Boolean);
  }, [options, search, tag, selectedProduct]);

  const updateAttr = (optionKey: string, attrId: string, field: string, value: any) => {
    setOptions((prev) =>
      prev.map((o) =>
        o.option_key === optionKey
          ? {
              ...o,
              attributes: o.attributes.map((a: any) =>
                a.id === attrId ? { ...a, [field]: value } : a
              ),
            }
          : o
      )
    );
  };

  const toggleOption = (optionKey: string, enabled: boolean) => {
    setOptions((prev) =>
      prev.map((o) => (o.option_key === optionKey ? { ...o, enabled } : o))
    );
  };

  const handleSaveAll = async () => {
    if (!productId) return;
    setSavingAll(true);
    try {
      await api(`/api/products/${productId}/options/bulk-save`, {
        method: "POST",
        body: JSON.stringify(options),
      });
      toast.success("All options saved");
      fetchOptions(productId);
    } catch (e: any) {
      toast.error(`Save All failed: ${e.message}`);
    } finally {
      setSavingAll(false);
    }
  };

  // Derived stats
  const totalOptions = filteredOptions.length;
  const enabledOptions = filteredOptions.filter((o: any) => o.enabled).length;
  const totalAttrs = filteredOptions.reduce((acc: number, o: any) => acc + o.attributes.length, 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh] flex-col gap-4">
        <div className="w-10 h-10 border-[3px] border-[#1e4d92] border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-[#888894] font-medium animate-pulse">Loading configuration…</p>
      </div>
    );
  }

  return (
    <div id="s-product-setup">
      {/* Page Header */}
      <div className="flex items-end justify-between mb-10 pb-5 border-b-2 border-[#1e1e24]">
        <div>
          <div className="text-[32px] font-extrabold tracking-[-0.04em] leading-none text-[#1e1e24]">
            Product Options
          </div>
          <div className="text-[13px] text-[#888894] mt-2 font-normal">
            Configure decoration options, pricing tiers, and attribute visibility per storefront.
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            onClick={() => router.back()}
            className="h-9 px-4 text-[#888894] text-[12px] font-semibold border border-[#cfccc8] hover:border-[#1e4d92] hover:text-[#1e4d92] rounded-full"
          >
            <ChevronLeft className="w-3.5 h-3.5 mr-1" />
            Back
          </Button>
          {productId && (
            <>
              <Button
                variant="ghost"
                onClick={() => toast.info("Duplication logic is pending backend implementation.")}
                className="h-9 px-4 text-[#888894] text-[12px] font-semibold border border-[#cfccc8] hover:border-[#1e4d92] hover:text-[#1e4d92] rounded-full"
              >
                <Copy className="w-3.5 h-3.5 mr-1.5" />
                Duplicate
              </Button>
              <Button
                onClick={handleSaveAll}
                disabled={savingAll}
                className="h-9 px-6 bg-[#1e4d92] hover:bg-[#173d74] text-white text-[12px] font-bold rounded-full shadow-lg shadow-blue-900/10"
              >
                <Save className="w-3.5 h-3.5 mr-1.5" />
                {savingAll ? "Saving…" : "Save All"}
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Selector Panel */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        {/* Storefront picker */}
        <div className="bg-white border border-[#cfccc8] rounded-2xl p-4 space-y-2">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-lg bg-[#f9f7f4] border border-[#cfccc8] flex items-center justify-center">
              <Store className="w-3.5 h-3.5 text-[#1e4d92]" />
            </div>
            <span className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Storefront</span>
          </div>
          <Select value={customerId} onValueChange={(v) => { setCustomerId(v); setProductId(""); }}>
            <SelectTrigger className="h-10 border-[#cfccc8] rounded-xl text-[13px] font-semibold text-[#1e1e24] focus:ring-[#1e4d92] focus:ring-1 focus:ring-offset-0">
              <SelectValue placeholder="Select storefront…" />
            </SelectTrigger>
            <SelectContent className="rounded-xl border-[#cfccc8]">
              {customers.length === 0 ? (
                <div className="px-3 py-4 text-[12px] text-[#888894] text-center">No storefronts configured</div>
              ) : (
                customers.map((c) => (
                  <SelectItem key={c.id} value={c.id} className="text-[13px] font-medium">
                    {c.name}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        </div>

        {/* Supplier filter */}
        <div className="bg-white border border-[#cfccc8] rounded-2xl p-4 space-y-2">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-lg bg-[#f9f7f4] border border-[#cfccc8] flex items-center justify-center">
              <Layers className="w-3.5 h-3.5 text-[#1e4d92]" />
            </div>
            <span className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Filter by Supplier</span>
          </div>
          <Select value={supplierId} onValueChange={(v) => { setSupplierId(v); setProductId(""); }} disabled={!customerId}>
            <SelectTrigger className="h-10 border-[#cfccc8] rounded-xl text-[13px] font-semibold text-[#1e1e24] focus:ring-[#1e4d92] focus:ring-1 focus:ring-offset-0 disabled:opacity-40">
              <SelectValue placeholder="All Suppliers" />
            </SelectTrigger>
            <SelectContent className="rounded-xl border-[#cfccc8]">
              <SelectItem value="all" className="text-[13px]">All Suppliers</SelectItem>
              {suppliers.map((s) => (
                <SelectItem key={s.id} value={s.id} className="text-[13px] font-medium">
                  {s.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Product picker */}
        <div className="bg-white border border-[#cfccc8] rounded-2xl p-4 space-y-2">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-lg bg-[#f9f7f4] border border-[#cfccc8] flex items-center justify-center">
              <Package className="w-3.5 h-3.5 text-[#1e4d92]" />
            </div>
            <span className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Catalog Item</span>
          </div>
          <Select value={productId} onValueChange={setProductId} disabled={!customerId || productsLoading}>
            <SelectTrigger className="h-10 border-[#cfccc8] rounded-xl text-[13px] font-semibold text-[#1e1e24] focus:ring-[#1e4d92] focus:ring-1 focus:ring-offset-0 disabled:opacity-40">
              <SelectValue placeholder={productsLoading ? "Loading…" : customerId ? "Select product…" : "Select storefront first"} />
            </SelectTrigger>
            <SelectContent className="rounded-xl border-[#cfccc8]">
              {productsList.length === 0 ? (
                <div className="px-3 py-4 text-[12px] text-[#888894] text-center">No products found</div>
              ) : (
                productsList.map((p) => (
                  <SelectItem key={p.id} value={p.id} className="text-[13px] font-medium">
                    {p.product_name}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Content area */}
      {!productId ? (
        /* Empty state */
        <div className="py-24 text-center border-2 border-dashed border-[#f2f0ed] rounded-3xl bg-[#fcfbf9]">
          <div className="w-16 h-16 rounded-2xl bg-white border border-[#cfccc8] flex items-center justify-center text-3xl mx-auto mb-6 shadow-sm">
            <Settings2 className="w-7 h-7 text-[#1e4d92]" />
          </div>
          <div className="text-[15px] font-black text-[#1e1e24] tracking-tight mb-2">
            {!customerId ? "Start by selecting a storefront" : "Now choose a product"}
          </div>
          <p className="text-[13px] text-[#888894] max-w-sm mx-auto font-normal leading-relaxed">
            {!customerId
              ? "Pick a storefront above, then filter by supplier and select a catalog item to configure its decoration options."
              : "Select a catalog item from the dropdown above to view and configure its decoration options, pricing overrides, and attribute visibility."}
          </p>

          {/* Step indicators */}
          <div className="flex items-center justify-center gap-3 mt-8">
            {[
              { label: "Storefront", done: !!customerId },
              { label: "Supplier", done: supplierId !== "all" },
              { label: "Product", done: !!productId },
            ].map((step, i) => (
              <React.Fragment key={step.label}>
                {i > 0 && <div className="w-8 h-px bg-[#cfccc8]" />}
                <div className="flex items-center gap-1.5">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-black border transition-all ${
                    step.done
                      ? "bg-[#1e4d92] border-[#1e4d92] text-white"
                      : "bg-white border-[#cfccc8] text-[#888894]"
                  }`}>
                    {step.done ? <CheckCircle2 className="w-3 h-3" /> : i + 1}
                  </div>
                  <span className={`text-[11px] font-bold uppercase tracking-widest ${step.done ? "text-[#1e4d92]" : "text-[#888894]"}`}>
                    {step.label}
                  </span>
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      ) : (
        <>
          {/* Stats bar */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-[#1e4d92]" />
                <span className="text-[13px] font-black text-[#1e1e24]">{selectedProduct?.product_name}</span>
                {selectedCustomer && (
                  <span className="text-[11px] text-[#888894] font-medium">→ {selectedCustomer.name}</span>
                )}
              </div>
              <div className="flex items-center gap-4 pl-4 border-l border-[#f2f0ed]">
                <div className="text-center">
                  <div className="text-[18px] font-black text-[#1e1e24] leading-none">{enabledOptions}</div>
                  <div className="text-[9px] text-[#888894] font-black uppercase tracking-widest mt-0.5">Active</div>
                </div>
                <div className="text-center">
                  <div className="text-[18px] font-black text-[#1e1e24] leading-none">{totalOptions}</div>
                  <div className="text-[9px] text-[#888894] font-black uppercase tracking-widest mt-0.5">Options</div>
                </div>
                <div className="text-center">
                  <div className="text-[18px] font-black text-[#1e1e24] leading-none">{totalAttrs}</div>
                  <div className="text-[9px] text-[#888894] font-black uppercase tracking-widest mt-0.5">Attributes</div>
                </div>
              </div>
            </div>

            {/* Search / filter row */}
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#b4b4bc] pointer-events-none" />
                <Input
                  placeholder="Search attributes…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="h-9 pl-9 w-52 border-[#cfccc8] rounded-full text-[12px] font-medium text-[#1e1e24] placeholder:text-[#b4b4bc] outline-none focus-visible:ring-1 focus-visible:ring-[#1e4d92] focus-visible:ring-offset-0 bg-white"
                />
              </div>
              <Select value={tag} onValueChange={setTag}>
                <SelectTrigger className="h-9 w-36 border-[#cfccc8] rounded-full text-[12px] text-[#484852] bg-white focus:ring-[#1e4d92] focus:ring-1 focus:ring-offset-0">
                  <SelectValue placeholder="All Tags" />
                </SelectTrigger>
                <SelectContent className="rounded-xl border-[#cfccc8]">
                  <SelectItem value="all">All Tags</SelectItem>
                  <SelectItem value="ink">Ink</SelectItem>
                  <SelectItem value="material">Material</SelectItem>
                  <SelectItem value="finish">Finish</SelectItem>
                </SelectContent>
              </Select>
              {(search || tag !== "all") && (
                <button
                  onClick={() => { setSearch(""); setTag("all"); }}
                  className="text-[11px] text-[#888894] hover:text-[#1e4d92] font-semibold underline"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Options grid or empty */}
          {filteredOptions.length === 0 ? (
            <div className="py-20 text-center border-2 border-dashed border-[#f2f0ed] rounded-3xl bg-[#fcfbf9]">
              <div className="text-[14px] font-bold text-[#1e1e24]">No option groups found</div>
              <p className="text-[12px] text-[#888894] mt-1">
                {search ? "Try a different search term." : "No options are configured for this product yet."}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredOptions.map((opt: any) => (
                <OptionCard
                  key={opt.id}
                  productId={productId}
                  option={opt}
                  onUpdateAttr={(attrId, field, value) =>
                    updateAttr(opt.option_key, attrId, field, value)
                  }
                  onToggle={(enabled) => toggleOption(opt.option_key, enabled)}
                  onRefresh={() => fetchOptions(productId)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
