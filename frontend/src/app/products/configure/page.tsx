"use client";

import { useState, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CategoryAssign } from "@/components/products/category-assign";
import { OptionsMapping } from "@/components/products/options-mapping";
import { PricingPreview } from "@/components/products/pricing-preview";
import { Separator } from "@/components/ui/separator";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { Loader2, Settings2, ShoppingBag, Truck } from "lucide-react";

export default function ConfigureProductsPage() {
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [selectedSupplierId, setSelectedSupplierId] = useState("");
  const [customers, setCustomers] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [isInitialLoading, setIsInitialLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      try {
        const [custRes, suppRes] = await Promise.all([
          fetch("http://localhost:8000/api/customers"),
          fetch("http://localhost:8000/api/suppliers")
        ]);
        
        const custData = await custRes.json();
        const suppData = await suppRes.json();
        
        setCustomers(Array.isArray(custData) ? custData : []);
        setSuppliers(Array.isArray(suppData) ? suppData : []);
        
        if (custData.length > 0) setSelectedCustomerId(custData[0].id);
        if (suppData.length > 0) setSelectedSupplierId(suppData[0].id);
      } catch (err) {
        console.error("Initialization failed", err);
      } finally {
        setIsInitialLoading(false);
      }
    };
    init();
  }, []);

  if (isInitialLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="container py-8 max-w-6xl animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col gap-6">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold tracking-tight">Storefront Product Setup</h1>
            <p className="text-sm text-muted-foreground flex items-center">
              <Settings2 className="mr-2 h-4 w-4" /> 
              Map warehouse data to OnPrintShop storefront configurations
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex flex-col">
              <span className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Target Storefront</span>
              <Select value={selectedCustomerId} onValueChange={setSelectedCustomerId}>
                <SelectTrigger className="w-[200px] h-9 bg-background">
                  <ShoppingBag className="mr-2 h-3 w-3" />
                  <SelectValue placeholder="Select Storefront" />
                </SelectTrigger>
                <SelectContent>
                  {customers.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col">
              <span className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Source Supplier</span>
              <Select value={selectedSupplierId} onValueChange={setSelectedSupplierId}>
                <SelectTrigger className="w-[180px] h-9 bg-background">
                  <Truck className="mr-2 h-3 w-3" />
                  <SelectValue placeholder="Select Supplier" />
                </SelectTrigger>
                <SelectContent>
                  {suppliers.map(s => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <Separator />

        {/* Tabbed Content Section */}
        <Tabs defaultValue="categories" className="w-full">
          <TabsList className="bg-muted/50 border mb-4">
            <TabsTrigger value="categories" className="px-6">Categories</TabsTrigger>
            <TabsTrigger value="options" className="px-6">Options</TabsTrigger>
            <TabsTrigger value="pricing" className="px-6">Pricing Logic</TabsTrigger>
          </TabsList>

          <div className="mt-6 min-h-[600px] overflow-visible">
            <TabsContent value="categories" className="border-none p-0 outline-none overflow-visible">
              <CategoryAssign customerId={selectedCustomerId} supplierId={selectedSupplierId} />
            </TabsContent>
            
            <TabsContent value="options" className="border-none p-0 outline-none overflow-visible">
              <OptionsMapping customerId={selectedCustomerId} supplierId={selectedSupplierId} />
            </TabsContent>
            
            <TabsContent value="pricing" className="border-none p-0 outline-none overflow-visible">
              <PricingPreview customerId={selectedCustomerId} supplierId={selectedSupplierId} />
            </TabsContent>
          </div>
        </Tabs>
      </div>

      <footer className="mt-12 py-6 border-t border-dashed text-center">
        <p className="text-[11px] text-muted-foreground font-mono uppercase tracking-widest opacity-50">
          V1.0-BETA // API PERSISTENCE VERIFIED
        </p>
      </footer>
    </div>
  );
}
