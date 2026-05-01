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
  auth_config: Record<string, string>;
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
  created_at: string;
  products_pushed: number;
  markup_rules_count: number;
}

/* ─── Markup Rules ───────────────────────────────────────────────────────── */
export interface MarkupRule {
  id: string;
  customer_id: string;
  scope: string;
  markup_pct: number;
  min_margin: number | null;
  rounding: string;
  priority: number;
  created_at: string;
}

export interface MarkupRuleCreate {
  customer_id: string;
  scope: string;
  markup_pct: number;
  min_margin?: number | null;
  rounding: string;
  priority: number;
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
  started_at: string;
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
