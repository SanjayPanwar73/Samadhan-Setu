"""Compute (or recompute) complaint embeddings used for duplicate grouping.

    python -m scripts.reembed           # only complaints without an embedding (after the backfill)
    python -m scripts.reembed --all     # everything (after changing EMBEDDING_MODEL)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.models  # noqa: F401
from app.ai.providers import get_providers, safe_embed
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.complaint import Complaint
from app.models.complaint_embedding import ComplaintEmbedding


def reembed(db, everything: bool = False, batch: int = 200) -> int:
    q = db.query(Complaint)
    if not everything:
        q = q.outerjoin(ComplaintEmbedding, ComplaintEmbedding.complaint_id == Complaint.id).filter(
            ComplaintEmbedding.complaint_id.is_(None))
    model = get_providers().embedding_model_name or settings.EMBEDDING_MODEL
    done = 0
    for complaint in q.order_by(Complaint.id).all():
        vec = safe_embed(f"{complaint.title}. {complaint.description}")
        if vec is None:
            continue
        row = db.get(ComplaintEmbedding, complaint.id)
        if row is None:
            db.add(ComplaintEmbedding(complaint_id=complaint.id, model=model, dim=int(vec.shape[0]),
                                      vector=vec.astype("float32").tobytes()))
        else:
            row.model, row.dim, row.vector = model, int(vec.shape[0]), vec.astype("float32").tobytes()
        done += 1
        if done % batch == 0:
            db.commit()
    db.commit()
    return done


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    session = SessionLocal()
    try:
        print(f"Embedded {reembed(session, args.all)} complaint(s).")
    finally:
        session.close()
