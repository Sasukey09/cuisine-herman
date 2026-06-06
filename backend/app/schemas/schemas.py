from typing import Optional, List
from pydantic import BaseModel
from datetime import date, datetime


class SupplierBase(BaseModel):
    name: str
    code: Optional[str]
    contact: Optional[dict]


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    contact: Optional[dict] = None


class SupplierRead(SupplierBase):
    id: str

    class Config:
        orm_mode = True


class SupplierPriceRead(BaseModel):
    id: str
    product_id: Optional[str]
    product_name: Optional[str]
    price: Optional[float]
    currency: Optional[str]
    unit_id: Optional[int]
    effective_date: Optional[date]
    source_invoice_line_id: Optional[str]


class ProductBase(BaseModel):
    name: str
    sku: Optional[str]
    base_unit_id: Optional[int]


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    base_unit_id: Optional[int] = None


class ProductRead(ProductBase):
    id: str

    class Config:
        orm_mode = True


class InvoiceCreateResp(BaseModel):
    id: str
    status: str


class InvoiceRead(BaseModel):
    id: str
    invoice_number: Optional[str]
    date: Optional[date]
    total_amount: Optional[float]
    currency: Optional[str]
    parsed: Optional[bool]
    ocr_status: Optional[str]
    supplier_id: Optional[str]
    created_at: Optional[datetime]

    class Config:
        orm_mode = True


class InvoiceLineRead(BaseModel):
    id: str
    product_id: Optional[str]
    description: Optional[str]
    qty: Optional[float]
    unit_id: Optional[int]
    unit_price: Optional[float]
    line_total: Optional[float]
    match_confidence: Optional[float]

    class Config:
        orm_mode = True


class MapProductRequest(BaseModel):
    product_id: str


class MapProductResult(BaseModel):
    line_id: str
    product_id: str
    price_id: Optional[str]


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
    yield_qty: Optional[float]


class RecipeCreate(RecipeBase):
    pass


class RecipeRead(RecipeBase):
    id: str
    current_version_id: Optional[str]
    yield_unit_id: Optional[int]

    class Config:
        orm_mode = True


class RecipeIngredientCreate(BaseModel):
    product_id: str
    qty: Optional[float] = None
    unit_id: Optional[int] = None
    qty_normalized: Optional[float] = None
    loss_pct: Optional[float] = 0
    yield_pct: Optional[float] = 100
    prep_notes: Optional[str] = None


class RecipeIngredientRead(RecipeIngredientCreate):
    id: str

    class Config:
        orm_mode = True


class RecipeVersionCreate(BaseModel):
    notes: Optional[str] = None
    is_published: Optional[bool] = False
    ingredients: List[RecipeIngredientCreate] = []


class RecipeVersionRead(BaseModel):
    id: str
    recipe_id: str
    version_number: int
    notes: Optional[str]
    is_published: bool
    ingredients: List[RecipeIngredientRead] = []

    class Config:
        orm_mode = True


class ComputeCostRequest(BaseModel):
    selling_price: Optional[float] = None
    as_of: Optional[date] = None


class CostLine(BaseModel):
    product_id: Optional[str]
    qty_base: Optional[float]
    unit_price: Optional[float]
    line_cost: Optional[float]
    price_id: Optional[str]
    missing_price: bool = False


class RecipeCostRead(BaseModel):
    recipe_version_id: str
    computed_cost_total: Optional[float]
    cost_per_portion: Optional[float]
    food_cost_pct: Optional[float]
    margin_estimated: Optional[float]
    has_missing_prices: bool = False
    snapshot_id: Optional[str] = None
    breakdown: List[CostLine] = []


class CostTrendPoint(BaseModel):
    computed_at: Optional[datetime]
    recipe_id: str
    recipe_name: Optional[str]
    recipe_version_id: str
    computed_cost_total: Optional[float]
    cost_per_portion: Optional[float]
    food_cost_pct: Optional[float]


class TopProduct(BaseModel):
    product_id: str
    name: Optional[str]
    total_spend: float
    total_qty: float
    line_count: int


class PriceTrendPoint(BaseModel):
    effective_date: Optional[date]
    price: Optional[float]
    currency: Optional[str]
    supplier_id: Optional[str]


class MarginAlert(BaseModel):
    recipe_id: str
    recipe_name: Optional[str]
    recipe_version_id: str
    cost_per_portion: Optional[float]
    food_cost_pct: Optional[float]
    computed_at: Optional[datetime]


class PriceAlert(BaseModel):
    product_id: str
    product_name: Optional[str]
    previous_price: Optional[float]
    latest_price: Optional[float]
    change_pct: Optional[float]
    currency: Optional[str]
    effective_date: Optional[date]
    supplier_id: Optional[str]


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
    product_id: Optional[str]
    confidence_score: Optional[float]
    match_type: Optional[str]
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
    name: Optional[str]
    tenant_id: str

    class Config:
        orm_mode = True


class MeRead(BaseModel):
    id: str
    email: str
    name: Optional[str]
    tenant_id: str
    roles: List[str] = []
