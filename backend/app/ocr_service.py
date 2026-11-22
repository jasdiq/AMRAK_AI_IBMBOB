from __future__ import annotations

"""
OCR service — three-tier engine with graceful fallback.

Priority order:
  1. EasyOCR  (deep-learning, no external binary needed)
  2. Tesseract via pytesseract  (requires `tesseract` binary on PATH
     or at TESSERACT_CMD env / common brew path)

Install:
  pip install easyocr            ← best quality
  brew install tesseract         ← enables pytesseract fallback
"""
# macOS arm64 + conda: suppress OpenMP duplicate-library segfault
import os as _os
_os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageFilter, ImageOps

# ── Optional cv2 ─────────────────────────────────────────────────────────────
try:
    import cv2 as _cv2
    _CV2_OK = True
except Exception:
    _cv2 = None          # type: ignore
    _CV2_OK = False

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Engine 1 — EasyOCR
# Set SKIP_EASYOCR=1 in env to disable (useful on conda/macOS ARM64 where
# PyTorch's OpenMP can segfault against conda's libomp).
# ─────────────────────────────────────────────────────────────────────────────
_easyocr_reader = None
_easyocr_tried  = False
_SKIP_EASYOCR   = os.environ.get("SKIP_EASYOCR", "").strip() in ("1", "true", "yes")


def _easyocr_read(img_array: np.ndarray) -> Optional[str]:
    global _easyocr_reader, _easyocr_tried
    if _SKIP_EASYOCR:
        return None
    if _easyocr_tried and _easyocr_reader is None:
        return None
    if not _easyocr_tried:
        _easyocr_tried = True
        try:
            import easyocr
            _easyocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            logger.info("EasyOCR reader initialised.")
        except Exception as exc:
            logger.warning("EasyOCR unavailable: %s", exc)
            _easyocr_reader = None
            return None
    try:
        results = _easyocr_reader.readtext(img_array, detail=0, paragraph=True)  # type: ignore
        return "\n".join(results)
    except Exception as exc:
        logger.warning("EasyOCR inference error: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Engine 2 — Tesseract / pytesseract
# ─────────────────────────────────────────────────────────────────────────────

# Common install paths — tried in order (includes conda-forge path)
_TESS_CANDIDATES = [
    os.environ.get("TESSERACT_CMD", ""),
    "/opt/homebrew/Caskroom/miniforge/base/bin/tesseract",   # conda-forge / miniforge
    "/opt/homebrew/Caskroom/miniforge/base/envs/base/bin/tesseract",
    os.path.expanduser("~/miniforge3/bin/tesseract"),
    os.path.expanduser("~/miniconda3/bin/tesseract"),
    os.path.expanduser("~/anaconda3/bin/tesseract"),
    "/opt/homebrew/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/usr/bin/tesseract",
]


def _configure_tesseract() -> bool:
    """Point pytesseract at the tesseract binary; return True if found."""
    try:
        import pytesseract
    except ImportError:
        return False

    # Already working?
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        pass

    for path in _TESS_CANDIDATES:
        if path and Path(path).is_file():
            pytesseract.pytesseract.tesseract_cmd = path
            try:
                pytesseract.get_tesseract_version()
                logger.info("Tesseract found at %s", path)
                return True
            except Exception:
                continue

    logger.warning("Tesseract binary not found on this machine.")
    return False


_tess_ok: Optional[bool] = None   # None = not yet checked


def _tesseract_read(pil_img: Image.Image) -> Optional[str]:
    global _tess_ok
    if _tess_ok is False:
        return None
    if _tess_ok is None:
        _tess_ok = _configure_tesseract()
        if not _tess_ok:
            return None
    try:
        import pytesseract
        # psm 6 = assume a single uniform block of text
        t6 = pytesseract.image_to_string(pil_img, config="--oem 3 --psm 6").strip()
        # psm 11 = sparse text — better for mixed-layout packaging labels
        t11 = pytesseract.image_to_string(pil_img, config="--oem 3 --psm 11").strip()
        # Return whichever result has more non-whitespace characters
        return t6 if len(t6.replace(" ", "")) >= len(t11.replace(" ", "")) else t11
    except Exception as exc:
        logger.warning("Tesseract read error: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Image pre-processing
# ─────────────────────────────────────────────────────────────────────────────

def _white_regions(img_bgr: "np.ndarray") -> "np.ndarray":
    """
    Detect large white/light regions (stickers, labels) and return a mask.
    White stickers on coloured packaging contain the most reliable text.
    """
    hsv = _cv2.cvtColor(img_bgr, _cv2.COLOR_BGR2HSV)
    # High value, low saturation = white/near-white
    mask = _cv2.inRange(hsv, (0, 0, 180), (180, 60, 255))
    # Keep only large connected regions (sticker, not noise)
    kernel = _cv2.getStructuringElement(_cv2.MORPH_RECT, (20, 20))
    mask = _cv2.morphologyEx(mask, _cv2.MORPH_CLOSE, kernel)
    return mask


def _preprocess_to_array(img_bytes: bytes) -> np.ndarray:
    """
    Return a greyscale numpy array optimised for OCR on product packaging.

    Two-pass strategy:
    Pass A — white sticker crop: detect and isolate any white label/sticker
             region, then apply adaptive threshold.  This gives clean text
             from inkjet/dot-matrix printed date stamps.
    Pass B — full image CLAHE + adaptive threshold (fallback).

    Both passes are returned stacked vertically so Tesseract sees all text.
    """
    if _CV2_OK:
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = _cv2.imdecode(arr, _cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("cv2 could not decode image.")

        # Upscale
        h, w = img.shape[:2]
        if max(h, w) < 1500:
            scale = 1500 / max(h, w)
            img = _cv2.resize(img, (int(w * scale), int(h * scale)),
                              interpolation=_cv2.INTER_CUBIC)

        gray = _cv2.cvtColor(img, _cv2.COLOR_BGR2GRAY)

        # ── Pass A: white sticker isolation ──────────────────────────────────
        sticker_mask = _white_regions(img)
        contours, _ = _cv2.findContours(sticker_mask, _cv2.RETR_EXTERNAL,
                                         _cv2.CHAIN_APPROX_SIMPLE)
        passes = []

        if contours:
            # Sort by area, take the largest white region
            largest = max(contours, key=_cv2.contourArea)
            x, y, bw, bh = _cv2.boundingRect(largest)
            # Add 5% padding
            pad = int(max(bw, bh) * 0.05)
            x1 = max(0, x - pad); y1 = max(0, y - pad)
            x2 = min(img.shape[1], x + bw + pad)
            y2 = min(img.shape[0], y + bh + pad)
            crop_gray = gray[y1:y2, x1:x2]
            # Scale sticker up to at least 800px wide for legibility
            cw = crop_gray.shape[1]
            if cw < 800:
                crop_gray = _cv2.resize(crop_gray, (800, int(800 * crop_gray.shape[0] / cw)),
                                         interpolation=_cv2.INTER_CUBIC)
            # Otsu threshold on the clean white background
            _, sticker_bin = _cv2.threshold(crop_gray, 0, 255,
                                             _cv2.THRESH_BINARY + _cv2.THRESH_OTSU)
            passes.append(sticker_bin)

        # ── Pass B: full image CLAHE + adaptive threshold ─────────────────────
        clahe = _cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        full_bin = _cv2.adaptiveThreshold(
            enhanced, 255,
            _cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            _cv2.THRESH_BINARY,
            blockSize=25, C=12,
        )
        passes.append(full_bin)

        # Stack passes vertically (Tesseract reads top-to-bottom)
        # Normalise widths first
        target_w = max(p.shape[1] for p in passes)
        resized = []
        for p in passes:
            if p.shape[1] != target_w:
                p = _cv2.resize(p, (target_w, int(target_w * p.shape[0] / p.shape[1])),
                                interpolation=_cv2.INTER_LINEAR)
            resized.append(p)

        # Add white separator between passes
        sep = np.full((30, target_w), 255, dtype=np.uint8)
        combined = np.vstack([resized[0], sep] + ([resized[1], sep] if len(resized) > 1 else []))
        return combined

    # PIL path
    pil = Image.open(BytesIO(img_bytes)).convert("L")
    w, h = pil.size
    if max(w, h) < 1000:
        scale = 1000 / max(w, h)
        pil = pil.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    pil = ImageOps.autocontrast(pil, cutoff=2)
    pil = pil.filter(ImageFilter.SHARPEN)
    return np.array(pil)


def _array_to_pil(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(arr)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def extract_text(img_bytes: bytes) -> str:
    """
    Run OCR on image bytes and return extracted text.
    Tries EasyOCR → Tesseract → returns empty string with a log warning.
    Never raises — an empty string means 'no text extracted'.
    """
    try:
        processed = _preprocess_to_array(img_bytes)
    except Exception as exc:
        logger.error("Image pre-processing failed: %s", exc)
        return ""

    pil_img = _array_to_pil(processed)

    # ── Engine 1: EasyOCR ────────────────────────────────────────────────────
    text = _easyocr_read(processed)
    if text and text.strip():
        logger.debug("EasyOCR: %d chars", len(text))
        return text.strip()

    # ── Engine 2: Tesseract ──────────────────────────────────────────────────
    text = _tesseract_read(pil_img)
    if text and text.strip():
        logger.debug("Tesseract: %d chars", len(text))
        return text.strip()

    # ── No engine succeeded ───────────────────────────────────────────────────
    logger.warning(
        "No OCR engine produced output. "
        "Install EasyOCR (pip install easyocr) or "
        "Tesseract (brew install tesseract) for text extraction."
    )
    return ""


def save_upload(img_bytes: bytes, filename: str, upload_dir: Path) -> str:
    """Save uploaded image; return path relative to upload_dir's parent."""
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    dest = upload_dir / safe_name
    stem, suffix = dest.stem, dest.suffix
    counter = 1
    while dest.exists():
        dest = upload_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    dest.write_bytes(img_bytes)
    return str(dest.relative_to(upload_dir.parent))
