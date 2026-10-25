"""The O2 Belfast (formerly the SSE Arena) via the JSON its own events page loads.

The listing has no times and shows a multi-night run as one date range, so each event's detail
page is read for the individual nights: one block per night with its doors time and Ticketmaster link.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..dates import parse_time
from ..http import Http, parse_html
from ..models import RawEvent
from ..text import ticket_provider
from .base import Adapter

LISTING = "https://theo2belfast.com/events.json"
VENUE = "The O2 Belfast"
# Ticket links for add-ons rather than the gig itself.
_ADDON = re.compile(r"suite|vip|hospitality|parking|package|upgrade|lounge|premium|platinum", re.I)
_TM_DATE = re.compile(r"-(\d{2})-(\d{2})-(\d{4})/event/")


class O2Belfast(Adapter):
    name = "o2belfast"
    authority = 1
    licence = "Public JSON and pages on theo2belfast.com; robots.txt allows /events."

    def fetch(self, http: Http) -> list[RawEvent]:
        listings, page = [], 1
        while True:
            payload = http.get_json(LISTING, {"page": page, "genres[]": "music"})
            listings.extend(payload.get("data", []))
            if page >= payload.get("meta", {}).get("pagination", {}).get("total_pages", 1):
                break
            page += 1
        events = []
        for listing in listings:
            detail = http.get_text(listing["url"]) if listing.get("url") else ""
            events.extend(parse_event(listing, detail))
        return events


def _support(listing: dict) -> list[str]:
    acts = listing.get("supportingAct") or ""
    return [a.strip() for a in re.split(r",|\s&\s|\sand\s", acts) if a.strip()]


def _date(text: str) -> str | None:
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})", text)
    if not m:
        return None
    return datetime.strptime(f"{m[1]} {m[2]} {m[3]}", "%d %b %Y").date().isoformat()


def parse_nights(detail_html: str) -> list[dict]:
    """One dict per night: date, doors_time, ticket url (or None), sold_out."""
    nights = []
    page = parse_html(detail_html)
    for item in page.css(".eventDetail__modal--item"):
        day = item.css(".modal-event-day")
        date = _date(day[0].get_all_text(separator=" ")) if day else None
        if not date:
            continue
        doors = item.css(".modal-event-doors")
        links = [str(h) for h in item.css("a::attr(href)").getall() if "ticketmaster" in h and not _ADDON.search(h)]
        text = item.get_all_text(separator=" ").lower()
        nights.append(
            {
                "date": date,
                "doors_time": parse_time(doors[0].get_all_text(separator=" ")) if doors else None,
                "ticket": links[0] if links else None,
                "sold_out": "sold out" in text and not links,
            }
        )
    return nights


def parse_event(listing: dict, detail_html: str) -> list[RawEvent]:
    base = dict(
        source="o2belfast",
        source_url=listing.get("url"),
        title=listing["title"].strip(),
        support=_support(listing),
        venue_name=VENUE,
        categories=[g["slug"] for g in listing.get("genre") or []],
        is_music_hint=True,  # the listing is already filtered to genres[]=music
    )
    nights = parse_nights(detail_html) if detail_html else []
    if nights:
        return [
            RawEvent(
                source_key=f"o2belfast:{listing['id']}:{n['date']}",
                date=n["date"],
                doors_time=n["doors_time"],
                status="sold_out" if n["sold_out"] else "on_sale",
                tickets=[(ticket_provider(n["ticket"]), n["ticket"])] if n["ticket"] else [],
                **base,
            )
            for n in nights
        ]
    start = listing["eventStartDate"]["date"][:10]
    end = (listing.get("eventEndDate") or {}).get("date", "")[:10] or None
    return [RawEvent(source_key=f"o2belfast:{listing['id']}", date=start, end_date=end if end and end != start else None, **base)]
