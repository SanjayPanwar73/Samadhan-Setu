# Complaint Prioritization & Escalation System — Backend

AI-powered complaint intake, classification, prioritization, and escalation API.

> **Fixed in this version:** added missing `email-validator` dependency (required
> by Pydantic's `EmailStr`, was causing a startup crash), and added CORS
> middleware (`CORS_ORIGINS` in `.env`) so the Part B frontend can call this API.
> Verified end-to-end: register → login → JWT → complaint submission → AI
> pipeline → RBAC enforcement, all working.

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env            # edit if needed (defaults work out of the box)
```

> The first run of the AI modules (classifier, similarity, sentiment) will
> download models from Hugging Face (~1.5GB total). This needs internet
> access once; models are cached locally after that.

## Run the API

```bash
uvicorn app.main:app --reload
```

- Swagger UI: http://127.0.0.1:8000/docs
- The app creates all tables automatically on startup (SQLite by default,
  `complaints.db` in this folder). No manual migration needed for a fresh
  run — Alembic is there for when the schema changes later.

## Seed sample data

Populates departments, one user per role, and ~25 sample complaints run
through the full AI pipeline:

```bash
python -m scripts.seed
```

Login credentials for all seeded users: password is `password123`
- user@example.com (role: user)
- staff@example.com (role: staff)
- admin@example.com (role: admin)
- management@example.com (role: management)

## Run the eval harness

Produces classification/priority/similarity metrics for your report:

```bash
python -m scripts.evaluate
```

## Database migrations (Alembic)

```bash
# after changing a model:
python -m alembic revision --autogenerate -m "describe the change"
python -m alembic upgrade head
```

## Project layout

```
app/
├── main.py          # FastAPI app, router wiring, startup scheduler
├── core/             # config, DB session, JWT/password utilities
├── models/           # SQLAlchemy tables
├── schemas/          # Pydantic request/response contracts
├── routers/           # auth, complaints, admin, management endpoints
├── services/           # business logic (complaint pipeline, escalation)
└── ai/                  # classifier, similarity, sentiment, priority
scripts/
├── seed.py            # populate sample data
└── evaluate.py         # AI evaluation metrics
```

## Manually testing the escalation job

The scheduler runs automatically every `ESCALATION_CHECK_INTERVAL_MINUTES`.
To test without waiting, call as an admin:

```
POST /admin/escalations/run-now
```

## Exit criteria checklist (Part A10 of the build plan)

- [x] Every endpoint documented and testable in Swagger
- [x] Auth + RBAC enforced on all protected routes
- [x] A complaint submitted via API comes back fully classified, scored, and assigned
- [x] Escalation job runs and visibly changes complaint state on an overdue complaint
- [x] Dashboard aggregation endpoints return sane JSON
- [x] Eval script produces real numbers

Run through these yourself against your seeded data before moving to the frontend.
