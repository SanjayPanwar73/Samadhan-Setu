from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User, UserRole
from app.core.config import settings
from app.core.roles import has_role
from app.schemas.auth import EnrollmentIn, MeOut, UserRegister, UserLogin, UserOut, Token
from app.deps import Scope, get_current_user, get_scope

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    domain = payload.email.rsplit("@", 1)[-1].lower()
    allowed = [d.lower().lstrip("@") for d in settings.ALLOWED_EMAIL_DOMAINS]
    if allowed and domain not in allowed:
        raise HTTPException(status_code=400, detail="Please register with your college email address")
    if settings.REQUIRE_ENROLLMENT_NO and not payload.enrollment_no:
        raise HTTPException(status_code=422, detail="Enrollment number is required")

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if payload.enrollment_no and db.query(User).filter(User.enrollment_no == payload.enrollment_no).first():
        raise HTTPException(status_code=400, detail="Enrollment number already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        enrollment_no=payload.enrollment_no,
        # Public registration has no role input; the server owns this decision.
        role=UserRole.student,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    return _authenticate(payload.email, payload.password, db)


def _authenticate(email: str, password: str, db: Session) -> Token:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password) or user.is_active is False:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return Token(access_token=token, role=user.role, user=user)


@router.post("/token", response_model=Token)
def swagger_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2 form-compatible login endpoint used by Swagger Authorize."""
    return _authenticate(form_data.username, form_data.password, db)


@router.get("/me", response_model=MeOut)
def current_profile(
    current_user: User = Depends(get_current_user), scope: Scope = Depends(get_scope)
):
    return MeOut(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        enrollment_no=current_user.enrollment_no,
        needs_enrollment_no=has_role(current_user, "student") and not current_user.enrollment_no,
        is_global=scope.is_global,
        department_ids=sorted(scope.department_ids),
    )


@router.patch("/me/enrollment", response_model=MeOut)
def set_enrollment(
    payload: EnrollmentIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: Scope = Depends(get_scope),
):
    """Accounts migrated from V1 have no enrollment number; students add it once after login."""
    if not has_role(current_user, "student"):
        raise HTTPException(status_code=403, detail="Only students have an enrollment number")
    if current_user.enrollment_no:
        raise HTTPException(status_code=409, detail="Your enrollment number is already set")
    if db.query(User).filter(User.enrollment_no == payload.enrollment_no).first():
        raise HTTPException(status_code=400, detail="Enrollment number already registered")
    current_user.enrollment_no = payload.enrollment_no
    db.commit()
    return current_profile(current_user, scope)
