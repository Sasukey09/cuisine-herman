"""ai_conversations + ai_messages — the assistant stops forgetting

Revision ID: 0011_ai_conversations
Revises: 0010_perf_indexes
Create Date: 2026-07-13

The chat history lived in React state only: reloading the page erased every
question the chef had asked and every answer the assistant had given. Nothing
could be revisited, quoted, or acted on later.

NB: revision ids must stay <= 32 chars (alembic_version.version_num is varchar(32)).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0011_ai_conversations"
down_revision = "0010_perf_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("id", UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=False),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_conversations_tenant", "ai_conversations", ["tenant_id", "updated_at"])

    op.create_table(
        "ai_messages",
        sa.Column("id", UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("conversation_id", UUID(as_uuid=False),
                  sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_messages_conversation", "ai_messages", ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
