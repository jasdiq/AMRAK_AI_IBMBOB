"""
LLM extraction service.

Two modes:
  1. Vision mode  — image bytes sent directly to a multimodal model (llava).
                    Best accuracy; model reads label directly.
  2. Text mode    — OCR text sent to a text-only model (llama3.2).
                    Fallback when no vision model is available.

The LLM returns JSON:
  {
    "product_name":       string | null,
    "batch_number":       string | null,
    "manufacturing_date": "YYYY-MM-DD" | null,
    "expiry_date":        "YYYY-MM-DD" | null,
    "date_type":          "expiry" | "use-by" | "best-before" | "unknown",
    "reasoning":          string,
    "ambiguity_notes":    string[]
  }
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE    = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL   = os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_VISION  = os.environ.get("OLLAMA_VISION_MODEL", "llava:7b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "60"))

# Cache: whether vision model is available (checked once)
_vision_available: Optional[bool] = None

# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a product label data extractor. You receive raw OCR text from a product packaging label and must extract key fields as JSON.

Rules:
- Extract: product_name, batch_number, manufacturing_date, expiry_date, date_type, reasoning, ambiguity_notes
- Dates MUST be in ISO format YYYY-MM-DD. If only month/year known, use YYYY-MM-01.
- For ambiguous dates like 13/09/23 (could be DD/MM/YY or MM/DD/YY): use context clues.
  Indian/UK products use DD/MM/YY. If unsure, pick the most likely and note the ambiguity.
- "PKD" or "PKGD" means Packed Date = manufacturing date.
- "USE BY", "USE BEFORE", "BB", "BEST BEFORE", "EXP", "EXPIRY" = expiry date.
- Batch number: alphanumeric code near "BATCH", "BATCH NO", "LOT". Exclude timestamps (HH:MM).
- If a line has both a code and a time (e.g. "A02M3 14:55"), the code part is the batch number.
- product_name: the main product name. If not visible, return null.
- reasoning: 1-2 sentences explaining how you interpreted the dates.
- ambiguity_notes: list any date ambiguity issues.
- Return ONLY valid JSON. No markdown, no explanation outside the JSON."""

_USER_TEMPLATE = """Extract product label fields from this OCR text:

---
{ocr_text}
---

Return JSON with keys: product_name, batch_number, manufacturing_date, expiry_date, date_type, reasoning, ambiguity_notes"""


# ── LLM call ─────────────────────────────────────────────────────────────────

@dataclass
class LLMResult:
    product_name:        Optional[str]  = None
    batch_number:        Optional[str]  = None
    manufacturing_date:  Optional[str]  = None
    expiry_date:         Optional[str]  = None
    date_type:           str            = "expiry"
    reasoning:           str            = ""
    ambiguity_notes:     list[str]      = field(default_factory=list)
    llm_used:            bool           = False
    raw_llm_response:    str            = ""


_VISION_PROMPT = """Look at this product packaging label image. Extract the following fields and return ONLY valid JSON (no markdown):

{
  "product_name": "name of the product or null",
  "batch_number": "batch/lot number (alphanumeric, exclude HH:MM timestamps) or null",
  "manufacturing_date": "YYYY-MM-DD or null (PKD/MFG/Manufactured date)",
  "expiry_date": "YYYY-MM-DD or null (USE BY/EXP/BEST BEFORE date)",
  "date_type": "use-by or best-before or expiry or unknown",
  "reasoning": "brief explanation of how you read the dates",
  "ambiguity_notes": ["list any ambiguous dates"]
}

Rules:
- Dates must be YYYY-MM-DD. For DD/MM/YY on Indian products, treat as DD/MM/YY.
- PKD = Packed Date = manufacturing date.
- Batch number is near BATCH NO — do NOT include the time stamp (14:55 etc).
- Return ONLY the JSON object."""


def _check_vision_available() -> bool:
    """Return True if the llava vision model is pulled and available."""
    global _vision_available
    if _vision_available is not None:
        return _vision_available
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        _vision_available = any(OLLAMA_VISION.split(":")[0] in m for m in models)
        if _vision_available:
            logger.info("Vision model %s available.", OLLAMA_VISION)
        else:
            logger.info("Vision model %s not available. Using text-only LLM.", OLLAMA_VISION)
    except Exception:
        _vision_available = False
    return _vision_available


def _call_ollama_vision(img_bytes: bytes) -> Optional[str]:
    """Send image directly to llava for extraction. Returns raw response."""
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    payload = {
        "model": OLLAMA_VISION,
        "prompt": _VISION_PROMPT,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 512},
    }
    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        logger.warning("Ollama vision call failed (connection).")
        return None
    except Exception as exc:
        logger.warning("Ollama vision call failed: %s", exc)
        return None


def _call_ollama(ocr_text: str) -> Optional[str]:
    """POST to Ollama generate endpoint with OCR text; return raw response."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": _USER_TEMPLATE.format(ocr_text=ocr_text),
        "system": _SYSTEM_PROMPT,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 512},
    }
    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        logger.warning("Ollama not reachable at %s. Using regex fallback.", OLLAMA_BASE)
        return None
    except Exception as exc:
        logger.warning("Ollama call failed: %s", exc)
        return None


def _parse_llm_json(raw: str) -> Optional[dict]:
    """Extract the first JSON object from an LLM response string."""
    # Strip markdown code fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    # Find the first {...} block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        logger.warning("Could not parse LLM JSON: %s", raw[:200])
        return None


def _normalise_date(val: Optional[str]) -> Optional[str]:
    """Accept YYYY-MM-DD or YYYY-MM and return as-is; reject garbage."""
    if not val:
        return None
    val = str(val).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", val):
        return val
    if re.fullmatch(r"\d{4}-\d{2}", val):
        return val + "-01"
    return None


def extract_with_llm(ocr_text: str, img_bytes: Optional[bytes] = None) -> LLMResult:
    """
    Extract label fields using LLM.

    If img_bytes is provided and a vision model (llava) is available,
    the image is sent directly — bypassing OCR quality issues entirely.
    Otherwise falls back to sending the OCR text to llama3.2.
    """
    result = LLMResult()

    raw: Optional[str] = None

    # ── Vision path (best quality) ────────────────────────────────────────────
    if img_bytes and _check_vision_available():
        logger.info("Using vision model %s for extraction.", OLLAMA_VISION)
        raw = _call_ollama_vision(img_bytes)
        if raw:
            logger.info("Vision model returned %d chars.", len(raw))

    # ── Text path (OCR → LLM) ─────────────────────────────────────────────────
    if not raw:
        if not ocr_text.strip():
            return result
        raw = _call_ollama(ocr_text)
        if raw is None:
            return result

    result.raw_llm_response = raw
    parsed = _parse_llm_json(raw)
    if parsed is None:
        logger.warning("LLM returned unparseable response: %s", raw[:300])
        return result

    result.llm_used           = True
    result.product_name       = parsed.get("product_name") or None
    result.batch_number       = parsed.get("batch_number") or None
    result.manufacturing_date = _normalise_date(parsed.get("manufacturing_date"))
    result.expiry_date        = _normalise_date(parsed.get("expiry_date"))
    result.date_type          = parsed.get("date_type") or "expiry"
    result.reasoning          = parsed.get("reasoning") or ""

    notes = parsed.get("ambiguity_notes", [])
    if isinstance(notes, list):
        result.ambiguity_notes = [str(n) for n in notes]
    elif isinstance(notes, str) and notes:
        result.ambiguity_notes = [notes]

    return result


def ollama_available() -> bool:
    """Quick check whether Ollama is reachable."""
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False
