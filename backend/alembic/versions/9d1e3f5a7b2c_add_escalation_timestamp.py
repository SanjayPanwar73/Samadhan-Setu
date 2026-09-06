"""add idempotent escalation timestamp

Revision ID: 9d1e3f5a7b2c
Revises: 8c4d1e2f6a7b
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d1e3f5a7b2c"
down_revision: Union[str, None] = "8c4d1e2f6a7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "complaints",
        sa.Column("last_escalated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_complaints_last_escalated_at",
        "complaints",
        ["last_escalated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_complaints_last_escalated_at", table_name="complaints")
    op.drop_column("complaints", "last_escalated_at")
