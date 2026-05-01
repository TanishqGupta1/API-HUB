"use client";

import type { ProductType } from "@/lib/types";

const LABELS: Record<ProductType, string> = {
  apparel: "Apparel",
  print: "Print",
  template: "Template",
  promo: "Promo",
};

interface Props {
  available: ProductType[];
  value: ProductType | null;
  onChange: (value: ProductType | null) => void;
}

export function ProductTypeFilter({ available, value, onChange }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Pill active={value === null} onClick={() => onChange(null)}>
        All
      </Pill>
      {available.map((t) => (
        <Pill
          key={t}
          active={value === t}
          onClick={() => onChange(value === t ? null : t)}
        >
          {LABELS[t]}
        </Pill>
      ))}
    </div>
  );
}

function Pill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "px-3 py-1 rounded-full border text-[12px] font-semibold transition-colors " +
        (active
          ? "border-[#1e4d92] bg-[#1e4d92] text-white"
          : "border-[#cfccc8] bg-white text-[#1e1e24] hover:border-[#1e4d92] hover:text-[#1e4d92]")
      }
    >
      {children}
    </button>
  );
}
