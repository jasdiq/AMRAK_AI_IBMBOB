"""
Database models and setup for Label Tracker.
"""
import os
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, create_engine
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

DB_PATH = os.environ.get("LABEL_TRACKER_DB", "label_tracker.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class LabelRecord(Base):
    __tablename__ = "labels"

    id              = Column(Integer, primary_key=True, index=True)
    product_name    = Column(String(255))
    batch_number    = Column(String(100))
    manufacturing_date = Column(String(20))   # ISO YYYY-MM-DD or empty
    expiry_date     = Column(String(20))       # ISO YYYY-MM-DD or empty
    date_type       = Column(String(30))       # expiry | use-by | best-before | unknown
    label_image     = Column(String(512))      # relative path under uploads/
    raw_text        = Column(Text)
    review_status   = Column(String(20), default="needs_review")
    # 'confirmed' | 'needs_review'
    ambiguity_notes = Column(Text)   # JSON array string
    llm_reasoning   = Column(Text)   # LLM explanation of date decisions
    llm_used        = Column(String(5), default="false")
    created_at      = Column(DateTime, default=datetime.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
