"use client";

/**
 * Phase 8 — Cleanup checklist for `failed` pushes.
 *
 * Spec §Failure handling — halt-no-rollback. When a mid-sequence
 * mutation fails, the backend snapshots every OPS target ID created
 * so far into `cleanup_targets`. This component renders that snapshot
 * as a copy-pasteable checklist for the operator to clean up manually
 * in the OPS admin UI.
 */
import { AlertTriangle, Check, Copy, ExternalLink } from "lucide-react";
import { useState } from "react";

import type { CleanupTargets } from "@/lib/types";

interface Props {
  targets: CleanupTargets;
  /** OPS storefront URL to link to in the banner header. */
  opsBaseUrl?: string;
}

export function CleanupChecklist({ targets, opsBaseUrl }: Props) {
  // New-spec keys
  const opsProductId = targets.ops_product_id ?? targets.product_id ?? null;
  const productSizeIds = targets.product_size_ids ?? targets.size_ids ?? [];
  const optionIds = targets.option_ids ?? [];
  const attributeIds = targets.attribute_ids ?? [];
  // Legacy keys (older fixtures)
  const categoryIds = targets.category_ids ?? [];
  const priceIds = targets.price_ids ?? [];

  const items: Array<{ kind: string; ids: Array<string | number> }> = [];
  if (opsProductId != null) items.push({ kind: "Product", ids: [opsProductId] });
  if (productSizeIds.length > 0) items.push({ kind: "Size", ids: productSizeIds });
  if (optionIds.length > 0) items.push({ kind: "Option", ids: optionIds });
  if (attributeIds.length > 0) items.push({ kind: "Attribute", ids: attributeIds });
  if (categoryIds.length > 0) items.push({ kind: "Category", ids: categoryIds });
  if (priceIds.length > 0) items.push({ kind: "Price", ids: priceIds });

  return (
    <section className="bg-[#fdf2f2] border-2 border-[#b93232] rounded-2xl overflow-hidden">
      <header className="flex items-center gap-3 px-6 py-4 bg-[#fdf2f2] border-b-2 border-[#b93232]">
        <AlertTriangle className="w-5 h-5 text-[#b93232]" />
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-extrabold uppercase tracking-widest text-[#b93232]">
            Manual cleanup required
          </div>
          <div className="text-[12px] text-[#7b1d1d] mt-0.5">
            Push failed mid-sequence. No auto-rollback (by spec design).
            Delete these OPS entities from the staging admin before
            re-running.
          </div>
        </div>
        {opsBaseUrl && (
          <a
            href={opsBaseUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#b93232] text-[#b93232] rounded-full font-bold text-[10px] uppercase tracking-wide hover:bg-[#b93232] hover:text-white transition-colors shrink-0"
          >
            <ExternalLink className="w-3 h-3" />
            Open OPS admin
          </a>
        )}
      </header>

      <ul className="divide-y divide-[#fecaca]">
        {items.map((item) => (
          <li key={item.kind} className="px-6 py-3 flex items-center gap-3">
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-[#b93232] w-20 shrink-0">
              {item.kind}
            </span>
            <div className="flex-1 flex flex-wrap items-center gap-1.5">
              {item.ids.map((id) => (
                <CopyChip key={id} value={String(id)} />
              ))}
            </div>
          </li>
        ))}

        {targets.instructions && (
          <li className="px-6 py-3 text-[12px] text-[#7b1d1d] bg-[#fef5f5] font-mono leading-relaxed">
            {targets.instructions}
          </li>
        )}
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Copy-to-clipboard chip for individual IDs
// ---------------------------------------------------------------------------

function CopyChip({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      // Fail silent — clipboard isn't critical
    }
  }

  return (
    <button
      onClick={handleCopy}
      title="Click to copy"
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-mono text-[11px] font-bold border transition-colors ${
        copied
          ? "bg-[#247a52] border-[#247a52] text-white"
          : "bg-white border-[#b93232] text-[#b93232] hover:bg-[#fdf2f2]"
      }`}
    >
      {value}
      {copied ? (
        <Check className="w-3 h-3" />
      ) : (
        <Copy className="w-2.5 h-2.5 opacity-60" />
      )}
    </button>
  );
}
