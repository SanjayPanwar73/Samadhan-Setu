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
from app.routers import auth, complaints, admin, management, notifications
import app.models  # noqa: F401  (ensures all models are registered on Base)
from app.services.escalation_service import run_escalation_check
from app.ai.rag import load_resolution_index
from app.ai.similarity import get_index

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def _scheduled_escalation_job():
    db = SessionLocal()
    try:
        run_escalation_check(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fresh local demos can create an empty schema. Production deployments
    # must run `alembic upgrade head` explicitly before starting the API.
    if settings.AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine)
    get_index()
    load_resolution_index()
    scheduler.add_job(
        _scheduled_escalation_job,
        "interval",
        minutes=settings.ESCALATION_CHECK_INTERVAL_MINUTES,
        id="escalation_check",
        replace_existing=True,
    )
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
app.include_router(complaints.router)
app.include_router(admin.router)
app.include_router(management.router)
app.include_router(notifications.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Complaint Prioritization API is running"}
