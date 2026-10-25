"""Ticketmaster Discovery API v2: music events within 15 km of Belfast.

Needs TICKETMASTER_KEY. Without it the adapter is skipped (reported, not treated as broken).
Terms: no earning from the API outside Ticketmaster's affiliate programme.
"""

from __future__ import annotations

import os
import re

from ..http import Http
from ..models import RawEvent, Status
from .base import Adapter, MissingCredentials

API = "https://app.ticketmaster.com/discovery/v2/events.json"
MUSIC_SEGMENT = "KZFzniwnSyZfZ7v7nJ"
PAGE_SIZE = 200  # the API refuses size * page beyond 1000
# Separate listings for extras rather than the gig itself.
JUNK = re.compile(
    r"\b(vip|platinum|package|parking|car park|upgrade|hotel|hospitality|suite|meet\s*(&|and)\s*greet|resale|fast\s*track|premium|merch)\b",
    re.I,
)
STATUS: dict[str, Status] = {"canceled": "cancelled", "cancelled": "cancelled", "postponed": "postponed", "rescheduled": "rescheduled"}
# Belfast city centre (54.5973, -5.9301) as a 6-character geohash.
BELFAST_GEOHASH = "gcey95"


class Ticketmaster(Adapter):
    name = "ticketmaster"
    authority = 5
    licence = "Ticketmaster Discovery API terms: non-commercial unless in the affiliate programme."

    def fetch(self, http: Http) -> list[RawEvent]:
        key = os.environ.get("TICKETMASTER_KEY")
        if not key:
            raise MissingCredentials("TICKETMASTER_KEY is not set")
        events, page = [], 0
        while True:
            payload = http.get_json(
                API,
                {
                    "apikey": key,
                    "segmentId": MUSIC_SEGMENT,
                    "geoPoint": BELFAST_GEOHASH,
                    "radius": 15,
                    "unit": "km",
                    "locale": "*",
                    "sort": "date,asc",
                    "size": PAGE_SIZE,
                    "page": page,
                },
            )
            events.extend(parse(payload))
            total_pages = payload.get("page", {}).get("totalPages", 1)
            page += 1
            if page >= total_pages or PAGE_SIZE * (page + 1) > 1000:
                return collapse(events)


def parse(payload: dict) -> list[RawEvent]:
    out = []
    for e in payload.get("_embedded", {}).get("events", []):
        name = e.get("name", "").strip()
        if JUNK.search(name):
            continue
        start = e.get("dates", {}).get("start", {})
        date = start.get("localDate")
        if not date:
            continue
        venue = (e.get("_embedded", {}).get("venues") or [{}])[0]
        attractions = [a.get("name", "").strip() for a in e.get("_embedded", {}).get("attractions", []) if a.get("name")]
        cls = (e.get("classifications") or [{}])[0]
        genres = [cls.get(k, {}).get("name", "") for k in ("genre", "subGenre")]
        prices = [p for p in e.get("priceRanges") or [] if p.get("currency") == "GBP"]
        location = venue.get("location") or {}
        code = e.get("dates", {}).get("status", {}).get("code", "")
        out.append(
            RawEvent(
                source="ticketmaster",
                source_key=f"ticketmaster:{e['id']}",
                source_url=e.get("url"),
                title=name,
                headliner=attractions[0] if attractions else None,
                support=attractions[1:],
                venue_name=venue.get("name", ""),
                address=", ".join(filter(None, [venue.get("address", {}).get("line1"), venue.get("city", {}).get("name"), venue.get("postalCode")])) or None,
                lat=float(location["latitude"]) if location.get("latitude") else None,
                lng=float(location["longitude"]) if location.get("longitude") else None,
                date=date,
                start_time=_local_time(start),
                price_min=min(p["min"] for p in prices) if prices else None,
                price_max=max(p["max"] for p in prices) if prices else None,
                status="sold_out" if code == "offsale" and _sold_out(e) else STATUS.get(code, "on_sale"),
                tickets=[("Ticketmaster", e["url"])] if e.get("url") else [],
                categories=[g.lower() for g in genres if g and g.lower() not in ("undefined", "other")],
                is_music_hint=True,
                attraction_key=(e.get("_embedded", {}).get("attractions") or [{}])[0].get("id"),
            )
        )
    return out


def _local_time(start: dict) -> str | None:
    """Venue-local HH:MM. Never derived from the UTC dateTime; TBA times stay empty."""
    if start.get("timeTBA") or start.get("noSpecificTime"):
        return None
    return (start.get("localTime") or "")[:5] or None


def _sold_out(e: dict) -> bool:
    return "sold out" in (e.get("info", "") + e.get("pleaseNote", "")).lower()


def collapse(events: list[RawEvent]) -> list[RawEvent]:
    """Several listings for one attraction at one venue on one night (standard + seated + extras): keep one."""
    seen: dict[tuple, RawEvent] = {}
    for ev in events:
        key = (ev.attraction_key or ev.title.lower(), ev.venue_name.lower(), ev.date)
        if key not in seen:
            seen[key] = ev
        else:
            kept = seen[key]
            for t in ev.tickets:
                if t not in kept.tickets:
                    kept.tickets.append(t)
    return list(seen.values())
