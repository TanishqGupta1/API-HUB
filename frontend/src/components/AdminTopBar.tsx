"use client";

/**
 * Thin sticky strip above admin pages. Hosts the customer selector
 * (Phase 6) and is the natural home for future global admin widgets
 * (notifications, user menu, search, etc.).
 */
import { CustomerSelector } from "@/components/CustomerSelector";

export default function AdminTopBar() {
  return (
    <div className="sticky top-0 z-30 -mx-[clamp(24px,4vw,48px)] mb-6 flex items-center justify-end gap-3 px-[clamp(24px,4vw,48px)] py-3 bg-[#f2f0ed]/80 backdrop-blur-sm border-b border-[#cfccc8]">
      <CustomerSelector />
    </div>
  );
}
