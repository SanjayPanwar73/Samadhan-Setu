from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.routers import auth, complaints, admin, management
import app.models  # noqa: F401  (ensures all models are registered on Base)
from app.services.escalation_service import run_escalation_check

scheduler = BackgroundScheduler()


def _scheduled_escalation_job():
    db = SessionLocal()
    try:
        run_escalation_check(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(complaints.router)
app.include_router(admin.router)
app.include_router(management.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Complaint Prioritization API is running"}
