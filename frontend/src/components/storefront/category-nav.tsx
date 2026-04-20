"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Category } from "@/lib/types";

interface CategoryNavProps {
  categories: Category[];
  activeCategoryId?: string;
}

interface CategoryNode extends Category {
  children: CategoryNode[];
}

function buildTree(categories: Category[]): CategoryNode[] {
  const byId = new Map<string, CategoryNode>();
  categories.forEach((c) => byId.set(c.id, { ...c, children: [] }));

  const roots: CategoryNode[] = [];
  byId.forEach((node) => {
    if (node.parent_id && byId.has(node.parent_id)) {
      byId.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });

  const sortRec = (nodes: CategoryNode[]) => {
    nodes.sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name));
    nodes.forEach((n) => sortRec(n.children));
  };
  sortRec(roots);

  return roots;
}

function CategoryLink({
  node,
  depth,
  activeCategoryId,
}: {
  node: CategoryNode;
  depth: number;
  activeCategoryId?: string;
}) {
  const pathname = usePathname();
  const href = `/storefront/vg/category/${node.id}`;
  const isActive = activeCategoryId === node.id || pathname === href;

  return (
    <>
      <Link
        href={href}
        className={`flex items-center gap-2 px-3 py-2 rounded-md text-[13px] font-medium transition-colors
          ${isActive
            ? "bg-[#1e4d92] text-white"
            : "text-[#1e1e24] hover:bg-[#eef4fb] hover:text-[#1e4d92]"
          }`}
        style={{ paddingLeft: `${12 + depth * 14}px` }}
      >
        <span className="flex-1 truncate">{node.name}</span>
      </Link>
      {node.children.map((child) => (
        <CategoryLink
          key={child.id}
          node={child}
          depth={depth + 1}
          activeCategoryId={activeCategoryId}
        />
      ))}
    </>
  );
}

export function CategoryNav({ categories, activeCategoryId }: CategoryNavProps) {
  const tree = buildTree(categories);

  return (
    <aside className="w-[240px] shrink-0 border border-[#cfccc8] rounded-[10px] bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-[#cfccc8] bg-[#f9f7f4]">
        <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">
          Categories
        </div>
      </div>
      <nav className="p-2 flex flex-col gap-[2px] max-h-[70vh] overflow-y-auto">
        <Link
          href="/storefront/vg"
          className={`flex items-center gap-2 px-3 py-2 rounded-md text-[13px] font-medium transition-colors
            ${!activeCategoryId
              ? "bg-[#1e4d92] text-white"
              : "text-[#1e1e24] hover:bg-[#eef4fb] hover:text-[#1e4d92]"
            }`}
        >
          <span className="flex-1 truncate">All products</span>
        </Link>
        {tree.length === 0 && (
          <div className="px-3 py-6 text-center text-[12px] text-[#888894]">
            No categories yet. Run an OPS sync.
          </div>
        )}
        {tree.map((node) => (
          <CategoryLink
            key={node.id}
            node={node}
            depth={0}
            activeCategoryId={activeCategoryId}
          />
        ))}
      </nav>
    </aside>
  );
}
