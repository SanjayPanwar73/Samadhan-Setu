"""add resolution history

Revision ID: 7f2a9c1d4e6b
Revises: 4f3a6c2d1b09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f2a9c1d4e6b"
down_revision: Union[str, None] = "4f3a6c2d1b09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resolution_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("complaint_id", sa.Integer(), nullable=False),
        sa.Column("resolution_text", sa.Text(), nullable=False),
        sa.Column("resolved_by", sa.Integer(), nullable=False),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["complaint_id"], ["complaints.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_resolution_history_id"), "resolution_history", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_resolution_history_complaint_id"),
        "resolution_history",
        ["complaint_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_resolution_history_complaint_id"),
        table_name="resolution_history",
    )
    op.drop_index(op.f("ix_resolution_history_id"), table_name="resolution_history")
    op.drop_table("resolution_history")
