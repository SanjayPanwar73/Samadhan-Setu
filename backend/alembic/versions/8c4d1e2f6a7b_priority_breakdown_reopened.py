"""add priority breakdown and reopened status

Revision ID: 8c4d1e2f6a7b
Revises: 7f2a9c1d4e6b
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c4d1e2f6a7b"
down_revision: Union[str, None] = "7f2a9c1d4e6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("complaints", sa.Column("priority_breakdown", sa.JSON(), nullable=True))
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE complaintstatus ADD VALUE IF NOT EXISTS 'reopened'")


def downgrade() -> None:
    op.drop_column("complaints", "priority_breakdown")
