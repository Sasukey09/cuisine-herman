from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Text,
    Date,
    Boolean,
    TIMESTAMP,
    ForeignKey,
    DateTime,
    JSON,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import declarative_base, relationship

try:
    # optional dependency for pgvector support
    from pgvector.sqlalchemy import Vector
except Exception:
    Vector = None

Base = declarative_base()


def uuid_default():
    return text("uuid_generate_v4()")


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    name = Column(Text, nullable=False)
    meta = Column("metadata", JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    email = Column(Text, nullable=False)
    password_hash = Column(Text)
    name = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_login = Column(TIMESTAMP)
    meta = Column("metadata", JSONB)


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    name = Column(Text, nullable=False)
    code = Column(Text)
    contact = Column(JSONB)
    default_currency = Column(Text)
    meta = Column("metadata", JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())


class Unit(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True)
    category = Column(Text, nullable=False)
    code = Column(Text, nullable=False)
    name = Column(Text)
    ratio_to_base = Column(Numeric, nullable=False, default=1)


class UnitConversion(Base):
    __tablename__ = "unit_conversions"
    id = Column(Integer, primary_key=True)
    from_unit_id = Column(Integer, ForeignKey("units.id", ondelete="CASCADE"))
    to_unit_id = Column(Integer, ForeignKey("units.id", ondelete="CASCADE"))
    factor = Column(Numeric, nullable=False)


class ProductCategory(Base):
    __tablename__ = "product_categories"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    name = Column(Text)


class Product(Base):
    __tablename__ = "products"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    sku = Column(Text)
    name = Column(Text, nullable=False)
    base_unit_id = Column(Integer, ForeignKey("units.id"))
    category_id = Column(Integer, ForeignKey("product_categories.id"))
    allergenes = Column(JSONB)
    meta = Column("metadata", JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())

    aliases = relationship("ProductAlias", back_populates="product")


class ProductAlias(Base):
    __tablename__ = "product_aliases"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    product_id = Column(UUID(as_uuid=False), ForeignKey("products.id", ondelete="CASCADE"))
    alias = Column(Text, nullable=False)

    product = relationship("Product", back_populates="aliases")


class ProductMatchResult(Base):
    __tablename__ = "product_match_results"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    ocr_text = Column(Text, nullable=False)
    matched_product_id = Column(UUID(as_uuid=False), ForeignKey("products.id", ondelete="SET NULL"))
    confidence = Column(Numeric)
    match_type = Column(Text)
    manual_review = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class ProductPrice(Base):
    __tablename__ = "product_prices"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    product_id = Column(UUID(as_uuid=False), ForeignKey("products.id", ondelete="SET NULL"))
    supplier_id = Column(UUID(as_uuid=False), ForeignKey("suppliers.id", ondelete="SET NULL"))
    price = Column(Numeric, nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"))
    currency = Column(Text)
    effective_date = Column(Date, nullable=False, server_default=func.current_date())
    source_invoice_line_id = Column(UUID(as_uuid=False))
    created_at = Column(TIMESTAMP, server_default=func.now())


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    supplier_id = Column(UUID(as_uuid=False), ForeignKey("suppliers.id", ondelete="SET NULL"))
    invoice_number = Column(Text)
    date = Column(Date)
    total_amount = Column(Numeric)
    currency = Column(Text)
    file_url = Column(Text)
    parsed = Column(Boolean, default=False)
    ocr_status = Column(Text)
    meta = Column("metadata", JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())

    lines = relationship("InvoiceLine", back_populates="invoice")


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    invoice_id = Column(UUID(as_uuid=False), ForeignKey("invoices.id", ondelete="CASCADE"))
    product_id = Column(UUID(as_uuid=False), ForeignKey("products.id", ondelete="SET NULL"))
    description = Column(Text)
    qty = Column(Numeric)
    unit_id = Column(Integer, ForeignKey("units.id"))
    qty_normalized = Column(Numeric)
    unit_price = Column(Numeric)
    line_total = Column(Numeric)
    currency = Column(Text)
    raw_line = Column(JSONB)
    match_confidence = Column(Numeric)
    created_at = Column(TIMESTAMP, server_default=func.now())

    invoice = relationship("Invoice", back_populates="lines")


class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    product_id = Column(UUID(as_uuid=False), ForeignKey("products.id"))
    supplier_id = Column(UUID(as_uuid=False), ForeignKey("suppliers.id"))
    invoice_line_id = Column(UUID(as_uuid=False), ForeignKey("invoice_lines.id", ondelete="SET NULL"))
    qty = Column(Numeric)
    unit_id = Column(Integer, ForeignKey("units.id"))
    price = Column(Numeric)
    currency = Column(Text)
    purchased_at = Column(TIMESTAMP, server_default=func.now())


class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    name = Column(Text, nullable=False)
    yield_qty = Column(Numeric)
    yield_unit_id = Column(Integer, ForeignKey("units.id"))
    current_version_id = Column(UUID(as_uuid=False))
    tags = Column(ARRAY(Text))
    meta = Column("metadata", JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())

    versions = relationship("RecipeVersion", back_populates="recipe")


class RecipeVersion(Base):
    __tablename__ = "recipe_versions"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    recipe_id = Column(UUID(as_uuid=False), ForeignKey("recipes.id", ondelete="CASCADE"))
    version_number = Column(Integer, nullable=False)
    author_id = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    notes = Column(Text)
    is_published = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    meta = Column("metadata", JSONB)

    recipe = relationship("Recipe", back_populates="versions")
    ingredients = relationship("RecipeIngredient", back_populates="version")


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    recipe_version_id = Column(UUID(as_uuid=False), ForeignKey("recipe_versions.id", ondelete="CASCADE"))
    product_id = Column(UUID(as_uuid=False), ForeignKey("products.id"))
    qty = Column(Numeric)
    unit_id = Column(Integer, ForeignKey("units.id"))
    qty_normalized = Column(Numeric)
    loss_pct = Column(Numeric, default=0)
    yield_pct = Column(Numeric, default=100)
    prep_notes = Column(Text)

    version = relationship("RecipeVersion", back_populates="ingredients")


class RecipeCost(Base):
    __tablename__ = "recipe_costs"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    recipe_version_id = Column(UUID(as_uuid=False), ForeignKey("recipe_versions.id", ondelete="CASCADE"))
    computed_cost_total = Column(Numeric)
    cost_per_portion = Column(Numeric)
    food_cost_pct = Column(Numeric)
    margin_estimated = Column(Numeric)
    computed_at = Column(TIMESTAMP, server_default=func.now())
    snapshot_price_source = Column(JSONB)


class VideoSource(Base):
    __tablename__ = "video_sources"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    url = Column(Text)
    platform = Column(Text)
    fetched_at = Column(TIMESTAMP)
    meta = Column("metadata", JSONB)


class Transcription(Base):
    __tablename__ = "transcriptions"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    source_id = Column(UUID(as_uuid=False), ForeignKey("video_sources.id", ondelete="CASCADE"))
    text = Column(Text)
    language = Column(Text)
    confidence = Column(Numeric)
    created_at = Column(TIMESTAMP, server_default=func.now())


class AISuggestion(Base):
    __tablename__ = "ai_suggestions"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    target_type = Column(Text)
    target_id = Column(UUID(as_uuid=False))
    suggestion = Column(JSONB)
    score = Column(Numeric)
    created_at = Column(TIMESTAMP, server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    type = Column(Text)
    payload = Column(JSONB)
    read = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id"))
    action = Column(Text)
    data = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())


class Role(Base):
    __tablename__ = "roles"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    name = Column(Text, nullable=False)
    description = Column(Text)


class Permission(Base):
    __tablename__ = "permissions"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    code = Column(Text, unique=True)
    description = Column(Text)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    role_id = Column(UUID(as_uuid=False), ForeignKey("roles.id", ondelete="CASCADE"))
    permission_id = Column(UUID(as_uuid=False), ForeignKey("permissions.id", ondelete="CASCADE"))


class UserRole(Base):
    __tablename__ = "user_roles"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    role_id = Column(UUID(as_uuid=False), ForeignKey("roles.id", ondelete="CASCADE"))


class CustomField(Base):
    __tablename__ = "custom_fields"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    name = Column(Text, nullable=False)
    target_entity = Column(Text, nullable=False)
    schema = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class CustomMetric(Base):
    __tablename__ = "custom_metrics"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    name = Column(Text, nullable=False)
    formula = Column(Text, nullable=False)
    meta = Column("metadata", JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())


class CustomReport(Base):
    __tablename__ = "custom_reports"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    name = Column(Text, nullable=False)
    definition = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class CustomFormula(Base):
    __tablename__ = "custom_formulas"
    id = Column(UUID(as_uuid=False), primary_key=True, server_default=uuid_default())
    tenant_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"))
    name = Column(Text, nullable=False)
    expression = Column(Text, nullable=False)
    meta = Column("metadata", JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())
