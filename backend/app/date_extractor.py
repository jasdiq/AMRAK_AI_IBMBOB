"""
Date extraction and ambiguity detection.

Handles common label date formats:
  - DD/MM/YY, DD/MM/YYYY
  - MM/YY, MM/YYYY
  - DD-Mon-YY, DD-Mon-YYYY
  - YYYY-MM-DD (ISO)
  - MonYY, Mon YYYY
  - Various "MFG:", "EXP:", "BB:", "USE BY:" prefixed forms

Ambiguity rule:
  When a date is numeric-only with two leading components that could be
  either DD/MM or MM/DD (e.g. 03/04/26), the date is flagged as ambiguous
  and the review_status is set to 'needs_review'.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Month name maps ───────────────────────────────────────────────────────────
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

# ── Keyword → date_type maps ──────────────────────────────────────────────────
_EXP_KEYWORDS   = re.compile(
    r"\b(exp(?:iry)?|expir(?:es?|ation)|best\s*before|bb|use[-\s]by)\b",
    re.IGNORECASE,
)
_MFG_KEYWORDS   = re.compile(
    r"\b(mfg|mfg\.?|manufactured|manufacture\s+date|dom|date\s+of\s+mfg)\b",
    re.IGNORECASE,
)
_USEBY_KEYWORDS = re.compile(r"\buse[-\s]by\b", re.IGNORECASE)
_BB_KEYWORDS    = re.compile(r"\bbest[-\s]before\b", re.IGNORECASE)

# ── Date patterns ─────────────────────────────────────────────────────────────
# Each pattern yields groups that _parse_match() can interpret.

# DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
_P_DMY_FULL = re.compile(
    r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b"
)
# DD/MM/YY or DD-MM-YY
_P_DMY_SHORT = re.compile(
    r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2})\b"
)
# YYYY-MM-DD (ISO)
_P_ISO = re.compile(
    r"\b(20\d{2})[-/\.](\d{2})[-/\.](\d{2})\b"
)
# MM/YYYY or MM-YYYY
_P_MY_FULL = re.compile(
    r"\b(\d{1,2})[/\-](20\d{2})\b"
)
# MM/YY
_P_MY_SHORT = re.compile(
    r"\b(\d{1,2})[/\-](\d{2})\b"
)
# DD Mon YYYY  (e.g. 15 Mar 2025)
_P_DMon_FULL = re.compile(
    r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(20\d{2})\b"
)
# Mon YYYY  (e.g. Mar 2025)
_P_Mon_FULL = re.compile(
    r"\b([A-Za-z]{3,9})\s+(20\d{2})\b"
)
# MonYY  (e.g. Mar25)
_P_Mon_SHORT = re.compile(
    r"\b([A-Za-z]{3,9})(\d{2})\b"
)


@dataclass
class ParsedDate:
    iso: str            # YYYY-MM-DD or YYYY-MM
    ambiguous: bool = False
    note: str = ""


def _expand_year(yy: int) -> int:
    """Convert 2-digit year to 4-digit. 00-50 → 2000-2050, 51-99 → 1951-1999."""
    return 2000 + yy if yy <= 50 else 1900 + yy


def _iso(year: int, month: int, day: int | None = None) -> str:
    if day:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return f"{year:04d}-{month:02d}"


def _try_dmy_full(m: re.Match) -> ParsedDate | None:
    a, b, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    ambiguous = (1 <= a <= 12 and 1 <= b <= 12 and a != b)
    if 1 <= b <= 12 and 1 <= a <= 31:
        return ParsedDate(
            iso=_iso(year, b, a),
            ambiguous=ambiguous,
            note=f"DD/MM/YYYY ambiguous: day={a} month={b} possible, or month={a} day={b}" if ambiguous else "",
        )
    return None


def _try_dmy_short(m: re.Match) -> ParsedDate | None:
    a, b, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year = _expand_year(yy)
    ambiguous = (1 <= a <= 12 and 1 <= b <= 12 and a != b)
    if 1 <= b <= 12 and 1 <= a <= 31:
        return ParsedDate(
            iso=_iso(year, b, a),
            ambiguous=ambiguous,
            note=f"Short date {a}/{b}/{yy:02d} is ambiguous (DD/MM or MM/DD?)" if ambiguous else "",
        )
    return None


def _try_iso(m: re.Match) -> ParsedDate | None:
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if 1 <= month <= 12 and 1 <= day <= 31:
        return ParsedDate(iso=_iso(year, month, day))
    return None


def _try_my_full(m: re.Match) -> ParsedDate | None:
    month, year = int(m.group(1)), int(m.group(2))
    if 1 <= month <= 12:
        return ParsedDate(iso=_iso(year, month))
    return None


def _try_my_short(m: re.Match) -> ParsedDate | None:
    month, yy = int(m.group(1)), int(m.group(2))
    year = _expand_year(yy)
    # Reject cases where the "month" looks more like a day (> 12)
    if 1 <= month <= 12:
        return ParsedDate(iso=_iso(year, month))
    return None


def _try_dmon_full(m: re.Match) -> ParsedDate | None:
    day  = int(m.group(1))
    mon  = m.group(2).lower()
    year = int(m.group(3))
    if mon in _MONTHS and 1 <= day <= 31:
        return ParsedDate(iso=_iso(year, _MONTHS[mon], day))
    return None


def _try_mon_full(m: re.Match) -> ParsedDate | None:
    mon  = m.group(1).lower()
    year = int(m.group(2))
    if mon in _MONTHS:
        return ParsedDate(iso=_iso(year, _MONTHS[mon]))
    return None


def _try_mon_short(m: re.Match) -> ParsedDate | None:
    mon = m.group(1).lower()
    yy  = int(m.group(2))
    year = _expand_year(yy)
    if mon in _MONTHS:
        return ParsedDate(iso=_iso(year, _MONTHS[mon]))
    return None


# Ordered list: more-specific patterns first
_PATTERNS = [
    (_P_ISO,        _try_iso),
    (_P_DMY_FULL,   _try_dmy_full),
    (_P_DMon_FULL,  _try_dmon_full),
    (_P_Mon_FULL,   _try_mon_full),
    (_P_MY_FULL,    _try_my_full),
    (_P_DMY_SHORT,  _try_dmy_short),
    (_P_Mon_SHORT,  _try_mon_short),
    (_P_MY_SHORT,   _try_my_short),
]


def _extract_all_dates(text: str) -> list[tuple[int, ParsedDate]]:
    """Return list of (start_pos, ParsedDate) for all dates found in text."""
    found: list[tuple[int, ParsedDate]] = []
    seen_spans: set[tuple[int, int]] = set()

    for pattern, parser in _PATTERNS:
        for m in pattern.finditer(text):
            span = (m.start(), m.end())
            if any(s <= span[0] < e or s < span[1] <= e for s, e in seen_spans):
                continue   # already captured by a wider match
            result = parser(m)
            if result:
                found.append((m.start(), result))
                seen_spans.add(span)

    found.sort(key=lambda x: x[0])
    return found


def _classify_line(line: str) -> str:
    """Return 'exp', 'mfg', 'useby', 'bestbefore', or ''."""
    if _USEBY_KEYWORDS.search(line):
        return "useby"
    if _BB_KEYWORDS.search(line):
        return "bestbefore"
    if _EXP_KEYWORDS.search(line):
        return "exp"
    if _MFG_KEYWORDS.search(line):
        return "mfg"
    return ""


# ── Product name / batch heuristics ──────────────────────────────────────────

_BATCH_RE = re.compile(
    r"\b(?:batch|lot|batch\s*no\.?|lot\s*no\.?|b\.?\s*no\.?)\s*[:\s]?\s*([A-Z0-9\-/]{3,20})\b",
    re.IGNORECASE,
)
_PROD_PREFIXES = re.compile(
    r"^(?:product|item|name|description)\s*[:\-]?\s*",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_batch(text: str) -> Optional[str]:
    m = _BATCH_RE.search(text)
    return m.group(1).strip() if m else None


def _extract_product_name(text: str) -> Optional[str]:
    """
    Heuristic: take the first non-empty, non-date, non-numeric line
    that looks like a product title (> 3 chars, not all digits).
    """
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        if re.fullmatch(r"[\d/\-\.\s:]+", line):
            continue
        # Skip lines that start with date/batch keywords
        if re.match(
            r"(?:MFG|EXP|BB|BATCH|LOT|DATE|BEST\s*BEFORE|USE\s*BY|"
            r"EXPIRY|EXPIRES?|MANUFACTURED|DOM)[\s:\.]*",
            line, re.I,
        ):
            continue
        # Skip lines that contain only a date and no other words
        if _extract_all_dates(line) and len(line.split()) <= 3:
            continue
        return line
    return None


# ── Public API ────────────────────────────────────────────────────────────────

@dataclass
class ExtractionResult:
    product_name:        Optional[str]  = None
    batch_number:        Optional[str]  = None
    manufacturing_date:  Optional[str]  = None
    expiry_date:         Optional[str]  = None
    date_type:           str            = "expiry"
    ambiguity_notes:     list[str]      = field(default_factory=list)


def extract_label_info(raw_text: str) -> ExtractionResult:
    """
    Parse OCR text and return an ExtractionResult.
    All ambiguous dates are flagged in ambiguity_notes.
    """
    result = ExtractionResult()
    result.batch_number  = _extract_batch(raw_text)
    result.product_name  = _extract_product_name(raw_text)

    lines = raw_text.splitlines()

    mfg_dates: list[ParsedDate] = []
    exp_dates: list[ParsedDate] = []

    for line in lines:
        kind = _classify_line(line)
        dates_in_line = _extract_all_dates(line)
        for _, pd in dates_in_line:
            if pd.ambiguous and pd.note:
                result.ambiguity_notes.append(pd.note)
            if kind == "mfg":
                mfg_dates.append(pd)
            elif kind in ("exp", "useby", "bestbefore"):
                exp_dates.append(pd)
                if kind == "useby":
                    result.date_type = "use-by"
                elif kind == "bestbefore":
                    result.date_type = "best-before"
            else:
                # Unclassified — add to exp pool as a fallback
                exp_dates.append(pd)

    # Deduplicate: prefer non-ambiguous
    def _best(pool: list[ParsedDate]) -> Optional[str]:
        if not pool:
            return None
        non_amb = [p for p in pool if not p.ambiguous]
        return (non_amb[0] if non_amb else pool[0]).iso

    result.manufacturing_date = _best(mfg_dates)
    result.expiry_date        = _best(exp_dates)

    # If only one date found and unclassified, treat it as expiry
    if result.expiry_date is None and result.manufacturing_date:
        result.expiry_date        = result.manufacturing_date
        result.manufacturing_date = None

    return result
