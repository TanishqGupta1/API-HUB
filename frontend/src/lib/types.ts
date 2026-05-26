/* ────────────────────────────────────────────────────────────────────────── *
 * API-HUB  —  Shared TypeScript Types                                       *
 * Mirrors the Pydantic schemas in backend/modules/{module}/schemas.py       *
 * ────────────────────────────────────────────────────────────────────────── */

/* ─── Supplier ───────────────────────────────────────────────────────────── */
export interface Supplier {
  id: string;
  name: string;
  slug: string;
  protocol: string;
  promostandards_code: string | null;
  base_url: string | null;
  adapter_class: string | null;
  has_credentials: boolean;
  field_mappings: Record<string, string> | null;
  is_active: boolean;
  created_at: string;
  product_count: number;
}

export interface SupplierCreate {
  name: string;
  slug: string;
  protocol: string;
  promostandards_code?: string | null;
  base_url?: string | null;
  adapter_class?: string | null;
  auth_config?: Record<string, string>;
}

/* ─── PromoStandards Directory ───────────────────────────────────────────── */
export interface PSCompany {
  Code: string;
  Name: string;
  Type: string;
}

export interface PSEndpoint {
  Name: string | null;
  ServiceType: string | null;
  Version: string | null;
  Status: string | null;
  ProductionURL: string | null;
  TestURL: string | null;
}

/* ─── Product Catalog ────────────────────────────────────────────────────── */
export interface VariantPriceTier {
  group_name: string;
  qty_min: number;
  qty_max: number;
  price: string;        // backend returns Decimal as string for precision
  currency: string;
  effective_from?: string | null;
  effective_to?: string | null;
}

export interface Variant {
  id: string;
  color: string | null;
  size: string | null;
  sku: string | null;
  base_price: number | null;
  inventory: number | null;
  warehouse: string | null;
  part_id: string | null;
  gtin: string | null;
  flags: Record<string, unknown> | null;   // pms_color, standard_color, label_size, weight_oz
  prices: VariantPriceTier[];
}

export interface ApparelDetails {
  ps_part_id: string | null;
  apparel_style: string | null;
  is_closeout: boolean;
  is_hazmat: boolean | null;
  is_caution: boolean;
  caution_comment: string | null;
  is_on_demand: boolean | null;
  fabric_specs: Record<string, unknown> | null;
  fob_points: Array<Record<string, unknown>> | null;
  keywords: string[] | null;
}

export interface PrintDetails {
  ops_product_id_int: number | null;
  default_category_id: number | null;
  external_catalogue: number | null;
  width_min: string | null;
  width_max: string | null;
  height_min: string | null;
  height_max: string | null;
  formula: Record<string, unknown> | null;
  size_template_id: number | null;
}

export interface ProductSize {
  id: string;
  ops_size_id: number | null;
  size_title: string;
  size_width: string;
  size_height: string;
  width_min: string | null;
  width_max: string | null;
  height_min: string | null;
  height_max: string | null;
  sort_order: number;
}

export type ProductType = "apparel" | "print" | "template" | "promo";
export type PricingMethod = "tiered_variants" | "formula";

export interface ProductImage {
  id: string;
  url: string;
  image_type: string;
  color: string | null;
  sort_order: number;
}

export interface ProductOptionAttribute {
  id: string;
  title: string;
  sort_order: number;
  ops_attribute_id: number | null;
}

export interface ProductOption {
  id: string;
  option_key: string;
  title: string;
  options_type: string | null;
  sort_order: number;
  master_option_id: number | null;
  ops_option_id: number | null;
  required: boolean;
  attributes: ProductOptionAttribute[];
}

export interface Product {
  id: string;
  supplier_id: string;
  supplier_name: string;
  supplier_slug: string | null;
  supplier_has_decoration_overlay: boolean;
  supplier_sku: string;
  product_name: string;
  brand: string | null;
  category: string | null;
  category_id: string | null;
  description: string | null;
  product_type: ProductType;
  pricing_method: PricingMethod | null;
  image_url: string | null;
  ops_product_id: string | null;
  external_catalogue: number | null;
  last_synced: string | null;
  archived_at: string | null;
  variants: Variant[];
  images: ProductImage[];
  options: ProductOption[];
  apparel_details: ApparelDetails | null;
  print_details: PrintDetails | null;
  sizes: ProductSize[];
}

export interface VariantPreview {
  sku: string | null;
  size: string | null;
  color: string | null;
  price: number | null;
  inventory: number | null;
}

export interface ProductPreview {
  id: string;
  title: string;
  description: string | null;
  brand: string | null;
  category: string | null;
  images: ProductImage[];
  variants: VariantPreview[];
  missing_fields: string[];
}

export interface ProductPushStatus {
  customer_id: string;
  customer_name: string;
  status: "pushed" | "failed" | "not_pushed";
  pushed_at: string | null;
  ops_product_id: string | null;
}

export interface ProductListItem {
  id: string;
  supplier_id: string;
  supplier_name: string;
  supplier_sku: string;
  product_name: string;
  brand: string | null;
  category_id: string | null;
  product_type: ProductType;
  pricing_method: PricingMethod | null;
  image_url: string | null;
  ops_product_id: string | null;
  external_catalogue: number | null;
  variant_count: number;
  price_min: number | null;
  price_max: number | null;
  total_inventory: number | null;
  archived_at: string | null;
}

/* ─── Pricing Quote ───────────────────────────────────────────────────────── */
export interface PriceQuoteRequest {
  product_id: string;
  variant_id?: string;
  width?: number;
  height?: number;
  qty: number;
  selected_attribute_ids?: string[];
}

export interface PriceQuote {
  unit_price: string;
  total: string;
  currency: string;
  breakdown: Record<string, unknown>;
}

/* ─── Category (hierarchical) ────────────────────────────────────────────── */
export interface Category {
  id: string;
  supplier_id: string;
  external_id: string;
  name: string;
  parent_id: string | null;
  sort_order: number;
}

/* ─── Supplier Category Browse (for import picker) ───────────────────────── */
export interface SupplierCategoryBrowse {
  name: string;
  slug: string | null;
  product_count: number | null;
  preview_image_url: string | null;
}

export interface ImportCategoryResponse {
  job_id: string;
  status: string;
  category_name: string;
  limit: number;
}

/* ─── Customer ───────────────────────────────────────────────────────────── */
export interface Customer {
  id: string;
  name: string;
  ops_base_url: string;
  ops_token_url: string;
  ops_client_id: string;
  is_active: boolean;
  logo_url: string | null;
  created_at: string;
  products_pushed: number;
  markup_rules_count: number;
}

/* ─── Markup Rules ───────────────────────────────────────────────────────── */
export interface MarkupRule {
  id: string;
  customer_id: string;
  scope: string;
  markup_pct: number | null;
  markup_amount: number | null;
  min_margin: number | null;
  min_price: number | null;
  max_price: number | null;
  rounding: string;
  priority: number;
  is_active: boolean;
  effective_from: string | null;
  effective_until: string | null;
  created_at: string;
}

export interface MarkupRuleCreate {
  customer_id: string;
  scope: string;
  markup_pct?: number | null;
  markup_amount?: number | null;
  min_margin?: number | null;
  min_price?: number | null;
  max_price?: number | null;
  rounding: string;
  priority: number;
  is_active?: boolean;
  effective_from?: string | null;
  effective_until?: string | null;
}

/* ─── Sync Jobs ──────────────────────────────────────────────────────────── */
export type SyncStatus = "pending" | "running" | "completed" | "failed";
export type JobType = "full" | "delta" | "inventory" | "pricing" | "images";

export interface SyncJob {
  id: string;
  supplier_id: string;
  supplier_name: string;
  job_type: JobType;
  status: SyncStatus;
  started_at: string | null;
  completed_at: string | null;
  total_products: number;
  success_count: number;
  failed_count: number;
  records_processed: number;
  error_log: string | null;
  discovery_mode: string | null;
}

/* ─── Dashboard Stats ────────────────────────────────────────────────────── */
export interface Stats {
  suppliers: number;
  products: number;
  variants: number;
  customers?: number;
}

/* ─── Field Mapping ──────────────────────────────────────────────────────── */
export interface FieldMapping {
  source_field: string;
  target_field: string;
  transform: string | null;
}

/* ─── Push Log ───────────────────────────────────────────────────────────── */
export interface ProductPushLogRead {
  id: string;
  product_id: string;
  product_name: string | null;
  customer_id: string;
  customer_name: string | null;
  supplier_name: string | null;
  ops_product_id: string | null;
  status: "pushed" | "failed" | "skipped";
  error: string | null;
  pushed_at: string;
}

/* ─── Master Options ─────────────────────────────────────────────────────── */
export interface MasterOptionAttribute {
  id: string;
  ops_attribute_id: number;
  title: string;
  sort_order: number;
  default_price: number | null;
}

export interface MasterOption {
  id: string;
  ops_master_option_id: number;
  title: string;
  option_key: string | null;
  options_type: string | null;
  pricing_method: string | null;
  status: number;
  sort_order: number;
  description: string | null;
  master_option_tag: string | null;
  attributes: MasterOptionAttribute[];
}

export interface MasterOptionsSyncStatus {
  total: number;
  last_synced_at: string | null;
}

/* Per-product config */
export interface AttributeConfigItem {
  attribute_id: string | null;
  ops_attribute_id: number;
  title: string;
  attribute_key: string | null;
  enabled: boolean;
  price: number;
  numeric_value: number;
  sort_order: number;
}

/* Phase 6 — customer-curated catalog selections.
 *
 * Status vocabulary widened from the original 4 values (Phase 6 selection
 * UI) to the 11-value gateway vocab so the same field can carry Phase 8
 * push states. Canonical metadata + lookup helpers live in
 * `frontend/src/lib/push-status.ts` (T4). */
export type SelectionStatus =
  | "selected"
  | "accepted"
  | "queued"
  | "processing"
  | "pushed"
  | "failed"
  | "partial_failure"
  | "rejected"
  | "canceled"
  | "dry_run_pushed"
  | "stale";

export interface CustomerProductSelection {
  id: string;
  customer_id: string;
  product_id: string;
  status: SelectionStatus;
  added_at: string;
  pushed_at: string | null;

  // Embedded product fields (saves an extra fetch on the catalog page)
  supplier_id: string;
  supplier_slug: string | null;
  supplier_sku: string;
  product_name: string;
  product_type: string;
  image_url: string | null;
  ops_product_id: string | null;
  last_synced: string | null;

  // Decoration visibility
  supplier_has_decoration_overlay: boolean;
  decoration_ready: boolean;
}

export interface SelectionBulkResponse {
  added: number;
  already_selected: number;
  not_found: number;
}

export interface OptionConfigItem {
  master_option_id: string;
  ops_master_option_id: number;
  title: string;
  option_key: string | null;
  options_type: string | null;
  master_option_tag: string | null;
  enabled: boolean;
  attributes: AttributeConfigItem[];
}

/* ─── Phase 8 — Decorations & Branding ───────────────────────────────────── */
export interface DecorationOption {
  type: "logo" | "text";
  url?: string;
  text?: string;
  position_x: number;  // 0-100 percentage
  position_y: number;  // 0-100 percentage
  scale: number;       // 0.1 - 2.0
  rotation: number;    // 0-360
  layer: number;
}

export interface ProductDecoration {
  customer_id: string;
  product_id: string;
  decoration_options: DecorationOption[];
  updated_at: string;
}

/* ─── Phase 8 — SanMar → OPS Staging Push (Beta) ───────────────────────────
 * Types mirror the spec at
 * `docs/superpowers/specs/2026-05-08-sanmar-ops-staging-push-design.md`.
 * Locked status vocab + JSONB shapes — UI must match exactly so the
 * admin/operator views stay consistent with backend payloads.
 */

/* ─────────────────────────────────────────────────────────────────────────── *
 *  Integration Gateway (M0–M5)                                               *
 *                                                                            *
 *  Mirrors `docs/superpowers/specs/2026-05-11-integration-gateway-design.md` *
 *  Rev 1+2+3. Replaces the prior VPCE preview/execute pair with a single    *
 *  POST /api/integrations/v1/push-requests + Idempotency-Key + payload_hash.*
 * ─────────────────────────────────────────────────────────────────────────── */

/** Persisted product_push_log.status (spec §"Status vocabulary"). */
export type PushStatus =
  | "queued"            // durable row reserved; awaiting worker claim
  | "processing"        // worker actively calling OPS
  | "pushed"            // OPS confirmed; push_mappings written
  | "failed"            // hard failure before any OPS writes
  | "partial_failure"   // some OPS steps succeeded; cleanup_targets populated
  | "rejected"          // preflight blocker or policy rejection
  | "canceled"          // operator-initiated cancel
  | "dry_run_pushed";   // dry_run=true ran cleanly through FakeOpsClient

/** product_push_log.callback_status (spec §"Status vocabulary"). */
export type CallbackStatus =
  | "not_requested"
  | "pending"
  | "sent"
  | "failed";

/** Option-attach strategy chosen once per customer (spec §"Preflight gates"). */
export type OptionStrategy = "master_option_attach" | "product_local_option_create";

export interface PreflightCheck {
  name: string;
  ok: boolean;
  detail: string;
  /** Field path to fix; populated only when ok=false. */
  field?: string | null;
  /** One-line operator hint; populated only when ok=false. */
  suggestion?: string | null;
}

export interface PreflightResult {
  checks: PreflightCheck[];
  blockers: string[];
  warnings: PreflightCheck[];
  computed_at: string;
}

/** Gateway error envelope (spec §"Error envelope"). */
export interface GatewayErrorEnvelope {
  status: "error";
  code:
    | "BAD_SIGNATURE"
    | "KEY_NOT_ALLOWED"
    | "KEY_REVOKED"
    | "UNKNOWN_REF"
    | "IDEMPOTENCY_CONFLICT"
    | "IN_FLIGHT"
    | "PREFLIGHT_BLOCKER"
    | "RATE_LIMITED"
    | "OPS_UPSTREAM_ERROR"
    | "CALLBACK_HOST_NOT_ALLOWED";
  message: string;
  details: Record<string, unknown> & {
    field?: string;
    suggestion?: string;
    blockers?: string[];
  };
  trace_id: string | null;
}

/** One OPS mutation in the push plan (spec §"OPS auth flow and outbound mutation contract"). */
export interface OPSMutationStep {
  step: number;
  mutation: string;
  /** Stable lookup key for step_results recovery */
  source_key: string;
  variables: Record<string, unknown>;
  requires_response_from: number[];
}

export interface OPSComputedPrice {
  variant_sku: string;
  color: string | null;
  size: string | null;
  sort_order: number;
  base_price: number;
  final_price: number;
  markup_pct: number | null;
  markup_amount: number | null;
  rounding: string;
}

/** Returned from POST /push-requests when dry_run=true and surfaced in the UI dry-run preview panel. */
export interface OPSPushPayload {
  customer_id: string;
  product_id: string;
  supplier_slug: string;
  supplier_sku: string;
  push_mode: "create" | "update";
  option_strategy: OptionStrategy;
  existing_ops_product_id: number | null;
  computed_prices: OPSComputedPrice[];
  markup_rule_id: string | null;
  plan: OPSMutationStep[];
  primary_image_url: string | null;
  image_warnings: string[];
  estimated_mutations: number;
  built_at: string;
  ops_target: {
    base_url?: string;
    client_id_last4?: string;
  };
}

/** Append-only entry written by the worker to product_push_log.step_results JSONB. */
export interface OPSStepResult {
  /** Sequential step index (always a number — backend StepResultOut uses int). */
  step: number;
  source_key?: string | null;
  mutation: string;
  request_fingerprint?: string | null;
  ops_ids?: Record<string, unknown> | null;
  attempted_at?: string | null;
  status?: "ok" | "failed" | null;
  /** Derived boolean — true when status === "ok". */
  ok?: boolean;
  error?: string | null;
  latency_ms?: number | null;
}

/** Opaque JSONB shape; spec leaves the contents flexible. */
export interface CleanupTargets {
  ops_product_id?: number | null;
  product_size_ids?: number[];
  option_ids?: number[];
  attribute_ids?: number[];
  inventory_keys?: string[];
  /** Legacy shape — older fixtures may still set these. */
  category_ids?: number[];
  size_ids?: number[];
  price_ids?: number[];
  product_id?: number | null;
  instructions?: string;
  [extra: string]: unknown;
}

/**
 * product_push_log row (spec §"Expand product_push_log" — 15 columns added in M0).
 *
 * `id` is the public `push_log_id`. `request_id` is a server-generated UUID
 * for tracing; never confused with `idempotency_key` which comes from the
 * caller's header.
 */
export interface PushLog {
  id: string;
  request_id: string;
  customer_id: string;
  product_id: string;
  /** FK to integration_keys.id when push came via the gateway. */
  key_id: string | null;
  idempotency_key: string | null;
  payload_hash: string | null;
  supplier_slug: string | null;
  supplier_sku: string | null;
  status: PushStatus;
  dry_run: boolean;
  ops_product_id: string | null;
  error: string | null;
  step_results: OPSStepResult[];
  cleanup_targets: CleanupTargets | null;
  /** Worker lease metadata (spec §"Worker lease, heartbeat, and reclaim"). */
  worker_id: string | null;
  lease_until: string | null;
  /** Callback (webhook) tracking. */
  callback_url: string | null;
  callback_status: CallbackStatus;
  callback_attempts: number;
  callback_next_attempt_at: string | null;
  /** Retry chain — if this push is a retry of another, points at the prior id. */
  retry_of: string | null;
  created_at: string;
  /** Optional finished_at for terminal-state rendering. */
  finished_at?: string | null;
}

/**
 * Request body for POST /api/integrations/v1/push-requests
 * (spec §"Push request envelope").
 */
export interface PushRequestBody {
  target: { system: "ops"; customer_id: string };
  source: { supplier_slug: string };
  /** Either product_ref OR product inline; never both. Supply product_id OR supplier_sku. */
  product_ref?: { product_id?: string; supplier_sku?: string };
  product?: Record<string, unknown>; // ProductIngest shape
  decorations?: Array<{
    placement: string;
    method: string;
    price_addition: string;
  }>;
  dry_run: boolean;
  callback?: {
    url: string;
    secret?: string;
  };
}

/** Response (sync-sized push that finished within long-poll window). */
export interface PushTerminalResponse {
  push_log_id: string;
  status: PushStatus;
  customer_id: string;
  supplier_slug: string;
  supplier_sku: string;
  ops_product_id: string | null;
  mapping_id: string | null;
  error: string | null;
  step_results: OPSStepResult[];
  cleanup_targets: CleanupTargets | null;
  callback_status: CallbackStatus;
  callback_attempts: number;
  finished_at: string | null;
  /** When dry_run=true, the dry-run plan that ran through FakeOpsClient. */
  plan?: OPSPushPayload;
}

/** Response (202 — async or long-poll deadline elapsed). */
export interface PushAcceptedResponse {
  push_log_id: string;
  status: "queued" | "processing";
  customer_id: string;
  supplier_slug: string;
  supplier_sku: string;
  ops_product_id: null;
  dry_run: boolean;
  callback_status: CallbackStatus;
  created_at: string;
  links: {
    self: string;
  };
}

export type PushRequestResponse = PushTerminalResponse | PushAcceptedResponse;

// `IntegrationKey` and related types intentionally live in Vidhi's
// `frontend/src/app/(admin)/integrations/page.tsx` (the canonical admin
// UI for integration-key CRUD). Duplicate types were removed when the
// duplicate `/integrations/keys/page.tsx` page was deleted.
