"""Gig dates and times are Europe/London local strings: "YYYY-MM-DD" and "HH:MM"."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")


def now_utc() -> datetime:
    return datetime.now(UTC)


def london_today(now: datetime | None = None) -> str:
    return (now or now_utc()).astimezone(LONDON).date().isoformat()


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_london(dt: datetime) -> tuple[str, str]:
    """Split an aware datetime into London (date, time). Naive datetimes are taken as London time."""
    local = dt.replace(tzinfo=LONDON) if dt.tzinfo is None else dt.astimezone(LONDON)
    return local.date().isoformat(), local.strftime("%H:%M")


def as_date_str(value: object) -> str | None:
    """Accept str or date (YAML may hand back either) and return YYYY-MM-DD."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


_TIME_RE = re.compile(r"(?P<h>\d{1,2})(?:[:.](?P<m>\d{2}))?\s*(?P<ampm>am|pm)?", re.I)


def parse_time(text: str | None) -> str | None:
    """'7pm' -> '19:00', '7.30PM' -> '19:30', '19:45' -> '19:45'. Returns None if no time found."""
    if not text:
        return None
    m = _TIME_RE.search(text)
    if not m:
        return None
    hour, minute, ampm = int(m["h"]), int(m["m"] or 0), (m["ampm"] or "").lower()
    if not ampm and m["m"] is None:
        return None  # a bare number isn't a time
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
GRACE_DAYS = 14
_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def infer_date(day: int, month: str, today: str, weekday: str | None = None) -> str | None:
    """A listing date with no year ("Thu 19 Nov", "28th October"): the next one on or after
    today, with two weeks' grace for listings not yet taken down. A weekday, when given, picks the year."""
    m = _MONTHS.get(month[:3].lower())
    if not m:
        return None
    t = date.fromisoformat(today)
    candidates = []
    for year in (t.year - 1, t.year, t.year + 1, t.year + 2):
        try:
            candidates.append(date(year, m, day))
        except ValueError:
            continue
    if weekday:
        wd = _WEEKDAYS.index(weekday[:3].lower()) if weekday[:3].lower() in _WEEKDAYS else None
        matching = [d for d in candidates if d.weekday() == wd and (t - d).days <= GRACE_DAYS]
        if matching:
            return min(matching, key=lambda d: abs((d - t).days)).isoformat()
    upcoming = [d for d in candidates if (t - d).days <= GRACE_DAYS]
    return min(upcoming).isoformat() if upcoming else None
