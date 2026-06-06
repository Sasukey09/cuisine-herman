// Shared API types mirroring the FastAPI backend schemas.
// Feature-specific types are added to this file as modules are built.

export interface AuthTokens {
  access_token: string;
  token_type: string;
  refresh_token?: string | null;
}

export interface User {
  id: string;
  email: string;
  name?: string | null;
  tenant_id: string;
}

export interface Me extends User {
  roles: string[];
}

export interface RegisterPayload {
  email: string;
  password: string;
  org_name: string;
  name?: string;
}

export interface CreateUserPayload {
  email: string;
  password: string;
  name?: string;
  role: string;
}

export interface ApiError {
  detail?: string | { msg: string }[];
}

// --- Products --------------------------------------------------------------

export interface Product {
  id: string;
  name: string;
  sku?: string | null;
  base_unit_id?: number | null;
}

export interface ProductPayload {
  name: string;
  sku?: string | null;
  base_unit_id?: number | null;
}

export type ProductUpdatePayload = Partial<ProductPayload>;

// --- Suppliers -------------------------------------------------------------

export interface SupplierContact {
  email?: string;
  phone?: string;
  [key: string]: unknown;
}

export interface Supplier {
  id: string;
  name: string;
  code?: string | null;
  contact?: SupplierContact | null;
}

export interface SupplierPayload {
  name: string;
  code?: string | null;
  contact?: SupplierContact | null;
}

export type SupplierUpdatePayload = Partial<SupplierPayload>;

export interface SupplierPrice {
  id: string;
  product_id: string | null;
  product_name: string | null;
  price: number | null;
  currency: string | null;
  unit_id: number | null;
  effective_date: string | null;
  source_invoice_line_id: string | null;
}

// --- Invoices --------------------------------------------------------------

export interface Invoice {
  id: string;
  invoice_number?: string | null;
  date?: string | null;
  total_amount?: number | null;
  currency?: string | null;
  parsed?: boolean | null;
  ocr_status?: string | null;
  supplier_id?: string | null;
  created_at?: string | null;
}

export interface InvoiceLine {
  id: string;
  product_id?: string | null;
  description?: string | null;
  qty?: number | null;
  unit_id?: number | null;
  unit_price?: number | null;
  line_total?: number | null;
  match_confidence?: number | null;
}

export interface InvoiceProcessSummary {
  invoice_id: string;
  lines: number;
  matched: number;
  prices_created: number;
  needs_review: string[];
}

export interface InvoiceIngestResult {
  invoice_id: string;
  summary: InvoiceProcessSummary;
}

export interface MapProductResult {
  line_id: string;
  product_id: string;
  price_id: string | null;
}

// --- Recipes ---------------------------------------------------------------

export interface Recipe {
  id: string;
  name: string;
  yield_qty?: number | null;
  current_version_id?: string | null;
  yield_unit_id?: number | null;
}

export interface RecipePayload {
  name: string;
  yield_qty?: number | null;
}

export interface RecipeIngredient {
  id?: string;
  product_id: string;
  qty?: number | null;
  unit_id?: number | null;
  qty_normalized?: number | null;
  loss_pct?: number | null;
  yield_pct?: number | null;
  prep_notes?: string | null;
}

export interface RecipeVersion {
  id: string;
  recipe_id: string;
  version_number: number;
  notes?: string | null;
  is_published: boolean;
  ingredients: RecipeIngredient[];
}

export interface RecipeVersionPayload {
  notes?: string | null;
  is_published?: boolean;
  ingredients: RecipeIngredient[];
}

export interface ComputeCostRequest {
  selling_price?: number | null;
  as_of?: string | null;
}

export interface CostLine {
  product_id: string | null;
  qty_base: number | null;
  unit_price: number | null;
  line_cost: number | null;
  price_id: string | null;
  missing_price: boolean;
}

export interface RecipeCost {
  recipe_version_id: string;
  computed_cost_total: number | null;
  cost_per_portion: number | null;
  food_cost_pct: number | null;
  margin_estimated: number | null;
  has_missing_prices: boolean;
  snapshot_id?: string | null;
  breakdown: CostLine[];
}

// --- Dashboard -------------------------------------------------------------

export interface CostTrendPoint {
  computed_at: string | null;
  recipe_id: string;
  recipe_name: string | null;
  recipe_version_id: string;
  computed_cost_total: number | null;
  cost_per_portion: number | null;
  food_cost_pct: number | null;
}

export interface TopProduct {
  product_id: string;
  name: string | null;
  total_spend: number;
  total_qty: number;
  line_count: number;
}

export interface PriceTrendPoint {
  effective_date: string | null;
  price: number | null;
  currency: string | null;
  supplier_id: string | null;
}

export interface MarginAlert {
  recipe_id: string;
  recipe_name: string | null;
  recipe_version_id: string;
  cost_per_portion: number | null;
  food_cost_pct: number | null;
  computed_at: string | null;
}

export interface PriceAlert {
  product_id: string;
  product_name: string | null;
  previous_price: number | null;
  latest_price: number | null;
  change_pct: number | null;
  currency: string | null;
  effective_date: string | null;
  supplier_id: string | null;
}

export interface DashboardFilters {
  from?: string;
  to?: string;
}
