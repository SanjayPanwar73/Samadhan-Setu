# Samadhan Setu V2: College Complaint Intelligence System

Students report problems; duplicates become **one shared issue** (many preserved complaints);
department staff resolve it; students confirm. FastAPI + SQLAlchemy + Alembic backend, React + Vite frontend.

## Roles
| Role | Home | Can do |
|---|---|---|
| `student` | `/complaints` | Submit (optionally anonymous), track, give feedback |
| `staff` | `/tasks` | Acknowledge, update, resolve assigned tasks (never sees who reported) |
| `dept_admin` | `/department` | Queue, assign, verify resolutions, override priority, merge duplicates |
| `hod` | `/hod` | Read-only aggregates for their departments |
| `super_admin` | `/super/*` | Users, departments, locations/assets, priority/SLA/escalation config, audit, identity reveal |

Department scope is always read from `department_memberships` in the database, never from the JWT.
Another department's data answers **404**, not 403.

## Run locally
```bash
cd backend
pip install -r requirements-dev.txt
alembic upgrade head            # on a fresh database this creates everything
python -m scripts.seed_org      # departments, categories, a sample campus, demo users (password123)
uvicorn app.main:app --reload

cd ../frontend && npm install && npm run dev
```
Demo logins (development only): `student@example.com`, `water.staff@example.com`, `water.admin@example.com`,
`hod@example.com`, `super@example.com`.

## Upgrading an existing V1 database (expand, backfill, contract)
```bash
alembic upgrade b2d4f6a8c0e2                 # additive tables and columns
python -m scripts.migrate_v2_backfill --dry-run     # review the report; nothing is saved
python -m scripts.migrate_v2_backfill               # migrate + verify (row counts, text checksum)
python -m scripts.reembed                           # embeddings for duplicate grouping
alembic upgrade head                                # contract: drops V1-only columns (refuses if any complaint is unlinked)
```
Back up the database first. Old departments are retired, not deleted. Migrated students without an
enrollment number are asked for it on next login. V1 `management` users become `hod` with every real
department; narrow this from **Users and roles**.

## How it works
- **Intake** (`POST /complaints`): classify and embed outside the DB lock, then in one transaction: lock, group,
  link or create the issue, recompute counts, score priority, set SLA, write audit and outbox events.
- **Grouping**: SQL hard filters (department, category, asset, location) then a weighted score
  (asset .35, location .20, semantic .35, time .10). A named asset always joins that asset's active issue.
  If the student cannot name the asset and the place holds several identical ones, the result is capped at
  *possible duplicate* for an admin to decide. Concurrency: advisory lock (PostgreSQL) / write lock (SQLite) plus a
  partial unique index (one active issue per asset).
- **Priority v2**: nine interpretable factors, safety-rule floors, a critical gate (volume alone never makes
  Critical), versioned assessments, overrides with a reason.
- **State machine**: `open > assigned > in_progress > awaiting_verification > resolved > closed`, plus `reopened`,
  `rejected`, `merged`. Clients call action endpoints; invalid jumps return `409 {code}`.
- **Notifications**: transactional outbox, in-app, polled every 30 s. Payloads use an allow-list of keys.
- **Privacy**: separate view models per audience; anonymous complaints carry a per-complaint code; reveal is
  super-admin only, with a reason, and logged.

## Tests
```bash
cd backend && pytest -q          # needs requirements-dev.txt
cd frontend && npm test          # Vitest
python -m scripts.evaluate_priority      # ordering vs a labelled fixture ranking + regression snapshot
python -m scripts.evaluate_grouping      # precision/recall on labelled pairs
```

## Known limitations
- SQLite serialises writers (fine for one college; the schema and locking are PostgreSQL-ready).
- Priority weights, SLA minutes, escalation rules and safety patterns are **starting values**; calibrate on real incidents.
- Anonymous redaction is pattern based and cannot catch every name typed into free text.
- No email/SMS or real-time push; no per-IP rate limiting yet (a per-student daily cap exists); email verification is not enforced.
