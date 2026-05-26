"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { resolveApiBase } from "@/lib/api-base";
import { log } from "@/lib/log";
import type { Customer, Product, ProductDecoration, DecorationOption } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Loader2, Palette, Image as ImageIcon, Move, Maximize, RefreshCw, Trash2 } from "lucide-react";
import Image from "next/image";

interface Props {
  product: Product;
  customer: Customer;
  onUpdate?: () => void;
}

const DEFAULT_DECORATION: DecorationOption = {
  type: "logo",
  position_x: 50,
  position_y: 35,
  scale: 0.5,
  rotation: 0,
  layer: 0,
};

export function BrandingPanel({ product, customer, onUpdate }: Props) {
  const [decoration, setDecoration] = useState<ProductDecoration | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  // Local edit state
  const [logoUrl, setLogoUrl] = useState<string>("");
  const [posX, setPosX] = useState<number>(50);
  const [posY, setPosY] = useState<number>(35);
  const [scale, setScale] = useState<number>(0.5);
  const [previewMode, setPreviewMode] = useState<"css" | "engine">("css");

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const data = await api<ProductDecoration>(`/api/customers/${customer.id}/products/${product.id}/decorations`);
        setDecoration(data);
        if (data.decoration_options.length > 0) {
          const opt = data.decoration_options[0];
          setLogoUrl(opt.url || "");
          setPosX(opt.position_x);
          setPosY(opt.position_y);
          setScale(opt.scale);
          setPreviewMode("engine"); // Default to engine if already exists
        } else {
           setLogoUrl(customer.logo_url || "");
           setPreviewMode("css");
        }
      } catch (err: any) {
        if (err.status !== 404) {
          log.error("Failed to load decorations", err);
        }
        setLogoUrl(customer.logo_url || "");
        setPreviewMode("css");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [product.id, customer.id, customer.logo_url]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        decoration_options: [
          {
            ...DEFAULT_DECORATION,
            url: logoUrl,
            position_x: posX,
            position_y: posY,
            scale: scale,
          },
        ],
      };
      await api(`/api/customers/${customer.id}/products/${product.id}/decorations`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      toast.success("Branding saved for this product");
      setPreviewMode("engine");
      if (onUpdate) onUpdate();
    } catch (err) {
      toast.error("Failed to save branding");
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async () => {
    if (!confirm("Remove branding for this product?")) return;
    setSaving(true);
    try {
      await api(`/api/customers/${customer.id}/products/${product.id}/decorations`, {
        method: "DELETE",
      });
      setDecoration(null);
      setLogoUrl(customer.logo_url || "");
      setPreviewMode("css");
      toast.success("Branding removed");
      if (onUpdate) onUpdate();
    } catch (err) {
      toast.error("Failed to remove branding");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-[#1e4d92]" /></div>;

  return (
    <div className="bg-white border border-[#cfccc8] rounded-lg shadow-[4px_6px_0_rgba(30,77,146,0.08)] overflow-hidden mb-8">
      <div className="flex items-center justify-between px-6 py-4 bg-[#ebe8e3] border-b border-[#cfccc8]">
        <div>
          <div className="text-[14px] font-bold uppercase tracking-[0.05em] text-[#1e1e24] flex items-center gap-2">
            <Palette className="w-4 h-4 text-[#1e4d92]" />
            Branding & Decoration
          </div>
          <div className="text-[11px] text-[#888894] font-mono mt-0.5">
            Customer: {customer.name}
          </div>
        </div>
        <div className="flex gap-2">
           <div className="flex bg-[#f2f0ed] rounded-md p-1 mr-4">
              <button 
                onClick={() => setPreviewMode("css")}
                className={`px-3 py-1 text-[10px] font-bold uppercase rounded ${previewMode === 'css' ? 'bg-white shadow-sm text-[#1e4d92]' : 'text-[#888894]'}`}
              >
                Editor
              </button>
              <button 
                onClick={() => setPreviewMode("engine")}
                className={`px-3 py-1 text-[10px] font-bold uppercase rounded ${previewMode === 'engine' ? 'bg-white shadow-sm text-[#1e4d92]' : 'text-[#888894]'}`}
              >
                Mockup
              </button>
           </div>
           {decoration && (
             <Button variant="ghost" size="sm" onClick={handleRemove} className="text-rose-600 hover:bg-rose-50 h-8 px-3 text-[11px] font-bold uppercase">
               <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Remove
             </Button>
           )}
           <Button onClick={handleSave} disabled={saving} className="bg-[#1e4d92] text-white h-8 px-4 text-[11px] font-bold uppercase tracking-wider">
             {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
             Save Branding
           </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-0">
        {/* Real-time Preview */}
        <div className="p-8 bg-[#f9f7f4] border-r border-[#cfccc8] flex flex-col items-center justify-center">
            <div className="flex justify-between w-full mb-6">
              <div className="text-[10px] font-black uppercase tracking-widest text-[#888894]">
                {previewMode === 'css' ? 'Interactive Editor' : 'Generated Engine Mockup'}
              </div>
              <div className="text-[10px] font-mono text-[#1e4d92] font-bold">
                {previewMode === 'css' ? 'REALTIME_CSS_MODE' : 'SERVER_RENDER_MODE'}
              </div>
            </div>
            
            <div className="relative w-[300px] h-[300px] bg-white rounded-xl shadow-inner border border-[#cfccc8] overflow-hidden group">
                {previewMode === 'css' ? (
                  <>
                    {/* Product Image Base */}
                    <Image
                        src={product.image_url || "/placeholder-product.png"}
                        alt="Preview Base"
                        fill
                        sizes="300px"
                        className="object-contain p-4 opacity-40 mix-blend-multiply"
                    />
                    
                    {/* Decoration Overlay */}
                    {logoUrl && (
                        <div
                            className="absolute pointer-events-none transition-all duration-200 relative"
                            style={{
                                left: `${posX}%`,
                                top: `${posY}%`,
                                transform: `translate(-50%, -50%) scale(${scale})`,
                                width: '100px',
                                height: '100px',
                            }}
                        >
                            <Image
                                src={logoUrl}
                                alt="Logo Overlay"
                                fill
                                sizes="100px"
                                className="object-contain drop-shadow-md"
                            />
                        </div>
                    )}
                  </>
                ) : (
                  <Image
                    src={`${resolveApiBase()}/api/customers/${customer.id}/products/${product.id}/decorations/preview.png?t=${Date.now()}`}
                    alt="Engine Preview"
                    fill
                    sizes="300px"
                    className="object-contain"
                  />
                )}
                
                {/* Guides */}
                {previewMode === 'css' && <div className="absolute inset-0 border border-blue-400/20 pointer-events-none hidden group-hover:block" />}
            </div>
            
            <p className="text-[11px] text-[#888894] mt-6 text-center italic">
              Logo positioning is relative to the &ldquo;Front&rdquo; view of the {product.product_type}.
            </p>
        </div>

        {/* Controls */}
        <div className="p-8 flex flex-col gap-8">
            {/* Logo URL */}
            <div className="space-y-3">
                <label className="text-[10px] font-black uppercase tracking-widest text-[#484852] flex items-center gap-2">
                   <ImageIcon className="w-3.5 h-3.5" /> Logo URL
                </label>
                <div className="flex gap-2">
                    <input 
                        type="text" 
                        value={logoUrl}
                        onChange={(e) => setLogoUrl(e.target.value)}
                        placeholder="https://example.com/logo.png"
                        className="flex-1 h-10 px-4 text-sm font-medium border border-[#cfccc8] rounded-md bg-white outline-none focus:border-[#1e4d92] transition-all"
                    />
                    <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => setLogoUrl(customer.logo_url || "")}
                        className="h-10 text-[10px] font-bold uppercase border-[#cfccc8]"
                    >
                        <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Use Default
                    </Button>
                </div>
            </div>

            {/* Position X */}
            <div className="space-y-3">
                <div className="flex justify-between items-center">
                    <label className="text-[10px] font-black uppercase tracking-widest text-[#484852] flex items-center gap-2">
                        <Move className="w-3.5 h-3.5" /> Horizontal Position ({posX}%)
                    </label>
                    <button onClick={() => setPosX(50)} className="text-[9px] font-bold text-[#1e4d92] uppercase">Center</button>
                </div>
                <input 
                    type="range" 
                    min="0" 
                    max="100" 
                    value={posX}
                    onChange={(e) => setPosX(Number(e.target.value))}
                    className="w-full h-1 bg-[#ebe8e3] rounded-lg appearance-none cursor-pointer accent-[#1e4d92]"
                />
            </div>

            {/* Position Y */}
            <div className="space-y-3">
                <div className="flex justify-between items-center">
                    <label className="text-[10px] font-black uppercase tracking-widest text-[#484852] flex items-center gap-2">
                        <Move className="w-3.5 h-3.5 rotate-90" /> Vertical Position ({posY}%)
                    </label>
                    <button onClick={() => setPosY(35)} className="text-[9px] font-bold text-[#1e4d92] uppercase">Reset</button>
                </div>
                <input 
                    type="range" 
                    min="0" 
                    max="100" 
                    value={posY}
                    onChange={(e) => setPosY(Number(e.target.value))}
                    className="w-full h-1 bg-[#ebe8e3] rounded-lg appearance-none cursor-pointer accent-[#1e4d92]"
                />
            </div>

            {/* Scale */}
            <div className="space-y-3">
                <div className="flex justify-between items-center">
                    <label className="text-[10px] font-black uppercase tracking-widest text-[#484852] flex items-center gap-2">
                        <Maximize className="w-3.5 h-3.5" /> Logo Scale ({Math.round(scale * 100)}%)
                    </label>
                    <button onClick={() => setScale(0.5)} className="text-[9px] font-bold text-[#1e4d92] uppercase">Default</button>
                </div>
                <input 
                    type="range" 
                    min="10" 
                    max="200" 
                    step="5"
                    value={scale * 100}
                    onChange={(e) => setScale(Number(e.target.value) / 100)}
                    className="w-full h-1 bg-[#ebe8e3] rounded-lg appearance-none cursor-pointer accent-[#1e4d92]"
                />
            </div>
        </div>
      </div>
    </div>
  );
}
