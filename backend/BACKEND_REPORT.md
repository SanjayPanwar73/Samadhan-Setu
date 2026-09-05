# Samadhan Setu Backend Report

## 1. Overview

This backend is a FastAPI-based **Complaint Prioritization and Escalation System**. It accepts public complaints, uses AI to classify and score them, assigns them to a department, controls access using roles, and escalates overdue complaints automatically.

## 2. Technology Stack

- **API framework:** FastAPI
- **Server:** Uvicorn
- **Database ORM:** SQLAlchemy
- **Database:** Neon PostgreSQL (configured through `DATABASE_URL`)
- **Authentication:** JWT bearer tokens
- **Password hashing:** bcrypt
- **Validation:** Pydantic and email-validator
- **Background jobs:** APScheduler
- **AI/NLP:** Hugging Face Transformers
- **Text similarity:** Sentence Transformers with FAISS
- **Evaluation:** scikit-learn
- **Migrations:** Alembic

Main dependencies are listed in [requirements.txt](./requirements.txt).

## 3. Application Structure

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── security.py
│   ├── models/
│   │   ├── user.py
│   │   ├── complaint.py
│   │   ├── department.py
│   │   ├── complaint_history.py
│   │   └── feedback.py
│   ├── schemas/
│   │   ├── auth.py
│   │   └── complaint.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── complaints.py
│   │   ├── admin.py
│   │   └── management.py
│   ├── services/
│   │   ├── complaint_service.py
│   │   └── escalation_service.py
│   └── ai/
│       ├── classifier.py
│       ├── sentiment.py
│       ├── similarity.py
│       └── priority.py
├── scripts/
│   ├── seed.py
│   └── evaluate.py
└── alembic/
```

## 4. Main Features

### Complaint intake

Users submit a complaint with:

- Title
- Description
- Number of people affected

The complaint is then processed through the complete AI pipeline.

### AI processing pipeline

1. Complaint is initially saved in the database.
2. Zero-shot classification predicts a category.
3. Sentence embeddings and FAISS search detect similar complaints.
4. Sentiment analysis identifies positive or negative sentiment.
5. A transparent priority score from 0 to 100 is calculated.
6. A department is selected using the predicted category.
7. AI results are saved to the complaint record.
8. A history entry is created.

Supported categories include electricity, water supply, sanitation, road maintenance, public safety, noise complaint, internet/telecom, and other.

### Priority scoring

The priority score uses these weighted factors:

- Severity: 35%
- People affected: 30%
- Complaint age: 20%
- Repeat count: 15%

Higher scores indicate more urgent complaints.

### Escalation

Pending or in-progress complaints past their SLA deadline are escalated. The system:

- Increases `escalation_level`
- Creates a complaint history record
- Runs automatically every 10 minutes by default
- Can also be triggered manually by an admin

New complaints receive a default SLA of 72 hours.

## 5. Authentication and Roles

The backend uses JWT authentication and bcrypt password hashing.

Available roles:

- `user`: Submit and view own complaints, add feedback
- `staff`: View complaints and update complaint status
- `admin`: Manage escalations and departments
- `management`: View priority and analytics dashboards

Complaint status transitions are controlled:

```text
pending -> in_progress or rejected
in_progress -> resolved or rejected
resolved -> no further transition
rejected -> no further transition
```

## 6. API Endpoints

### Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login and receive JWT token |

### Complaints

| Method | Endpoint | Access |
|---|---|---|
| POST | `/complaints` | Authenticated users |
| GET | `/complaints/me` | Own complaints |
| GET | `/complaints/{complaint_id}` | Owner, staff, admin, management |
| PATCH | `/complaints/{complaint_id}/status` | Staff and admin |
| POST | `/complaints/{complaint_id}/feedback` | Complaint owner |

### Admin

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/admin/escalations` | List escalated complaints |
| POST | `/admin/escalations/run-now` | Run escalation check immediately |
| GET | `/admin/departments` | List departments |

### Management dashboard

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/management/priority-queue` | Show highest-priority open complaints |
| GET | `/management/category-distribution` | Count complaints by category |
| GET | `/management/sla-violations` | Count overdue complaints |
| GET | `/management/resolution-trends` | Average resolution time by category |

### Health/status

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Confirm that the API is running |

Swagger documentation is available at `/docs`.

## 7. Database Entities

### Users

Stores name, email, hashed password, role, and creation time.

### Complaints

Stores complaint text, AI category, priority score, sentiment, status, department, SLA deadline, escalation level, and timestamps.

### Departments

Stores department names and category keywords used for automatic assignment.

### Complaint history

Audits creation/classification, status changes, and system escalations.

### Feedback

Stores a 1-to-5 rating and optional comment from the complaint owner.

## 8. Configuration

Configuration is read from `.env` through [config.py](./app/core/config.py).

### Neon setup

1. Create a project in Neon.
2. Copy the pooled PostgreSQL connection string from Neon.
3. Put it in `backend/.env`:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

Do not commit `.env` or expose the connection string publicly. The required `psycopg2-binary` driver is already in [requirements.txt](./requirements.txt). Tables are created automatically when the API starts.

Important settings:

- `DATABASE_URL`
- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `ESCALATION_CHECK_INTERVAL_MINUTES`
- `DEFAULT_SLA_HOURS`
- `CORS_ORIGINS`

For production, the default secret key must be replaced and CORS origins should be restricted.

## 9. Seed Data and Evaluation

The seed script creates:

- Eight departments
- One sample user for every role
- Approximately 25 sample complaints

Run it from the `backend` directory:

```powershell
python -m scripts.seed
```

The evaluation script measures classification, priority ranking, and similarity performance:

```powershell
python -m scripts.evaluate
```

The first AI run downloads models from Hugging Face and may require approximately 1.5 GB of internet downloads.

## 10. How to Run

From the project root in PowerShell:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload
```

Open the API documentation:

```text
http://127.0.0.1:8000/docs
```

## 11. Overall Assessment

The backend already contains the core functionality expected from a complaint management system: authentication, role-based access, complaint processing, AI classification, prioritization, duplicate detection, department assignment, feedback, analytics, audit history, and automatic escalation.

Before production deployment, the following should be reviewed:

- Replace the default `SECRET_KEY`.
- Restrict CORS origins.
- Use PostgreSQL instead of SQLite for production workloads.
- Add rate limiting and stronger input constraints.
- Add automated API and service tests.
- Review FAISS index concurrency and persistence for multi-worker deployment.
- Replace SQLite-specific resolution-trend SQL when using PostgreSQL.
