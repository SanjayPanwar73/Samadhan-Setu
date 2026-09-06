from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.complaint import ComplaintStatus


class ComplaintCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=10_000)
    people_affected: int = Field(default=1, ge=1, le=1_000_000)

    @field_validator("title", "description")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text must not be blank")
        return value


class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus
    resolution_text: str | None = Field(default=None, max_length=5_000)
    remarks: str | None = Field(default=None, max_length=5_000)


class ComplaintOut(BaseModel):
    id: int
    title: str
    description: str
    category: str | None
    priority_score: float | None
    priority_breakdown: dict | None
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
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2_000)


class ComplaintOverride(BaseModel):
    department_id: int | None = None
    priority_score: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )


class ComplaintAssignment(BaseModel):
    staff_id: int | None = Field(default=None, ge=1)
