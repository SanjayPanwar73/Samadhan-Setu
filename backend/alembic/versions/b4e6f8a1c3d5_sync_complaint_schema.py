"""sync complaint indexes and nullability with the ORM model

Revision ID: b4e6f8a1c3d5
Revises: 9d1e3f5a7b2c
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4e6f8a1c3d5"
down_revision: Union[str, None] = "9d1e3f5a7b2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Existing databases may contain NULL values from the original schema.
    op.execute(
        sa.text(
            "UPDATE complaints SET escalation_level = 0 "
            "WHERE escalation_level IS NULL"
        )
    )
    op.alter_column(
        "complaints",
        "escalation_level",
        existing_type=sa.Integer(),
        nullable=False,
    )

    existing_indexes = {
        index["name"] for index in inspector.get_indexes("complaints")
    }
    if "ix_complaints_issue_root_id" not in existing_indexes:
        op.create_index(
            "ix_complaints_issue_root_id",
            "complaints",
            ["issue_root_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {
        index["name"] for index in inspector.get_indexes("complaints")
    }
    if "ix_complaints_issue_root_id" in existing_indexes:
        op.drop_index("ix_complaints_issue_root_id", table_name="complaints")
    op.alter_column(
        "complaints",
        "escalation_level",
        existing_type=sa.Integer(),
        nullable=True,
    )
