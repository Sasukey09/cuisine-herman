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
  category?: string | null;
  unit?: string | null;
  vat_rate?: number | null;
}

// --- Product detail tabs (Phase 2) ----------------------------------------

export interface ProductSupplierRow {
  supplier_id: string;
  supplier_name?: string | null;
  last_cost?: number | null;
  avg_cost?: number | null;
  best_cost?: number | null;
  unit_code?: string | null;
  currency?: string | null;
  last_purchase_date?: string | null;
  available?: boolean;
  preferred?: boolean;
  supplier_sku?: string | null;
  pack_size?: string | null;
  lead_time_days?: number | null;
  link_id?: string | null;
  is_cheapest?: boolean;
}

export interface ProductSuppliersResponse {
  product_id: string;
  suppliers: ProductSupplierRow[];
  cheapest_supplier_id?: string | null;
}

export interface ProductSupplierPayload {
  supplier_id: string;
  supplier_sku?: string | null;
  pack_size?: string | null;
  available?: boolean;
  preferred?: boolean;
  lead_time_days?: number | null;
  notes?: string | null;
}

export type ProductSupplierUpdatePayload = Partial<Omit<ProductSupplierPayload, "supplier_id">>;

export interface ProductInvoiceRow {
  invoice_id: string;
  invoice_number?: string | null;
  date?: string | null;
  supplier_name?: string | null;
  total_amount?: number | null;
  currency?: string | null;
  qty: number;
  line_total: number;
  lines: number;
}

export interface ProductRecipeRow {
  recipe_id: string;
  name: string;
  ingredient_name?: string | null;
  qty?: number | null;
  unit?: string | null;
}

export interface ProductRow {
  id: string;
  name: string;
  sku?: string | null;
  category?: string | null;
  unit?: string | null;
  last_cost?: number | null;
  currency?: string | null;
  supplier?: string | null;
  variation_pct?: number | null;
}

export interface ProductPayload {
  name: string;
  sku?: string | null;
  base_unit_id?: number | null;
  /** A taxonomy category name; omit/null to auto-classify from the name. */
  category?: string | null;
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
  rating?: number | null;
}

export interface SupplierRow {
  id: string;
  name: string;
  code?: string | null;
  contact?: SupplierContact | null;
  rating?: number | null;
  product_count: number;
}

export interface SupplierPayload {
  name: string;
  code?: string | null;
  contact?: SupplierContact | null;
  rating?: number | null;
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

// --- Smart invoice import (Phase 3) ---------------------------------------

export interface InvoicePreviewLineData {
  description: string;
  qty?: number | null;
  unit?: string | null;
  unit_price?: number | null;
  line_total?: number | null;
  vat_rate?: number | null;
  matched_product_id?: string | null;
  matched_product_name?: string | null;
  match_confidence?: number | null;
  needs_review: boolean;
  suggested_category?: string | null;
}

export interface InvoicePreviewResult {
  supplier?: string | null;
  supplier_id?: string | null;
  date?: string | null;
  invoice_number?: string | null;
  total_amount?: number | null;
  lines: InvoicePreviewLineData[];
}

export interface InvoiceConfirmLineData {
  description: string;
  qty?: number | null;
  unit?: string | null;
  unit_price?: number | null;
  line_total?: number | null;
  vat_rate?: number | null;
  action: "create" | "associate" | "skip";
  product_id?: string | null;
  category?: string | null;
}

export interface InvoiceConfirmRequest {
  supplier?: string | null;
  supplier_id?: string | null;
  date?: string | null;
  invoice_number?: string | null;
  total_amount?: number | null;
  currency?: string | null;
  lines: InvoiceConfirmLineData[];
}

// --- Recipes ---------------------------------------------------------------

export interface Recipe {
  id: string;
  name: string;
  yield_qty?: number | null;
  selling_price?: number | null;
  current_version_id?: string | null;
  yield_unit_id?: number | null;
}

export interface RecipeRow {
  id: string;
  name: string;
  yield_qty: number | null;
  selling_price: number | null;
  cost_per_portion: number | null;
  food_cost_pct: number | null;
  margin_pct: number | null;
  has_missing_prices: boolean;
  defined: boolean;
}

export interface RecipePayload {
  name: string;
  yield_qty?: number | null;
  selling_price?: number | null;
}

export interface RecipeIngredient {
  id?: string;
  product_id: string | null;
  ingredient_name?: string | null;
  qty?: number | null;
  unit_id?: number | null;
  qty_normalized?: number | null;
  loss_pct?: number | null;
  yield_pct?: number | null;
  prep_notes?: string | null;
}

export interface RecipeInstruction {
  id?: string;
  step_number: number;
  content: string;
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

export interface LossMakingDish {
  recipe_id: string;
  name: string;
  cost_per_portion: number | null;
  selling_price: number | null;
  loss_per_portion?: number;
  food_cost_pct?: number | null;
}

export interface LossReport {
  losing_money: LossMakingDish[];
  loss_per_portion_total: number;
  no_selling_price: LossMakingDish[];
  not_costable: LossMakingDish[];
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

export interface AIChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AIToolCall {
  name: string;
  input: Record<string, unknown>;
}

export interface AIChatResponse {
  reply: string;
  tool_calls: AIToolCall[];
  usage: { input_tokens: number; output_tokens: number } | null;
  conversation_id: string | null;
}

export interface AIConversation {
  id: string;
  title: string | null;
  updated_at: string | null;
}

export interface AIStoredMessage {
  role: "user" | "assistant";
  content: string;
  created_at: string | null;
}

export interface AIConversationDetail extends AIConversation {
  messages: AIStoredMessage[];
}

export interface VideoIngredientDraft {
  name: string;
  qty: number | null;
  unit: string | null;
}

export interface VideoRecipeDraft {
  name: string;
  yield_qty: number | null;
  ingredients: VideoIngredientDraft[];
  steps: string[];
  summary: string | null;
}

export interface VideoExtractResult {
  source_id: string;
  platform: string;
  transcript_source: string;
  transcript_excerpt: string;
  draft: VideoRecipeDraft;
  note: string;
}

export interface VideoSaveResult {
  recipe_id: string;
  version_id: string;
  name: string;
  yield_qty: number;
  unmatched_ingredients: string[];
  cost: {
    computed_cost_total: number | null;
    cost_per_portion: number | null;
    food_cost_pct: number | null;
    has_missing_prices: boolean;
  };
  note: string;
}

// --- Recipe import from PDF ------------------------------------------------
export interface RecipeImportIngredient {
  name: string;
  quantity: number | null;
  unit: string | null;
  matched_product_id: string | null;
  matched_product_name: string | null;
  match_confidence: number | null;
  unit_recognized: boolean;
}

export interface RecipeImportCost {
  computed_cost_total: number | null;
  cost_per_portion: number | null;
  food_cost_pct: number | null;
  margin_estimated: number | null;
  has_missing_prices: boolean;
}

export interface RecipeImportPreview {
  recipe_name: string;
  servings: number | null;
  ingredients: RecipeImportIngredient[];
  instructions: string[];
  cost: RecipeImportCost;
  unmatched_ingredients: string[];
  unknown_units: string[];
  note: string | null;
}

export interface RecipeImportStatus {
  job_id: string;
  status: "queued" | "processing" | "done" | "error";
  error: string | null;
  recipe_id: string | null;
  preview: RecipeImportPreview | null;
}

export interface RecipeImportSaveIngredient {
  name: string;
  quantity: number | null;
  unit: string | null;
  product_id: string | null;
}

export interface RecipeImportSaveRequest {
  recipe_name: string;
  servings: number | null;
  instructions: string[];
  ingredients: RecipeImportSaveIngredient[];
  selling_price?: number | null;
}

export interface RecipeImportSaveResult {
  recipe_id: string;
  version_id: string;
  name: string;
  yield_qty: number;
  unmatched_ingredients: string[];
  unknown_units: string[];
  cost: RecipeImportCost;
}

// --- Purchase & price tracking ---------------------------------------------
export interface PurchaseRow {
  id: string;
  purchase_date: string | null;
  supplier_id?: string | null;
  supplier_name?: string | null;
  product_id?: string | null;
  product_name?: string | null;
  qty: number | null;
  unit_code: string | null;
  unit_price: number | null;
  total_price: number | null;
  unit_cost_standard: number | null;
  currency: string | null;
  variation_pct: number | null;
}

export interface ProductPriceHistory {
  product_id: string;
  purchases: PurchaseRow[];
  count: number;
}

export interface SupplierComparisonRow {
  supplier_id: string | null;
  supplier_name: string | null;
  unit_cost_standard: number | null;
  unit_code: string | null;
  currency: string | null;
  purchase_date: string | null;
  is_cheapest: boolean;
}

export interface SupplierComparison {
  product_id: string;
  suppliers: SupplierComparisonRow[];
  cheapest_supplier_id: string | null;
}

export interface SupplierPurchaseHistory {
  supplier_id: string;
  purchases: PurchaseRow[];
  count: number;
}

export interface StoredPriceAlert {
  id: string;
  type: "price_increase" | "price_decrease" | "margin";
  product_id: string | null;
  product_name: string | null;
  recipe_id: string | null;
  old_value: number | null;
  new_value: number | null;
  change_pct: number | null;
  message: string;
  is_read: boolean;
  created_at: string | null;
}

export interface PriceMovement {
  product_id: string;
  product_name: string | null;
  old_cost: number;
  new_cost: number;
  change_pct: number;
  unit_code: string | null;
}

export interface SavingOpportunity {
  product_id: string;
  product_name: string | null;
  cheapest_supplier: string | null;
  cheapest_cost: number;
  current_max_cost: number;
  saving_per_unit: number;
  saving_pct: number | null;
  unit_code: string | null;
}

export interface RecipeImpact {
  recipe_id: string | null;
  message: string;
  change_pct: number | null;
  created_at: string | null;
}

export interface PriceDashboard {
  most_increased: PriceMovement[];
  most_decreased: PriceMovement[];
  savings_opportunities: SavingOpportunity[];
  potential_savings_total: number;
  recipe_impact: RecipeImpact[];
}

export interface CustomMetric {
  id: string;
  name: string;
  formula: string;
  target: string;
  format: string; // number | currency | percent
  description: string | null;
}

export interface MetricVariable {
  name: string;
  description: string;
}

export interface MetricEvaluation {
  id: string;
  name: string;
  format: string;
  value: number | null;
  error: string | null;
}

export interface MetricEvaluationResult {
  recipe_id: string;
  context: Record<string, number | null>;
  metrics: MetricEvaluation[];
}

export interface CustomFieldDef {
  id: string;
  label: string;
  target: string; // product | recipe
  key: string | null;
  type: string; // text | number | boolean | select
  options: string[];
  required: boolean;
  description: string | null;
}

export interface CustomFieldValues {
  target: string;
  entity_id: string;
  definitions: CustomFieldDef[];
  values: Record<string, unknown>;
}

export interface ReportColumn {
  key: string;
  label: string;
  type: string;
}

export interface ReportSource {
  key: string;
  label: string;
  columns: ReportColumn[];
}

export interface ReportFilter {
  field: string;
  op: string;
  value: string | number | null;
}

export interface ReportDefinition {
  source: string;
  columns: string[];
  filters: ReportFilter[];
  sort?: { field: string; dir: string } | null;
  limit?: number | null;
}

export interface CustomReport {
  id: string;
  name: string;
  definition: ReportDefinition;
}

export interface ReportRunResult {
  source: string;
  columns: ReportColumn[];
  rows: Record<string, unknown>[];
  count: number;
}

// --- Quotes / comparateur de devis (Phase 4) ------------------------------

export type QuoteStatus = "draft" | "ordered" | "archived";

export interface Quote {
  id: string;
  reference?: string | null;
  title?: string | null;
  status?: QuoteStatus | string | null;
  supplier_id?: string | null;
  supplier_name?: string | null;
  total_amount?: number | null;
  notes?: string | null;
  line_count?: number | null;
  ordered_at?: string | null;
  created_at?: string | null;
}

export interface QuoteLine {
  id: string;
  product_id?: string | null;
  product_name?: string | null;
  description?: string | null;
  qty?: number | null;
  unit_id?: number | null;
  unit_price?: number | null;
  supplier_id?: string | null;
}

export interface QuoteDetail extends Quote {
  lines: QuoteLine[];
}

export interface QuoteLinePayload {
  product_id?: string | null;
  description?: string | null;
  qty?: number | null;
  unit_id?: number | null;
}

export interface QuoteCreatePayload {
  title?: string | null;
  notes?: string | null;
  lines: QuoteLinePayload[];
}

export interface QuoteComparisonLine {
  product_id: string;
  product_name?: string | null;
  qty?: number | null;
  unit_cost?: number | null;
  line_cost?: number | null;
  available?: boolean;
}

export interface QuoteComparisonSupplier {
  supplier_id: string;
  supplier_name?: string | null;
  covered_count: number;
  priceable_count: number;
  missing: { product_id: string; product_name?: string | null }[];
  total: number;
  max_lead_time_days?: number | null;
  preferred?: boolean;
  is_full_coverage?: boolean;
  is_cheapest?: boolean;
  is_best_coverage?: boolean;
  lines: QuoteComparisonLine[];
}

export interface QuoteComparison {
  quote_id?: string;
  line_count: number;
  priceable_count: number;
  suppliers: QuoteComparisonSupplier[];
  cheapest_supplier_id?: string | null;
  best_coverage_supplier_id?: string | null;
}

// --- Import de devis par OCR (miroir de l'import intelligent de facture) ---

export interface QuotePreviewLineData {
  description: string;
  qty?: number | null;
  unit?: string | null;
  unit_price?: number | null;
  line_total?: number | null;
  vat_rate?: number | null;
  discount_pct?: number | null;
  pack_size?: string | null;
  brand?: string | null;
  min_qty?: number | null;
  matched_product_id?: string | null;
  matched_product_name?: string | null;
  match_confidence?: number | null;
  needs_review: boolean;
  suggested_category?: string | null;
}

export interface QuotePreviewResult {
  supplier?: string | null;
  supplier_id?: string | null;
  date?: string | null;
  valid_until?: string | null;
  quote_number?: string | null;
  total_amount?: number | null;
  currency?: string | null;
  discount_total?: number | null;
  delivery_fee?: number | null;
  conditions?: string | null;
  lines: QuotePreviewLineData[];
}

export interface QuoteConfirmLineData {
  description: string;
  qty?: number | null;
  unit?: string | null;
  unit_price?: number | null;
  line_total?: number | null;
  vat_rate?: number | null;
  discount_pct?: number | null;
  pack_size?: string | null;
  brand?: string | null;
  min_qty?: number | null;
  action: "create" | "associate" | "skip";
  product_id?: string | null;
  category?: string | null;
}

export interface QuoteConfirmRequest {
  title?: string | null;
  supplier?: string | null;
  supplier_id?: string | null;
  date?: string | null;
  valid_until?: string | null;
  quote_number?: string | null;
  total_amount?: number | null;
  currency?: string | null;
  discount_total?: number | null;
  /** Frais de port du devis : ils portent sur la commande entière. */
  delivery_fee?: number | null;
  conditions?: string | null;
  lines: QuoteConfirmLineData[];
}

// --- Écarts devis ↔ facture (§9) ------------------------------------------

export type VarianceStatus =
  | "ok" | "price_up" | "price_down" | "qty_diff" | "missing" | "extra";

export interface VarianceSide {
  qty?: number | null;
  unit_price?: number | null;
  vat_rate?: number | null;
  total?: number | null;
}

export interface VarianceLine {
  product_id?: string | null;
  product_name?: string | null;
  quoted: VarianceSide;
  billed: VarianceSide;
  qty_delta?: number | null;
  price_delta?: number | null;
  price_delta_pct?: number | null;
  total_delta?: number | null;
  vat_mismatch: boolean;
  status: VarianceStatus;
}

export interface QuoteVariance {
  linked: boolean;
  invoice_id: string;
  invoice_number?: string | null;
  quote_id?: string;
  quote_reference?: string | null;
  lines?: VarianceLine[];
  quoted_total?: number;
  billed_total?: number;
  total_delta?: number;
  total_delta_pct?: number | null;
  issue_count?: number;
  is_conform?: boolean;
}

// --- Tableau comparatif multi-devis (produit × fournisseur) ---------------

/** Rang d'une offre : vert / orange / rouge. `null` = hors classement
 *  (offre périmée ou produit indisponible). */
export type OfferRank = "best" | "mid" | "worst" | null;

export interface MatrixOffer {
  supplier_id: string | null;
  supplier_name?: string | null;
  quote_id?: string | null;
  quote_reference?: string | null;
  unit_price?: number | null;
  qty?: number | null;
  vat_rate?: number | null;
  discount_pct?: number | null;
  pack_size?: string | null;
  brand?: string | null;
  min_qty?: number | null;
  delivery_fee?: number | null;
  /** Le seul prix comparable entre conditionnements différents. */
  price_per_base_unit?: number | null;
  base_unit?: string | null;
  lead_time_days?: number | null;
  available: boolean;
  preferred: boolean;
  valid_until?: string | null;
  expired: boolean;
  rank: OfferRank;
  delta_pct_vs_best?: number | null;
}

export interface MatrixProduct {
  product_id: string;
  product_name?: string | null;
  /** "base_unit" = classement au prix/kg ; "unit_price" = repli fragile. */
  basis: "base_unit" | "unit_price";
  mixed_packaging: boolean;
  offers: MatrixOffer[];
  best_supplier_id?: string | null;
  best_price?: number | null;
  history: {
    last_paid?: number | null;
    avg_paid?: number | null;
    best_paid?: number | null;
  };
  vs_last_paid_pct?: number | null;
}

export interface MatrixSupplier {
  supplier_id: string;
  supplier_name?: string | null;
  covered: number;
  best_count: number;
  total: number;
  delivery_fee?: number | null;
  /** Panier + frais de port : ce qu'on paie vraiment, et ce sur quoi se juge
   *  le « moins cher ». */
  total_with_delivery: number;
  max_lead_time_days?: number | null;
  preferred: boolean;
}

export interface QuoteMatrix {
  products: MatrixProduct[];
  suppliers: MatrixSupplier[];
  product_count: number;
  cheapest_supplier_id?: string | null;
  fastest_supplier_id?: string | null;
  potential_savings: number;
}

export interface QuoteImportResult {
  quote_id: string;
  reference?: string | null;
  lines: number;
  created_products: number;
  associated: number;
  skipped: number;
}

// --- Historique des offres reçues pour un produit (§10) ---------------------
// Distinct de l'historique d'ACHAT : ce sont des prix proposés, pas payés.
export interface ProductQuoteOffer {
  quote_id?: string | null;
  quote_reference?: string | null;
  quote_number?: string | null;
  status?: string | null;
  date?: string | null;
  valid_until?: string | null;
  supplier_id?: string | null;
  supplier_name?: string | null;
  unit_price?: number | null;
  /** Prix remise de ligne déduite : le prix réellement offert. */
  net_unit_price?: number | null;
  discount_pct?: number | null;
  vat_rate?: number | null;
  qty?: number | null;
  pack_size?: string | null;
  brand?: string | null;
  min_qty?: number | null;
  /** Écart avec l'offre précédente DU MÊME fournisseur. */
  delta_pct_vs_previous?: number | null;
  is_best: boolean;
}

export interface ProductQuoteHistory {
  offers: ProductQuoteOffer[];
  count: number;
  supplier_count: number;
  best_price?: number | null;
  best_supplier_id?: string | null;
  best_supplier_name?: string | null;
  latest_price?: number | null;
  avg_price?: number | null;
}
