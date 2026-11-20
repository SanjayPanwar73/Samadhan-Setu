"""Request schemas and role-specific response views (the privacy boundary, design 9.2).

No endpoint returns an ORM object. Each audience has its own view model; fields that
identify a student exist only on the views that are allowed to show them."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip(v):
    return v.strip() if isinstance(v, str) else v


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------- requests
class ComplaintCreate(Strict):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=4000)
    location_id: int = Field(ge=1)
    department_id: int | None = Field(default=None, ge=1)
    category_id: int | None = Field(default=None, ge=1)
    asset_id: int | None = Field(default=None, ge=1)
    people_affected: int | None = Field(default=None, ge=0, le=100000)  # a hint only, never scored
    is_anonymous: bool = False
    location_text: str | None = Field(default=None, max_length=200)
    client_request_id: str | None = Field(default=None, min_length=8, max_length=64)

    @field_validator("title", "description", "location_text", mode="before")
    @classmethod
    def strip_text(cls, v):
        return _strip(v)


class FeedbackIn(Strict):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)
    resolved_for_me: bool
    still_unresolved: bool = False


class RelinkIn(Strict):
    issue_id: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=500)


class ReasonIn(Strict):
    reason: str = Field(min_length=5, max_length=500)


class ClassificationPatch(Strict):
    category_id: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=500)
    expected_version: int | None = Field(default=None, ge=1)


class OverrideIn(Strict):
    score: float = Field(ge=0, le=100)
    reason: str = Field(min_length=1, max_length=500)  # minimum length enforced in the service
    expires_at: datetime | None = None


class AssignIn(Strict):
    staff_ids: list[int] = Field(min_length=1, max_length=10)
    lead_staff_id: int | None = Field(default=None, ge=1)
    task_description: str | None = Field(default=None, max_length=1000)
    due_at: datetime | None = None


class AssignmentPatch(Strict):
    staff_id: int | None = Field(default=None, ge=1)
    due_at: datetime | None = None


class TaskUpdateIn(Strict):
    kind: str = Field(pattern="^(progress|blocker|note)$")
    body: str = Field(min_length=2, max_length=2000)


class ReassignRequestIn(Strict):
    reason: str = Field(min_length=5, max_length=1000)


class ResolveIn(Strict):
    what_was_wrong: str | None = Field(default=None, max_length=2000)
    root_cause: str | None = Field(default=None, max_length=2000)
    action_taken: str | None = Field(default=None, max_length=2000)
    parts_replaced: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
    followup_needed: bool = False
    followup_notes: str | None = Field(default=None, max_length=1000)
    public_summary: str | None = Field(default=None, max_length=500)
    completed_at: datetime | None = None


class ApproveIn(Strict):
    comment: str | None = Field(default=None, max_length=1000)


class RejectResolutionIn(Strict):
    comment: str = Field(min_length=3, max_length=1000)


class RevealIn(Strict):
    reason: str = Field(min_length=10, max_length=500)


# --------------------------------------------------------------- response views
class ComplaintOwnerView(BaseModel):
    """The student's own record (and nothing about other students)."""
    id: int
    ticket_no: str | None
    title: str
    description: str
    department_name: str | None
    category_name: str | None
    location_path: str | None
    asset_name: str | None
    is_anonymous: bool
    anon_code: str | None
    status: str
    status_label: str
    created_at: datetime
    shared_message: str
    resolution_summary: str | None
    feedback_state: str          # none | pending | submitted
    has_dissent: bool


class ComplaintAdminView(BaseModel):
    """Department admin / super admin. The name appears only for identified complaints."""
    id: int
    title: str
    description: str
    created_at: datetime
    is_anonymous: bool
    anon_code: str | None
    submitter_name: str | None
    link_type: str | None = None
    match_score: float | None = None
    classification_disagreement: bool = False
    ai_confidence: float | None = None
    has_dissent: bool = False


class ComplaintStaffView(BaseModel):
    """Assigned staff: what is wrong and where, never who reported it."""
    id: int
    title: str
    description: str
    location_path: str | None
    asset_name: str | None
    created_at: datetime


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    issue_id: int | None
    complaint_id: int | None
    title: str
    body: str
    payload: dict | None
    count: int
    is_read: bool
    created_at: datetime
