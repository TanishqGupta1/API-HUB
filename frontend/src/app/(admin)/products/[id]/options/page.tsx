"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { OptionConfigItem, Product } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { OptionCard } from "@/components/options/option-card";

export default function ConfigureProductOptionsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [product, setProduct] = useState<Product | null>(null);
  const [cards, setCards] = useState<OptionConfigItem[]>([]);
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [savingAll, setSavingAll] = useState(false);
  const [search, setSearch] = useState("");
  const [tag, setTag] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [p, cfg] = await Promise.all([
          api<Product>(`/api/products/${id}`),
          api<OptionConfigItem[]>(`/api/products/${id}/options-config`),
        ]);
        setProduct(p);
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
    return cards.filter((c) => {
      if (tag && c.master_option_tag !== tag) return false;
      if (search && !c.title.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [cards, search, tag]);

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
    try {
      await api(`/api/products/${id}/options-config`, {
        method: "PUT",
        body: JSON.stringify(cards),
      });
      setDirty(new Set());
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
          disabled={savingAll || dirty.size === 0}
          className="bg-[#1e4d92] hover:bg-[#173d74]"
        >
          {savingAll ? "Saving..." : `Save All ${dirty.size ? `(${dirty.size})` : ""}`}
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
