"""Staff task board. Staff only ever see assignments addressed to them."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import joinedload, Session

from app.core.database import get_db
from app.core.errors import DomainError
from app.core.timeutil import as_utc, utcnow
from app.deps import require_role
from app.models.issue import Issue
from app.models.user import User
from app.models.work import Assignment, TaskUpdate
from app.routers._common import commit_and_dispatch
from app.schemas.v2 import ReassignRequestIn, ResolveIn, TaskUpdateIn
from app.services import assignment_service, attachment_service, resolution_service, views

router = APIRouter(prefix="/tasks", tags=["tasks"])
staff_only = Depends(require_role("staff"))


def _row(a: Assignment) -> dict:
    issue = a.issue
    due = as_utc(a.due_at)
    active = a.status in ("assigned", "acknowledged", "in_progress", "awaiting_verification")
    return {"id": a.id, "issue_id": issue.id, "ticket_no": issue.ticket_no, "title": issue.title,
            "status": a.status, "issue_status": issue.status, "is_lead": a.is_lead,
            "priority_band": issue.priority_band, "due_at": a.due_at,
            "overdue": bool(active and due and utcnow() > due),
            "location_path": issue.location.path if issue.location else None,
            "reassign_requested": a.reassign_requested}


@router.get("")
def my_tasks(status: str | None = Query(None, max_length=30), offset: int = Query(0, ge=0, le=100_000),
             limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db),
             staff: User = staff_only):
    q = db.query(Assignment).filter(Assignment.staff_id == staff.id)
    if status:
        q = q.filter(Assignment.status == status)
    rows = (q.options(joinedload(Assignment.issue).joinedload(Issue.location))
            .order_by(Assignment.id.desc()).offset(offset).limit(limit).all())
    return [_row(a) for a in rows]


@router.get("/{task_id}")
def task_detail(task_id: int, db: Session = Depends(get_db), staff: User = staff_only):
    a = assignment_service.get_task(db, task_id, staff)
    issue = a.issue
    updates = db.query(TaskUpdate).filter(TaskUpdate.assignment_id == a.id).order_by(TaskUpdate.id).all()
    cat = issue.category
    return {**_row(a), "summary": issue.summary, "task_description": a.task_description,
            "report_count": issue.report_count,
            "requires_evidence": bool(cat and cat.requires_evidence),
            "resolution_schema": (cat.resolution_schema if cat else None),
            "complaints": [views.staff_view(c) for c in views.linked_complaints(db, issue.id, limit=20, staff=True)],
            "updates": [{"id": u.id, "kind": u.kind, "body": u.body, "at": u.created_at} for u in updates]}


@router.post("/{task_id}/acknowledge")
def acknowledge(task_id: int, db: Session = Depends(get_db), staff: User = staff_only):
    a = assignment_service.acknowledge(db, assignment_service.get_task(db, task_id, staff), staff)
    db.commit()
    return _row(a)


@router.post("/{task_id}/start")
def start(task_id: int, background: BackgroundTasks, db: Session = Depends(get_db), staff: User = staff_only):
    a = assignment_service.start(db, assignment_service.get_task(db, task_id, staff), staff)
    commit_and_dispatch(db, background)
    return _row(a)


@router.post("/{task_id}/updates", status_code=201)
def add_update(task_id: int, payload: TaskUpdateIn, background: BackgroundTasks, db: Session = Depends(get_db),
               staff: User = staff_only):
    a = assignment_service.get_task(db, task_id, staff)
    u = assignment_service.add_update(db, a, staff, payload.kind, payload.body)
    commit_and_dispatch(db, background)
    return {"id": u.id, "kind": u.kind}


@router.post("/{task_id}/request-reassignment")
def request_reassignment(task_id: int, payload: ReassignRequestIn, background: BackgroundTasks,
                         db: Session = Depends(get_db), staff: User = staff_only):
    a = assignment_service.request_reassignment(db, assignment_service.get_task(db, task_id, staff), staff,
                                                payload.reason)
    commit_and_dispatch(db, background)
    return _row(a)


@router.post("/{task_id}/resolve", status_code=201)
def resolve(task_id: int, payload: ResolveIn, background: BackgroundTasks, db: Session = Depends(get_db),
            staff: User = staff_only):
    a = assignment_service.get_task(db, task_id, staff)
    fields = payload.model_dump(exclude={"completed_at"})
    report = resolution_service.submit(db, a, staff, fields, payload.completed_at)
    commit_and_dispatch(db, background)
    issue = db.query(Issue).filter(Issue.id == a.issue_id).first()
    return {"resolution_id": report.id, "report_status": report.status, "issue_status": issue.status}


@router.post("/{task_id}/attachments", status_code=201)
async def upload(task_id: int, file: UploadFile = File(...), kind: str = Form("evidence"),
                 db: Session = Depends(get_db), staff: User = staff_only):
    a = assignment_service.get_task(db, task_id, staff)
    att = await attachment_service.save_upload(db, file, owner_type="assignment", owner_id=a.id, kind=kind,
                                               user=staff, issue_id=a.issue_id)
    db.commit()
    return {"id": att.id, "mime": att.mime, "size_bytes": att.size_bytes}


@router.get("/{task_id}/suggested-resolution")
def suggested_resolution(task_id: int, db: Session = Depends(get_db), staff: User = staff_only):
    """Advisory only. Never blocks the workflow if the RAG index or LLM is unavailable."""
    a = assignment_service.get_task(db, task_id, staff)
    issue = db.query(Issue).filter(Issue.id == a.issue_id).first()
    text = f"{issue.title}. {issue.summary or ''}"
    db.rollback()  # release the connection before model inference and the optional Ollama call
    try:
        from app.ai.rag import generate_suggestion, retrieve_similar_resolutions

        similar = retrieve_similar_resolutions(text, 3)
        return {"suggestion": generate_suggestion(text, similar), "similar": similar}
    except Exception:  # noqa: BLE001
        return {"suggestion": None, "similar": []}
