"""Ulster Sports Club, from the public JSON its events calendar widget (eventscalendar.co) loads.

No key is needed, and the widget host's robots.txt explicitly allows this data path. The feed
holds every event back to 2024 in no particular order, so future ones are picked out here.
The club also hosts DJ nights, art and film, which the rules and Claude sort out.
"""

from __future__ import annotations

import json
import re

from ..dates import london_today
from ..http import Http
from ..models import RawEvent
from ..text import ticket_provider
from .base import Adapter

FEED = "https://inffuse.eventscalendar.co/js/v0.1/calendar/data"
PROJECT = "proj_J3y1vazQf9Q8H8rNxFl6r"
VENUE = "Ulster Sports Club"


class UlsterSportsClub(Adapter):
    name = "usc"
    authority = 1
    licence = "Public calendar data used by ulstersportsclub.com; the feed host's robots.txt allows /js/*/*/data."

    def fetch(self, http: Http) -> list[RawEvent]:
        return parse(json.loads(http.get_text(FEED, {"id": PROJECT})), london_today())


def parse(payload: dict, today: str) -> list[RawEvent]:
    out = []
    for e in payload.get("project", {}).get("data", {}).get("events", []):
        date = str(e.get("startDate") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or date < today:
            continue
        end = str(e.get("endDate") or "")
        timed = not e.get("allday") and e.get("startHour") is not None
        links = [str(link.get("url")) for link in e.get("links") or [] if link.get("url")]
        out.append(
            RawEvent(
                source="usc",
                source_key=f"usc:{e.get('id')}",
                title=str(e.get("title") or "").strip(),
                venue_name=VENUE,
                date=date,
                end_date=end if re.fullmatch(r"\d{4}-\d{2}-\d{2}", end) and end > date and not timed else None,
                start_time=f"{int(e['startHour']):02d}:{int(e.get('startMinutes') or 0):02d}" if timed else None,
                tickets=[(ticket_provider(u), u) for u in dict.fromkeys(links)],
                is_music_hint=None,  # gigs, club nights, art and film share the calendar
            )
        )
    return [e for e in out if e.title]
