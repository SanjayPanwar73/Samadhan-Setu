"""add complaint issue grouping"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4f3a6c2d1b09"
down_revision: Union[str, None] = "1652eae1c885"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite cannot ALTER TABLE to add a foreign-key constraint. Batch mode
    # keeps the migration valid for both the local demo and PostgreSQL.
    with op.batch_alter_table("complaints", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("issue_root_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_complaints_issue_root_id",
            "complaints",
            ["issue_root_id"],
            ["id"],
        )
    op.create_index("ix_complaints_issue_root_id", "complaints", ["issue_root_id"], unique=False)
    op.execute(sa.text("UPDATE complaints SET issue_root_id = id WHERE issue_root_id IS NULL"))


def downgrade() -> None:
    op.drop_index("ix_complaints_issue_root_id", table_name="complaints")
    with op.batch_alter_table("complaints", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_complaints_issue_root_id", type_="foreignkey")
        batch_op.drop_column("issue_root_id")
