"use client";

import { useState, useEffect } from "react";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";
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

interface CategoryAssignProps {
  customerId: string;
  supplierId: string;
}

export function CategoryAssign({ customerId, supplierId }: CategoryAssignProps) {
  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [opsCategories, setOpsCategories] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!customerId || !supplierId) return;

    const fetchData = async () => {
      setIsLoading(true);
      try {
        const catRes = await fetch(`http://localhost:8000/api/ops-config/storefront/${customerId}/categories`);
        const catData = await catRes.json();
        setOpsCategories(Array.isArray(catData) ? catData : []);

        const prodRes = await fetch(`http://localhost:8000/api/products?supplier_id=${supplierId}`);
        const prodData = await prodRes.json();
        setProducts(Array.isArray(prodData) ? prodData : []);

        const mapRes = await fetch(`http://localhost:8000/api/ops-config/categories/${supplierId}`);
        const mapData = await mapRes.json();
        const initialMappings = Array.isArray(mapData) 
          ? mapData.reduce((acc: any, m: any) => {
              acc[m.source_category] = m.ops_category_id;
              return acc;
            }, {})
          : {};
        setMappings(initialMappings);
      } catch (err) {
        console.error("Failed to fetch Category Data", err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [customerId, supplierId]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      for (const [sourceCat, opsId] of Object.entries(mappings)) {
        if (!opsId || opsId === "none") continue;
        
        await fetch("http://localhost:8000/api/ops-config/categories", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            supplier_id: supplierId,
            source_category: sourceCat,
            ops_category_id: opsId
          })
        });
      }
      alert("Categories synchronized successful!");
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

  const uniqueSourceCategories = Array.from(new Set(products.map(p => p.category || "Uncategorized")));

  return (
    <div className="space-y-8 py-4">
      <div className="flex items-center justify-between bg-muted/30 p-6 rounded-xl border border-border/50">
        <div className="space-y-1">
          <h3 className="text-xl font-bold tracking-tight">Category Mapping</h3>
          <p className="text-sm text-muted-foreground">Link supplier data to your OnPrintShop storefront categories</p>
        </div>
        <Button size="lg" onClick={handleSave} disabled={isSaving} className="shadow-sm">
          {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save Mappings
        </Button>
      </div>

      <div className="space-y-6 min-h-[600px] pb-24">
        {uniqueSourceCategories.map((catName) => {
          const hasMapping = mappings[catName] && mappings[catName] !== "none";
          return (
            <div key={catName} className="grid grid-cols-12 items-center gap-6 p-6 rounded-2xl border-2 bg-background shadow-sm hover:shadow-md transition-all">
              <div className="col-span-4 border-r pr-6">
                <div className="font-bold text-lg tracking-tight">{catName}</div>
                <div className="text-[11px] text-muted-foreground font-mono mt-1 uppercase tracking-wider">
                  {products.filter(p => (p.category || "Uncategorized") === catName).length} Warehouse Products
                </div>
              </div>
              
              <div className="col-span-3 flex justify-center">
                {hasMapping ? (
                  <Badge variant="secondary" className="bg-emerald-50 text-emerald-700 border-emerald-200 px-4 py-1.5 text-xs font-bold uppercase whitespace-nowrap">
                    <CheckCircle2 className="mr-2 h-4 w-4" /> Fully Aligned
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-muted-foreground bg-muted/20 px-4 py-1.5 text-xs font-bold uppercase whitespace-nowrap">
                    <AlertCircle className="mr-2 h-4 w-4" /> Missing Link
                  </Badge>
                )}
              </div>

              <div className="col-span-5">
                <div className="text-[10px] font-bold text-muted-foreground uppercase mb-2 ml-1">OnPrintShop Destination</div>
                <Select
                  value={mappings[catName] || "none"}
                  onValueChange={(val) => setMappings({ ...mappings, [catName]: val })}
                >
                  <SelectTrigger className="w-full h-12 bg-background border-2 shadow-sm text-base">
                    <SelectValue placeholder="Select OPS Category..." />
                  </SelectTrigger>
                  <SelectContent position="popper" className="z-[9999] min-w-[320px] !bg-white !opacity-100 shadow-2xl border-2 p-1">
                    <SelectItem value="none" className="text-muted-foreground italic h-12 text-base hover:!bg-muted">Unassigned (Skip Sync)</SelectItem>
                    {opsCategories.map((opsCat) => (
                      <SelectItem key={opsCat.id} value={opsCat.id} className="h-12 text-base hover:!bg-muted cursor-pointer">
                        {opsCat.name}
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
