"""users.token_version — makes logout actually revoke tokens

Revision ID: 0009_user_token_version
Revises: 0008_supplier_rating
Create Date: 2026-07-13

Logging out was purely client-side, so a stolen refresh token stayed valid for
its full 14-day life with no way to cut it off. Every token now carries a `tv`
claim; bumping this column invalidates all of the user's tokens at once.

NB: revision ids must stay <= 32 chars (alembic_version.version_num is
varchar(32) — a longer id silently breaks the deploy).
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_user_token_version"
down_revision = "0008_supplier_rating"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
