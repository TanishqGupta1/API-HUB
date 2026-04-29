"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  ChevronLeft,
  Settings,
  Star,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import { OptionCard } from "@/components/options/option-card";

export default function ProductOptionsPage() {
  const router = useRouter();
  const { id } = useParams();
  const [options, setOptions] = useState<any[]>([]);
  const [product, setProduct] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchOptions = async () => {
    try {
      const data = await api<any>(`/api/products/${id}`);
      setProduct(data);
      setOptions(data.options || []);
    } catch (e: any) {
      log.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOptions();
  }, [id]);

  const updateAttr = (optionId: string, attrId: string, field: string, value: any) => {
    setOptions((prev) =>
      prev.map((o) =>
        o.id === optionId
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

  const toggleOption = (optionId: string, enabled: boolean) => {
    setOptions((prev) =>
      prev.map((o) => (o.id === optionId ? { ...o, enabled } : o))
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#f8fafc] flex items-center justify-center">
        <div className="text-[#475569] font-bold text-sm animate-pulse uppercase tracking-widest">Loading Options…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f8fafc] p-4 md:p-6 lg:p-8">
      <div className="max-w-[1400px] mx-auto bg-white border border-[#e2e8f0] shadow-md">
        {/* Top Header */}
        <div className="border-b border-[#e2e8f0] px-5 py-4 flex items-center justify-between bg-white">
          <div className="flex items-center gap-3 text-[16px] font-bold text-[#2563eb]">
            <span className="uppercase tracking-tight">Configure Options</span>
            <span className="text-[#94a3b8]">»</span>
            <span className="text-[#1e293b]">{product?.product_name}</span>
            <Settings className="w-5 h-5 text-[#64748b]" />
            <Star className="w-5 h-5 text-[#f59e0b] fill-[#f59e0b]" />
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              className="h-9 px-4 border-[#cbd5e1] bg-white text-[#475569] text-[12px] font-black uppercase tracking-widest rounded-none hover:bg-[#f1f5f9] shadow-sm"
              onClick={() => router.back()}
            >
              <ChevronLeft className="w-4 h-4 mr-1" />
              Back to Product
            </Button>
            <Button
              className="h-9 px-4 bg-[#1e4d92] text-white text-[12px] font-black uppercase tracking-widest rounded-none shadow-sm"
              onClick={() => log.info("Custom options pending implementation")}
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Add Custom Option
            </Button>
          </div>
        </div>

        {/* Options grid */}
        <div className="p-8 bg-[#f8fafc]">
          {options.length === 0 ? (
            <div className="py-32 text-center border-2 border-dashed border-[#cbd5e1] rounded-xl bg-white/50">
              <div className="text-[#94a3b8] font-bold text-sm uppercase tracking-widest">
                No options found for this product.
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {options.map((opt) => (
                <OptionCard
                  key={opt.id}
                  productId={id as string}
                  option={opt}
                  onUpdateAttr={(attrId, field, value) =>
                    updateAttr(opt.id, attrId, field, value)
                  }
                  onToggle={(enabled) => toggleOption(opt.id, enabled)}
                  onRefresh={fetchOptions}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
