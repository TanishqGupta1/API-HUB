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
export interface Variant {
  id: string;
  color: string | null;
  size: string | null;
  sku: string | null;
  base_price: number | null;
  inventory: number | null;
  warehouse: string | null;
}

export interface Product {
  id: string;
  supplier_id: string;
  supplier_name: string;
  supplier_sku: string;
  product_name: string;
  brand: string | null;
  description: string | null;
  product_type: string;
  image_url: string | null;
  last_synced: string | null;
  variants: Variant[];
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
  product_type: string;
  image_url: string | null;
  variant_count: number;
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
  finished_at: string | null;
  records_processed: number;
  error_log: string | null;
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
