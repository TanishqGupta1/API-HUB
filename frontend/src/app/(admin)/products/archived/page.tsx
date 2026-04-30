"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import type { ProductListItem } from "@/lib/types";
import { Button } from "@/components/ui/button";

export default function ArchivedProductsPage() {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const rows = await api<ProductListItem[]>(
          "/api/products?archived=true&limit=500"
        );
        setProducts(rows);
      } catch (err) {
        log.error(err);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const restore = async (id: string) => {
    try {
      await api(`/api/products/${id}/restore`, { method: "POST" });
      setProducts((prev) => prev.filter((x) => x.id !== id));
    } catch (err) {
      log.error(err);
      alert("Failed to restore product.");
    }
  };

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#1e1e24]">Archived Products</h1>
          <p className="text-sm text-[#888894] mt-1">
            Products hidden from the main catalog. Restore to make active again.
          </p>
        </div>
        <Link href="/products">
          <Button variant="outline" className="border-[#1e4d92] text-[#1e4d92] hover:bg-[#1e4d92] hover:text-white transition-colors">← Active Products</Button>
        </Link>
      </div>

      {loading ? (
        <div className="text-sm text-[#888894]">Loading…</div>
      ) : products.length === 0 ? (
        <div className="bg-white rounded-[10px] border border-[#cfccc8] p-10 text-center">
          <div className="text-[15px] font-semibold text-[#1e1e24] mb-2">
            No archived products
          </div>
          <p className="text-sm text-[#888894]">Nothing archived yet.</p>
        </div>
      ) : (
        <div className="bg-white rounded-[10px] border border-[#cfccc8] overflow-hidden">
          <table className="w-full border-collapse">
            <thead className="bg-[#ebe8e3] border-b border-[#cfccc8]">
              <tr>
                {["Product", "SKU", "Brand", "Action"].map((h) => (
                  <th
                    key={h}
                    className="text-left px-4 py-3 text-[10px] font-bold uppercase tracking-[0.1em] text-[#888894]"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr
                  key={p.id}
                  className="border-b border-[#f9f7f4] hover:bg-[rgba(30,77,146,0.03)]"
                >
                  <td className="px-4 py-3 text-sm">{p.product_name}</td>
                  <td className="px-4 py-3 text-xs font-mono">
                    {p.supplier_sku}
                  </td>
                  <td className="px-4 py-3 text-xs">{p.brand || "—"}</td>
                  <td className="px-4 py-3">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => restore(p.id)}
                      className="border-[#247a52] text-[#247a52]"
                    >
                      Restore
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
