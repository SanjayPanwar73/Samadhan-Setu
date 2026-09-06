"""add complaint issue grouping"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4f3a6c2d1b09"
down_revision: Union[str, None] = "1652eae1c885"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "complaints",
        sa.Column("issue_root_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_complaints_issue_root_id",
        "complaints",
        ["issue_root_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_complaints_issue_root_id",
        "complaints",
        "complaints",
        ["issue_root_id"],
        ["id"],
    )
    op.execute(sa.text("UPDATE complaints SET issue_root_id = id WHERE issue_root_id IS NULL"))


def downgrade() -> None:
    op.drop_constraint("fk_complaints_issue_root_id", "complaints", type_="foreignkey")
    op.drop_index("ix_complaints_issue_root_id", table_name="complaints")
    op.drop_column("complaints", "issue_root_id")
