"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  ChevronLeft,
  Copy,
  Star,
  Settings,
  GripVertical,
  ArrowUpDown,
  Trash2,
  Save,
  CheckCircle2,
  Filter,
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
import { toast } from "sonner";
import { api } from "@/lib/api";

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
    () => [...option.attributes].sort((a, b) => a.sort_order - b.sort_order),
    [option.attributes]
  );

  const visible = showAll ? sortedAttrs : sortedAttrs.slice(0, VISIBLE_LIMIT);
  const hasMore = sortedAttrs.length > VISIBLE_LIMIT;

  const handleSaveCard = async () => {
    setIsSaving(true);
    try {
      // Save individual option state
      await api(`/api/products/${productId}/options/${option.id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: option.enabled }),
      });

      // Save each attribute (concurrently)
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
      toast.success("Saved successfully");
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
      toast.success("Deleted successfully");
      onRefresh();
    } catch (e: any) {
      toast.error(`Delete failed: ${e.message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="bg-white border border-[#e2e8f0] flex flex-col shadow-sm">
      {/* Header */}
      <div className="bg-[#dbeafe] border-b border-[#bfdbfe] px-3 py-2 flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <GripVertical className="w-4 h-4 text-[#64748b] shrink-0 cursor-grab" />
          <span className="text-[13px] font-bold text-[#1e40af] truncate uppercase tracking-tight">
            {option.title}
          </span>
        </div>
        <Switch
          checked={option.enabled}
          onCheckedChange={onToggle}
          className="data-[state=checked]:bg-[#22c55e] data-[state=unchecked]:bg-[#cbd5e1]"
        />
      </div>

      {/* Attribute rows */}
      <div className="flex-1 overflow-y-auto min-h-[220px] max-h-[350px] custom-scrollbar">
        {visible.map((attr: any) => (
          <div 
            key={attr.id} 
            className="grid grid-cols-[32px_1fr_90px_70px] items-center gap-0 border-b border-[#f1f5f9] last:border-0 hover:bg-[#f8fafc] transition-colors"
          >
            <div className="flex justify-center py-2 border-r border-[#f1f5f9] h-full items-center">
              <Checkbox
                checked={attr.enabled}
                onCheckedChange={(v) => onUpdateAttr(attr.id, "enabled", !!v)}
                className="rounded-none border-[#94a3b8] data-[state=checked]:bg-[#3b82f6] data-[state=checked]:border-[#3b82f6]"
              />
            </div>
            <span className="px-3 text-[12px] font-medium text-[#334155] truncate border-r border-[#f1f5f9] py-2 h-full flex items-center">
              {attr.title}
            </span>
            <div className="flex items-center px-2 gap-1 border-r border-[#f1f5f9] h-full">
              <span className="text-[10px] font-bold text-[#94a3b8]">$</span>
              <Input
                type="number"
                step="0.01"
                value={attr.price ?? 0}
                onChange={(e) => onUpdateAttr(attr.id, "price", parseFloat(e.target.value) || 0)}
                className="h-7 w-full p-1 text-[11px] font-mono border-[#cbd5e1] rounded-none text-right focus-visible:ring-1 focus-visible:ring-[#3b82f6] focus-visible:ring-offset-0 bg-white"
              />
            </div>
            <div className="flex items-center px-2 gap-1 h-full">
              <ArrowUpDown className="w-3 h-3 text-[#94a3b8] shrink-0" />
              <Input
                type="number"
                value={attr.sort_order ?? 0}
                onChange={(e) => onUpdateAttr(attr.id, "sort_order", parseInt(e.target.value) || 0)}
                className="h-7 w-full p-1 text-[11px] font-mono border-[#cbd5e1] rounded-none text-right focus-visible:ring-1 focus-visible:ring-[#3b82f6] focus-visible:ring-offset-0 bg-white"
              />
            </div>
          </div>
        ))}
        {visible.length === 0 && (
          <div className="px-3 py-12 text-center text-[12px] text-[#94a3b8] font-medium">
            No attributes available
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-[#e2e8f0] px-3 py-2 flex items-center justify-between bg-white">
        {hasMore ? (
          <button
            onClick={() => setShowAll((v) => !v)}
            className="text-[11px] font-bold text-[#2563eb] hover:underline flex items-center gap-1 uppercase tracking-tight"
          >
            {showAll ? "Show Less" : "Show More"}
          </button>
        ) : (
          <span />
        )}
        <div className="flex items-center gap-2">
          <Button
            variant="default"
            disabled={isSaving}
            onClick={handleSaveCard}
            className="h-8 px-3 bg-[#3b82f6] hover:bg-[#2563eb] text-white text-[11px] font-bold rounded-none"
          >
            <Save className="w-3.5 h-3.5 mr-1.5" />
            {isSaving ? "..." : "Save"}
          </Button>
          <Button
            variant="outline"
            disabled={isDeleting}
            onClick={handleDeleteCard}
            className="h-8 px-3 border-[#fecaca] bg-white text-[#ef4444] hover:bg-[#fef2f2] text-[11px] font-bold rounded-none"
          >
            <Trash2 className="w-3.5 h-3.5 mr-1.5" />
            {isDeleting ? "..." : "Delete"}
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
  const [productsList, setProductsList] = useState<any[]>([]);

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
        const [c, p] = await Promise.all([
          api<any[]>("/api/customers"),
          api<any[]>("/api/products?limit=200"),
        ]);
        setCustomers(c);
        setProductsList(p);
      } catch (e: any) {
        toast.error(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!productId || !customerId) {
      setOptions([]);
      return;
    }
    fetchOptions(productId);
  }, [productId, customerId]);

  const filteredOptions = useMemo(() => {
    if (!search.trim() && tag === "all") return options;
    return options
      .map((opt) => {
        const filteredAttrs = opt.attributes.filter((a: any) =>
          a.title.toLowerCase().includes(search.toLowerCase())
        );
        if (search.trim() && filteredAttrs.length === 0) return null;
        return { ...opt, attributes: search.trim() ? filteredAttrs : opt.attributes };
      })
      .filter(Boolean);
  }, [options, search, tag]);

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
      // Send the entire options tree for bulk save
      await api(`/api/products/${productId}/options/bulk-save`, {
        method: "POST",
        body: JSON.stringify(options),
      });
      toast.success("Saved successfully");
      fetchOptions(productId);
    } catch (e: any) {
      toast.error(`Save All failed: ${e.message}`);
    } finally {
      setSavingAll(false);
    }
  };

  const handleReset = () => {
    setSearch("");
    setTag("all");
    if (productId) fetchOptions(productId);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#f8fafc] flex items-center justify-center">
        <div className="text-[#475569] font-bold text-sm animate-pulse uppercase tracking-widest">Initialising Manager…</div>
      </div>
    );
  }

  const selectedProductName = productsList.find(p => p.id === productId)?.product_name || "Select Product";

  return (
    <div className="min-h-screen bg-[#f8fafc] p-4 md:p-6 lg:p-8">
      <div className="max-w-[1600px] mx-auto bg-white border border-[#e2e8f0] shadow-md">
        {/* Top breadcrumb header */}
        <div className="border-b border-[#e2e8f0] px-5 py-3 flex items-center justify-between bg-white">
          <div className="flex items-center gap-2 text-[14px] font-bold text-[#2563eb]">
            <span className="uppercase tracking-tight">Assign Product Options</span>
            <span className="text-[#94a3b8]">»</span>
            <span className="text-[#1e293b]">{selectedProductName}</span>
            <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-[#22c55e] text-white text-[11px]">
              ✓
            </span>
            <Settings className="w-4 h-4 text-[#64748b] ml-1" />
            <Star className="w-4 h-4 text-[#f59e0b] fill-[#f59e0b] ml-1" />
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              className="h-8 px-4 bg-[#22c55e] hover:bg-[#16a34a] text-white text-[11px] font-black uppercase tracking-widest rounded-none shadow-sm"
              onClick={() => toast.info("Duplication logic is pending backend implementation.")}
            >
              <Copy className="w-3.5 h-3.5 mr-1.5" />
              Duplicate Options
            </Button>
            <Button
              variant="outline"
              className="h-8 px-4 border-[#cbd5e1] bg-white text-[#475569] text-[11px] font-black uppercase tracking-widest rounded-none hover:bg-[#f1f5f9] shadow-sm"
              onClick={() => router.back()}
            >
              <ChevronLeft className="w-3.5 h-3.5 mr-1" />
              Back
            </Button>
          </div>
        </div>

        {/* Product Selectors Integration */}
        <div className="px-5 py-4 border-b border-[#e2e8f0] bg-slate-50/30 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Storefront</span>
            <Select value={customerId} onValueChange={setCustomerId}>
              <SelectTrigger className="h-10 border-[#cbd5e1] bg-white rounded-none text-[13px] font-bold">
                <SelectValue placeholder="Select Storefront" />
              </SelectTrigger>
              <SelectContent className="rounded-none">
                {customers.map(c => (
                  <SelectItem key={c.id} value={c.id} className="font-bold">{c.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Catalog Item</span>
            <Select value={productId} onValueChange={setProductId}>
              <SelectTrigger className="h-10 border-[#cbd5e1] bg-white rounded-none text-[13px] font-bold">
                <SelectValue placeholder="Select Product" />
              </SelectTrigger>
              <SelectContent className="rounded-none">
                {productsList.map(p => (
                  <SelectItem key={p.id} value={p.id} className="font-bold">{p.product_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Toolbar */}
        <div className="px-5 py-3 border-b border-[#e2e8f0] bg-white flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px] max-w-[300px]">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-[#94a3b8]" />
            <Input
              placeholder="Filter attributes..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 pl-9 border-[#cbd5e1] rounded-none text-[13px] focus-visible:ring-1 focus-visible:ring-[#3b82f6] focus-visible:ring-offset-0 bg-white"
            />
          </div>
          <Select value={tag} onValueChange={setTag}>
            <SelectTrigger className="h-9 w-[180px] border-[#cbd5e1] rounded-none text-[13px] text-[#64748b] bg-white">
              <SelectValue placeholder="All Tags" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="all">All Tags</SelectItem>
              <SelectItem value="ink">Ink</SelectItem>
              <SelectItem value="material">Material</SelectItem>
              <SelectItem value="finish">Finish</SelectItem>
            </SelectContent>
          </Select>
          <Button
            className="h-9 px-6 bg-[#3b82f6] hover:bg-[#2563eb] text-white text-[11px] font-black uppercase tracking-widest rounded-none shadow-sm"
            onClick={() => toast.info(`Filtering view: ${search || 'all'}`)}
          >
            <Search className="w-3.5 h-3.5 mr-1.5" />
            Search
          </Button>
          <Button
            variant="ghost"
            className="h-9 px-4 text-[#64748b] text-[11px] font-black uppercase tracking-widest hover:bg-[#f1f5f9] rounded-none"
            onClick={handleReset}
          >
            Reset
          </Button>
          <div className="ml-auto">
            <Button
              onClick={handleSaveAll}
              disabled={savingAll || !productId}
              className="h-9 px-8 bg-[#3b82f6] hover:bg-[#2563eb] text-white text-[11px] font-black uppercase tracking-widest rounded-none shadow-sm"
            >
              {savingAll ? "Syncing..." : "Save All"}
            </Button>
          </div>
        </div>

        {/* Options grid */}
        <div className="p-5 bg-[#f8fafc]">
          {!productId ? (
            <div className="py-32 text-center flex flex-col items-center justify-center space-y-4">
               <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center text-slate-300">
                  <Filter className="w-8 h-8" />
               </div>
               <div className="text-slate-400 font-bold text-sm uppercase tracking-widest">Select a product to configure options</div>
            </div>
          ) : filteredOptions.length === 0 ? (
            <div className="py-20 text-center text-[#94a3b8] text-sm font-bold uppercase tracking-widest">
              No matching option patterns found.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredOptions.map((opt) => (
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
        </div>
      </div>
    </div>
  );
}
