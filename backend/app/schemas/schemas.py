from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
# Alias for fields literally named ``date``: the field name shadows the ``date``
# type in the class namespace, which makes some pydantic versions resolve
# ``Optional[date]`` to ``Optional[None]`` and 500 on any real date value.
from datetime import date as DateType


class SupplierBase(BaseModel):
    name: str
    code: Optional[str] = None
    contact: Optional[dict] = None
    rating: Optional[float] = None


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    contact: Optional[dict] = None
    rating: Optional[float] = None


class SupplierRead(SupplierBase):
    id: str

    model_config = ConfigDict(from_attributes=True)


class SupplierPriceRead(BaseModel):
    id: str
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    unit_id: Optional[int] = None
    effective_date: Optional[date] = None
    source_invoice_line_id: Optional[str] = None


class ProductBase(BaseModel):
    name: str
    sku: Optional[str] = None
    base_unit_id: Optional[int] = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    base_unit_id: Optional[int] = None


class ProductRead(ProductBase):
    id: str

    model_config = ConfigDict(from_attributes=True)


class InvoiceCreateResp(BaseModel):
    id: str
    status: str


class InvoiceRead(BaseModel):
    id: str
    invoice_number: Optional[str] = None
    date: Optional[DateType] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    parsed: Optional[bool] = None
    ocr_status: Optional[str] = None
    supplier_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceLineRead(BaseModel):
    id: str
    product_id: Optional[str] = None
    description: Optional[str] = None
    qty: Optional[float] = None
    unit_id: Optional[int] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    match_confidence: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class MapProductRequest(BaseModel):
    product_id: str


class MapProductResult(BaseModel):
    line_id: str
    product_id: str
    price_id: Optional[str] = None


class InvoiceProcessSummary(BaseModel):
    invoice_id: str
    lines: int
    matched: int
    prices_created: int
    needs_review: List[str] = []


class InvoiceFileUrl(BaseModel):
    url: str


class InvoiceIngestResult(BaseModel):
    invoice_id: str
    summary: InvoiceProcessSummary


class RecipeBase(BaseModel):
    name: str
    yield_qty: Optional[float] = None
    selling_price: Optional[float] = None


class RecipeCreate(RecipeBase):
    pass


class RecipeUpdate(BaseModel):
    name: Optional[str] = None
    yield_qty: Optional[float] = None
    selling_price: Optional[float] = None


class RecipeInstructionRead(BaseModel):
    id: str
    step_number: int
    content: str

    model_config = ConfigDict(from_attributes=True)


class RecipeRead(RecipeBase):
    id: str
    current_version_id: Optional[str] = None
    yield_unit_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class RecipeIngredientCreate(BaseModel):
    # Optional: ingredients imported from a PDF / video / the assistant may not be
    # matched to a catalog product yet (kept by free-text ingredient_name).
    product_id: Optional[str] = None
    qty: Optional[float] = None
    unit_id: Optional[int] = None
    qty_normalized: Optional[float] = None
    loss_pct: Optional[float] = 0
    yield_pct: Optional[float] = 100
    prep_notes: Optional[str] = None


class RecipeIngredientRead(RecipeIngredientCreate):
    id: str
    ingredient_name: Optional[str] = None  # free-text label when unmatched

    model_config = ConfigDict(from_attributes=True)


class RecipeVersionCreate(BaseModel):
    notes: Optional[str] = None
    is_published: Optional[bool] = False
    ingredients: List[RecipeIngredientCreate] = []


class RecipeVersionRead(BaseModel):
    id: str
    recipe_id: str
    version_number: int
    notes: Optional[str] = None
    is_published: bool
    ingredients: List[RecipeIngredientRead] = []

    model_config = ConfigDict(from_attributes=True)


class ComputeCostRequest(BaseModel):
    selling_price: Optional[float] = None
    as_of: Optional[date] = None


class CostLine(BaseModel):
    product_id: Optional[str] = None
    qty_base: Optional[float] = None
    unit_price: Optional[float] = None
    line_cost: Optional[float] = None
    price_id: Optional[str] = None
    missing_price: bool = False


class RecipeCostRead(BaseModel):
    recipe_version_id: str
    computed_cost_total: Optional[float] = None
    cost_per_portion: Optional[float] = None
    food_cost_pct: Optional[float] = None
    margin_estimated: Optional[float] = None
    has_missing_prices: bool = False
    snapshot_id: Optional[str] = None
    breakdown: List[CostLine] = []


class CostTrendPoint(BaseModel):
    computed_at: Optional[datetime] = None
    recipe_id: str
    recipe_name: Optional[str] = None
    recipe_version_id: str
    computed_cost_total: Optional[float] = None
    cost_per_portion: Optional[float] = None
    food_cost_pct: Optional[float] = None


class TopProduct(BaseModel):
    product_id: str
    name: Optional[str] = None
    total_spend: float
    total_qty: float
    line_count: int


class PriceTrendPoint(BaseModel):
    effective_date: Optional[date] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    supplier_id: Optional[str] = None


class MarginAlert(BaseModel):
    recipe_id: str
    recipe_name: Optional[str] = None
    recipe_version_id: str
    cost_per_portion: Optional[float] = None
    food_cost_pct: Optional[float] = None
    computed_at: Optional[datetime] = None


class PriceAlert(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    previous_price: Optional[float] = None
    latest_price: Optional[float] = None
    change_pct: Optional[float] = None
    currency: Optional[str] = None
    effective_date: Optional[date] = None
    supplier_id: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class ProductMatchRequest(BaseModel):
    text: str
    fuzzy_min_score: Optional[float] = 60.0


class ProductMatchResultRead(BaseModel):
    product_id: Optional[str] = None
    confidence_score: Optional[float] = None
    match_type: Optional[str] = None
    manual_review: bool = False
    matched_alias: Optional[str] = None


class RegisterRequest(BaseModel):
    email: str
    password: str
    org_name: str
    name: Optional[str] = None


class CreateUserRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
    role: str = "viewer"


class UserRead(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    tenant_id: str

    model_config = ConfigDict(from_attributes=True)


class MeRead(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    tenant_id: str
    roles: List[str] = []


# --------------------------------------------------------------------------- #
# AI assistant
# --------------------------------------------------------------------------- #
class AIChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class AIChatRequest(BaseModel):
    message: str
    history: List[AIChatMessage] = []


class AIToolCall(BaseModel):
    name: str
    input: dict = {}


class AIChatResponse(BaseModel):
    reply: str
    tool_calls: List[AIToolCall] = []
    usage: Optional[dict] = None


# --------------------------------------------------------------------------- #
# Video import
# --------------------------------------------------------------------------- #
class VideoExtractRequest(BaseModel):
    url: str


class VideoIngredientDraft(BaseModel):
    name: str
    qty: Optional[float] = None
    unit: Optional[str] = None


class VideoRecipeDraft(BaseModel):
    name: str = ""
    yield_qty: Optional[float] = None
    ingredients: List[VideoIngredientDraft] = []
    steps: List[str] = []
    summary: Optional[str] = None


class VideoExtractResult(BaseModel):
    source_id: str
    platform: str
    transcript_source: str
    transcript_excerpt: str
    draft: VideoRecipeDraft
    note: str


class VideoSaveRequest(BaseModel):
    name: str
    yield_qty: Optional[float] = None
    ingredients: List[VideoIngredientDraft] = []
    steps: List[str] = []


# --------------------------------------------------------------------------- #
# Recipe import from PDF
# --------------------------------------------------------------------------- #
class RecipeImportIngredient(BaseModel):
    """An extracted ingredient with its (auto) product match."""
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    matched_product_id: Optional[str] = None
    matched_product_name: Optional[str] = None
    match_confidence: Optional[float] = None
    unit_recognized: bool = True


class RecipeImportCost(BaseModel):
    computed_cost_total: Optional[float] = None
    cost_per_portion: Optional[float] = None
    food_cost_pct: Optional[float] = None
    margin_estimated: Optional[float] = None
    has_missing_prices: bool = False


class RecipeImportPreview(BaseModel):
    recipe_name: str = ""
    servings: Optional[float] = None
    ingredients: List[RecipeImportIngredient] = []
    instructions: List[str] = []
    cost: RecipeImportCost = RecipeImportCost()
    unmatched_ingredients: List[str] = []
    unknown_units: List[str] = []
    note: Optional[str] = None


class RecipeImportStatus(BaseModel):
    job_id: str
    status: str  # queued | processing | done | error
    error: Optional[str] = None
    recipe_id: Optional[str] = None  # set once the preview is validated/saved
    preview: Optional[RecipeImportPreview] = None


class RecipeImportSaveIngredient(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    product_id: Optional[str] = None  # user-confirmed/corrected mapping


class RecipeImportSaveRequest(BaseModel):
    recipe_name: str
    servings: Optional[float] = None
    instructions: List[str] = []
    ingredients: List[RecipeImportSaveIngredient] = []
    selling_price: Optional[float] = None


# --------------------------------------------------------------------------- #
# Custom metrics (no-code indicators)
# --------------------------------------------------------------------------- #
class CustomMetricCreate(BaseModel):
    name: str
    formula: str
    target: str = "recipe"
    format: str = "number"  # number | currency | percent
    description: Optional[str] = None


class CustomMetricUpdate(BaseModel):
    name: Optional[str] = None
    formula: Optional[str] = None
    format: Optional[str] = None
    description: Optional[str] = None


class CustomMetricRead(BaseModel):
    id: str
    name: str
    formula: str
    target: str = "recipe"
    format: str = "number"
    description: Optional[str] = None


class MetricVariable(BaseModel):
    name: str
    description: str


class MetricEvaluation(BaseModel):
    id: str
    name: str
    format: str
    value: Optional[float] = None
    error: Optional[str] = None


class MetricEvaluationResult(BaseModel):
    recipe_id: str
    context: dict
    metrics: List[MetricEvaluation] = []


# --------------------------------------------------------------------------- #
# Custom fields (no-code fields on products / recipes)
# --------------------------------------------------------------------------- #
class CustomFieldCreate(BaseModel):
    label: str
    target: str  # product | recipe
    type: str  # text | number | boolean | select
    key: Optional[str] = None
    options: List[str] = []
    required: bool = False
    description: Optional[str] = None


class CustomFieldRead(BaseModel):
    id: str
    label: str
    target: str
    key: Optional[str] = None
    type: str = "text"
    options: List[str] = []
    required: bool = False
    description: Optional[str] = None


class CustomFieldValues(BaseModel):
    target: str
    entity_id: str
    definitions: List[CustomFieldRead] = []
    values: dict = {}


class CustomFieldValuesUpdate(BaseModel):
    values: dict = {}


# --------------------------------------------------------------------------- #
# Custom reports (no-code report builder)
# --------------------------------------------------------------------------- #
class ReportColumn(BaseModel):
    key: str
    label: str
    type: str


class ReportSource(BaseModel):
    key: str
    label: str
    columns: List[ReportColumn] = []


class ReportFilter(BaseModel):
    field: str
    op: str
    value: Optional[object] = None


class ReportDefinition(BaseModel):
    source: str
    columns: List[str] = []
    filters: List[ReportFilter] = []
    sort: Optional[dict] = None
    limit: Optional[int] = None


class CustomReportCreate(BaseModel):
    name: str
    definition: ReportDefinition


class CustomReportUpdate(BaseModel):
    name: Optional[str] = None
    definition: Optional[ReportDefinition] = None


class CustomReportRead(BaseModel):
    id: str
    name: str
    definition: dict


class ReportRunResult(BaseModel):
    source: str
    columns: List[ReportColumn] = []
    rows: List[dict] = []
    count: int


class InvoiceQueuedResp(BaseModel):
    invoice_id: str
    status: str  # queued | done | error


class InvoiceLineUpdate(BaseModel):
    description: Optional[str] = None
    qty: Optional[float] = None
    unit: Optional[str] = None  # unit code (g, kg, l, ml, piece...)
    unit_price: Optional[float] = None
    line_total: Optional[float] = None


class InvoiceUpdate(BaseModel):
    invoice_number: Optional[str] = None
    date: Optional[DateType] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None


class InvoiceLineCreate(BaseModel):
    description: Optional[str] = None
    qty: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    product_id: Optional[str] = None


class CreateProductFromLine(BaseModel):
    """Optional overrides when turning an invoice line into a new product.

    Defaults: name = the line description, unit = the line's unit.
    """
    name: Optional[str] = None
    sku: Optional[str] = None
