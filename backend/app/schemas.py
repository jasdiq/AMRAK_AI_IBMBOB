"""
Pydantic schemas for request/response bodies.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ExtractedLabel(BaseModel):
    """Returned immediately after OCR — may contain ambiguous dates."""
    product_name: Optional[str] = None
    batch_number: Optional[str] = None
    manufacturing_date: Optional[str] = None   # ISO or raw string
    expiry_date: Optional[str] = None          # ISO or raw string
    date_type: Optional[str] = None
    raw_text: str
    ambiguity_notes: list[str] = []
    label_image: Optional[str] = None
    # LLM fields
    llm_used: bool = False
    llm_reasoning: Optional[str] = None


class ConfirmPayload(BaseModel):
    """Frontend sends this after the user reviews and confirms the details."""
    product_name: Optional[str] = None
    batch_number: Optional[str] = None
    manufacturing_date: Optional[str] = None   # YYYY-MM-DD
    expiry_date: Optional[str] = None          # YYYY-MM-DD
    date_type: Optional[str] = "expiry"
    review_status: str = "confirmed"


class LabelOut(BaseModel):
    id: int
    product_name: Optional[str]
    batch_number: Optional[str]
    manufacturing_date: Optional[str]
    expiry_date: Optional[str]
    date_type: Optional[str]
    label_image: Optional[str]
    raw_text: Optional[str]
    review_status: str
    ambiguity_notes: Optional[str]
    llm_reasoning: Optional[str] = None
    llm_used: Optional[str] = None
    created_at: datetime
    expiry_status: Optional[str] = None   # expired | expiring_soon | ok | unknown

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total: int
    confirmed: int
    needs_review: int
    expired: int
    expiring_soon: int
    ok: int
