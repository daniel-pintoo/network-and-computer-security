"""
Database configuration and session management.
"""
import os

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Public repo-safe default. For the original multi-VM setup, define DATABASE_URL in
# the environment before starting the API. api/.env.example documents the expected value.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://appuser:change-me@localhost:5432/appdb",
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def fix_sequence():
    """
    Fix the PostgreSQL sequence for protected_documents.id after deletions.
    Resets the sequence to max(id) + 1 to prevent ID conflicts.
    """
    if "postgresql" not in DATABASE_URL:
        return  # Only needed for PostgreSQL
    
    with engine.connect() as conn:
        # Get the current max ID
        result = conn.execute(text("SELECT COALESCE(MAX(id), 0) FROM protected_documents"))
        max_id = result.scalar()
        
        # If table is empty, set sequence to 1 (not 0, as sequences have min value of 1)
        # If table has data, set sequence to max_id with is_called=true so next is max_id+1
        if max_id == 0:
            # Empty table: set sequence to 1, not called yet, so next value will be 1
            conn.execute(text("SELECT setval('protected_documents_id_seq', 1, false)"))
            next_id = 1
        else:
            # Table has data: set sequence to max_id, marked as called, so next is max_id+1
            conn.execute(text(f"SELECT setval('protected_documents_id_seq', {max_id}, true)"))
            next_id = max_id + 1
        
        conn.commit()
        
    print(f"Sequence reset: next ID will be {next_id}")

