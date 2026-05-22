/**
 * Mock fixtures for the Integration Gateway push flow (M0–M5).
 *
 * Drives the admin UI in MOCK mode until the backend gateway endpoints
 * (M2) are live. Once `NEXT_PUBLIC_PHASE8_LIVE=true`, the hooks in
 * `use-push-preview.ts` swap to real `POST /api/integrations/v1/push-requests`.
 *
 * Aligned to `docs/superpowers/specs/2026-05-11-integration-gateway-design.md`
 * Rev 1+2+3 (status vocabulary, callback_status, idempotency_key,
 * payload_hash, step_results JSONB, cleanup_targets JSONB).
 */
import type {
  CleanupTargets,
  GatewayErrorEnvelope,
  OPSComputedPrice,
  OPSMutationStep,
  OPSPushPayload,
  OPSStepResult,
  PreflightResult,
  PushAcceptedResponse,
  PushLog,
  PushTerminalResponse,
} from "@/lib/types";

// ───────────────────────────────────────────────────────────────────────────
// Preflight
// ───────────────────────────────────────────────────────────────────────────

export const FIXTURE_PREFLIGHT_PASS: PreflightResult = {
  checks: [
    { name: "base_price_set", ok: true, detail: "all 7 variants have base_price > 0" },
    { name: "markup_rule_resolves", ok: true, detail: "all → 50% (rule 8f3a)" },
    { name: "push_mappings_present", ok: true, detail: "product has no options — nothing to map" },
    { name: "customer_ops_creds_present", ok: true, detail: "ops_base_url + token_url + client_id + client_secret all set" },
    { name: "ops_oauth2_reachable", ok: true, detail: "token issued, exp 3600s" },
    { name: "image_urls_reachable", ok: true, detail: "1/1 HEAD 200" },
    { name: "prefix_collision", ok: true, detail: "no existing OPS product with internal_title 'PC61'" },
    { name: "required_fields", ok: true, detail: "name + sku set, 7 variant(s)" },
    { name: "decoration_attached", ok: true, detail: "supplier doesn't require decoration overlay" },
  ],
  blockers: [],
  warnings: [],
  computed_at: "2026-05-13T10:00:00.000Z",
};

export const FIXTURE_PREFLIGHT_BLOCKED: PreflightResult = {
  checks: [
    {
      name: "base_price_set",
      ok: false,
      detail: "2 variant(s) missing base_price: PC61-NAV-S, PC61-NAV-M",
      field: "product.variants[].base_price",
      suggestion: "Re-run the supplier inventory sync, or check the normalizer for upstream changes that left base_price null.",
    },
    { name: "markup_rule_resolves", ok: true, detail: "all → 50% (rule 8f3a)" },
    {
      name: "push_mappings_present",
      ok: false,
      detail: "missing target_ops_option_id for: embroidery",
      field: "push_mappings.target_ops_option_id",
      suggestion: "Run /api/push-mappings/resolve to discover the missing OPS option IDs.",
    },
    { name: "customer_ops_creds_present", ok: true, detail: "all set" },
    { name: "ops_oauth2_reachable", ok: true, detail: "token cache hit" },
    { name: "image_urls_reachable", ok: true, detail: "1/1 HEAD 200" },
    { name: "prefix_collision", ok: true, detail: "skipped (no OpsClient wired)" },
    { name: "required_fields", ok: true, detail: "name + sku set, 7 variant(s)" },
    { name: "decoration_attached", ok: true, detail: "supplier doesn't require decoration overlay" },
  ],
  blockers: ["base_price_set", "push_mappings_present"],
  warnings: [],
  computed_at: "2026-05-13T10:00:00.000Z",
};

// ───────────────────────────────────────────────────────────────────────────
// Gateway error envelopes (422)
// ───────────────────────────────────────────────────────────────────────────

export const FIXTURE_ERROR_PREFLIGHT_BLOCKER: GatewayErrorEnvelope = {
  status: "error",
  code: "PREFLIGHT_BLOCKER",
  message: "2 variant(s) missing base_price: PC61-NAV-S, PC61-NAV-M",
  details: {
    field: "product.variants[].base_price",
    suggestion: "Re-run the supplier inventory sync.",
    blockers: ["base_price_set", "push_mappings_present"],
  },
  trace_id: "0a1b2c3d-4e5f-6789-abcd-ef0123456789",
};

// ───────────────────────────────────────────────────────────────────────────
// PC61 OPS push payload (returned when dry_run=true)
// ───────────────────────────────────────────────────────────────────────────

const PC61_CUSTOMER = "11111111-1111-1111-1111-111111111111";
const PC61_PRODUCT = "22222222-2222-2222-2222-222222222222";

const PC61_COMPUTED_PRICES: OPSComputedPrice[] = [
  {
    variant_sku: "PC61-NAV-S",
    color: "Navy",
    size: "S",
    sort_order: 1,
    base_price: 8.32,
    final_price: 12.48,
    markup_pct: 50,
    markup_amount: null,
    rounding: "penny",
  },
  {
    variant_sku: "PC61-NAV-M",
    color: "Navy",
    size: "M",
    sort_order: 2,
    base_price: 8.32,
    final_price: 12.48,
    markup_pct: 50,
    markup_amount: null,
    rounding: "penny",
  },
  {
    variant_sku: "PC61-NAV-L",
    color: "Navy",
    size: "L",
    sort_order: 3,
    base_price: 8.32,
    final_price: 12.48,
    markup_pct: 50,
    markup_amount: null,
    rounding: "penny",
  },
];

const PC61_PLAN: OPSMutationStep[] = [
  // Step 1: setProduct (no separate setProductCategory — category is on setProduct.input)
  {
    step: 1,
    mutation: "setProduct",
    source_key: "supplier_sku:PC61",
    variables: {
      input: {
        products_id: 0,
        products_title: "VG-Port & Company Essential Tee",
        products_internal_title: "PC61",
        category_name: "T-Shirts",
        visible: 1,
        products_description: "A customer favorite, this value-priced tee.",
        brand: "Port & Company",
        products_image: "https://www.sanmar.com/imgindex/PC61_NAVY_front.jpg",
      },
    },
    requires_response_from: [],
  },
  // Steps 2-4: setProductSize × 3 (one per variant)
  ...PC61_COMPUTED_PRICES.map((p, i): OPSMutationStep => ({
    step: 2 + i,
    mutation: "setProductSize",
    source_key: `variant_sku:${p.variant_sku}`,
    variables: {
      input: {
        product_size_id: 0,
        products_id: "$step1.products_id",
        size_name: p.size,
        color_name: p.color,
        products_sku: p.variant_sku,
        visible: 1,
      },
    },
    requires_response_from: [1],
  })),
  // Steps 5-7: setProductPrice × 3 (depends on matching size step)
  ...PC61_COMPUTED_PRICES.map((p, i): OPSMutationStep => ({
    step: 5 + i,
    mutation: "setProductPrice",
    source_key: `variant_sku:${p.variant_sku}`,
    variables: {
      input: {
        product_price_id: 0,
        products_id: "$step1.products_id",
        size_id: `$step${2 + i}.product_size_id`,
        qty: 1,
        qty_to: 999999,
        price: p.final_price,
        vendor_price: p.base_price,
        visible: "1",
      },
    },
    requires_response_from: [1, 2 + i],
  })),
  // Steps 8-10: updateProductStock × 3 (inventory LAST, action=Reset)
  ...PC61_COMPUTED_PRICES.map((p, i): OPSMutationStep => ({
    step: 8 + i,
    mutation: "updateProductStock",
    source_key: `variant_sku:${p.variant_sku}`,
    variables: {
      input: {
        action: "Reset",
        product_sku: p.variant_sku,
        stock_quantity: 250,
      },
    },
    requires_response_from: [1],
  })),
];

export const FIXTURE_OPS_PUSH_PAYLOAD: OPSPushPayload = {
  customer_id: PC61_CUSTOMER,
  product_id: PC61_PRODUCT,
  supplier_slug: "sanmar",
  supplier_sku: "PC61",
  push_mode: "create",
  option_strategy: "master_option_attach",
  existing_ops_product_id: null,
  computed_prices: PC61_COMPUTED_PRICES,
  markup_rule_id: "8f3a4b5c-6789-4def-9012-3456789abcde",
  plan: PC61_PLAN,
  primary_image_url: "https://www.sanmar.com/imgindex/PC61_NAVY_front.jpg",
  image_warnings: [],
  estimated_mutations: PC61_PLAN.length,
  built_at: "2026-05-13T10:00:00.000Z",
  ops_target: {
    base_url: "https://staging.visualgraphx.com",
    client_id_last4: "5678",
  },
};

// ───────────────────────────────────────────────────────────────────────────
// step_results (worker writes these as it walks the plan)
// ───────────────────────────────────────────────────────────────────────────

const _stepOk = (
  step: number,
  source_key: string,
  mutation: string,
  ops_ids: Record<string, unknown> = {},
): OPSStepResult => ({
  step,
  source_key,
  mutation,
  request_fingerprint: `f${step.toString(16).padStart(15, "0")}`,
  ops_ids,
  attempted_at: new Date(Date.now() - (PC61_PLAN.length - step) * 1200).toISOString(),
  status: "ok",
});

export const FIXTURE_STEP_RESULTS_DRY_RUN: OPSStepResult[] = [
  _stepOk(1, "supplier_sku:PC61", "setProduct", { products_id: 0 }),
  _stepOk(2, "variant_sku:PC61-NAV-S", "setProductSize", { product_size_id: 0 }),
  _stepOk(3, "variant_sku:PC61-NAV-M", "setProductSize", { product_size_id: 0 }),
  _stepOk(4, "variant_sku:PC61-NAV-L", "setProductSize", { product_size_id: 0 }),
  _stepOk(5, "variant_sku:PC61-NAV-S", "setProductPrice", { product_price_id: 0 }),
  _stepOk(6, "variant_sku:PC61-NAV-M", "setProductPrice", { product_price_id: 0 }),
  _stepOk(7, "variant_sku:PC61-NAV-L", "setProductPrice", { product_price_id: 0 }),
  _stepOk(8, "variant_sku:PC61-NAV-S", "updateProductStock", { stock_id: 0 }),
  _stepOk(9, "variant_sku:PC61-NAV-M", "updateProductStock", { stock_id: 0 }),
  _stepOk(10, "variant_sku:PC61-NAV-L", "updateProductStock", { stock_id: 0 }),
];

export const FIXTURE_STEP_RESULTS_PUSHED: OPSStepResult[] = [
  _stepOk(1, "supplier_sku:PC61", "setProduct", { products_id: 12345 }),
  _stepOk(2, "variant_sku:PC61-NAV-S", "setProductSize", { product_size_id: 901 }),
  _stepOk(3, "variant_sku:PC61-NAV-M", "setProductSize", { product_size_id: 902 }),
  _stepOk(4, "variant_sku:PC61-NAV-L", "setProductSize", { product_size_id: 903 }),
  _stepOk(5, "variant_sku:PC61-NAV-S", "setProductPrice", { product_price_id: 2001 }),
  _stepOk(6, "variant_sku:PC61-NAV-M", "setProductPrice", { product_price_id: 2002 }),
  _stepOk(7, "variant_sku:PC61-NAV-L", "setProductPrice", { product_price_id: 2003 }),
  _stepOk(8, "variant_sku:PC61-NAV-S", "updateProductStock", { stock_id: 3001 }),
  _stepOk(9, "variant_sku:PC61-NAV-M", "updateProductStock", { stock_id: 3002 }),
  _stepOk(10, "variant_sku:PC61-NAV-L", "updateProductStock", { stock_id: 3003 }),
];

export const FIXTURE_STEP_RESULTS_PARTIAL: OPSStepResult[] = [
  _stepOk(1, "supplier_sku:PC61", "setProduct", { products_id: 12345 }),
  _stepOk(2, "variant_sku:PC61-NAV-S", "setProductSize", { product_size_id: 901 }),
  _stepOk(3, "variant_sku:PC61-NAV-M", "setProductSize", { product_size_id: 902 }),
  {
    step: 4,
    source_key: "variant_sku:PC61-NAV-L",
    mutation: "setProductSize",
    request_fingerprint: "f0000000000000004",
    ops_ids: {},
    attempted_at: new Date(Date.now() - 1200).toISOString(),
    status: "failed",
  },
];

// ───────────────────────────────────────────────────────────────────────────
// Cleanup targets (populated when status='partial_failure')
// ───────────────────────────────────────────────────────────────────────────

export const FIXTURE_CLEANUP_TARGETS: CleanupTargets = {
  ops_product_id: 12345,
  product_size_ids: [901, 902],
  option_ids: [],
  attribute_ids: [],
  inventory_keys: [],
  instructions:
    "Halt-no-rollback: delete the partial OPS records from staging admin (products_id=12345, sizes 901+902) before retrying.",
};

// ───────────────────────────────────────────────────────────────────────────
// PushLog fixtures (terminal states)
// ───────────────────────────────────────────────────────────────────────────

const _base = {
  request_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  customer_id: PC61_CUSTOMER,
  product_id: PC61_PRODUCT,
  key_id: "n8n-vidhi-staging",
  idempotency_key: "sm-pc61-vg-20260513-001",
  payload_hash: "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
  supplier_slug: "sanmar",
  supplier_sku: "PC61",
  worker_id: null,
  lease_until: null,
  callback_url: "https://n8n.example.com/webhook/api-hub-push-complete",
  callback_next_attempt_at: null,
  retry_of: null,
  created_at: "2026-05-13T10:00:00.000Z",
};

export const FIXTURE_PUSH_LOG_DRY_RUN_PUSHED: PushLog = {
  ..._base,
  id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
  status: "dry_run_pushed",
  dry_run: true,
  ops_product_id: null,
  error: null,
  step_results: FIXTURE_STEP_RESULTS_DRY_RUN,
  cleanup_targets: null,
  callback_status: "not_requested",
  callback_attempts: 0,
  callback_url: null,
  finished_at: new Date(Date.now() - 5000).toISOString(),
};

export const FIXTURE_PUSH_LOG_PUSHED: PushLog = {
  ..._base,
  id: "11111111-2222-3333-4444-555555555555",
  status: "pushed",
  dry_run: false,
  ops_product_id: "12345",
  error: null,
  step_results: FIXTURE_STEP_RESULTS_PUSHED,
  cleanup_targets: null,
  callback_status: "sent",
  callback_attempts: 1,
  finished_at: new Date(Date.now() - 5000).toISOString(),
};

export const FIXTURE_PUSH_LOG_FAILED: PushLog = {
  ..._base,
  id: "ffffffff-ffff-ffff-ffff-ffffffffffff",
  status: "partial_failure",
  dry_run: false,
  ops_product_id: "12345",
  error: "GraphQL error on setProductSize (variant PC61-NAV-L): duplicate size key",
  step_results: FIXTURE_STEP_RESULTS_PARTIAL,
  cleanup_targets: FIXTURE_CLEANUP_TARGETS,
  callback_status: "sent",
  callback_attempts: 1,
  finished_at: new Date(Date.now() - 3000).toISOString(),
};

export const FIXTURE_PUSH_LOG_PROCESSING: PushLog = {
  ..._base,
  id: "99999999-9999-9999-9999-999999999999",
  status: "processing",
  dry_run: false,
  ops_product_id: null,
  error: null,
  step_results: FIXTURE_STEP_RESULTS_PARTIAL.slice(0, 2),
  cleanup_targets: null,
  callback_status: "pending",
  callback_attempts: 0,
  worker_id: "integration-gateway-worker-1",
  lease_until: new Date(Date.now() + 60_000).toISOString(),
  finished_at: null,
};

export const FIXTURE_PUSH_LOG_REJECTED: PushLog = {
  ..._base,
  id: "44444444-4444-4444-4444-444444444444",
  status: "rejected",
  dry_run: false,
  ops_product_id: null,
  error: "Preflight blocker: 2 variants missing base_price",
  step_results: [],
  cleanup_targets: null,
  callback_status: "not_requested",
  callback_attempts: 0,
  callback_url: null,
  finished_at: new Date(Date.now() - 1000).toISOString(),
};

// ───────────────────────────────────────────────────────────────────────────
// Gateway responses
// ───────────────────────────────────────────────────────────────────────────

export const FIXTURE_PUSH_TERMINAL_DRY_RUN: PushTerminalResponse = {
  push_log_id: FIXTURE_PUSH_LOG_DRY_RUN_PUSHED.id,
  status: "dry_run_pushed",
  customer_id: PC61_CUSTOMER,
  supplier_slug: "sanmar",
  supplier_sku: "PC61",
  ops_product_id: null,
  mapping_id: null,
  error: null,
  step_results: FIXTURE_STEP_RESULTS_DRY_RUN,
  cleanup_targets: null,
  callback_status: "not_requested",
  callback_attempts: 0,
  finished_at: FIXTURE_PUSH_LOG_DRY_RUN_PUSHED.finished_at ?? null,
  plan: FIXTURE_OPS_PUSH_PAYLOAD,
};

export const FIXTURE_PUSH_TERMINAL_PUSHED: PushTerminalResponse = {
  push_log_id: FIXTURE_PUSH_LOG_PUSHED.id,
  status: "pushed",
  customer_id: PC61_CUSTOMER,
  supplier_slug: "sanmar",
  supplier_sku: "PC61",
  ops_product_id: "12345",
  mapping_id: "abcdef00-1111-2222-3333-444444444444",
  error: null,
  step_results: FIXTURE_STEP_RESULTS_PUSHED,
  cleanup_targets: null,
  callback_status: "sent",
  callback_attempts: 1,
  finished_at: FIXTURE_PUSH_LOG_PUSHED.finished_at ?? null,
};

export const FIXTURE_PUSH_ACCEPTED: PushAcceptedResponse = {
  push_log_id: FIXTURE_PUSH_LOG_PROCESSING.id,
  status: "queued",
  customer_id: PC61_CUSTOMER,
  supplier_slug: "sanmar",
  supplier_sku: "PC61",
  ops_product_id: null,
  dry_run: false,
  callback_status: "pending",
  created_at: FIXTURE_PUSH_LOG_PROCESSING.created_at,
  links: { self: `/api/integrations/v1/push-requests/${FIXTURE_PUSH_LOG_PROCESSING.id}` },
};

// Integration-key fixtures intentionally removed — the canonical
// admin UI for integration keys is Vidhi's `/integrations` page, which
// talks to the real backend. No mock fixtures needed here.
