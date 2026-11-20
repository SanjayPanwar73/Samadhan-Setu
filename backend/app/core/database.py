from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    # A generous busy timeout lets concurrent writers queue behind the grouping lock.
    connect_args=(
        {"check_same_thread": False, "timeout": 30}
        if settings.DATABASE_URL.startswith("sqlite")
        else {}
    ),
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def acquire_grouping_lock(db, department_id: int, location_parent_id: int | None) -> None:
    """Serialise the duplicate-grouping critical section.

    PostgreSQL: transaction-scoped advisory lock keyed by (department, location parent).
    SQLite: a no-op UPDATE on the department's ticket counter takes the single
    database write lock, so grouping transactions run one at a time.
    The lock is released automatically on commit or rollback.
    """
    from sqlalchemy import text

    if db.get_bind().dialect.name == "postgresql":
        key = (int(department_id) << 32) ^ int(location_parent_id or 0)
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})
        return
    db.execute(
        text("UPDATE ticket_counters SET next_value = next_value WHERE department_id = :d"),
        {"d": department_id},
    )
