from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class DepartmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=8, pattern=r"^[A-Za-z]+$")
    requires_verification_default: bool = False

    @field_validator("name", "code", mode="before")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)


class DepartmentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=120)
    is_active: bool | None = None
    requires_verification_default: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str | None
    is_active: bool
    is_system: bool
    requires_verification_default: bool


class CategoryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department_id: int = Field(ge=1)
    name: str = Field(min_length=2, max_length=120)
    base_severity: float = Field(default=0.3, ge=0, le=1)
    default_criticality: float = Field(default=0.3, ge=0, le=1)
    impact_level: float = Field(default=0.3, ge=0, le=1)
    expected_resolution_hours: int = Field(default=48, ge=1, le=24 * 90)
    requires_verification: bool = False
    requires_evidence: bool = False
    resolution_schema: dict | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)


class CategoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=120)
    base_severity: float | None = Field(default=None, ge=0, le=1)
    default_criticality: float | None = Field(default=None, ge=0, le=1)
    impact_level: float | None = Field(default=None, ge=0, le=1)
    expected_resolution_hours: int | None = Field(default=None, ge=1, le=24 * 90)
    requires_verification: bool | None = None
    requires_evidence: bool | None = None
    resolution_schema: dict | None = None
    is_active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    department_id: int
    name: str
    base_severity: float
    default_criticality: float
    impact_level: float
    expected_resolution_hours: int
    requires_verification: bool
    requires_evidence: bool
    resolution_schema: dict | None
    is_active: bool


class LocationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_id: int | None = Field(default=None, ge=1)
    kind: str
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name", "kind", mode="before")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)


class LocationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parent_id: int | None
    kind: str
    name: str
    path: str
    is_active: bool


class AssetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department_id: int = Field(ge=1)
    location_id: int = Field(ge=1)
    asset_type: str = Field(min_length=2, max_length=60)
    tag: str = Field(min_length=2, max_length=60)
    name: str = Field(min_length=2, max_length=120)
    criticality: int = Field(default=3, ge=1, le=5)

    @field_validator("asset_type", "tag", "name", mode="before")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)


class AssetPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=120)
    location_id: int | None = Field(default=None, ge=1)
    criticality: int | None = Field(default=None, ge=1, le=5)
    is_active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    department_id: int
    location_id: int
    asset_type: str
    tag: str
    name: str
    criticality: int
    is_active: bool


class AdminUserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: UserRole
    enrollment_no: str | None = Field(default=None, max_length=32)
    department_ids: list[int] = []

    @field_validator("name", mode="before")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("enrollment_no", mode="before")
    @classmethod
    def normalize_enrollment(cls, value):
        return (value.strip().upper() or None) if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def check_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class AdminUserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: UserRole | None = None
    is_active: bool | None = None
    # Lets a role change and its new departments land in one validated step.
    department_ids: list[int] | None = None
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)


class MembershipsPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department_ids: list[int]
    reason: str | None = Field(default=None, max_length=500)


class AdminUserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    enrollment_no: str | None
    is_active: bool
    department_ids: list[int]


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_id: int | None
    actor_role: str | None
    action: str
    entity_type: str
    entity_id: int | None
    issue_id: int | None
    before: dict | None
    after: dict | None
    reason: str | None
    created_at: datetime
