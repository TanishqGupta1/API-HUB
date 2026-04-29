"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { OptionConfigItem, Product, Supplier } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { OptionCard } from "@/components/options/option-card";

export default function ConfigureProductOptionsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [product, setProduct] = useState<Product | null>(null);
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [cards, setCards] = useState<OptionConfigItem[]>([]);
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [savingAll, setSavingAll] = useState(false);
  const [savedAll, setSavedAll] = useState(false);
  const [search, setSearch] = useState("");
  const [tag, setTag] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const p = await api<Product>(`/api/products/${id}`);
        setProduct(p);
        const sup = await api<Supplier>(`/api/suppliers/${p.supplier_id}`);
        setSupplier(sup);
        const cfg = await api<OptionConfigItem[]>(`/api/products/${id}/options-config`);
        setCards(cfg);
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const tags = useMemo(() => {
    const s = new Set<string>();
    cards.forEach((c) => c.master_option_tag && s.add(c.master_option_tag));
    return Array.from(s);
  }, [cards]);

  const visible = useMemo(() => {
    let result = cards;

    // Smart Filter: If it's an apparel product (like a Toddler T-Shirt), hide signage options
    if (product) {
      const pName = (product.product_name || "").toLowerCase();
      const pType = (product.product_type || "").toLowerCase();
      const isApparel = pName.includes("shirt") || pName.includes("tee") || pName.includes("hoodie") || pType.includes("apparel") || (supplier?.name || "").toLowerCase().includes("sanmar");
      
      if (isApparel) {
        const signageKeywords = ["laminate", "substrate", "ink", "finish", "packaging", "binding", "paper"];
        result = result.filter(o => {
          const t = (o.title || o.option_key || "").toLowerCase();
          return !signageKeywords.some(kw => t.includes(kw));
        });
      }
    }

    return result.filter((c) => {
      if (tag && c.master_option_tag !== tag) return false;
      if (search && !c.title.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [cards, search, tag, product, supplier]);

  const updateCard = (idx: number, next: OptionConfigItem) => {
    setCards((prev) => prev.map((c, i) => (i === idx ? next : c)));
    setDirty((d) => new Set(d).add(next.master_option_id));
  };

  const saveOne = async (card: OptionConfigItem) => {
    await api(`/api/products/${id}/options-config/${card.master_option_id}`, {
      method: "PATCH",
      body: JSON.stringify(card),
    });
    setDirty((d) => {
      const n = new Set(d);
      n.delete(card.master_option_id);
      return n;
    });
  };

  const saveAll = async () => {
    setSavingAll(true);
    setSavedAll(false);
    try {
      await api(`/api/products/${id}/options-config`, {
        method: "PUT",
        body: JSON.stringify(cards),
      });
      setDirty(new Set());
      setSavedAll(true);
      setTimeout(() => setSavedAll(false), 2000);
    } catch (err) {
      alert("Failed to save all.");
    } finally {
      setSavingAll(false);
    }
  };

  const deleteCard = async (card: OptionConfigItem) => {
    await api(`/api/products/${id}/options-config/${card.master_option_id}`, { method: "DELETE" });
    setCards((prev) => prev.map((c) => (c.master_option_id === card.master_option_id
      ? { ...c, enabled: false, attributes: c.attributes.map((a) => ({ ...a, enabled: false })) }
      : c)));
  };

  // Protocol check removed to allow configuring master options for any product (e.g. SanMar SOAP) 
  // that will eventually be pushed to an OPS storefront.
  
  if (loading) return <div className="p-6 text-[#888894]">Loading…</div>;

  if (loading) return <div className="p-6 text-[#888894]">Loading…</div>;

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-[#888894]">
            <button onClick={() => router.back()} className="hover:underline">← Back</button>
          </div>
          <h1 className="text-xl font-bold text-[#1e1e24] mt-1">
            Assign Product Options » <span className="text-[#1e4d92]">{product?.product_name}</span>
          </h1>
        </div>
        <Button
          onClick={saveAll}
          disabled={savingAll || savedAll || (!savedAll && dirty.size === 0)}
          className={savedAll ? "bg-green-600 hover:bg-green-700" : "bg-[#1e4d92] hover:bg-[#173d74]"}
        >
          {savingAll ? "Saving..." : savedAll ? "Saved!" : `Save All ${dirty.size ? `(${dirty.size})` : ""}`}
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <Input
          placeholder="Search..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <select
          value={tag}
          onChange={(e) => setTag(e.target.value)}
          className="h-9 px-3 text-sm border border-[#cfccc8] rounded bg-white"
        >
          <option value="">All tags</option>
          {tags.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <Button variant="ghost" onClick={() => { setSearch(""); setTag(""); }}>Reset</Button>
      </div>

      {visible.length === 0 ? (
        <div className="bg-white rounded-[10px] border border-[#cfccc8] p-10 text-center text-[#888894]">
          {cards.length === 0
            ? "No master options synced. Visit /products/configure and click Sync from OPS."
            : "No matches for the current filter."}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {visible.map((card) => {
            const idx = cards.indexOf(card);
            return (
              <OptionCard
                key={card.master_option_id}
                card={card}
                dirty={dirty.has(card.master_option_id)}
                onChange={(next) => updateCard(idx, next)}
                onSave={() => saveOne(cards[idx])}
                onDelete={() => deleteCard(card)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
