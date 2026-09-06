# Complaint Prioritization & Escalation System — Backend

AI-powered complaint intake, classification, prioritization, and escalation API.

The local demo uses SQLite and generates an ephemeral signing key when no
`SECRET_KEY` is configured. Configure a random `SECRET_KEY` (at least 32
characters), `ENVIRONMENT=production`, and `AUTO_CREATE_SCHEMA=false` for
production.

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
- A fresh local SQLite database is created automatically. Existing or
  production databases must be upgraded explicitly with `python -m alembic
  upgrade head`; the API does not mutate an existing schema at startup.

## Seed sample data and provision the initial admin

Provision the initial admin from backend-only environment variables, then
populate demo users and ~25 sample complaints run
through the full AI pipeline:

```bash
python -m scripts.seed
```

For local development, the default admin and demo password is `password123`.
Set `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` in `.env` before
running the seed command in any non-development environment. The seed is
idempotent and never creates a second admin.

- Initial admin: admin@example.com (role: admin)
- user@example.com (role: user)
- staff@example.com (role: staff)
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

Migrations form one linear chain ending at `9d1e3f5a7b2c`; do not use
`Base.metadata.create_all` as a substitute for migrations in production.

## Project layout

```
app/
├── main.py          # FastAPI app, router wiring, startup scheduler
├── core/             # config, DB session, JWT/password utilities
├── models/           # SQLAlchemy tables
├── schemas/          # Pydantic request/response contracts
├── routers/           # auth, complaints, admin, management endpoints
├── services/           # business logic (complaint pipeline, escalation)
└── ai/                  # classifier, similarity, sentiment, priority, RAG
scripts/
├── seed.py            # populate sample data
├── evaluate.py         # AI evaluation metrics
├── backfill_resolution_index.py
└── evaluate_rag.py     # qualitative RAG retrieval evaluation
```

### Resolution suggestions

Staff and admins can call `GET /complaints/{id}/suggested-resolution` after
resolved complaints have been recorded with a resolution note. Retrieval-only
mode works without any external service. If local Ollama is running at
`http://localhost:11434` with the `phi3` model, the endpoint also returns an
advisory generated suggestion; otherwise `generated` is `false`.

```bash
python -m scripts.backfill_resolution_index
python -m scripts.evaluate_rag
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
