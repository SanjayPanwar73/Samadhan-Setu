from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.routers import auth, complaints, admin, management, notifications
import app.models  # noqa: F401  (ensures all models are registered on Base)
from app.services.escalation_service import run_escalation_check

scheduler = BackgroundScheduler()


def _scheduled_escalation_job():
    db = SessionLocal()
    try:
        run_escalation_check(db)
    finally:
        db.close()


def _ensure_compatibility_schema():
    """Add non-destructive columns for databases created before new model fields."""
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("complaints")}
    if "issue_root_id" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE complaints ADD COLUMN issue_root_id INTEGER "
                    "REFERENCES complaints(id)"
                )
            )
            connection.execute(
                text("UPDATE complaints SET issue_root_id = id WHERE issue_root_id IS NULL")
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    _ensure_compatibility_schema()
    scheduler.add_job(
        _scheduled_escalation_job,
        "interval",
        minutes=settings.ESCALATION_CHECK_INTERVAL_MINUTES,
        id="escalation_check",
    )
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown()


app = FastAPI(title="Complaint Prioritization & Escalation System", lifespan=lifespan)

# Allow the React frontend (Vite dev server, typically localhost:5173) to call this API.
# Wide open for local dev/demo purposes; tighten allow_origins before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    # Vite may move to the next available port when another dev server is
    # already running. Keep local development working without weakening
    # production origins configured through CORS_ORIGINS.
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
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
