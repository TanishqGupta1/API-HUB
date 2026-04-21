"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname } from "next/navigation";
import type { Category } from "@/lib/types";

interface RailProps {
  categories: Category[];
  counts: Record<string, number>;
}

interface Node extends Category {
  children: Node[];
}

function buildTree(cats: Category[]): Node[] {
  const byId = new Map<string, Node>();
  cats.forEach((c) => byId.set(c.id, { ...c, children: [] }));
  const roots: Node[] = [];
  byId.forEach((n) => {
    if (n.parent_id && byId.has(n.parent_id)) byId.get(n.parent_id)!.children.push(n);
    else roots.push(n);
  });
  const sortRec = (list: Node[]) => {
    list.sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name));
    list.forEach((n) => sortRec(n.children));
  };
  sortRec(roots);
  return roots;
}

function Row({ node, depth, counts }: { node: Node; depth: number; counts: Record<string, number> }) {
  const pathname = usePathname();
  const href = `/storefront/vg/category/${node.id}`;
  const active = pathname === href;
  const count = counts[node.id];
  return (
    <>
      <Link
        href={href}
        className={`flex items-center gap-2 rounded-md text-[12.5px] font-medium transition-colors
          ${active ? "bg-[#1e4d92] text-white" : "text-[#1e1e24] hover:bg-[#eef4fb] hover:text-[#1e4d92]"}`}
        style={{ paddingLeft: `${12 + depth * 14}px`, paddingRight: 12, paddingTop: 8, paddingBottom: 8 }}
      >
        <span className="flex-1 truncate">{node.name}</span>
        {typeof count === "number" && (
          <span className={`font-mono text-[10px] ${active ? "text-white/70" : "text-[#888894]"}`}>
            {count}
          </span>
        )}
      </Link>
      {node.children.map((c) => (
        <Row key={c.id} node={c} depth={depth + 1} counts={counts} />
      ))}
    </>
  );
}

export function LeftRail({ categories, counts }: RailProps) {
  const [collapsed, setCollapsed] = useState(
    typeof window !== "undefined" && localStorage.getItem("vg-rail-collapsed") === "1"
  );
  const tree = buildTree(categories);

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    if (typeof window !== "undefined") {
      localStorage.setItem("vg-rail-collapsed", next ? "1" : "0");
    }
  };

  if (collapsed) {
    return (
      <aside className="w-[48px] shrink-0 border-r border-[#cfccc8] bg-white flex flex-col items-center py-3">
        <button
          onClick={toggle}
          className="w-8 h-8 rounded-md border border-[#cfccc8] hover:bg-[#eef4fb] text-[#484852]"
          aria-label="Expand categories"
        >
          →
        </button>
      </aside>
    );
  }

  return (
    <aside className="w-[260px] shrink-0 border-r border-[#cfccc8] bg-white sticky top-[60px] self-start"
      style={{ maxHeight: "calc(100vh - 60px)" }}>
      <div className="flex items-center justify-between px-4 h-10 border-b border-[#cfccc8] bg-[#f9f7f4]">
        <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">Categories</span>
        <button onClick={toggle} className="text-[#484852] hover:text-[#1e4d92]" aria-label="Collapse categories">
          ←
        </button>
      </div>
      <nav className="overflow-y-auto p-2 flex flex-col gap-[2px]" style={{ maxHeight: "calc(100vh - 100px)" }}>
        <Link
          href="/storefront/vg"
          className="flex items-center gap-2 px-3 py-2 rounded-md text-[12.5px] font-medium
            text-[#1e1e24] hover:bg-[#eef4fb] hover:text-[#1e4d92]"
        >
          All products
        </Link>
        {tree.length === 0 ? (
          <div className="px-3 py-6 text-center text-[11px] text-[#888894]">
            No categories synced.
          </div>
        ) : (
          tree.map((n) => <Row key={n.id} node={n} depth={0} counts={counts} />)
        )}
      </nav>
    </aside>
  );
}
