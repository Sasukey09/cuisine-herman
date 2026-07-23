from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core import security as _security
from datetime import date, datetime
# Alias for fields literally named ``date``: the field name shadows the ``date``
# type in the class namespace, which makes some pydantic versions resolve
# ``Optional[date]`` to ``Optional[None]`` and 500 on any real date value.
from datetime import date as DateType


class SupplierBase(BaseModel):
    name: str = Field(max_length=200)
    code: Optional[str] = Field(default=None, max_length=100)
    contact: Optional[dict] = None
    rating: Optional[float] = Field(default=None, allow_inf_nan=False)


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    code: Optional[str] = Field(default=None, max_length=100)
    contact: Optional[dict] = None
    rating: Optional[float] = Field(default=None, allow_inf_nan=False)


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


class ProductPriceCreate(BaseModel):
    """A price a human types in, rather than one an invoice brought."""

    price: float = Field(gt=0, allow_inf_nan=False, description="Prix pour UNE unité (ex. 8.50 pour 8,50 €/kg)")
    unit_id: int = Field(description="L'unité à laquelle ce prix s'applique (kg, L, pièce…)")
    supplier_id: Optional[str] = None
    currency: str = "EUR"
    effective_date: Optional[DateType] = None


class ProductBase(BaseModel):
    name: str = Field(max_length=200)
    sku: Optional[str] = Field(default=None, max_length=100)
    base_unit_id: Optional[int] = None
    vat_rate: Optional[float] = Field(default=None, ge=0, le=100)


class ProductCreate(ProductBase):
    # A category name from the taxonomy (see /products/categories). Omit it and
    # the product is auto-classified from its name at creation.
    category: Optional[str] = Field(default=None, max_length=60)


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    sku: Optional[str] = Field(default=None, max_length=100)
    base_unit_id: Optional[int] = None
    category: Optional[str] = Field(default=None, max_length=60)
    vat_rate: Optional[float] = Field(default=None, ge=0, le=100)


class ProductRead(ProductBase):
    id: str

    model_config = ConfigDict(from_attributes=True)


# --- Product ↔ Supplier catalog links -------------------------------------


class SupplierProductBase(BaseModel):
    supplier_sku: Optional[str] = Field(default=None, max_length=100)
    pack_size: Optional[str] = Field(default=None, max_length=100)
    available: bool = True
    preferred: bool = False
    lead_time_days: Optional[int] = Field(default=None, ge=0, le=365)
    notes: Optional[str] = Field(default=None, max_length=500)


class SupplierProductCreate(SupplierProductBase):
    supplier_id: str


class SupplierProductUpdate(BaseModel):
    supplier_sku: Optional[str] = Field(default=None, max_length=100)
    pack_size: Optional[str] = Field(default=None, max_length=100)
    available: Optional[bool] = None
    preferred: Optional[bool] = None
    lead_time_days: Optional[int] = Field(default=None, ge=0, le=365)
    notes: Optional[str] = Field(default=None, max_length=500)


class SupplierProductRead(BaseModel):
    id: str
    product_id: str
    supplier_id: str
    supplier_sku: Optional[str] = None
    pack_size: Optional[str] = None
    available: Optional[bool] = None
    preferred: Optional[bool] = None
    lead_time_days: Optional[int] = None
    notes: Optional[str] = None

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
    vat_rate: Optional[float] = None
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
    name: str = Field(max_length=200)
    yield_qty: Optional[float] = Field(default=None, allow_inf_nan=False)
    selling_price: Optional[float] = Field(default=None, allow_inf_nan=False)


class RecipeCreate(RecipeBase):
    pass


class RecipeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    yield_qty: Optional[float] = Field(default=None, allow_inf_nan=False)
    selling_price: Optional[float] = Field(default=None, allow_inf_nan=False)


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
    qty: Optional[float] = Field(default=None, allow_inf_nan=False)
    unit_id: Optional[int] = None
    qty_normalized: Optional[float] = Field(default=None, allow_inf_nan=False)
    loss_pct: Optional[float] = Field(default=0, allow_inf_nan=False, ge=0)
    yield_pct: Optional[float] = Field(default=100, allow_inf_nan=False, ge=0)
    prep_notes: Optional[str] = Field(default=None, max_length=2000)


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


class _EmailPasswordMixin:
    """Shared registration/creation input hardening (I2): validated email format
    (normalized to lowercase) and a strong password. Raises 422 on violation."""

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v):
        err = _security.email_error(v)
        if err:
            raise ValueError(err)
        return _security.normalize_email(v)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v):
        err = _security.password_error(v)
        if err:
            raise ValueError(err)
        return v


class RegisterRequest(_EmailPasswordMixin, BaseModel):
    email: str
    password: str
    org_name: str
    name: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    # Strength is enforced in the endpoint (400) to keep the existing status
    # contract; the same security.password_error policy is applied there.
    password: str


class ForgotPasswordRequest(BaseModel):
    """Self-service recovery: the user gives only their email. The endpoint
    always answers the same way, so it never reveals who has an account."""
    email: str = Field(max_length=320)


class PasswordResetConfirmRequest(BaseModel):
    """Redeem a reset link. Password strength is enforced in the endpoint (400),
    same policy as everywhere else."""
    token: str = Field(min_length=16, max_length=512)
    password: str


class GoogleAuthRequest(BaseModel):
    """Google Sign-In: the client sends the ID token it obtained natively."""
    id_token: str
    # Only used when this is a brand-new user (names their organization).
    org_name: Optional[str] = None


class AppleAuthRequest(BaseModel):
    """Sign in with Apple: the client sends the identity token. Apple returns the
    display name only on the first consent, so the client forwards it here."""
    identity_token: str
    name: Optional[str] = None
    org_name: Optional[str] = None


class CreateUserRequest(_EmailPasswordMixin, BaseModel):
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
    # `history` is kept for backward compatibility with older clients, but it is
    # IGNORED: the server now reads the thread from the database. The client's
    # copy was the only source of truth, so a reload lost it — and a crafted
    # request could rewrite what the model believed had been said.
    history: List[AIChatMessage] = []
    conversation_id: Optional[str] = None


class AIToolCall(BaseModel):
    name: str
    input: dict = {}


class AIChatResponse(BaseModel):
    reply: str
    tool_calls: List[AIToolCall] = []
    usage: Optional[dict] = None
    conversation_id: Optional[str] = None


class AIConversationRead(BaseModel):
    id: str
    title: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AIStoredMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[datetime] = None


class AIConversationDetail(BaseModel):
    id: str
    title: Optional[str] = None
    updated_at: Optional[datetime] = None
    messages: List[AIStoredMessage] = []


class AISuggestions(BaseModel):
    suggestions: List[str] = []


# --------------------------------------------------------------------------- #
# Video import
# --------------------------------------------------------------------------- #
class VideoExtractRequest(BaseModel):
    url: str


class VideoTranscriptRequest(BaseModel):
    """The client (mobile app) fetched the transcript itself — from the phone's
    residential IP, which YouTube does not block like a datacenter one — and
    sends it here for AI extraction. No server-side YouTube fetch happens."""
    transcript: str = Field(min_length=1, max_length=200000)
    url: Optional[str] = Field(default=None, max_length=2048)
    title: Optional[str] = Field(default=None, max_length=500)


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
    formula: str = Field(max_length=500)  # I4: bound formula size (DoS)
    target: str = "recipe"
    format: str = "number"  # number | currency | percent
    description: Optional[str] = None


class CustomMetricUpdate(BaseModel):
    name: Optional[str] = None
    formula: Optional[str] = Field(default=None, max_length=500)
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
    vat_rate: Optional[float] = Field(default=None, ge=0, le=100)


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
    vat_rate: Optional[float] = Field(default=None, ge=0, le=100)
    product_id: Optional[str] = None


class InvoicePreviewLine(BaseModel):
    """A detected invoice line enriched for the smart-import validation dialog:
    the OCR fields + a product-match suggestion + a category suggestion."""

    description: str
    qty: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    vat_rate: Optional[float] = None
    matched_product_id: Optional[str] = None
    matched_product_name: Optional[str] = None
    match_confidence: Optional[float] = None
    # True when no confident match was found -> the user should create/associate.
    needs_review: bool = True
    suggested_category: Optional[str] = None


class InvoicePreviewResult(BaseModel):
    supplier: Optional[str] = None
    supplier_id: Optional[str] = None
    date: Optional[DateType] = None
    invoice_number: Optional[str] = None
    total_amount: Optional[float] = None
    lines: List[InvoicePreviewLine] = []


class InvoiceConfirmLine(BaseModel):
    """A line the user validated in the smart-import dialog."""

    description: str
    qty: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    vat_rate: Optional[float] = Field(default=None, ge=0, le=100)
    # create a new product, associate to an existing one, or skip the line.
    action: str = "create"
    product_id: Optional[str] = None  # for action="associate"
    category: Optional[str] = None  # for action="create" (else auto-classified)


class InvoiceConfirmRequest(BaseModel):
    supplier: Optional[str] = None
    supplier_id: Optional[str] = None
    date: Optional[DateType] = None
    invoice_number: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = "EUR"
    lines: List[InvoiceConfirmLine] = []


class CreateProductFromLine(BaseModel):
    """Optional overrides when turning an invoice line into a new product.

    Defaults: name = the line description, unit = the line's unit.
    """
    name: Optional[str] = None
    sku: Optional[str] = None


class AuditLogRead(BaseModel):
    id: str
    action: Optional[str] = None
    user_id: Optional[str] = None
    data: Optional[dict] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DeleteOrganizationRequest(BaseModel):
    """Retyping the exact name is the only thing between a mis-click and every
    invoice, recipe and price this restaurant has ever recorded.

    ``password`` is verified for password-based accounts (a second confirmation
    factor before irreversible erasure); it is optional so social-login admins,
    who have no password, can still exercise their right to erasure."""

    confirm_name: str
    password: Optional[str] = None


# --- Quotes (comparateur de devis) ----------------------------------------


class QuoteLineBase(BaseModel):
    product_id: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=300)
    qty: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    unit_id: Optional[int] = None


class QuoteLineCreate(QuoteLineBase):
    pass


class QuoteLineUpdate(BaseModel):
    product_id: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=300)
    qty: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    unit_id: Optional[int] = None


class QuoteLineRead(BaseModel):
    id: str
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    description: Optional[str] = None
    qty: Optional[float] = None
    unit_id: Optional[int] = None
    unit_price: Optional[float] = None
    supplier_id: Optional[str] = None
    # Import OCR
    vat_rate: Optional[float] = None
    line_total: Optional[float] = None
    discount_pct: Optional[float] = None
    pack_size: Optional[str] = None
    brand: Optional[str] = None
    min_qty: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class QuoteCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=1000)
    lines: List[QuoteLineCreate] = []


class QuoteUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[str] = Field(default=None, max_length=20)


class QuoteRead(BaseModel):
    id: str
    reference: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    total_amount: Optional[float] = None
    notes: Optional[str] = None
    line_count: Optional[int] = None
    ordered_at: Optional[datetime] = None
    order_reference: Optional[str] = None
    created_at: Optional[datetime] = None
    # Import OCR : ce que le document du fournisseur dit
    quote_number: Optional[str] = None
    date: Optional[DateType] = None
    valid_until: Optional[DateType] = None
    currency: Optional[str] = None
    discount_total: Optional[float] = None
    delivery_fee: Optional[float] = None
    conditions: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class QuoteOrderRequest(BaseModel):
    """Convert a quote into an order by retaining one supplier's prices."""

    supplier_id: str


# --- Import de devis (OCR) — miroir de l'import intelligent de facture ------


class QuotePreviewLine(BaseModel):
    """Une ligne de devis détectée, enrichie pour le dialogue de validation :
    champs OCR + suggestion produit + suggestion de catégorie."""

    description: str
    qty: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    vat_rate: Optional[float] = None
    discount_pct: Optional[float] = None
    pack_size: Optional[str] = None
    brand: Optional[str] = None
    min_qty: Optional[float] = None
    matched_product_id: Optional[str] = None
    matched_product_name: Optional[str] = None
    match_confidence: Optional[float] = None
    needs_review: bool = True
    suggested_category: Optional[str] = None


class QuotePreviewResult(BaseModel):
    supplier: Optional[str] = None
    supplier_id: Optional[str] = None
    date: Optional[DateType] = None
    valid_until: Optional[DateType] = None
    quote_number: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    discount_total: Optional[float] = None
    delivery_fee: Optional[float] = None
    conditions: Optional[str] = None
    lines: List[QuotePreviewLine] = []


class QuoteConfirmLine(BaseModel):
    """Une ligne validée par l'utilisateur dans le dialogue d'import."""

    description: str
    qty: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    vat_rate: Optional[float] = Field(default=None, ge=0, le=100)
    discount_pct: Optional[float] = Field(default=None, ge=0, le=100)
    pack_size: Optional[str] = Field(default=None, max_length=100)
    brand: Optional[str] = Field(default=None, max_length=100)
    min_qty: Optional[float] = Field(default=None, ge=0)
    # créer un produit, associer un produit existant, ou ignorer la ligne.
    action: str = "create"
    product_id: Optional[str] = None  # pour action="associate"
    category: Optional[str] = None  # pour action="create" (sinon auto-classé)


class QuoteConfirmRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    supplier: Optional[str] = None
    supplier_id: Optional[str] = None
    date: Optional[DateType] = None
    valid_until: Optional[DateType] = None
    quote_number: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = "EUR"
    discount_total: Optional[float] = None
    delivery_fee: Optional[float] = Field(default=None, ge=0)
    conditions: Optional[str] = Field(default=None, max_length=2000)
    lines: List[QuoteConfirmLine] = []


class QuoteImportResult(BaseModel):
    quote_id: str
    reference: Optional[str] = None
    lines: int
    created_products: int
    associated: int
    skipped: int


# --------------------------------------------------------------------------- #
# Domaine Achats : commandes fournisseur
# --------------------------------------------------------------------------- #
class PurchaseOrderLineRead(BaseModel):
    id: str
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    description: Optional[str] = None
    qty_ordered: Optional[float] = None
    unit_id: Optional[int] = None
    unit_price: Optional[float] = None
    vat_rate: Optional[float] = None
    discount_pct: Optional[float] = None
    line_total: Optional[float] = None
    pack_size: Optional[str] = None
    brand: Optional[str] = None
    source_quote_line_id: Optional[str] = None
    # Calculé depuis les réceptions : la commande ne stocke aucun compteur.
    qty_received: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderRead(BaseModel):
    id: str
    reference: Optional[str] = None
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    status: Optional[str] = None
    status_label: Optional[str] = None
    expected_date: Optional[date] = None
    ordered_at: Optional[datetime] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    delivery_fee: Optional[float] = None
    discount_total: Optional[float] = None
    conditions: Optional[str] = None
    notes: Optional[str] = None
    line_count: int = 0
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderDetail(PurchaseOrderRead):
    lines: List[PurchaseOrderLineRead] = []


class OrderFromQuoteLinesRequest(BaseModel):
    """Commander les offres retenues dans le comparateur.

    On envoie des identifiants de LIGNES de devis, pas un devis : le
    comparateur désigne le moins cher produit par produit, donc le panier
    retenu traverse plusieurs devis et plusieurs fournisseurs. Le serveur
    regroupe par fournisseur — une commande par fournisseur.
    """

    quote_line_ids: List[str] = Field(min_length=1, max_length=500)
    expected_date: Optional[date] = None
    # `draft` laisse la main pour relire avant d'engager ; `sent` engage tout de
    # suite. Le défaut est prudent.
    status: str = "draft"


class PurchaseOrderUpdate(BaseModel):
    status: Optional[str] = None
    expected_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    conditions: Optional[str] = Field(default=None, max_length=2000)


class OrderPlanLine(BaseModel):
    product_id: Optional[str] = None
    description: Optional[str] = None
    qty_ordered: Optional[float] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    pack_size: Optional[str] = None
    brand: Optional[str] = None
    source_quote_line_id: Optional[str] = None


class OrderPlan(BaseModel):
    """Ce qui SERA commandé, avant de l'être. L'aperçu évite d'engager trois
    commandes pour découvrir ensuite qu'on s'est trompé de lignes."""

    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    currency: Optional[str] = None
    delivery_fee: Optional[float] = None
    discount_total: Optional[float] = None
    conditions: Optional[str] = None
    lines_total: float = 0
    total_amount: float = 0
    lines: List[OrderPlanLine] = []


# --------------------------------------------------------------------------- #
# Domaine Achats : réceptions de marchandise
# --------------------------------------------------------------------------- #
class ReceiptLineWrite(BaseModel):
    order_line_id: Optional[str] = None  # nul = livré hors commande
    product_id: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=300)
    qty_received: Optional[float] = Field(default=None, ge=0)
    unit_id: Optional[int] = None
    unit_price: Optional[float] = Field(default=None, ge=0)
    pack_size: Optional[str] = Field(default=None, max_length=100)
    condition: str = "ok"
    substituted_product_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    photo_url: Optional[str] = Field(default=None, max_length=1000)


class ReceiptCreate(BaseModel):
    order_id: Optional[str] = None
    supplier_id: Optional[str] = None
    received_at: Optional[date] = None
    delivery_note_number: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=2000)
    file_url: Optional[str] = Field(default=None, max_length=1000)
    lines: List[ReceiptLineWrite] = []


class ReceiptUpdate(BaseModel):
    received_at: Optional[date] = None
    delivery_note_number: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=2000)
    file_url: Optional[str] = Field(default=None, max_length=1000)
    supplier_id: Optional[str] = None
    # Remplace l'intégralité des lignes. Une réception en brouillon est un
    # travail en cours ; tant qu'elle n'est pas validée, elle se réécrit.
    lines: Optional[List[ReceiptLineWrite]] = None


class ReceiptLineRead(ReceiptLineWrite):
    id: str
    product_name: Optional[str] = None
    condition_label: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReceiptRead(BaseModel):
    id: str
    reference: Optional[str] = None
    order_id: Optional[str] = None
    order_reference: Optional[str] = None
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    received_at: Optional[date] = None
    delivery_note_number: Optional[str] = None
    status: Optional[str] = None
    status_label: Optional[str] = None
    received_by: Optional[str] = None
    received_by_name: Optional[str] = None
    checked_at: Optional[datetime] = None
    checked_by_name: Optional[str] = None
    notes: Optional[str] = None
    file_url: Optional[str] = None
    line_count: int = 0
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ReceiptDetail(ReceiptRead):
    lines: List[ReceiptLineRead] = []
