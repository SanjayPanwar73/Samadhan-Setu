from contextlib import asynccontextmanager
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.routers import (
    admin_config, admin_org, assignments, attachments, auth, complaints, identity, issues,
    notifications, reference, reports, resolutions, tasks,
)
from app.core.errors import DomainError
import app.models  # noqa: F401  (ensures all models are registered on Base)
from app.ai.rag import load_resolution_index
from app.ai.providers import warm_intake_models

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def _run_job(fn):
    """Run a scheduled service function in its own session; one failing job never kills the scheduler."""
    db = SessionLocal()
    try:
        fn(db)
    except Exception:  # noqa: BLE001
        logger.exception("scheduled job %s failed", getattr(fn, "__name__", fn))
        db.rollback()
    finally:
        db.close()


def _issue_escalation_job():
    from app.services.sla_service import run_issue_escalations

    _run_job(run_issue_escalations)


def _priority_refresh_job():
    from app.services.priority_service import refresh_active

    _run_job(refresh_active)


def _feedback_close_job():
    from app.services.feedback_service import close_expired

    _run_job(close_expired)


def _outbox_job():
    from app.services.notification_service import dispatch_pending

    try:
        dispatch_pending()
    except Exception:  # noqa: BLE001
        logger.exception("outbox sweep failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fresh local demos can create an empty schema. Production deployments
    # must run `alembic upgrade head` explicitly before starting the API.
    if settings.AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine)
    load_resolution_index()
    if settings.AI_PRELOAD_MODELS:
        scheduler.add_job(warm_intake_models, "date", id="warm_intake_models",
                          replace_existing=True, misfire_grace_time=None)
    # max_instances=1 + coalesce: jobs never overlap and missed runs collapse into one.
    for fn, job_id, kwargs in (
        (_issue_escalation_job, "issue_escalation", {"minutes": settings.ISSUE_ESCALATION_INTERVAL_MINUTES}),
        (_priority_refresh_job, "priority_refresh", {"minutes": settings.PRIORITY_REFRESH_MINUTES}),
        (_feedback_close_job, "feedback_close", {"hours": 1}),
        (_outbox_job, "outbox_sweep", {"seconds": settings.OUTBOX_SWEEP_SECONDS}),
    ):
        scheduler.add_job(fn, "interval", id=job_id, replace_existing=True, max_instances=1,
                          coalesce=True, **kwargs)
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown()


app = FastAPI(title="Complaint Prioritization & Escalation System", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "errors": jsonable_encoder(exc.errors()),
        },
    )


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code,
                        content={"code": exc.code, "detail": exc.detail, **exc.extra})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error while handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "A database error occurred"})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error while handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Localhost regex is intentionally disabled in production; production origins
# must be explicitly listed in CORS_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=(
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        if settings.ENVIRONMENT != "production"
        else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(reference.router)
app.include_router(complaints.router)
app.include_router(notifications.router)
app.include_router(admin_org.router)
app.include_router(issues.router)
app.include_router(assignments.router)
app.include_router(tasks.router)
app.include_router(resolutions.router)
app.include_router(attachments.router)
app.include_router(reports.router)
app.include_router(admin_config.router)
app.include_router(identity.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Complaint Prioritization API is running"}
