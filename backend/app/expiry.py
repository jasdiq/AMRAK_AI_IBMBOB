"""
Expiry status helper shared by endpoints and dashboard.
"""
from datetime import date as Date
from typing import Optional


def expiry_status(exp_date_str: Optional[str]) -> str:
    """
    Return one of: 'expired' | 'expiring_soon' | 'ok' | 'unknown'
    expiring_soon = within 30 days.
    """
    if not exp_date_str:
        return "unknown"
    try:
        # Accept YYYY-MM-DD or YYYY-MM (assume last day of month)
        parts = exp_date_str.split("-")
        if len(parts) == 3:
            exp = Date(int(parts[0]), int(parts[1]), int(parts[2]))
        elif len(parts) == 2:
            import calendar
            y, m = int(parts[0]), int(parts[1])
            last_day = calendar.monthrange(y, m)[1]
            exp = Date(y, m, last_day)
        else:
            return "unknown"
    except (ValueError, IndexError):
        return "unknown"

    today = Date.today()
    if exp < today:
        return "expired"
    if (exp - today).days <= 30:
        return "expiring_soon"
    return "ok"
