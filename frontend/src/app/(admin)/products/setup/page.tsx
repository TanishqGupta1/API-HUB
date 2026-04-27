"use client";

import { 
  useEffect, 
  useState, 
  useMemo 
} from "react";
import { api } from "@/lib/api";
import type { 
  Product, 
  Customer, 
  MasterOption 
} from "@/lib/types";
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
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle,
  DialogFooter,
  DialogDescription
} from "@/components/ui/dialog";
import { X, Settings2, Link2, Info, Layers, Activity } from "lucide-react";

export default function ProductSetupPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [masterOptions, setMasterOptions] = useState<MasterOption[]>([]);
  
  const [customerId, setCustomerId] = useState("");
  const [productId, setProductId] = useState("");
  const [productSearch, setProductSearch] = useState("");
  
  const [fullProduct, setFullProduct] = useState<Product | null>(null);
  const [config, setConfig] = useState<any>(null);
  
  const [loading, setLoading] = useState(true);
  const [mappingOpen, setMappingOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [c, p, mo] = await Promise.all([
          api<Customer[]>("/api/customers"),
          api<Product[]>("/api/products?limit=200"),
          api<MasterOption[]>("/api/master-options"),
        ]);
        setCustomers(c);
        setProducts(p);
        setMasterOptions(mo);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!productId || !customerId) {
      setFullProduct(null);
      setConfig(null);
      return;
    }

    (async () => {
      try {
        const [p, conf] = await Promise.all([
          api<Product>(`/api/products/${productId}`),
          api<any>(`/api/ops-config/${customerId}/product/${productId}`),
        ]);
        setFullProduct(p);
        setConfig(conf);
      } catch (e) {
        console.error("Failed to load product config", e);
      }
    })();
  }, [productId, customerId]);

  const filteredProducts = useMemo(() => {
    if (!productSearch.trim()) return products;
    return products.filter((p) =>
      p.product_name.toLowerCase().includes(productSearch.toLowerCase()) ||
      p.supplier_sku?.toLowerCase().includes(productSearch.toLowerCase())
    );
  }, [products, productSearch]);

  const chosenCustomer = customers.find((c) => c.id === customerId);
  const isReady = !!customerId && !!productId && !!fullProduct;

  const handleSaveConfig = async (updatedConfig: any) => {
    setSaving(true);
    try {
      const res = await api<any>("/api/ops-config", {
        method: "POST",
        body: JSON.stringify(updatedConfig),
      });
      setConfig(res);
      setMappingOpen(false);
    } catch (e) {
      alert("Failed to save configuration");
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateMapping = (optionKey: string, masterOptionId: string) => {
    const newMappings = { ...config.option_mappings };
    if (masterOptionId === "none") {
      delete newMappings[optionKey];
    } else {
      const mo = masterOptions.find(m => m.id === masterOptionId);
      newMappings[optionKey] = {
        master_option_id: masterOptionId,
        ops_master_option_id: mo?.ops_master_option_id,
        title: mo?.title
      };
    }
    setConfig({ ...config, option_mappings: newMappings });
  };

  if (loading) return (
    <div className="flex items-center justify-center h-[60vh] flex-col gap-4">
      <div className="w-8 h-8 border-[3px] border-[#1e4d92] border-t-transparent rounded-full animate-spin" />
      <p className="text-sm text-[#888894]">Loading setup tools...</p>
    </div>
  );

  const mappedCount = config ? Object.keys(config.option_mappings).length : 0;
  const pendingCount = fullProduct ? fullProduct.options.length - mappedCount : 0;

  return (
    <div className="p-8 max-w-5xl mx-auto flex flex-col gap-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-2xl font-extrabold text-[#1e1e24] tracking-tight">Product Setup</h1>
        <p className="text-sm text-[#888894] mt-1">
          Map supplier products to your OPS storefront categories and pricing rules.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="flex flex-col gap-2">
          <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest flex items-center gap-2">
            <span className="w-4 h-4 rounded-full bg-[#1e4d92] text-white flex items-center justify-center text-[9px]">1</span>
            Target Storefront
          </label>
          <Select value={customerId} onValueChange={setCustomerId}>
            <SelectTrigger className="h-11 bg-white border-[#cfccc8] text-[13px]">
              <SelectValue placeholder="Select a storefront..." />
            </SelectTrigger>
            <SelectContent className="w-[var(--radix-select-trigger-width)]">
              {customers.map((c) => (
                <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest flex items-center gap-2">
            <span className="w-4 h-4 rounded-full bg-[#1e4d92] text-white flex items-center justify-center text-[9px]">2</span>
            Product to Configure
          </label>
          <div className="relative group">
            <Input
              placeholder="Filter products..."
              value={productSearch}
              onChange={(e) => { setProductSearch(e.target.value); }}
              className="h-11 text-[13px] bg-white border-[#cfccc8] pr-10 focus:ring-1 focus:ring-[#1e4d92]"
            />
            {productSearch && (
              <button 
                onClick={() => setProductSearch("")}
                className="absolute right-3 top-3 text-[#888894] hover:text-[#1e1e24]"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          <Select value={productId} onValueChange={setProductId}>
            <SelectTrigger className="h-11 bg-white border-[#cfccc8] text-[13px]">
              <SelectValue placeholder="Select a product..." />
            </SelectTrigger>
            <SelectContent className="w-[var(--radix-select-trigger-width)]">
              {filteredProducts.length === 0 ? (
                <div className="px-4 py-3 text-xs text-[#888894]">No products match search.</div>
              ) : (
                filteredProducts.map((p) => (
                  <SelectItem key={p.id} value={p.id}>{p.product_name}</SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        </div>
      </div>

      {isReady ? (
        <div className="flex flex-col gap-6 animate-in slide-in-from-top-4 duration-500">
          <div className="flex items-center gap-4 bg-white border border-[#cfccc8] rounded-xl px-6 py-4 shadow-sm">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#1e4d92] to-[#173d74] text-white font-black text-xl flex items-center justify-center shrink-0 shadow-lg shadow-blue-900/20">
              {fullProduct?.product_name?.[0]}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-lg font-black text-[#1e1e24] truncate tracking-tight">{fullProduct?.product_name}</div>
              <div className="text-xs font-bold text-[#888894] uppercase tracking-wider">
                Configuring for <span className="text-[#1e4d92]">{chosenCustomer?.name}</span>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="border-[#cfccc8] text-[12px] font-bold h-10 px-6 uppercase tracking-wider" onClick={() => { setProductId(""); setFullProduct(null); }}>Discard</Button>
              <Button 
                className="bg-[#1e4d92] hover:bg-[#173d74] text-[12px] font-bold h-10 px-8 uppercase tracking-wider shadow-lg shadow-blue-900/10"
                onClick={() => handleSaveConfig(config)}
                disabled={saving}
              >
                {saving ? "Saving..." : "Finalize Setup"}
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="border-[#cfccc8] shadow-sm hover:shadow-md transition-shadow">
              <div className="bg-[#f9f7f4] border-b border-[#f2f0ed] px-5 py-3 text-[11px] font-black uppercase tracking-widest text-[#1e4d92] flex items-center gap-2">
                <Layers className="w-3.5 h-3.5" />
                Storefront Category
              </div>
              <div className="p-6 flex flex-col gap-4">
                <p className="text-[12px] text-[#888894] font-medium leading-relaxed">Where will this product appear in the VG catalog?</p>
                <Select 
                  value={config?.ops_category_id || ""} 
                  onValueChange={(val) => setConfig({ ...config, ops_category_id: val })}
                >
                  <SelectTrigger className="h-10 border-[#cfccc8] text-[13px] bg-white">
                    <SelectValue placeholder="Select category..." />
                  </SelectTrigger>
                  <SelectContent className="w-[var(--radix-select-trigger-width)]">
                    <SelectItem value="apparel-tee">Apparel › T-Shirts</SelectItem>
                    <SelectItem value="apparel-hoodie">Apparel › Hoodies</SelectItem>
                    <SelectItem value="apparel-polo">Apparel › Polo</SelectItem>
                    <SelectItem value="infant">Infant &amp; Toddler</SelectItem>
                  </SelectContent>
                </Select>
                <div className={`rounded-lg px-3 py-2 text-[11px] font-bold flex items-center gap-2 border ${
                  config?.ops_category_id ? "bg-emerald-50 text-emerald-700 border-emerald-100" : "bg-blue-50 text-blue-700 border-blue-100"
                }`}>
                  <Info className="w-3 h-3" />
                  Currently: {config?.ops_category_id ? "Assigned" : "Unassigned"}
                </div>
              </div>
            </Card>

            <Card className="border-[#cfccc8] shadow-sm hover:shadow-md transition-shadow">
              <div className="bg-[#f9f7f4] border-b border-[#f2f0ed] px-5 py-3 text-[11px] font-black uppercase tracking-widest text-[#1e4d92] flex items-center gap-2">
                <Settings2 className="w-3.5 h-3.5" />
                Option Mapping
              </div>
              <div className="p-6 flex flex-col gap-4">
                <p className="text-[12px] text-[#888894] font-medium leading-relaxed">Connect supplier attributes to OPS master options.</p>
                <Button 
                  className="w-full bg-white text-[#1e4d92] border-2 border-[#1e4d92] hover:bg-[#1e4d92] hover:text-white text-xs font-black h-10 uppercase tracking-widest transition-all"
                  onClick={() => setMappingOpen(true)}
                >
                  Open Mapping Editor
                </Button>
                <div className="flex justify-between text-[11px] font-black border-t border-dashed border-[#cfccc8] pt-4 uppercase tracking-tighter">
                  <span className="text-[#888894]">Mapped: {mappedCount}</span>
                  <span className="text-[#1e4d92]">Pending: {pendingCount}</span>
                </div>
              </div>
            </Card>

            <Card className="border-[#cfccc8] bg-[#f9f7f4] shadow-sm">
              <div className="bg-[#ebe8e3] border-b border-[#d8d4cf] px-5 py-3 text-[11px] font-black uppercase tracking-widest text-[#1e4d92] flex items-center gap-2">
                <Activity className="w-3.5 h-3.5" />
                Pricing Outlook
              </div>
              <div className="p-6">
                <div className="bg-white rounded-xl border border-[#cfccc8] p-5 flex flex-col gap-4 shadow-inner">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-black uppercase tracking-widest text-[#888894]">
                      Wholesale Base ({fullProduct?.supplier_name})
                    </label>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold text-[#888894]">$</span>
                      <Input 
                        type="number"
                        placeholder={Math.min(...(fullProduct?.variants?.map(v => v.base_price || 0) || [0])).toFixed(2)}
                        className="h-9 border-[#cfccc8] font-mono font-bold"
                        value={config?.pricing_overrides?.base_price || ""}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value) || 0;
                          setConfig({
                            ...config,
                            pricing_overrides: { ...config.pricing_overrides, base_price: val }
                          });
                        }}
                      />
                    </div>
                    {!config?.pricing_overrides?.base_price && (
                      <p className="text-[9px] text-[#888894] italic">* Using supplier catalog price</p>
                    )}
                  </div>
                  <div className="flex justify-between text-[13px] text-[#1e4d92] font-black">
                    <span>Markup (45%)</span>
                    <span className="font-mono">
                      +${((config?.pricing_overrides?.base_price || Math.min(...(fullProduct?.variants?.map(v => v.base_price || 0) || [3.99]))) * 0.45).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between text-[11px] text-[#888894] font-bold border-t border-dashed border-[#cfccc8] pt-3 mt-1">
                    <span className="uppercase tracking-widest">Final Price</span>
                    <span className="text-xl font-black text-[#1e4d92] font-mono leading-none tracking-tighter">
                      ${((config?.pricing_overrides?.base_price || Math.min(...(fullProduct?.variants?.map(v => v.base_price || 0) || [3.99]))) * 1.45).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      ) : (
        <div className="border-2 border-dashed border-[#cfccc8] rounded-3xl p-24 text-center bg-[#fafaf8] animate-in fade-in duration-1000">
          <div className="w-16 h-16 rounded-2xl bg-white border border-[#cfccc8] flex items-center justify-center text-3xl mx-auto mb-6 shadow-sm">⚙️</div>
          <h3 className="text-xl font-black text-[#1e1e24] mb-2 tracking-tight">Configuration Suite</h3>
          <p className="text-[13px] text-[#888894] max-w-sm mx-auto font-medium leading-relaxed">
            Select a target storefront and a product above to access the automated mapping and pricing tools.
          </p>
        </div>
      )}

      <Dialog open={mappingOpen} onOpenChange={setMappingOpen}>
        <DialogContent className="max-w-2xl border-none p-0 overflow-hidden shadow-2xl">
          <div className="bg-[#1e4d92] p-8 text-white">
            <DialogTitle className="text-2xl font-black tracking-tight flex items-center gap-3">
              <Link2 className="w-7 h-7" />
              Attribute Mapping Editor
            </DialogTitle>
            <DialogDescription className="text-blue-100 mt-2 font-medium">
              Link {fullProduct?.product_name}'s inbound attributes to OnPrintShop master options.
            </DialogDescription>
          </div>
          
          <div className="p-8 max-h-[60vh] overflow-y-auto space-y-8 bg-white">
            {fullProduct?.options.map((opt) => (
              <div key={opt.id} className="space-y-4 group">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-black text-[#1e1e24] uppercase tracking-wider">{opt.title}</h4>
                    <p className="text-[11px] text-[#888894] font-bold uppercase tracking-tighter mt-1">Supplier Key: {opt.option_key}</p>
                  </div>
                  <div className="px-3 py-1 rounded bg-[#f2f0ed] text-[10px] font-black text-[#888894] uppercase tracking-widest border border-[#cfccc8]">
                    {opt.attributes.length} Values
                  </div>
                </div>
                
                <Select 
                  value={config?.option_mappings[opt.option_key]?.master_option_id || "none"}
                  onValueChange={(val) => handleUpdateMapping(opt.option_key, val)}
                >
                  <SelectTrigger className="h-11 border-2 border-[#cfccc8] hover:border-[#1e4d92] transition-colors bg-white font-bold text-[13px]">
                    <SelectValue placeholder="Map to Master Option..." />
                  </SelectTrigger>
                  <SelectContent className="w-[var(--radix-select-trigger-width)]">
                    <SelectItem value="none" className="text-rose-600 font-bold italic">Unmapped (Default)</SelectItem>
                    {masterOptions.map((mo) => (
                      <SelectItem key={mo.id} value={mo.id}>{mo.title}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                
                <div className="flex flex-wrap gap-1.5 pt-1">
                   {opt.attributes.slice(0, 8).map(attr => (
                     <span key={attr.id} className="text-[9px] px-1.5 py-0.5 bg-[#f9f7f4] border border-[#cfccc8] text-[#888894] rounded font-bold uppercase truncate max-w-[80px]">
                       {attr.title}
                     </span>
                   ))}
                   {opt.attributes.length > 8 && <span className="text-[9px] text-[#cfccc8] font-black">+ {opt.attributes.length - 8} more</span>}
                </div>
              </div>
            ))}
          </div>

          <DialogFooter className="p-6 bg-[#f9f7f4] border-t border-[#f2f0ed]">
            <Button variant="ghost" className="font-bold text-xs uppercase tracking-widest" onClick={() => setMappingOpen(false)}>Cancel</Button>
            <Button className="bg-[#1e4d92] hover:bg-[#173d74] font-black text-xs uppercase tracking-widest px-8" onClick={() => setMappingOpen(false)}>Confirm Mappings</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
