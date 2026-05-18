"use client";

/**
 * Integration Gateway (M0–M5) — push entry page.
 *
 * URL: /products/[id]/push
 *
 * Spec §"What changes outside the backend":
 *   "Existing push button on customers/{id}/catalog keeps working —
 *    admin route URL unchanged. M3 explicitly preserves it."
 *
 * Flow:
 *   1. Page loads → usePushDryRun() auto-runs a dry-run on mount → preflight
 *      + plan + computed prices appear in PreviewPanel.
 *   2. If preflight blocks → DryRunControls disabled with reason.
 *   3. Click "Send Dry-Run" → POST /push-requests {dry_run: true} →
 *      redirect to /push-log/[push_log_id].
 *   4. Click "Send to OPS (LIVE)" → typed-confirm dialog →
 *      POST /push-requests {dry_run: false} → redirect.
 *
 * Mock mode (default): every call returns fixtures. Toggle by setting
 * NEXT_PUBLIC_PHASE8_LIVE=true once the gateway endpoints (M2) ship.
 */
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Loader2 } from "lucide-react";

import { CleanupChecklist } from "@/components/push/CleanupChecklist";
import { DryRunControls } from "@/components/push/DryRunControls";
import { PreviewPanel } from "@/components/push/PreviewPanel";
import {
  IS_MOCK_MODE,
  usePushDryRun,
  usePushRequest,
} from "@/lib/use-push-preview";

/** UUID v1-v5 test. Used to decide whether the "Back to product" link
 *  is safe — `/products/[id]` (legacy detail page) 500s on non-UUID ids. */
function _isUuid(s: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s);
}

export default function PushPreviewPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const productId = params.id;
  const customerId = searchParams.get("customer_id");
  const supplierSlugParam = searchParams.get("supplier_slug");

  const { preflight, payload, error: dryRunError, loading, refetch } =
    usePushDryRun(customerId, productId, supplierSlugParam);
  const { push, loading: pushing, error: pushError } = usePushRequest();

  if (!customerId) {
    return <MissingCustomerCard productId={productId} />;
  }

  if (loading) {
    return <LoadingCard />;
  }

  if (dryRunError && !payload) {
    return (
      <ErrorCard
        message={dryRunError.message}
        details={
          (dryRunError.details?.field as string | undefined) ?? null
        }
        suggestion={
          (dryRunError.details?.suggestion as string | undefined) ?? null
        }
        onRetry={refetch}
      />
    );
  }

  const blockers = preflight?.blockers ?? [];
  const hasBlockers = blockers.length > 0;
  const supplierSku = payload?.supplier_sku ?? "PRODUCT";
  const supplierSlug = payload?.supplier_slug ?? supplierSlugParam ?? "sanmar";
  const realConfirmText = `PUSH ${supplierSku} TO STAGING`;

  async function handlePush(dryRun: boolean) {
    if (!customerId) return;
    const resp = await push({
      customerId,
      productId,
      supplierSlug,
      supplierSku,
      dryRun,
    });
    if (resp?.push_log_id) {
      router.push(`/push-log/${resp.push_log_id}`);
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
      {/* Header */}
      <header className="flex items-end justify-between pb-5 border-b-2 border-[#1e1e24]">
        <div>
          <Link
            // Use the catalog list in mock/demo mode — the legacy /products/[id]
            // detail page requires a real UUID and 500s on demo strings like "abc-123".
            href={_isUuid(productId) ? `/products/${productId}` : "/products"}
            className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest text-[#888894] hover:text-[#1e4d92] transition-colors mb-3"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to {_isUuid(productId) ? "product" : "catalog"}
          </Link>
          <div className="text-[32px] font-extrabold tracking-[-0.04em] leading-none text-[#1e1e24]">
            Push to OPS
          </div>
          <div className="text-[13px] text-[#888894] mt-2">
            <span className="font-mono">{supplierSku}</span> →{" "}
            <span className="font-mono">
              {payload?.push_mode === "update"
                ? `update products_id=${payload.existing_ops_product_id}`
                : "staging"}
            </span>
            {IS_MOCK_MODE && (
              <span className="ml-2 inline-flex items-center px-1.5 py-0.5 bg-[#fff7e0] border border-[#c17c00] rounded font-mono text-[9px] font-bold uppercase tracking-wide text-[#c17c00]">
                mock mode
              </span>
            )}
          </div>
        </div>
        {payload && (
          <span className="font-mono text-[11px] text-[#888894]">
            built {new Date(payload.built_at).toLocaleTimeString()} · {payload.estimated_mutations} mutations
          </span>
        )}
      </header>

      {/* Image policy warnings — if any */}
      {payload?.image_warnings && payload.image_warnings.length > 0 && (
        <div className="bg-[#fff7e0] border-2 border-[#c17c00] rounded-2xl px-4 py-3 text-[12px] text-[#7a4900] flex items-start gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <div className="font-bold mb-1">Image policy notice</div>
            <ul className="list-disc pl-4 space-y-0.5">
              {payload.image_warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Preflight + computed prices + plan */}
      <PreviewPanel
        preflight={preflight}
        plan={payload?.plan ?? []}
        computedPrices={payload?.computed_prices}
      />

      {pushError && (
        <div className="bg-[#fdf2f2] border-2 border-[#b93232] rounded-2xl px-4 py-3 text-[12px] text-[#b93232] flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          {typeof pushError === "string"
            ? pushError
            : pushError.message}
        </div>
      )}

      {/* Dry-run + live controls */}
      <DryRunControls
        liveConfirmText={realConfirmText}
        disabled={hasBlockers || pushing}
        disabledReason={
          hasBlockers
            ? `Push blocked: ${blockers.join(", ")}`
            : pushing
              ? "A push is already in flight"
              : undefined
        }
        mockMode={IS_MOCK_MODE}
        onDryRun={() => handlePush(true)}
        onLive={() => handlePush(false)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty / loading / error states
// ---------------------------------------------------------------------------

function MissingCustomerCard({ productId }: { productId: string }) {
  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <div className="border-2 border-dashed border-[#cfccc8] rounded-2xl p-10 text-center bg-white">
        <div className="text-[16px] font-bold text-[#1e1e24]">
          Pick a customer to push for
        </div>
        <p className="text-[13px] text-[#888894] mt-2 leading-relaxed">
          The push pipeline runs per-customer (each storefront has its own
          markup + decoration config). Use the customer selector in the
          top bar, then come back to this page — or follow a link from{" "}
          <Link
            href={`/customers`}
            className="text-[#1e4d92] font-semibold hover:underline"
          >
            /customers
          </Link>
          .
        </p>
        <Link
          href={_isUuid(productId) ? `/products/${productId}` : "/products"}
          className="inline-flex items-center gap-1.5 mt-4 text-[12px] font-semibold text-[#1e4d92] hover:underline"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to {_isUuid(productId) ? "product" : "catalog"}
        </Link>
      </div>
    </div>
  );
}

function LoadingCard() {
  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <div className="border-2 border-dashed border-[#cfccc8] rounded-2xl p-16 text-center bg-white">
        <Loader2 className="w-8 h-8 text-[#1e4d92] animate-spin mx-auto mb-3" />
        <div className="text-[13px] text-[#484852]">
          Running dry-run preflight…
        </div>
      </div>
    </div>
  );
}

function ErrorCard({
  message,
  details,
  suggestion,
  onRetry,
}: {
  message: string;
  details: string | null;
  suggestion: string | null;
  onRetry: () => void;
}) {
  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <div className="border-2 border-[#b93232] rounded-2xl p-10 text-center bg-[#fdf2f2]">
        <AlertCircle className="w-8 h-8 text-[#b93232] mx-auto mb-3" />
        <div className="text-[14px] font-bold text-[#b93232]">
          Preflight blocked
        </div>
        <p className="text-[12px] text-[#7b1d1d] mt-2">{message}</p>
        {details && (
          <p className="font-mono text-[10px] text-[#7b1d1d] mt-2 opacity-80">
            field: {details}
          </p>
        )}
        {suggestion && (
          <p className="text-[12px] text-[#7b1d1d] mt-3 italic">{suggestion}</p>
        )}
        <button
          onClick={onRetry}
          className="mt-4 px-4 h-9 bg-white border-2 border-[#b93232] text-[#b93232] rounded-full font-bold text-[11px] uppercase tracking-wide hover:bg-[#fdf2f2] transition-colors"
        >
          Retry
        </button>
      </div>
    </div>
  );
}

// Silence unused-import linting for CleanupChecklist (used by the sibling
// /push-log/[id] page — kept in the same module hierarchy).
export { CleanupChecklist as _CleanupChecklist };
