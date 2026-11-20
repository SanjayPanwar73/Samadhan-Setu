"""V2 part 2: issues, grouping, work management, priority/SLA, outbox, notifications

Expand-only. Complaints/feedback get new nullable columns (batch mode for SQLite);
nothing is dropped. Works on SQLite and PostgreSQL.

Revision ID: b2d4f6a8c0e2
Revises: a1c3e5f7b9d1
"""

from typing import Sequence, Union

from alembic import op
from alembic_helpers import AdditiveSchema
import sqlalchemy as sa

revision: str = "b2d4f6a8c0e2"
down_revision: Union[str, None] = "a1c3e5f7b9d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_COMPLAINT_STATUSES = ("reopened", "open", "assigned", "awaiting_verification", "closed", "merged")
ACTIVE = "'open', 'assigned', 'in_progress', 'awaiting_verification', 'reopened'"


def _ts(name, **kw):
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def _escalation_column():
    return next(
        (col for col in sa.inspect(op.get_bind()).get_columns("complaints")
         if col["name"] == "escalation_level"),
        None,
    )


def upgrade() -> None:
    bind = op.get_bind()
    schema = AdditiveSchema()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for value in NEW_COMPLAINT_STATUSES:
                op.execute(f"ALTER TYPE complaintstatus ADD VALUE IF NOT EXISTS '{value}'")

    # ------------------------------------------------------------------ issues
    schema.create_table(
        "issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_no", sa.String(), nullable=False, unique=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("needs_review_reason", sa.String(), nullable=True),
        sa.Column("report_count", sa.Integer(), nullable=False),
        sa.Column("distinct_reporter_count", sa.Integer(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=True),
        sa.Column("priority_band", sa.String(), nullable=True),
        sa.Column("current_assessment_id", sa.Integer(), nullable=True),
        _ts("sla_anchor_at", nullable=True),
        _ts("sla_response_due_at", nullable=True),
        _ts("sla_resolution_due_at", nullable=True),
        sa.Column("escalation_level", sa.Integer(), nullable=False),
        _ts("last_escalated_at", nullable=True),
        _ts("first_reported_at", nullable=True),
        _ts("last_reported_at", nullable=True),
        _ts("last_progress_at", nullable=True),
        _ts("resolved_at", nullable=True),
        _ts("closed_at", nullable=True),
        sa.Column("reopen_count", sa.Integer(), nullable=False),
        sa.Column("recurrence_of_issue_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=True),
        sa.Column("merged_into_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        _ts("created_at", server_default=sa.func.now()),
        _ts("updated_at", server_default=sa.func.now()),
    )
    schema.create_index(op.f("ix_issues_id"), "issues", ["id"])
    schema.create_index("ix_issues_dept_status_priority", "issues", ["department_id", "status", "priority_score"])
    schema.create_index("ix_issues_asset", "issues", ["asset_id"])
    schema.create_index("ix_issues_location", "issues", ["location_id"])
    # Database guard behind Test C: at most one active issue per asset.
    where = sa.text(f"asset_id IS NOT NULL AND status IN ({ACTIVE})")
    schema.create_index("uq_issue_active_asset", "issues", ["asset_id"], unique=True,
                    sqlite_where=where, postgresql_where=where)

    # --------------------------------------------------------------- complaints
    legacy_level = _escalation_column()
    with op.batch_alter_table("complaints") as batch:
        # V2 writes escalation on issues. Legacy b4 requires a value on complaints.
        if legacy_level and not legacy_level["nullable"] and legacy_level["default"] is None:
            batch.alter_column("escalation_level", existing_type=sa.Integer(), server_default=sa.text("0"))
        batch.add_column(sa.Column("issue_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("location_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("asset_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("location_text", sa.String(), nullable=True))
        batch.add_column(sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("anon_code", sa.String(), nullable=True))
        batch.add_column(sa.Column("student_category_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("ai_category_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("ai_confidence", sa.Float(), nullable=True))
        batch.add_column(sa.Column("classification_disagreement", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("has_dissent", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("client_request_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("content_hash", sa.String(), nullable=True))
        batch.create_foreign_key("fk_complaints_issue", "issues", ["issue_id"], ["id"])
        batch.create_foreign_key("fk_complaints_category", "categories", ["category_id"], ["id"])
        batch.create_foreign_key("fk_complaints_location", "locations", ["location_id"], ["id"])
        batch.create_foreign_key("fk_complaints_asset", "assets", ["asset_id"], ["id"])
        batch.create_foreign_key("fk_complaints_student_category", "categories", ["student_category_id"], ["id"])
        batch.create_foreign_key("fk_complaints_ai_category", "categories", ["ai_category_id"], ["id"])
        batch.create_index("ix_complaints_issue_id", ["issue_id"])
        batch.create_index("ix_complaints_created_by_created_at", ["created_by", "created_at"])
        batch.create_unique_constraint("uq_complaint_client_request", ["created_by", "client_request_id"])

    # ---------------------------------------------------- links and suggestions
    schema.create_table(
        "issue_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("complaint_id", sa.Integer(), sa.ForeignKey("complaints.id"), nullable=False),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=False),
        sa.Column("link_type", sa.String(), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("match_breakdown", sa.JSON(), nullable=True),
        sa.Column("algorithm_version", sa.String(), nullable=True),
        sa.Column("linked_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        _ts("linked_at", nullable=False, server_default=sa.func.now()),
        _ts("unlinked_at", nullable=True),
        sa.Column("unlink_reason", sa.Text(), nullable=True),
    )
    schema.create_index(op.f("ix_issue_links_id"), "issue_links", ["id"])
    schema.create_index(op.f("ix_issue_links_issue_id"), "issue_links", ["issue_id"])
    cur = sa.text("unlinked_at IS NULL")
    schema.create_index("uq_issue_link_current", "issue_links", ["complaint_id"], unique=True,
                    sqlite_where=cur, postgresql_where=cur)

    schema.create_table(
        "complaint_embeddings",
        sa.Column("complaint_id", sa.Integer(), sa.ForeignKey("complaints.id"), primary_key=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("vector", sa.LargeBinary(), nullable=False),
    )

    schema.create_table(
        "duplicate_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("complaint_id", sa.Integer(), sa.ForeignKey("complaints.id"), nullable=False),
        sa.Column("candidate_issue_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        _ts("reviewed_at", nullable=True),
        _ts("created_at", server_default=sa.func.now()),
        sa.UniqueConstraint("complaint_id", "candidate_issue_id", name="uq_dup_suggestion"),
    )
    schema.create_index(op.f("ix_duplicate_suggestions_id"), "duplicate_suggestions", ["id"])
    schema.create_index(op.f("ix_duplicate_suggestions_candidate_issue_id"), "duplicate_suggestions", ["candidate_issue_id"])

    # ---------------------------------------------------------- work management
    schema.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_lead", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("task_description", sa.Text(), nullable=True),
        _ts("due_at", nullable=True),
        sa.Column("priority_at_assignment", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        _ts("assigned_at", server_default=sa.func.now()),
        _ts("acknowledged_at", nullable=True),
        _ts("started_at", nullable=True),
        _ts("completed_at", nullable=True),
        sa.Column("reassign_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reassign_reason", sa.Text(), nullable=True),
    )
    schema.create_index(op.f("ix_assignments_id"), "assignments", ["id"])
    schema.create_index("ix_assignments_staff_status", "assignments", ["staff_id", "status"])
    schema.create_index("ix_assignments_issue", "assignments", ["issue_id"])

    schema.create_table(
        "task_updates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id"), nullable=False),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        _ts("created_at", server_default=sa.func.now()),
    )
    schema.create_index(op.f("ix_task_updates_id"), "task_updates", ["id"])
    schema.create_index(op.f("ix_task_updates_assignment_id"), "task_updates", ["assignment_id"])
    schema.create_index(op.f("ix_task_updates_issue_id"), "task_updates", ["issue_id"])

    schema.create_table(
        "resolution_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=False),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id"), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("what_was_wrong", sa.Text(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("action_taken", sa.Text(), nullable=True),
        sa.Column("parts_replaced", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        _ts("completed_at", nullable=True),
        sa.Column("followup_needed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("followup_notes", sa.Text(), nullable=True),
        sa.Column("public_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        _ts("verified_at", nullable=True),
        sa.Column("verifier_comment", sa.Text(), nullable=True),
        _ts("created_at", server_default=sa.func.now()),
    )
    schema.create_index(op.f("ix_resolution_reports_id"), "resolution_reports", ["id"])
    schema.create_index("ix_resolution_reports_issue_cycle", "resolution_reports", ["issue_id", "cycle"])

    schema.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_type", sa.String(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("original_name", sa.String(), nullable=False),
        sa.Column("mime", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        _ts("created_at", server_default=sa.func.now()),
    )
    schema.create_index(op.f("ix_attachments_id"), "attachments", ["id"])
    schema.create_index("ix_attachments_owner", "attachments", ["owner_type", "owner_id"])

    # ---------------------------------------------------------------- feedback
    with op.batch_alter_table("feedback") as batch:
        batch.add_column(sa.Column("issue_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("resolution_report_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("resolved_for_me", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("still_unresolved", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_foreign_key("fk_feedback_issue", "issues", ["issue_id"], ["id"])
        batch.create_foreign_key("fk_feedback_report", "resolution_reports", ["resolution_report_id"], ["id"])
        batch.create_index("ix_feedback_issue_id", ["issue_id"])
        batch.create_unique_constraint("uq_feedback_complaint_report", ["complaint_id", "resolution_report_id"])

    # ------------------------------------------------- priority, SLA, escalation
    schema.create_table(
        "priority_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("weights", sa.JSON(), nullable=False),
        sa.Column("bands", sa.JSON(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        _ts("created_at", server_default=sa.func.now()),
    )
    schema.create_index(op.f("ix_priority_configs_id"), "priority_configs", ["id"])

    schema.create_table(
        "safety_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("applies_category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("risk_level", sa.Float(), nullable=False),
        sa.Column("floor_score", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    schema.create_index(op.f("ix_safety_rules_id"), "safety_rules", ["id"])

    schema.create_table(
        "priority_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("band", sa.String(), nullable=False),
        sa.Column("factors", sa.JSON(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("algorithm_version", sa.String(), nullable=False),
        sa.Column("config_version", sa.String(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=False),
        _ts("calculated_at", server_default=sa.func.now()),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    schema.create_index(op.f("ix_priority_assessments_id"), "priority_assessments", ["id"])
    schema.create_index("ix_assessments_issue_current", "priority_assessments", ["issue_id", "is_current"])

    schema.create_table(
        "priority_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("band", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("overridden_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        _ts("created_at", server_default=sa.func.now()),
        _ts("expires_at", nullable=True),
        _ts("cleared_at", nullable=True),
        sa.Column("cleared_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    schema.create_index(op.f("ix_priority_overrides_id"), "priority_overrides", ["id"])
    schema.create_index("ix_overrides_issue", "priority_overrides", ["issue_id"])

    schema.create_table(
        "sla_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("band", sa.String(), nullable=False),
        sa.Column("response_minutes", sa.Integer(), nullable=False),
        sa.Column("resolution_minutes", sa.Integer(), nullable=False),
        sa.Column("no_progress_minutes", sa.Integer(), nullable=False),
    )
    schema.create_index(op.f("ix_sla_policies_id"), "sla_policies", ["id"])

    schema.create_table(
        "escalation_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("band", sa.String(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("after_minutes", sa.Integer(), nullable=True),
        sa.Column("repeat_minutes", sa.Integer(), nullable=True),
        sa.Column("notify_role", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    schema.create_index(op.f("ix_escalation_rules_id"), "escalation_rules", ["id"])

    schema.create_table(
        "escalation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("escalation_rules.id"), nullable=True),
        sa.Column("rule_key", sa.String(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("recipient_ids", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        _ts("created_at", server_default=sa.func.now()),
    )
    schema.create_index(op.f("ix_escalation_events_id"), "escalation_events", ["id"])
    schema.create_index(op.f("ix_escalation_events_issue_id"), "escalation_events", ["issue_id"])

    # ----------------------------------------------- outbox, notifications, log
    schema.create_table(
        "domain_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=True),
        sa.Column("complaint_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        _ts("processed_at", nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    schema.create_index(op.f("ix_domain_events_id"), "domain_events", ["id"])
    schema.create_index(op.f("ix_domain_events_issue_id"), "domain_events", ["issue_id"])
    schema.create_index("ix_domain_events_pending", "domain_events", ["processed_at", "attempts"])

    schema.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=True),
        sa.Column("complaint_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("dedupe_key", sa.String(), nullable=False),
        sa.Column("group_key", sa.String(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        _ts("read_at", nullable=True),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        _ts("updated_at", server_default=sa.func.now()),
        sa.UniqueConstraint("recipient_id", "dedupe_key", name="uq_notification_dedupe"),
    )
    schema.create_index(op.f("ix_notifications_id"), "notifications", ["id"])
    schema.create_index(op.f("ix_notifications_group_key"), "notifications", ["group_key"])
    schema.create_index("ix_notifications_recipient_read", "notifications", ["recipient_id", "is_read", "created_at"])

    schema.create_table(
        "identity_access_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("complaint_id", sa.Integer(), sa.ForeignKey("complaints.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        _ts("created_at", server_default=sa.func.now()),
    )
    schema.create_index(op.f("ix_identity_access_log_id"), "identity_access_log", ["id"])


def downgrade() -> None:
    for table in ("identity_access_log", "notifications", "domain_events", "escalation_events",
                  "escalation_rules", "sla_policies", "priority_overrides", "priority_assessments",
                  "safety_rules", "priority_configs"):
        op.drop_table(table)
    with op.batch_alter_table("feedback") as batch:
        batch.drop_constraint("uq_feedback_complaint_report", type_="unique")
        batch.drop_index("ix_feedback_issue_id")
        batch.drop_constraint("fk_feedback_report", type_="foreignkey")
        batch.drop_constraint("fk_feedback_issue", type_="foreignkey")
        for col in ("still_unresolved", "resolved_for_me", "resolution_report_id", "issue_id"):
            batch.drop_column(col)
    for table in ("attachments", "resolution_reports", "task_updates", "assignments",
                  "duplicate_suggestions", "complaint_embeddings", "issue_links"):
        op.drop_table(table)
    legacy_level = _escalation_column()
    with op.batch_alter_table("complaints") as batch:
        if legacy_level and not legacy_level["nullable"] and legacy_level["default"] == "0":
            batch.alter_column("escalation_level", existing_type=sa.Integer(), server_default=None)
        batch.drop_constraint("uq_complaint_client_request", type_="unique")
        batch.drop_index("ix_complaints_created_by_created_at")
        batch.drop_index("ix_complaints_issue_id")
        for fk in ("fk_complaints_ai_category", "fk_complaints_student_category", "fk_complaints_asset",
                   "fk_complaints_location", "fk_complaints_category", "fk_complaints_issue"):
            batch.drop_constraint(fk, type_="foreignkey")
        for col in ("content_hash", "client_request_id", "has_dissent", "classification_disagreement",
                    "ai_confidence", "ai_category_id", "student_category_id", "anon_code", "is_anonymous",
                    "location_text", "asset_id", "location_id", "category_id", "issue_id"):
            batch.drop_column(col)
    op.drop_table("issues")
