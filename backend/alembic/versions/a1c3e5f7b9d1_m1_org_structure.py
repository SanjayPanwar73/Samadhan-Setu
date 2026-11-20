"""V2 part 1: org structure, department scope, audit events

Expand-only: adds columns/tables, drops nothing. Runs on SQLite and PostgreSQL.

Revision ID: a1c3e5f7b9d1
Revises: 9d1e3f5a7b2c
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1c3e5f7b9d1"
down_revision: Union[str, None] = "9d1e3f5a7b2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_ROLES = ("student", "dept_admin", "hod", "super_admin")


def upgrade() -> None:
    bind = op.get_bind()
    existing_user_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("users")
    }

    # --- extend the role enum (PostgreSQL uses a native enum type; SQLite stores text) ---
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for value in NEW_ROLES:
                op.execute(f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{value}'")

    # --- users ---
    if "enrollment_no" not in existing_user_columns:
        op.add_column("users", sa.Column("enrollment_no", sa.String(), nullable=True))
    if "is_active" not in existing_user_columns:
        op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    if "email_verified_at" not in existing_user_columns:
        op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    existing_user_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}
    if "ix_users_enrollment_no" not in existing_user_indexes:
        op.create_index(op.f("ix_users_enrollment_no"), "users", ["enrollment_no"], unique=True)

    # --- departments ---
    op.add_column("departments", sa.Column("code", sa.String(), nullable=True))
    op.add_column("departments", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("departments", sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(
        "departments",
        sa.Column("requires_verification_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # SQLite cannot add a column with a non-constant default, so this stays default-less here.
    op.add_column("departments", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_departments_code"), "departments", ["code"], unique=True)

    # --- new tables ---
    op.create_table(
        "department_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("user_id", "department_id", name="uq_membership_user_dept"),
    )
    op.create_index(op.f("ix_department_memberships_id"), "department_memberships", ["id"])
    op.create_index(op.f("ix_department_memberships_user_id"), "department_memberships", ["user_id"])
    op.create_index(op.f("ix_department_memberships_department_id"), "department_memberships", ["department_id"])

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("base_severity", sa.Float(), nullable=False),
        sa.Column("default_criticality", sa.Float(), nullable=False),
        sa.Column("impact_level", sa.Float(), nullable=False),
        sa.Column("expected_resolution_hours", sa.Integer(), nullable=False),
        sa.Column("requires_verification", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_evidence", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolution_schema", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("department_id", "name", name="uq_category_dept_name"),
    )
    op.create_index(op.f("ix_categories_id"), "categories", ["id"])
    op.create_index(op.f("ix_categories_department_id"), "categories", ["department_id"])

    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(op.f("ix_locations_id"), "locations", ["id"])
    op.create_index(op.f("ix_locations_parent_id"), "locations", ["parent_id"])

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("asset_type", sa.String(), nullable=False),
        sa.Column("tag", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("criticality", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(op.f("ix_assets_id"), "assets", ["id"])
    op.create_index(op.f("ix_assets_department_id"), "assets", ["department_id"])
    op.create_index("ix_assets_location_type", "assets", ["location_id", "asset_type"])

    op.create_table(
        "ticket_counters",
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), primary_key=True),
        sa.Column("next_value", sa.Integer(), nullable=False),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_role", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("issue_id", sa.Integer(), nullable=True),
        sa.Column("complaint_id", sa.Integer(), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_audit_events_id"), "audit_events", ["id"])
    op.create_index(op.f("ix_audit_events_action"), "audit_events", ["action"])
    op.create_index(op.f("ix_audit_events_issue_id"), "audit_events", ["issue_id"])
    op.create_index(op.f("ix_audit_events_created_at"), "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("ticket_counters")
    op.drop_table("assets")
    op.drop_table("locations")
    op.drop_table("categories")
    op.drop_table("department_memberships")

    op.drop_index(op.f("ix_departments_code"), table_name="departments")
    with op.batch_alter_table("departments") as batch:
        for col in ("created_at", "requires_verification_default", "is_system", "is_active", "code"):
            batch.drop_column(col)

    op.drop_index(op.f("ix_users_enrollment_no"), table_name="users")
    with op.batch_alter_table("users") as batch:
        for col in ("email_verified_at", "is_active", "enrollment_no"):
            batch.drop_column(col)
    # PostgreSQL enum values cannot be removed; the extra role values are harmless after downgrade.
