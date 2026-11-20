"""V2 part 3: contract. Drop V1-only complaint columns, deprecate departments.category.

Run ONLY after `python -m scripts.migrate_v2_backfill` has been run and verified. The upgrade
refuses to continue while any complaint is still not linked to an issue, because the dropped
columns (assigned_to, issue_root_id, priority_*, sla_deadline, ...) are the only copy of that data.

complaint_history is kept (read-only); its rows were copied into audit_events by the backfill.

Revision ID: c3e5a7b9d1f3
Revises: b2d4f6a8c0e2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3e5a7b9d1f3"
down_revision: Union[str, None] = "b2d4f6a8c0e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DROPPED = [
    ("priority_score", sa.Float()),
    ("priority_breakdown", sa.JSON()),
    ("assigned_to", sa.Integer()),
    ("issue_root_id", sa.Integer()),
    ("repeat_count", sa.Integer()),
    ("sla_deadline", sa.DateTime(timezone=True)),
    ("escalation_level", sa.Integer()),
    ("last_escalated_at", sa.DateTime(timezone=True)),
]


def upgrade() -> None:
    bind = op.get_bind()
    unlinked = bind.execute(sa.text("SELECT COUNT(*) FROM complaints WHERE issue_id IS NULL")).scalar()
    if unlinked:
        raise RuntimeError(
            f"{unlinked} complaint(s) are not linked to an issue yet. Run "
            "`python -m scripts.migrate_v2_backfill` and verify it before applying this migration."
        )
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("complaints")}
    indexes = {i["name"] for i in inspector.get_indexes("complaints")}
    with op.batch_alter_table("complaints") as batch:
        for index in ("ix_complaints_issue_root_id", "ix_complaints_last_escalated_at"):
            if index in indexes:
                batch.drop_index(index)
        for name, _ in DROPPED:
            if name in existing:
                batch.drop_column(name)
    with op.batch_alter_table("departments") as batch:
        batch.alter_column("category", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("departments") as batch:
        batch.alter_column("category", existing_type=sa.String(), nullable=True)
    with op.batch_alter_table("complaints") as batch:
        for name, type_ in DROPPED:
            if name == "escalation_level":
                batch.add_column(sa.Column(name, type_, nullable=False, server_default="0"))
            else:
                batch.add_column(sa.Column(name, type_, nullable=True))
        batch.create_index("ix_complaints_issue_root_id", ["issue_root_id"])
        batch.create_index("ix_complaints_last_escalated_at", ["last_escalated_at"])
