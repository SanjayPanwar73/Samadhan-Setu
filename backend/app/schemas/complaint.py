from datetime import datetime

from pydantic import BaseModel

from app.models.complaint import ComplaintStatus


class ComplaintCreate(BaseModel):
    title: str
    description: str
    people_affected: int = 1


class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus
    resolution_text: str | None = None
    remarks: str | None = None


class ComplaintOut(BaseModel):
    id: int
    title: str
    description: str
    category: str | None
    priority_score: float | None
    sentiment_label: str | None
    status: ComplaintStatus
    department_id: int | None
    created_by: int
    assigned_to: int | None
    issue_root_id: int | None
    escalation_level: int
    sla_deadline: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackCreate(BaseModel):
    rating: int
    comment: str | None = None


class ComplaintOverride(BaseModel):
    department_id: int | None = None
    priority_score: float | None = None


class ComplaintAssignment(BaseModel):
    staff_id: int | None = None
