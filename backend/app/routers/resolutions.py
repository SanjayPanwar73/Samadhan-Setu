from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import Scope, get_scope, require_role
from app.models.issue import Issue
from app.models.user import User
from app.models.work import ResolutionReport
from app.routers._common import commit_and_dispatch
from app.schemas.v2 import ApproveIn, RejectResolutionIn
from app.services import resolution_service

router = APIRouter(tags=["resolutions"])
MANAGERS = ("dept_admin", "super_admin")


def _check(db: Session, scope: Scope, resolution_id: int) -> ResolutionReport:
    r = db.query(ResolutionReport).filter(ResolutionReport.id == resolution_id).first()
    issue = db.query(Issue).filter(Issue.id == r.issue_id).first() if r else None
    if r is None or issue is None or not scope.can_access(issue.department_id):
        raise HTTPException(404, "Resolution not found")
    return r


@router.post("/resolutions/{resolution_id}/approve")
def approve(resolution_id: int, payload: ApproveIn, background: BackgroundTasks, db: Session = Depends(get_db),
            scope: Scope = Depends(get_scope), actor: User = Depends(require_role(*MANAGERS))):
    _check(db, scope, resolution_id)
    report = resolution_service.approve(db, resolution_id, actor, payload.comment)
    commit_and_dispatch(db, background)
    return {"resolution_id": report.id, "status": report.status}


@router.post("/resolutions/{resolution_id}/reject")
def reject(resolution_id: int, payload: RejectResolutionIn, background: BackgroundTasks,
           db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
           actor: User = Depends(require_role(*MANAGERS))):
    _check(db, scope, resolution_id)
    report = resolution_service.reject(db, resolution_id, actor, payload.comment)
    commit_and_dispatch(db, background)
    return {"resolution_id": report.id, "status": report.status}


@router.get("/issues/{issue_id}/resolutions")
def list_resolutions(issue_id: int, db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
                     _: User = Depends(require_role(*MANAGERS, "hod"))):
    from app.routers._common import get_issue_or_404

    issue = get_issue_or_404(db, scope, issue_id)
    rows = db.query(ResolutionReport).filter(ResolutionReport.issue_id == issue.id).order_by(ResolutionReport.id)
    return [{"id": r.id, "cycle": r.cycle, "status": r.status, "what_was_wrong": r.what_was_wrong,
             "root_cause": r.root_cause, "action_taken": r.action_taken, "parts_replaced": r.parts_replaced,
             "public_summary": r.public_summary, "followup_needed": r.followup_needed,
             "completed_at": r.completed_at, "verifier_comment": r.verifier_comment} for r in rows]
