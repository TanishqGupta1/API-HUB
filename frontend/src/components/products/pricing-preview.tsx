"use client";

import { useState } from "react";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Info, Calculator, DollarSign, ArrowRight } from "lucide-react";
import { Separator } from "@/components/ui/separator";

const STUB_PRODUCTS = [
  { id: "p1", name: "Port & Company Essential Tee", basePrice: 3.79, category: "Apparel" },
  { id: "p2", name: "Port Authority Silk Touch Polo", basePrice: 12.50, category: "Apparel" },
  { id: "p3", name: "Alternative Eco-Jersey Crew", basePrice: 8.95, category: "Sustainable" },
];

interface PricingPreviewProps {
  customerId: string;
  supplierId: string;
}

export function PricingPreview({ customerId, supplierId }: PricingPreviewProps) {
  const [selectedId, setSelectedId] = useState(STUB_PRODUCTS[0].id);
  const product = STUB_PRODUCTS.find(p => p.id === selectedId)!;

  // Real pricing engine logic mocked here
  const markupMultiplier = 1.4; // 40% markup example
  const markupPrice = product.basePrice * markupMultiplier;
  
  // Cleaned up rounding logic: Always end in .99
  const finalPrice = Math.floor(markupPrice) + 0.99;

  return (
    <div className="space-y-8 py-4">
      <Card className="bg-muted/30 border-2 overflow-visible mb-32">
        <CardHeader className="pb-6 px-6">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="text-xl font-bold tracking-tight">Pricing Engine Preview</CardTitle>
              <CardDescription>Test how your markup rules affect storefront pricing</CardDescription>
            </div>
            <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 uppercase text-[10px] font-bold px-3 py-1 whitespace-nowrap">
              Standard Apparel Rule (40%)
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="px-6 pb-20 min-h-[120px]">
          <div className="flex flex-col md:flex-row items-end gap-6">
            <div className="flex-1 w-full space-y-3">
              <label className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Select Product for Preview</label>
              <Select value={selectedId} onValueChange={setSelectedId}>
                <SelectTrigger className="w-full h-11 bg-background border-2 shadow-sm text-base">
                  <SelectValue placeholder="Pick a product..." />
                </SelectTrigger>
                <SelectContent position="popper" className="z-[9999] min-w-[350px] !bg-white !opacity-100 shadow-2xl border-2 p-1">
                  {STUB_PRODUCTS.map((p) => (
                    <SelectItem key={p.id} value={p.id} className="h-12 text-base hover:!bg-muted cursor-pointer">{p.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="py-4 px-6">
            <CardDescription className="flex items-center gap-2">
              <DollarSign className="h-3 w-3" /> Supplier Cost
            </CardDescription>
          </CardHeader>
          <CardContent className="px-6 pb-6 pt-0">
            <div className="text-2xl font-bold text-muted-foreground tracking-tight">
              ${product.basePrice.toFixed(2)}
            </div>
            <p className="text-[10px] text-muted-foreground mt-1 uppercase font-medium">Wholesale Baseline</p>
          </CardContent>
        </Card>

        <Card className="border-blue-100 bg-blue-50/10">
          <CardHeader className="py-4 px-6 text-blue-600">
            <CardDescription className="flex items-center gap-2 text-blue-600/70">
              <Calculator className="h-3 w-3" /> Calculated Markup
            </CardDescription>
          </CardHeader>
          <CardContent className="px-6 pb-6 pt-0">
            <div className="text-2xl font-bold text-blue-600 tracking-tight">
              ${markupPrice.toFixed(2)}
            </div>
            <p className="text-[10px] text-blue-500 mt-1 uppercase font-medium">+40% Margin Applied</p>
          </CardContent>
        </Card>

        <Card className="border-emerald-200 bg-emerald-50/30">
          <CardHeader className="py-4 px-6 text-emerald-700">
            <CardDescription className="flex items-center gap-2 text-emerald-700/70">
              <ArrowRight className="h-3 w-3" /> Storefront Price
            </CardDescription>
          </CardHeader>
          <CardContent className="px-6 pb-6 pt-0">
            <div className="text-3xl font-bold text-emerald-700 tracking-tighter">
              ${finalPrice.toFixed(2)}
            </div>
            <Badge className="mt-2 bg-emerald-600 hover:bg-emerald-600 border-none">Ready to Sync</Badge>
          </CardContent>
        </Card>
      </div>

      <div className="flex items-start gap-4 p-4 rounded-lg border border-amber-200 bg-amber-50/50">
        <Info className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="text-xs font-bold text-amber-800 uppercase tracking-wider">System Note</p>
          <p className="text-xs text-amber-700/80 leading-relaxed">
            This is a real-time preview of the OnPrintShop push pipeline. To adjust global markups, edit the 
            <span className="font-semibold mx-1">Pricing Rules</span> configuration in the sidebar.
          </p>
        </div>
      </div>
    </div>
  );
}
