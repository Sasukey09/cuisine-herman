-- PostgreSQL schema for restaurant cost management

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

-- organizations
CREATE TABLE organizations (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name text NOT NULL,
  metadata jsonb,
  created_at timestamptz DEFAULT now()
);

-- users
CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  email text NOT NULL,
  password_hash text,
  name text,
  created_at timestamptz DEFAULT now(),
  last_login timestamptz,
  metadata jsonb,
  UNIQUE(tenant_id, email)
);

-- password_reset_tokens (self-service "mot de passe oublié"; only the hash is stored)
CREATE TABLE password_reset_tokens (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX ix_password_reset_tokens_token_hash ON password_reset_tokens(token_hash);

-- suppliers
CREATE TABLE suppliers (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  code text,
  contact jsonb,
  default_currency text,
  metadata jsonb,
  created_at timestamptz DEFAULT now()
);

-- units
CREATE TABLE units (
  id serial PRIMARY KEY,
  category text NOT NULL, -- mass, volume, count
  code text NOT NULL, -- e.g. kg,g,L,ml,pcs
  name text,
  ratio_to_base numeric NOT NULL DEFAULT 1, -- relative to category base
  UNIQUE(category, code)
);

-- Unit conversions helper (optional explicit pairs)
CREATE TABLE unit_conversions (
  id serial PRIMARY KEY,
  from_unit_id integer REFERENCES units(id) ON DELETE CASCADE,
  to_unit_id integer REFERENCES units(id) ON DELETE CASCADE,
  factor numeric NOT NULL,
  UNIQUE(from_unit_id, to_unit_id)
);

-- product categories
CREATE TABLE product_categories (
  id serial PRIMARY KEY,
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  name text
);

-- products
CREATE TABLE products (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  sku text,
  name text NOT NULL,
  base_unit_id integer REFERENCES units(id),
  category_id integer REFERENCES product_categories(id),
  allergenes jsonb,
  metadata jsonb,
  created_at timestamptz DEFAULT now(),
  UNIQUE(tenant_id, sku)
);

CREATE TABLE product_aliases (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  product_id uuid REFERENCES products(id) ON DELETE CASCADE,
  alias text NOT NULL
);

-- Persisted OCR-line -> product match results (audit / training data)
CREATE TABLE product_match_results (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  ocr_text text NOT NULL,
  matched_product_id uuid REFERENCES products(id) ON DELETE SET NULL,
  confidence numeric,
  match_type text,
  manual_review boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX ON product_match_results(tenant_id, matched_product_id);

-- Product price history
CREATE TABLE product_prices (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  product_id uuid REFERENCES products(id) ON DELETE SET NULL,
  supplier_id uuid REFERENCES suppliers(id) ON DELETE SET NULL,
  price numeric NOT NULL,
  unit_id integer REFERENCES units(id),
  currency text,
  effective_date date NOT NULL DEFAULT current_date,
  source_invoice_line_id uuid,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX ON product_prices(tenant_id, product_id, supplier_id, effective_date);

-- Aggregates for quick access
CREATE MATERIALIZED VIEW IF NOT EXISTS product_price_latest AS
SELECT DISTINCT ON (tenant_id, product_id, supplier_id)
  id, tenant_id, product_id, supplier_id, price, unit_id, currency, effective_date, created_at
FROM product_prices
ORDER BY tenant_id, product_id, supplier_id, effective_date DESC;

CREATE TABLE invoices (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  supplier_id uuid REFERENCES suppliers(id) ON DELETE SET NULL,
  invoice_number text,
  date date,
  total_amount numeric,
  currency text,
  file_url text,
  parsed boolean DEFAULT false,
  ocr_status text,
  metadata jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE invoice_lines (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  invoice_id uuid REFERENCES invoices(id) ON DELETE CASCADE,
  product_id uuid REFERENCES products(id) ON DELETE SET NULL,
  description text,
  qty numeric,
  unit_id integer REFERENCES units(id),
  qty_normalized numeric,
  unit_price numeric,
  line_total numeric,
  currency text,
  raw_line jsonb,
  match_confidence numeric,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX ON invoice_lines(product_id);

CREATE TABLE purchases (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  product_id uuid REFERENCES products(id),
  supplier_id uuid REFERENCES suppliers(id),
  invoice_line_id uuid REFERENCES invoice_lines(id) ON DELETE SET NULL,
  qty numeric,
  unit_id integer REFERENCES units(id),
  price numeric,
  currency text,
  purchased_at timestamptz DEFAULT now()
);

CREATE TABLE recipes (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  yield_qty numeric,
  yield_unit_id integer REFERENCES units(id),
  current_version_id uuid,
  tags text[],
  metadata jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE recipe_versions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  recipe_id uuid REFERENCES recipes(id) ON DELETE CASCADE,
  version_number integer NOT NULL,
  author_id uuid REFERENCES users(id),
  notes text,
  is_published boolean DEFAULT false,
  created_at timestamptz DEFAULT now(),
  metadata jsonb,
  UNIQUE(recipe_id, version_number)
);

CREATE TABLE recipe_ingredients (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  recipe_version_id uuid REFERENCES recipe_versions(id) ON DELETE CASCADE,
  product_id uuid REFERENCES products(id),
  qty numeric,
  unit_id integer REFERENCES units(id),
  qty_normalized numeric,
  loss_pct numeric DEFAULT 0,
  yield_pct numeric DEFAULT 100,
  prep_notes text
);

CREATE TABLE recipe_costs (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  recipe_version_id uuid REFERENCES recipe_versions(id) ON DELETE CASCADE,
  computed_cost_total numeric,
  cost_per_portion numeric,
  food_cost_pct numeric,
  margin_estimated numeric,
  computed_at timestamptz DEFAULT now(),
  snapshot_price_source jsonb
);

CREATE TABLE video_sources (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  url text,
  platform text,
  fetched_at timestamptz,
  metadata jsonb
);

CREATE TABLE transcriptions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_id uuid REFERENCES video_sources(id) ON DELETE CASCADE,
  text text,
  language text,
  confidence numeric,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE ai_suggestions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  target_type text,
  target_id uuid,
  suggestion jsonb,
  score numeric,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE alerts (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  type text,
  payload jsonb,
  read boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE audit_logs (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id uuid REFERENCES users(id),
  tenant_id uuid REFERENCES organizations(id),
  action text,
  data jsonb,
  created_at timestamptz DEFAULT now()
);

-- RBAC: roles & permissions
CREATE TABLE roles (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text
);

CREATE TABLE permissions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  code text UNIQUE,
  description text
);

CREATE TABLE role_permissions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  role_id uuid REFERENCES roles(id) ON DELETE CASCADE,
  permission_id uuid REFERENCES permissions(id) ON DELETE CASCADE
);

CREATE TABLE user_roles (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id uuid REFERENCES users(id) ON DELETE CASCADE,
  role_id uuid REFERENCES roles(id) ON DELETE CASCADE
);

-- Customization tables
CREATE TABLE custom_fields (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  target_entity text NOT NULL,
  schema jsonb NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE custom_metrics (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  formula text NOT NULL,
  metadata jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE custom_reports (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  definition jsonb NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE custom_formulas (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  expression text NOT NULL,
  metadata jsonb,
  created_at timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX ON products(tenant_id);
CREATE INDEX ON purchases(product_id);
CREATE INDEX ON recipe_versions(recipe_id);
CREATE INDEX ON product_aliases USING gin (alias gin_trgm_ops);
CREATE INDEX ON products USING gin (name gin_trgm_ops);

-- Row level security hints (recommended)
-- Example: enable RLS on sensitive tables and create policies in migrations
-- ALTER TABLE products ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY tenant_isolation ON products USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Audit trigger example (basic)
CREATE OR REPLACE FUNCTION audit_if_needed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO audit_logs(id, user_id, tenant_id, action, data, created_at)
  VALUES (uuid_generate_v4(), NULL, NEW.tenant_id, TG_TABLE_NAME || '_' || TG_OP, row_to_json(NEW), now());
  RETURN NEW;
END;
$$;

-- You can attach the trigger in migrations for tables you want to audit

-- End of schema
