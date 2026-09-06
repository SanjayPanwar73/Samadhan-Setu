"""Qualitative retrieval evaluation for existing resolution histories."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.rag import retrieve_similar_resolutions
from app.core.database import SessionLocal
from app.models.complaint import Complaint
from app.models.resolution_history import ResolutionHistory


def run() -> None:
    db = SessionLocal()
    try:
        histories = db.query(ResolutionHistory).all()
        if not histories:
            print("No resolution history found. Run the backfill script first.")
            return
        scores = []
        for history in histories:
            complaint = db.query(Complaint).filter(Complaint.id == history.complaint_id).first()
            if not complaint:
                continue
            results = retrieve_similar_resolutions(f"{complaint.title}. {complaint.description}")
            top = next((item for item in results if item["complaint_id"] != complaint.id), None)
            if top:
                scores.append(top["similarity"])
                print(
                    f"Complaint #{complaint.id} -> #{top['complaint_id']} "
                    f"(similarity={top['similarity']:.4f})"
                )
        if scores:
            print(f"Average top-hit similarity: {sum(scores) / len(scores):.4f}")
        else:
            print("No related past cases were retrieved.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
