"""Initial schema from sql/schema.sql

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-06-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
import os

# revision identifiers, used by Alembic.
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Execute SQL schema file
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    sql_path = os.path.join(base_dir, 'sql', 'schema.sql')
    if not os.path.exists(sql_path):
        # try project root
        sql_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'sql', 'schema.sql'))
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql = f.read()
    # Split statements by semicolon might be dangerous; use execute directly
    conn = op.get_bind()
    conn.execute(sa.text(sql))


def downgrade():
    raise NotImplementedError('Downgrade not implemented for initial schema')
