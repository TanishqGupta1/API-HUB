"use client";

import { useState, useEffect } from "react";
import { Loader2, Palette } from "lucide-react";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface OptionsMappingProps {
  customerId: string;
  supplierId: string;
}

export function OptionsMapping({ customerId, supplierId }: OptionsMappingProps) {
  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [opsOptions, setOpsOptions] = useState<any[]>([]);
  const [variantColors, setVariantColors] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!customerId || !supplierId) return;

    const fetchData = async () => {
      setIsLoading(true);
      try {
        const optRes = await fetch(`http://localhost:8000/api/ops-config/storefront/${customerId}/options`);
        const optData = await optRes.json();
        setOpsOptions(Array.isArray(optData) ? optData : []);

        const summaryRes = await fetch(`http://localhost:8000/api/products/summary?supplier_id=${supplierId}`);
        const summaryData = await summaryRes.json();
        setVariantColors(summaryData.colors || []);

        const mapRes = await fetch(`http://localhost:8000/api/ops-config/options/${supplierId}`);
        const mapData = await mapRes.json();
        const initial = Array.isArray(mapData) 
          ? mapData.reduce((acc: any, m: any) => {
              if (m.option_type === "color") acc[m.source_value] = m.ops_attribute_id;
              return acc;
            }, {})
          : {};
        setMappings(initial);
      } catch (err) {
        console.error("Failed to fetch Options Data", err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [customerId, supplierId]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      for (const [sourceVal, opsAttrId] of Object.entries(mappings)) {
        if (!opsAttrId || opsAttrId === "none") continue;
        
        await fetch("http://localhost:8000/api/ops-config/options", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            supplier_id: supplierId,
            option_type: "color",
            source_value: sourceVal,
            ops_attribute_id: opsAttrId
          })
        });
      }
      alert("Option mappings saved successfully!");
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-dashed">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const colorGroup = opsOptions.find(o => o.name.toLowerCase() === "color");
  const colorAttributes = colorGroup?.attributes || [];

  return (
    <div className="space-y-8 py-4">
      <div className="flex items-center justify-between bg-muted/30 p-6 rounded-xl border border-border/50">
        <div className="space-y-1">
          <h3 className="text-xl font-bold tracking-tight">Color Normalization</h3>
          <p className="text-sm text-muted-foreground">Map raw supplier colors to your master storefront attributes</p>
        </div>
        <Button size="lg" onClick={handleSave} disabled={isSaving} className="shadow-sm">
          {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Sync Attributes
        </Button>
      </div>

      <div className="space-y-6 min-h-[600px] pb-24">
        {variantColors.map((color) => {
          const matchedAttr = colorAttributes.find((a: any) => a.id === mappings[color]);
          return (
            <div key={color} className="grid grid-cols-12 items-center gap-6 p-6 rounded-2xl border-2 bg-background shadow-sm hover:shadow-md transition-all">
              <div className="col-span-4 border-r pr-6">
                <div className="flex items-center gap-4">
                  <div className="h-6 w-6 rounded-full border-2 border-black/10 shadow-sm shrink-0" style={{ backgroundColor: color }} />
                  <span className="font-bold text-lg tracking-tight">{color}</span>
                </div>
              </div>
              
              <div className="col-span-3 flex justify-center">
                {matchedAttr ? (
                  <Badge variant="secondary" className="bg-blue-50 text-blue-700 border-blue-200 uppercase tracking-tighter text-[10px] font-bold px-4 py-1.5 whitespace-nowrap">
                    Mapped to {matchedAttr.name}
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-muted-foreground uppercase tracking-tighter text-[10px] bg-muted/20 px-4 py-1.5 whitespace-nowrap">
                    Manual Match Required
                  </Badge>
                )}
              </div>

              <div className="col-span-5">
                <div className="text-[10px] font-bold text-muted-foreground uppercase mb-2 ml-1">OPS Master color</div>
                <Select
                  value={mappings[color] || "none"}
                  onValueChange={(val) => setMappings({ ...mappings, [color]: val })}
                >
                  <SelectTrigger className="w-full h-12 bg-background border-2 shadow-sm text-base">
                    <SelectValue placeholder="Pick Master Color..." />
                  </SelectTrigger>
                  <SelectContent position="popper" className="z-[9999] min-w-[320px] !bg-white !opacity-100 shadow-2xl border-2 p-1">
                    <SelectItem value="none" className="text-muted-foreground italic h-12 text-base hover:!bg-muted">No Alignment</SelectItem>
                    {colorAttributes.map((attr: any) => (
                      <SelectItem key={attr.id} value={attr.id} className="h-12 text-base hover:!bg-muted cursor-pointer">
                        {attr.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
