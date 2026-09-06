"""Create resolution history/index entries for resolved complaints.

Run from backend/: python -m scripts.backfill_resolution_index
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.rag import add_resolution_to_index, embed_resolution
from app.core.database import SessionLocal
from app.models.complaint import Complaint, ComplaintStatus
from app.models.resolution_history import ResolutionHistory


def run() -> None:
    db = SessionLocal()
    added = 0
    try:
        resolved = db.query(Complaint).filter(Complaint.status == ComplaintStatus.resolved).all()
        for complaint in resolved:
            history = db.query(ResolutionHistory).filter(
                ResolutionHistory.complaint_id == complaint.id
            ).first()
            if history:
                add_resolution_to_index(history.id, embed_resolution(history.resolution_text))
                added += 1
            else:
                resolution_text = (
                    f"Complaint resolved: {complaint.title}. "
                    "No resolution note was recorded for this historical case."
                )
                history = ResolutionHistory(
                    complaint_id=complaint.id,
                    resolution_text=resolution_text,
                    resolved_by=complaint.assigned_to or complaint.created_by,
                )
                db.add(history)
                db.commit()
                db.refresh(history)
                add_resolution_to_index(history.id, embed_resolution(resolution_text))
                added += 1
        print(f"Indexed {added} resolution histories.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
