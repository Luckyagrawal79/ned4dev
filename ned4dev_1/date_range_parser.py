"""
Parse date range expressions from natural language queries.

Handles patterns like:
  - "from jan to march"
  - "from january to march 2025"
  - "from dec 2025 to feb 2026"
  - "from dec to feb"  (auto cross-year)
  - "jan to march"
  - "february 2025 to april 2025"
  
Returns a (start_date, end_date) tuple of datetime.date objects representing
the first day of the start month and the last day of the end month,
or None if no date range is detected.
"""

import re
import calendar
from datetime import date, datetime

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9, "sept": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Sort month names longest-first so "march" matches before "mar", "september" before "sep", etc.
_MONTH_NAMES_RE = "|".join(sorted(MONTH_MAP.keys(), key=len, reverse=True))

# Regex: captures  month [year]  to/through/-  month [year]
_RANGE_RE = re.compile(
    r"(?:from\s+)?"
    r"(?P<m1>" + _MONTH_NAMES_RE + r")"
    r"(?:\s+(?P<y1>\d{4}))?"
    r"\s+(?:to|through|till|until|-)\s+"
    r"(?P<m2>" + _MONTH_NAMES_RE + r")"
    r"(?:\s+(?P<y2>\d{4}))?",
    re.IGNORECASE,
)

# Regex: "from feb [year]" — open-ended, means month to latest
_FROM_MONTH_RE = re.compile(
    r"from\s+"
    r"(?P<m>" + _MONTH_NAMES_RE + r")"
    r"(?:\s+(?P<y>\d{4}))?",
    re.IGNORECASE,
)

# Regex: "in feb", "for march 2025", "during april" — single month only
_SINGLE_MONTH_RE = re.compile(
    r"(?:in|for|during|of)\s+"
    r"(?P<m>" + _MONTH_NAMES_RE + r")"
    r"(?:\s+(?P<y>\d{4}))?",
    re.IGNORECASE,
)


def parse_date_range(query: str, reference_year: int | None = None, latest_build: str | None = None) -> dict | None:
    """
    Parse a date range from a natural language query.

    Args:
        query: The user's query string
        reference_year: Year to assume when none is mentioned.
                        Defaults to the current year.
        latest_build: The latest week key in the data (YYYY-MM-DD).
                     Used as end date for open-ended "from feb" queries.

    Returns:
        dict with keys:
            start_date: date  (first day of start month)
            end_date:   date  (last day of end month, or latest_build date)
            start_month_name: str
            end_month_name:   str
            start_year: int
            end_year:   int
            open_ended: bool  (True if "from X" with no end month)
        or None if no date range found.
    """
    if reference_year is None:
        reference_year = datetime.now().year

    match = _RANGE_RE.search(query.lower())
    if not match:
        # Try "from feb [year]" — open-ended: month to latest data
        from_match = _FROM_MONTH_RE.search(query.lower())
        if from_match:
            m = MONTH_MAP[from_match.group("m").lower()]
            y = int(from_match.group("y")) if from_match.group("y") else reference_year

            start_date = date(y, m, 1)

            # End date = latest available week, or end of current month
            if latest_build:
                end_date = datetime.strptime(latest_build, "%Y-%m-%d").date()
            else:
                now = datetime.now()
                last_day = calendar.monthrange(now.year, now.month)[1]
                end_date = date(now.year, now.month, last_day)

            # If start is after end (e.g. "from dec" when latest is march,
            # user probably means previous year's dec)
            if start_date > end_date and not from_match.group("y"):
                start_date = date(y - 1, m, 1)

            return {
                "start_date": start_date,
                "end_date": end_date,
                "start_month_name": calendar.month_name[m],
                "end_month_name": end_date.strftime("%B"),
                "start_year": start_date.year,
                "end_year": end_date.year,
                "open_ended": True,
            }

        # Try "in feb", "for march 2025" — single month only
        single = _SINGLE_MONTH_RE.search(query.lower())
        if single:
            m = MONTH_MAP[single.group("m").lower()]
            y = int(single.group("y")) if single.group("y") else reference_year

            start_date = date(y, m, 1)
            last_day = calendar.monthrange(y, m)[1]
            end_date = date(y, m, last_day)

            return {
                "start_date": start_date,
                "end_date": end_date,
                "start_month_name": calendar.month_name[m],
                "end_month_name": calendar.month_name[m],
                "start_year": y,
                "end_year": y,
                "open_ended": False,
            }

        return None
    m1 = MONTH_MAP[match.group("m1").lower()]
    m2 = MONTH_MAP[match.group("m2").lower()]

    y1 = int(match.group("y1")) if match.group("y1") else None
    y2 = int(match.group("y2")) if match.group("y2") else None

    # --- Year resolution logic ---
    if y1 and y2:
        # Both years explicit — use as-is
        start_year, end_year = y1, y2
    elif y1 and not y2:
        # Only start year given
        start_year = y1
        end_year = y1 if m2 >= m1 else y1 + 1
    elif not y1 and y2:
        # Only end year given
        end_year = y2
        start_year = y2 if m1 <= m2 else y2 - 1
    else:
        # No year given — use reference year, handle cross-year
        if m2 >= m1:
            start_year = reference_year
            end_year = reference_year
        else:
            # Cross-year range (e.g. "dec to feb")
            # Prefer the most recent completed or ongoing range:
            #   If current month >= end month, use (ref_year-1, ref_year)
            #   e.g. in March 2026, "dec to feb" → Dec 2025 to Feb 2026
            #   Otherwise use (ref_year, ref_year+1)
            #   e.g. in Nov 2025, "dec to feb" → Dec 2025 to Feb 2026
            current_month = datetime.now().month
            if current_month >= m2:
                start_year = reference_year - 1
                end_year = reference_year
            else:
                start_year = reference_year
                end_year = reference_year + 1

    start_date = date(start_year, m1, 1)
    last_day = calendar.monthrange(end_year, m2)[1]
    end_date = date(end_year, m2, last_day)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "start_month_name": calendar.month_name[m1],
        "end_month_name": calendar.month_name[m2],
        "start_year": start_year,
        "end_year": end_year,
        "open_ended": False,
    }


def filter_builds_by_range(build_keys: list[str], start_date: date, end_date: date) -> list[str]:
    """
    Filter a list of build keys (YYYY-MM-DD strings) to only those
    that fall within [start_date, end_date].
    """
    filtered = []
    for wk in build_keys:
        wk_date = datetime.strptime(wk, "%Y-%m-%d").date()
        if start_date <= wk_date <= end_date:
            filtered.append(wk)
    return sorted(filtered)
