from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import Scope, get_scope, require_role
from app.models.issue import Issue
from app.models.user import User, UserRole
from app.core.roles import has_role
from app.core.timeutil import utcnow
from app.models.department_membership import DepartmentMembership
from app.models.work import ACTIVE_ASSIGNMENT_STATUSES, Assignment
from app.routers._common import commit_and_dispatch, get_issue_or_404
from app.schemas.v2 import AssignIn, AssignmentPatch
from app.services import assignment_service

router = APIRouter(tags=["assignments"])
MANAGERS = ("dept_admin", "super_admin")


def _out(a: Assignment) -> dict:
    return {"id": a.id, "issue_id": a.issue_id, "staff_id": a.staff_id, "is_lead": a.is_lead,
            "status": a.status, "due_at": a.due_at, "task_description": a.task_description,
            "reassign_requested": a.reassign_requested}


@router.post("/issues/{issue_id}/assignments", status_code=201)
def assign_issue(issue_id: int, payload: AssignIn, background: BackgroundTasks, db: Session = Depends(get_db),
                 scope: Scope = Depends(get_scope), actor: User = Depends(require_role(*MANAGERS))):
    issue = get_issue_or_404(db, scope, issue_id)
    result = assignment_service.assign(db, issue, actor, payload.staff_ids, task_description=payload.task_description,
                                       due_at=payload.due_at, lead_staff_id=payload.lead_staff_id)
    commit_and_dispatch(db, background)
    return [_out(a) for a in result]


@router.get("/issues/{issue_id}/assignments")
def list_assignments(issue_id: int, db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
                     _: User = Depends(require_role(*MANAGERS, "hod"))):
    issue = get_issue_or_404(db, scope, issue_id)
    return [_out(a) for a in db.query(Assignment).filter(Assignment.issue_id == issue.id).order_by(Assignment.id)]


@router.patch("/assignments/{assignment_id}")
def patch_assignment(assignment_id: int, payload: AssignmentPatch, background: BackgroundTasks,
                     db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
                     actor: User = Depends(require_role(*MANAGERS))):
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    issue = db.query(Issue).filter(Issue.id == a.issue_id).first() if a else None
    if a is None or issue is None or not scope.can_access(issue.department_id):
        raise HTTPException(404, "Assignment not found")
    result = assignment_service.reassign(db, a, actor, new_staff_id=payload.staff_id, due_at=payload.due_at)
    commit_and_dispatch(db, background)
    return _out(result)


@router.get("/department-staff")
def department_staff(department_id: int | None = Query(None, ge=1), db: Session = Depends(get_db),
                     scope: Scope = Depends(get_scope), _: User = Depends(require_role(*MANAGERS, "hod"))):
    """Active staff of the caller's department(s) with their current workload."""
    if department_id is not None and not scope.can_access(department_id):
        raise HTTPException(404, "Department not found")
    q = (db.query(User.id, User.name, DepartmentMembership.department_id,
                  func.count(Assignment.id).label("active_tasks"),
                  func.count(Assignment.id).filter(Assignment.due_at < utcnow()).label("overdue_tasks"))
         .select_from(User)
         .join(DepartmentMembership, DepartmentMembership.user_id == User.id)
         .outerjoin(Assignment, and_(Assignment.staff_id == User.id, Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES)))
         .filter(User.role == UserRole.staff, User.is_active.is_(True)))
    if department_id is not None:
        q = q.filter(DepartmentMembership.department_id == department_id)
    elif not scope.is_global:
        q = q.filter(DepartmentMembership.department_id.in_(scope.department_ids))
    rows = q.group_by(User.id, User.name, DepartmentMembership.department_id).order_by(User.name)
    return [dict(r._mapping) for r in rows]
