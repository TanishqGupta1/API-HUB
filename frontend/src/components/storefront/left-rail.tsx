"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import type { Category } from "@/lib/types";

interface LeftRailProps {
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
    list.sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.name.localeCompare(b.name));
    list.forEach((n) => sortRec(n.children));
  };
  sortRec(roots);
  return roots;
}

function Row({ node, depth, counts }: { node: Node; depth: number; counts: Record<string, number> }) {
  return (
    <div>
      <Link
        href={`/storefront/vg?category=${node.id}`}
        className="flex items-center justify-between px-3 py-1.5 rounded-md text-[12.5px]
                   text-[#1e1e24] hover:bg-[#eef4fb] hover:text-[#1e4d92]"
        style={{ paddingLeft: 12 + depth * 14 }}
      >
        <span className="truncate">{node.name}</span>
        {counts[node.id] != null && (
          <span className="text-[10px] font-mono text-[#888894]">{counts[node.id]}</span>
        )}
      </Link>
      {node.children.map((c) => (
        <Row key={c.id} node={c} depth={depth + 1} counts={counts} />
      ))}
    </div>
  );
}

export function LeftRail({ categories, counts }: LeftRailProps) {
  const tree = useMemo(() => buildTree(categories), [categories]);
  const [open, setOpen] = useState(false);

  return (
    <aside
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      className="relative shrink-0"
      aria-label="Category rail"
    >
      {/* Collapsed rail (always in flow) */}
      <div className="w-[60px] sticky top-[96px] h-[calc(100vh-96px)] border-r border-[#e9e7e3] bg-white flex flex-col items-center py-4 gap-2">
        <button
          aria-label={open ? "Collapse categories" : "Expand categories"}
          onClick={() => setOpen((v) => !v)}
          className="w-9 h-9 rounded-md flex items-center justify-center text-[#484852]
                     hover:bg-[#f2f0ed] hover:text-[#1e4d92]"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        {tree.slice(0, 8).map((n) => {
          const initial = n.name.slice(0, 1).toUpperCase();
          return (
            <Link
              key={n.id}
              href={`/storefront/vg?category=${n.id}`}
              title={n.name}
              className="w-9 h-9 rounded-md flex items-center justify-center bg-[#f9f7f4]
                         text-[#484852] text-[11px] font-bold font-mono hover:bg-[#eef4fb] hover:text-[#1e4d92]"
            >
              {initial}
            </Link>
          );
        })}
      </div>

      {/* Expanded overlay */}
      {open && (
        <div
          className="absolute left-[60px] top-0 z-40 w-[240px] h-[calc(100vh-96px)]
                     bg-white border-r border-b border-[#cfccc8] shadow-lg overflow-y-auto"
        >
          <nav className="py-3">
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
        </div>
      )}
    </aside>
  );
}
