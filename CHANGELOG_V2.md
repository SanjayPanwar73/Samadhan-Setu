# Samadhan Setu V2: what was changed

Compared with the original `Samadhan-Setu-main.zip` (107 files):
**95 files added, 26 modified, 18 removed** (now 184 files). Nothing here has been run against a real database or browser yet; see "Verification status" at the end.

---

## 1. The idea in one paragraph

V1 treated every complaint as its own task. V2 groups complaints about the same physical problem into **one shared issue** (for example, one broken water cooler with 50 reports). The issue is assigned, resolved and verified once. Every student's complaint is still kept, and each student is notified and gives feedback separately. Access is scoped by department, and anonymous complaints never expose the student to staff, admins or HODs.

---

## 2. Part 1: Organisation, roles and access control

**Roles:** `student`, `staff`, `dept_admin`, `hod`, `super_admin` (old `user`, `admin`, `management` still work as aliases until the backfill renames them).
**Scope:** department membership is read from the database on every request, never trusted from the token. Another department's data returns 404.

| File | What it does |
|---|---|
| `backend/app/core/roles.py` | V1/V2 role aliases, `has_role`, membership rules |
| `backend/app/deps.py` *(modified)* | `Scope` object, `get_scope`, V2-aware `require_role`, inactive users rejected |
| `backend/app/policies.py` | Object-level rules, including "staff must belong to the issue's department" |
| `backend/app/models/department_membership.py` | Who belongs to which department |
| `backend/app/models/category.py` | Categories per department (severity, criticality, SLA hours, verification/evidence flags) |
| `backend/app/models/location.py` | Location tree (campus > building > wing > floor > corridor > room) |
| `backend/app/models/asset.py` | Registered items (coolers, switchboards) with criticality |
| `backend/app/models/ticket_counter.py` | `WAT-001` style ticket numbers |
| `backend/app/models/audit_event.py` | Append-only audit log |
| `backend/app/models/user.py`, `department.py` *(modified)* | New roles, `enrollment_no`, `is_active`, department `code`/`is_system` |
| `backend/app/services/audit_service.py` | The only writer to the audit log |
| `backend/app/services/org_service.py` | Role/department consistency, location paths |
| `backend/app/schemas/org.py` | Request/response models for the admin screens |
| `backend/app/routers/reference.py` | Departments, categories, locations, assets for the forms |
| `backend/app/routers/admin_org.py` | Departments, categories, locations, assets, users, memberships, audit (`/admin/org/*`) |
| `backend/app/routers/auth.py`, `schemas/auth.py` *(modified)* | Enrollment number, email-domain allow-list, `/auth/me` with scope, enrollment prompt endpoint |
| `backend/alembic/versions/a1c3e5f7b9d1_m1_org_structure.py` | Migration m1 |
| `backend/scripts/seed_org.py` | Departments, categories, sample campus, demo users |

---

## 3. Part 2: The core workflow

### Intake and grouping
| File | What it does |
|---|---|
| `backend/app/services/intake_service.py` | Submit pipeline: validate, redact PII if anonymous, classify, embed, then one transaction to group, link/create the issue, score, notify |
| `backend/app/services/grouping_service.py` | SQL filters (department, category, asset, location) then scoring; high links, medium suggests, low creates |
| `backend/app/ai/grouping.py` | Scoring maths (asset .35, location .20, semantic .35, time .10), ambiguity cap |
| `backend/app/ai/providers.py` | Classifier/embedding/sentiment behind one interface, with safe fallbacks |
| `backend/app/models/issue.py` | Shared issue, plus a unique index: one active issue per asset |
| `backend/app/models/issue_link.py`, `complaint_embedding.py`, `duplicate_suggestion.py` | Link history, stored embeddings, suggestions for admins |
| `backend/app/core/database.py` *(modified)* | Grouping lock (PostgreSQL advisory lock / SQLite write lock), longer SQLite timeout |

### Work, resolution, feedback
| File | What it does |
|---|---|
| `backend/app/services/issue_service.py` | The only place status changes; state machine, counts, relink |
| `backend/app/services/assignment_service.py` | Assign, acknowledge, start, updates, reassignment |
| `backend/app/services/resolution_service.py` | Resolution report, approve/reject |
| `backend/app/services/feedback_service.py` | Per-student feedback, dissent, auto-reopen, auto-close |
| `backend/app/models/work.py` | Assignments, task updates, resolution reports, attachments |
| `backend/app/core/storage.py`, `services/attachment_service.py` | Safe file uploads (type checked by content, random names) |

### Priority, SLA, escalation
| File | What it does |
|---|---|
| `backend/app/ai/priority_v2.py` | Nine-factor priority model, safety floors, critical gate |
| `backend/app/services/priority_service.py` | Assessments, overrides, effective priority |
| `backend/app/services/sla_service.py` | SLA deadlines and escalation rules |
| `backend/app/models/priority.py` | Config, safety rules, assessments, overrides, SLA, escalation tables |

### Notifications and privacy
| File | What it does |
|---|---|
| `backend/app/services/notification_service.py` | Outbox events turned into in-app notifications; grouped and de-duplicated |
| `backend/app/models/events.py` | `domain_events`, `notifications`, `identity_access_log` |
| `backend/app/services/privacy.py` | PII redaction, anonymous codes, minimum-count message |
| `backend/app/schemas/v2.py`, `services/views.py` | Separate response views for student, staff, admin (no identity leaks) |

### API routers added
`complaints.py` and `notifications.py` (rewritten), `issues.py`, `assignments.py`, `tasks.py`, `resolutions.py`, `attachments.py`, `reports.py`, `admin_config.py`, `identity.py`, `_common.py`.

| Area | Main endpoints |
|---|---|
| Student | `POST /complaints`, `GET /complaints/me`, `GET /complaints/{id}`, `/timeline`, `/attachments`, `/feedback` |
| Admin | `GET /issues`, `/issues/{id}`, `/complaints`, `/history`, `PATCH /issues/{id}/classification`, `/reject`, `/reopen`, `/duplicate-suggestions`, `/priority`, `/priority/override`, `POST /issues/{id}/assignments`, `PATCH /assignments/{id}`, `/resolutions/{id}/approve|reject`, `/department-staff` |
| Staff | `GET /tasks`, `/tasks/{id}`, `/acknowledge`, `/start`, `/updates`, `/request-reassignment`, `/resolve`, `/attachments`, `/suggested-resolution` |
| Reports | `/reports/department-summary`, `resolution-times`, `staff-workload`, `satisfaction`, `repeat-failures`, `trends`, `escalations` |
| Super admin | `/admin/org/priority-config`, `safety-rules`, `sla-policies`, `escalation-rules`, `/admin/complaints/{id}/reveal-identity` |
| Everyone | `GET /notifications`, `/unread-count`, `POST /{id}/read`, `/read-all` |

`backend/alembic/versions/b2d4f6a8c0e2_m2_workflow.py` is migration m2. `backend/app/main.py` *(modified)* wires the routers, a `{code, detail}` error format and four scheduled jobs (escalation sweep, priority refresh, outbox sweep, feedback close).

---

## 4. Part 3: Frontend, migration and cleanup

### Frontend pages
| Role | Files |
|---|---|
| Student | `NewComplaint.jsx`, `Complaints.jsx`, `ComplaintDetail.jsx` (all rewritten) |
| Staff | `Tasks.jsx`, `TaskDetail.jsx` |
| Dept admin | `Department.jsx`, `IssueDetail.jsx`, `DepartmentStaff.jsx` |
| HOD | `Hod.jsx` |
| Super admin | `SuperUsers.jsx`, `SuperDepartments.jsx`, `SuperLocationsAssets.jsx`, `SuperConfig.jsx`, `SuperAudit.jsx` |
| Everyone | `Notifications.jsx` (rewritten), `Login.jsx`, `Register.jsx` (enrollment number), `Profile.jsx` |

### Frontend components, hooks, utilities
`pickers.jsx` (location and asset), `IssueParts.jsx` (priority badge, SLA, flags, factor breakdown), `IssueQueueTable.jsx`, `IssueFilters.jsx`, `AdminPanels.jsx` (linked complaints, duplicate card, assignment, priority override, resolution review, history), `ResolutionForm.jsx` (driven by the category's rules), `FeedbackForm.jsx`, `Timeline.jsx`, `NotificationBell.jsx`, `EnrollmentPrompt.jsx`, `hooks/useAction.js`, `hooks/useUnreadCount.js`, `utils/issues.js`.
Modified: `App.jsx` (role routes, old URLs redirect), `UserLayout.jsx` (per-role menu, bell), `ProtectedRoute.jsx`, `utils/auth.js` (V2 roles, safe return paths).

### Data migration and cleanup
| File | What it does |
|---|---|
| `backend/scripts/migrate_v2_backfill.py` | Converts V1 data: roles, department mapping and memberships, one issue per V1 group, priority kept as a legacy assessment, history to the audit log, resolutions to reports. Supports `--dry-run`, safe to re-run, verifies counts and a checksum of complaint text |
| `backend/scripts/reembed.py` | Computes embeddings after the backfill |
| `backend/scripts/evaluate_priority.py`, `evaluate_grouping.py` | Measure ordering and duplicate matching on labelled fixtures |
| `backend/alembic/versions/c3e5a7b9d1f3_m3_contract_v1_columns.py` | Drops V1-only columns; refuses to run if any complaint is not yet linked to an issue |
| `README.md`, `V2_PARTS.md` | Setup, upgrade order, delivery status |

---

## 5. Tests added

| File | Covers |
|---|---|
| `backend/tests/test_org_rbac.py` | Roles, department scope, memberships, audit |
| `backend/tests/test_part2_intake_grouping.py` | 50 students one cooler; two coolers in one corridor; concurrent submits; duplicates; recurrence; relink |
| `backend/tests/test_part2_workflow.py` | Full lifecycle, illegal transitions, per-student notifications, feedback, anonymity, safety vs volume, dissent and reopen, escalation, SLA |
| `backend/tests/test_part2_pure.py` | Priority and grouping maths, PII redaction (no database needed) |
| `backend/tests/test_backfill.py` | V1 to V2 migration on a V1-shaped database, re-run safety |
| `backend/tests/test_v1_characterization.py` | Registration, login, enrollment prompt, V1 routes gone |
| `frontend/src/test/roles.test.js`, `logic.test.jsx` | Role helpers, return paths, badges, SLA text, form rules |

`backend/tests/conftest.py` provides fake AI providers (no model downloads) and a small test campus.

---

## 6. Removed (V1 only)

`backend/app/routers/admin.py`, `management.py`; `schemas/complaint.py`; `services/complaint_service.py`, `escalation_service.py`; `ai/priority.py`, `ai/similarity.py` (complaint FAISS index); `scripts/seed.py`, `evaluate.py`; frontend `Admin.jsx`, `Management.jsx`, `Staff.jsx`, `Departments.jsx`, `ComplaintTable.jsx`, `ComplaintWorkspace.jsx`, `DistributionChart.jsx`, `PagePlaceholder.jsx`, `test/workspace.test.jsx`.

The old `complaint_history` and `resolution_history` tables are kept; the backfill copies them into the new audit log and reports.

---

## 7. Behaviour changes to be aware of

- New registrations are `student` and must give an enrollment number. Migrated students without one are asked on next login.
- A complaint can only be assigned to staff who belong to its department.
- The same student cannot report the same issue twice (409 with the existing complaint id).
- `people_affected` is only a hint; it does not change priority.
- One student's "still unresolved" never reopens an issue alone; it flags it for review until enough different students agree (default: at least 2 and 30%).
- Old `management` users become `hod` for every real department; narrow this afterwards.
- Old departments are retired (hidden), not deleted.

---

## 8. Verification status

| Check | Result |
|---|---|
| Python syntax and import resolution, all backend files | Passed |
| 21 pure-logic backend tests | Passed |
| `evaluate_priority.py` | Rank correlation 0.954, hazards Critical, volume never Critical (10 hand-made fixtures) |
| `evaluate_grouping.py` | Precision 1.00, recall 0.75 (8 hand-made pairs) |
| Frontend full bundle (all imports and exports resolve) | Passed |
| 19 frontend logic and render tests (through a small shim) | Passed |
| Backend API and backfill tests (78 tests) | **Not run yet** (needs FastAPI and SQLAlchemy installed) |
| Real Vitest, browser walkthrough, PostgreSQL, real AI models | **Not run yet** |

Starting values for priority weights, SLA minutes, escalation rules and safety patterns still need calibration on real incidents.
