"""Drop five tables no line of code has ever read or written.

Proof of uselessness, before deleting anything:

* `ai_suggestions`, `alerts`, `permissions`, `role_permissions`,
  `custom_formulas` appear in `sql/schema.sql` and in `app/models/models.py`,
  and **nowhere else** — no CRUD, no endpoint, no service, no test.
* nothing seeds them; `schema.sql` holds no INSERT for any of them.
* nothing references them from outside the group: the only inbound foreign key
  is `role_permissions.permission_id → permissions`, i.e. one dead table
  pointing at another.

They are therefore empty by construction, and dropping them cannot lose data.

Two of them are actively misleading, which is the real reason to remove them:

* `alerts` is not the alerts feature. The alerts a chef actually sees live in
  `price_alerts`. Someone reading the schema finds `alerts`, reads its `read`
  boolean, and concludes acknowledgement is unimplemented — it is, elsewhere.
* `permissions` / `role_permissions` promise fine-grained permissions. There are
  none. Authorisation is three roles, checked by name. A table that describes a
  feature you do not have will eventually be trusted by someone.

The downgrade recreates them exactly as `schema.sql` had them, so this is
reversible — empty, as they have always been.
"""
from alembic import op

revision = "0012_drop_dead_tables"
down_revision = "0011_ai_conversations"
branch_labels = None
depends_on = None

# Children before parents: role_permissions points at permissions.
DEAD = ["role_permissions", "permissions", "ai_suggestions", "alerts", "custom_formulas"]


def upgrade():
    for table in DEAD:
        op.execute(f"DROP TABLE IF EXISTS {table}")


def downgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS permissions (
          id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          code text UNIQUE,
          description text
        );
        CREATE TABLE IF NOT EXISTS role_permissions (
          id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          role_id uuid REFERENCES roles(id) ON DELETE CASCADE,
          permission_id uuid REFERENCES permissions(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS ai_suggestions (
          id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
          target_type text,
          target_id uuid,
          suggestion jsonb,
          score numeric,
          created_at timestamptz DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS alerts (
          id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
          type text,
          payload jsonb,
          read boolean DEFAULT false,
          created_at timestamptz DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS custom_formulas (
          id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
          tenant_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
          name text NOT NULL,
          expression text NOT NULL,
          metadata jsonb,
          created_at timestamptz DEFAULT now()
        );
        """
    )
