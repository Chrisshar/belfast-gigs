"""Limelight (Shine group) via the public venuecloud.net API that limelightbelfast.com itself calls.

One response covers Limelight 1 and 2, the Limelight club room, the Telegraph Building and Shine's
outdoor shows (Ormeau Park, Custom House Square).
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlsplit

from ..dates import parse_time, to_london
from ..http import Http
from ..models import RawEvent
from ..text import ticket_provider
from .base import Adapter

API = "https://www.venuecloud.net/api/events"
SITE = "https://www.limelightbelfast.com/"


class Limelight(Adapter):
    name = "limelight"
    authority = 1
    licence = "Public JSON used by limelightbelfast.com; venuecloud.net robots.txt allows all."

    def fetch(self, http: Http) -> list[RawEvent]:
        return parse(http.get_json(API, {"venueCloudId": 10}))


def _is_club_night(e: dict) -> bool:
    """The Limelight's club room and Shine's own club brand are DJ nights, which we don't list."""
    host = urlsplit(e.get("ticketsUrl") or "").netloc
    subtitle = (e.get("subTitle") or "").strip().lower()
    return e.get("venue") == "Limelight" or "shine.tickets" in host or subtitle.startswith("every ")


def parse(payload: dict) -> list[RawEvent]:
    events = []
    for e in payload.get("events", []):
        start = datetime.strptime(e["startDate"]["date"][:16], "%Y-%m-%d %H:%M")
        date, time = to_london(start)  # Europe/Dublin and Europe/London keep the same clock
        doors_text, _, age = (e.get("doors") or "").partition("/")
        doors = parse_time(doors_text) or time
        subtitle = (e.get("subTitle") or "").strip()
        support = [s.strip() for s in re.split(r",|\s&\s", subtitle.lstrip("+").strip())] if subtitle.startswith("+") else []
        venue = e.get("venue") or "Limelight"
        categories = [c.lower() for c in e.get("categories") or []]
        if _is_club_night(e):
            hint: bool | None = False
        elif "comedy" in categories:
            hint = False
        elif venue.startswith("Limelight ") or "ticketmaster" in urlsplit(e.get("ticketsUrl") or "").netloc:
            # Limelight 1 and 2 are the gig rooms, and the venue tags its comedy, so anything
            # untagged there is a gig. At its other venues (Telegraph Building, parks) Shine sells
            # gigs through Ticketmaster; bingo, markets and the like use other sellers.
            hint = True
        else:
            hint = None
        ticket = e.get("ticketsUrl")
        events.append(
            RawEvent(
                source="limelight",
                source_key=f"limelight:{e['id']}",
                source_url=SITE,
                title=e["title"].strip(),
                support=[s for s in support if s],
                venue_name=venue,
                room=venue if venue.startswith("Limelight ") else None,
                date=date,
                doors_time=doors,
                start_time=time if time != doors else None,
                status="sold_out" if e.get("isSoldOut") else "on_sale",
                age_restriction=age.strip() or None,
                tickets=[(ticket_provider(ticket), ticket)] if ticket else [],
                categories=categories,
                is_music_hint=hint,
            )
        )
    return events
