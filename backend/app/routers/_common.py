from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import Scope
from app.models.issue import Issue
from app.services import notification_service


def get_issue_or_404(db: Session, scope: Scope, issue_id: int) -> Issue:
    """Cross-department access is a 404, never a 403, so existence is not revealed."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if issue is None or not scope.can_access(issue.department_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found")
    return issue


def commit_and_dispatch(db: Session, background: BackgroundTasks) -> None:
    """Commit the transaction, then process the outbox after the response is sent."""
    db.commit()
    background.add_task(notification_service.dispatch_pending)
