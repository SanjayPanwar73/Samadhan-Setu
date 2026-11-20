from sqlalchemy import Column, ForeignKey, Integer, LargeBinary, String

from app.core.database import Base


class ComplaintEmbedding(Base):
    __tablename__ = "complaint_embeddings"

    complaint_id = Column(Integer, ForeignKey("complaints.id"), primary_key=True)
    model = Column(String, nullable=False)
    dim = Column(Integer, nullable=False)
    vector = Column(LargeBinary, nullable=False)  # float32 bytes
