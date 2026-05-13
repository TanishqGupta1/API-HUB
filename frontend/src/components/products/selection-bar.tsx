"use client";

import { useSelectedCustomer } from "@/lib/customer-context";
import { Button } from "@/components/ui/button";
import { X, Plus, Trash2, CheckSquare } from "lucide-react";
import { useState } from "react";

interface SelectionBarProps {
  selectedIds: string[];
  onClear: () => void;
  onSuccess: () => void;
}

export function SelectionBar({ selectedIds, onClear, onSuccess }: SelectionBarProps) {
  const { selectedCustomerId, selectedCustomerName, bulkAdd } = useSelectedCustomer();
  const [loading, setLoading] = useState(false);

  if (selectedIds.length === 0) return null;

  async function handleBulkAdd() {
    if (!selectedCustomerId || loading) return;
    setLoading(true);
    const res = await bulkAdd(selectedIds);
    setLoading(false);
    if (res.success) {
      onSuccess();
    }
  }

  return (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[100] animate-in fade-in slide-in-from-bottom-4 duration-300">
      <div className="bg-[#1e1e24] text-white px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-8 border border-white/10 backdrop-blur-md">
        
        {/* Count info */}
        <div className="flex items-center gap-3 pr-8 border-r border-white/10">
          <div className="w-8 h-8 bg-white/10 rounded-lg flex items-center justify-center">
            <CheckSquare className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-[14px] font-black leading-none">{selectedIds.length} items</div>
            <div className="text-[10px] font-bold text-white/50 uppercase tracking-widest mt-1">Selected</div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          {selectedCustomerId ? (
            <Button 
              onClick={handleBulkAdd}
              disabled={loading}
              className="bg-[#1e4d92] hover:bg-[#173d74] text-white font-bold text-xs uppercase tracking-wider h-10 px-6 rounded-xl"
            >
              {loading ? "Processing..." : `Add to ${selectedCustomerName}`}
              <Plus className="w-4 h-4 ml-2" />
            </Button>
          ) : (
            <div className="text-[11px] font-bold text-white/40 italic max-w-[140px] leading-tight">
              Pick a customer in top bar to enable bulk add
            </div>
          )}
          
          <Button 
            variant="ghost" 
            className="text-white/60 hover:text-white hover:bg-white/10 font-bold text-xs uppercase tracking-wider h-10 px-6 rounded-xl"
            onClick={onClear}
          >
            Clear
            <X className="w-4 h-4 ml-2" />
          </Button>
        </div>

      </div>
    </div>
  );
}
