"use client";

import { useMemo, useState } from "react";
import { GripVertical, ArrowUpDown, Save, Trash2 } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { log } from "@/lib/log";

const VISIBLE_LIMIT = 6;

interface OptionCardProps {
  option: any;
  productId: string;
  onUpdateAttr: (attrId: string, field: string, value: any) => void;
  onToggle: (enabled: boolean) => void;
  onRefresh: () => void;
}

export function OptionCard({
  option,
  productId,
  onUpdateAttr,
  onToggle,
  onRefresh,
}: OptionCardProps) {
  const [showAll, setShowAll] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const sortedAttrs = useMemo(
    () => [...(option.attributes || [])].sort((a, b) => a.sort_order - b.sort_order),
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
        body: JSON.stringify({ 
          enabled: option.enabled,
          sort_order: option.sort_order,
          title: option.title
        }),
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
      log.info("Saved successfully");
    } catch (e: any) {
      log.error(`Save failed: ${e.message}`);
      alert(`Save failed: ${e.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteCard = async () => {
    if (!confirm("Delete this option group entirely?")) return;
    setIsDeleting(true);
    try {
      await api(`/api/products/${productId}/options/${option.id}`, { method: "DELETE" });
      log.info("Deleted successfully");
      onRefresh();
    } catch (e: any) {
      log.error(`Delete failed: ${e.message}`);
      alert(`Delete failed: ${e.message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="bg-white border border-[#e2e8f0] flex flex-col shadow-sm">
      {/* Header */}
      <div className="bg-[#dbeafe] border-b border-[#bfdbfe] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <GripVertical className="w-4 h-4 text-[#64748b] shrink-0 cursor-grab" />
          <span className="text-[14px] font-bold text-[#1e40af] truncate uppercase tracking-tight">
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
      <div className="flex-1 overflow-y-auto min-h-[220px] max-h-[400px] custom-scrollbar">
        {visible.map((attr: any) => (
          <div 
            key={attr.id} 
            className="grid grid-cols-[40px_1fr_100px_80px] items-center gap-0 border-b border-[#f1f5f9] last:border-0 hover:bg-[#f8fafc] transition-colors"
          >
            <div className="flex justify-center py-2.5 border-r border-[#f1f5f9] h-full items-center">
              <Checkbox
                checked={attr.enabled}
                onCheckedChange={(v) => onUpdateAttr(attr.id, "enabled", !!v)}
                className="rounded-none border-[#94a3b8] data-[state=checked]:bg-[#3b82f6] data-[state=checked]:border-[#3b82f6]"
              />
            </div>
            <span className="px-4 text-[13px] font-medium text-[#334155] truncate border-r border-[#f1f5f9] py-2.5 h-full flex items-center">
              {attr.title}
            </span>
            <div className="flex items-center px-3 gap-1.5 border-r border-[#f1f5f9] h-full bg-[#fcfcfc]">
              <span className="text-[11px] font-bold text-[#94a3b8]">$</span>
              <Input
                type="number"
                step="0.01"
                value={attr.price ?? 0}
                onChange={(e) => onUpdateAttr(attr.id, "price", parseFloat(e.target.value) || 0)}
                className="h-7 w-full p-1.5 text-[12px] font-mono border-[#cbd5e1] rounded-none text-right focus-visible:ring-1 focus-visible:ring-[#3b82f6] focus-visible:ring-offset-0 bg-white"
              />
            </div>
            <div className="flex items-center px-3 gap-1.5 h-full">
              <ArrowUpDown className="w-3.5 h-3.5 text-[#94a3b8] shrink-0" />
              <Input
                type="number"
                value={attr.sort_order ?? 0}
                onChange={(e) => onUpdateAttr(attr.id, "sort_order", parseInt(e.target.value) || 0)}
                className="h-7 w-full p-1.5 text-[12px] font-mono border-[#cbd5e1] rounded-none text-right focus-visible:ring-1 focus-visible:ring-[#3b82f6] focus-visible:ring-offset-0 bg-white"
              />
            </div>
          </div>
        ))}
        {visible.length === 0 && (
          <div className="px-4 py-16 text-center text-[13px] text-[#94a3b8] font-medium italic">
            No attributes defined
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-[#e2e8f0] px-4 py-3 flex items-center justify-between bg-slate-50">
        {hasMore ? (
          <button
            onClick={() => setShowAll((v) => !v)}
            className="text-[11px] font-black text-[#2563eb] hover:underline flex items-center gap-1 uppercase tracking-widest"
          >
            {showAll ? "Show Less" : `Show ${sortedAttrs.length - VISIBLE_LIMIT} More`}
          </button>
        ) : (
          <div />
        )}
        <div className="flex items-center gap-3">
          <Button
            variant="default"
            disabled={isSaving}
            onClick={handleSaveCard}
            className="h-9 px-4 bg-[#3b82f6] hover:bg-[#2563eb] text-white text-[12px] font-bold rounded-none shadow-sm"
          >
            <Save className="w-4 h-4 mr-2" />
            {isSaving ? "..." : "Save"}
          </Button>
          <Button
            variant="outline"
            disabled={isDeleting}
            onClick={handleDeleteCard}
            className="h-9 px-4 border-[#fecaca] bg-white text-[#ef4444] hover:bg-[#fef2f2] text-[12px] font-bold rounded-none shadow-sm"
          >
            <Trash2 className="w-4 h-4 mr-2" />
            {isDeleting ? "..." : "Delete"}
          </Button>
        </div>
      </div>
    </div>
  );
}
