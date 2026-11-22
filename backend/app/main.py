"""
FastAPI application — Label Tracker API.

Endpoints:
  POST /api/scan          Upload image → OCR → extracted fields (not yet saved)
  POST /api/labels        Save a confirmed/reviewed label record
  GET  /api/labels        List all label records (with expiry status)
  GET  /api/labels/{id}   Single label record
  PUT  /api/labels/{id}   Update / confirm a label (review flow)
  DELETE /api/labels/{id} Remove a record
  GET  /api/dashboard     Aggregate stats
  GET  /uploads/{path}    Serve uploaded images
"""
# macOS ARM64 + conda: auto-enable SKIP_EASYOCR to use Tesseract instead.
import os as _os
if _os.path.exists("/opt/homebrew/Caskroom/miniforge/base/bin/python3"):
    _os.environ.setdefault("SKIP_EASYOCR", "1")

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import (
    FastAPI, Depends, File, Form, HTTPException, UploadFile, status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import get_db, init_db, LabelRecord
from app.schemas import ConfirmPayload, DashboardStats, ExtractedLabel, LabelOut
from app.ocr_service import extract_text, save_upload
from app.date_extractor import extract_label_info
from app.llm_extractor import extract_with_llm, ollama_available
from app.expiry import expiry_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB = 10

app = FastAPI(
    title="Label Tracker API",
    description="Product Label Detection and Expiry Tracking System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    UPLOAD_DIR.mkdir(exist_ok=True)
    logger.info("Label Tracker API started.")


# ── Serve uploaded images ─────────────────────────────────────────────────────

@app.get("/uploads/{file_path:path}")
async def serve_upload(file_path: str):
    full = UPLOAD_DIR / file_path
    if not full.exists():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(str(full))


# ── POST /api/scan ────────────────────────────────────────────────────────────

@app.post("/api/scan", response_model=ExtractedLabel, status_code=201)
async def scan_label(file: UploadFile = File(...)):
    """
    Accept an image upload, run OCR, extract product fields, and return
    the extraction result WITHOUT saving to the database.
    The client must call POST /api/labels to persist after user review.
    """
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{file.content_type}'. Use JPEG or PNG.",
        )

    img_bytes = await file.read()
    if len(img_bytes) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {MAX_SIZE_MB} MB limit.",
        )

    # Save image with a UUID prefix so filenames never collide
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    rel_path = save_upload(img_bytes, unique_name, UPLOAD_DIR)

    # ── Step 1: OCR ───────────────────────────────────────────────────────────
    raw_text = extract_text(img_bytes)

    # ── Step 2: Regex extraction (fast baseline) ──────────────────────────────
    regex_info = extract_label_info(raw_text)

    # ── Step 3: LLM extraction (vision if available, text otherwise) ─────────
    llm_info = extract_with_llm(raw_text, img_bytes=img_bytes)

    # ── Step 4: Merge — LLM wins when it succeeded, regex fills gaps ─────────
    if llm_info.llm_used:
        product_name       = llm_info.product_name       or regex_info.product_name
        batch_number       = llm_info.batch_number       or regex_info.batch_number
        manufacturing_date = llm_info.manufacturing_date or regex_info.manufacturing_date
        expiry_date        = llm_info.expiry_date        or regex_info.expiry_date
        date_type          = llm_info.date_type          if llm_info.date_type != "expiry" else regex_info.date_type
        # Merge ambiguity notes from both
        all_notes = llm_info.ambiguity_notes + [
            n for n in regex_info.ambiguity_notes if n not in llm_info.ambiguity_notes
        ]
    else:
        product_name       = regex_info.product_name
        batch_number       = regex_info.batch_number
        manufacturing_date = regex_info.manufacturing_date
        expiry_date        = regex_info.expiry_date
        date_type          = regex_info.date_type
        all_notes          = regex_info.ambiguity_notes

    return ExtractedLabel(
        product_name=product_name,
        batch_number=batch_number,
        manufacturing_date=manufacturing_date,
        expiry_date=expiry_date,
        date_type=date_type,
        raw_text=raw_text,
        ambiguity_notes=all_notes,
        label_image=rel_path,
        llm_used=llm_info.llm_used,
        llm_reasoning=llm_info.reasoning or None,
    )


# ── POST /api/labels ──────────────────────────────────────────────────────────

@app.post("/api/labels", response_model=LabelOut, status_code=201)
def create_label(
    product_name:        Optional[str] = Form(None),
    batch_number:        Optional[str] = Form(None),
    manufacturing_date:  Optional[str] = Form(None),
    expiry_date:         Optional[str] = Form(None),
    date_type:           Optional[str] = Form("expiry"),
    label_image:         Optional[str] = Form(None),
    raw_text:            Optional[str] = Form(None),
    review_status:       str           = Form("needs_review"),
    ambiguity_notes:     Optional[str] = Form(None),  # JSON string
    llm_reasoning:       Optional[str] = Form(None),
    llm_used:            Optional[str] = Form("false"),
    db: Session = Depends(get_db),
):
    """Save a label record. review_status should be 'confirmed' when the user
    has verified all fields, or 'needs_review' if ambiguous dates remain."""
    record = LabelRecord(
        product_name=product_name,
        batch_number=batch_number,
        manufacturing_date=manufacturing_date,
        expiry_date=expiry_date,
        date_type=date_type or "expiry",
        label_image=label_image,
        raw_text=raw_text,
        review_status=review_status,
        ambiguity_notes=ambiguity_notes,
        llm_reasoning=llm_reasoning,
        llm_used=llm_used or "false",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_out(record)


# ── GET /api/labels ───────────────────────────────────────────────────────────

@app.get("/api/labels", response_model=list[LabelOut])
def list_labels(
    status_filter: Optional[str] = None,   # expired | expiring_soon | ok | needs_review | confirmed
    db: Session = Depends(get_db),
):
    query = db.query(LabelRecord).order_by(LabelRecord.created_at.desc())
    records = query.all()
    out = [_to_out(r) for r in records]
    if status_filter:
        if status_filter in ("needs_review", "confirmed"):
            out = [o for o in out if o.review_status == status_filter]
        else:
            out = [o for o in out if o.expiry_status == status_filter]
    return out


# ── GET /api/labels/{id} ──────────────────────────────────────────────────────

@app.get("/api/labels/{label_id}", response_model=LabelOut)
def get_label(label_id: int, db: Session = Depends(get_db)):
    record = db.query(LabelRecord).filter(LabelRecord.id == label_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Label not found.")
    return _to_out(record)


# ── PUT /api/labels/{id} ──────────────────────────────────────────────────────

@app.put("/api/labels/{label_id}", response_model=LabelOut)
def update_label(
    label_id: int,
    payload: ConfirmPayload,
    db: Session = Depends(get_db),
):
    """Used by the review/confirm UI to update and confirm a label."""
    record = db.query(LabelRecord).filter(LabelRecord.id == label_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Label not found.")

    if payload.product_name   is not None: record.product_name        = payload.product_name
    if payload.batch_number   is not None: record.batch_number        = payload.batch_number
    if payload.manufacturing_date is not None: record.manufacturing_date = payload.manufacturing_date
    if payload.expiry_date    is not None: record.expiry_date         = payload.expiry_date
    if payload.date_type      is not None: record.date_type           = payload.date_type
    record.review_status = payload.review_status

    db.commit()
    db.refresh(record)
    return _to_out(record)


# ── DELETE /api/labels/{id} ───────────────────────────────────────────────────

@app.delete("/api/labels/{label_id}", status_code=204)
def delete_label(label_id: int, db: Session = Depends(get_db)):
    record = db.query(LabelRecord).filter(LabelRecord.id == label_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Label not found.")
    db.delete(record)
    db.commit()


# ── GET /api/dashboard ────────────────────────────────────────────────────────

@app.get("/api/dashboard", response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db)):
    records = db.query(LabelRecord).all()
    confirmed    = sum(1 for r in records if r.review_status == "confirmed")
    needs_review = sum(1 for r in records if r.review_status == "needs_review")
    statuses     = [expiry_status(r.expiry_date) for r in records]
    return DashboardStats(
        total=len(records),
        confirmed=confirmed,
        needs_review=needs_review,
        expired=statuses.count("expired"),
        expiring_soon=statuses.count("expiring_soon"),
        ok=statuses.count("ok"),
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_out(record: LabelRecord) -> LabelOut:
    return LabelOut(
        id=record.id,
        product_name=record.product_name,
        batch_number=record.batch_number,
        manufacturing_date=record.manufacturing_date,
        expiry_date=record.expiry_date,
        date_type=record.date_type,
        label_image=record.label_image,
        raw_text=record.raw_text,
        review_status=record.review_status,
        ambiguity_notes=record.ambiguity_notes,
        llm_reasoning=record.llm_reasoning,
        llm_used=record.llm_used,
        created_at=record.created_at,
        expiry_status=expiry_status(record.expiry_date),
    )
