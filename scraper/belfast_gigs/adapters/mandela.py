"""Queen's Students' Union venues (Mandela Hall, the Union Bar) from their Glistrr box office page.

glistrr.com/events/l/qub embeds every upcoming event as a JSON array (`var events = [...]`), with
categories, prices, sold-out status and ages. That's richer than the schema.org data the page
builds from it, so the array is read directly.
"""

from __future__ import annotations

import json
from datetime import datetime

from ..dates import to_london
from ..http import Http
from ..models import RawEvent
from .base import Adapter

PAGE = "https://glistrr.com/events/l/qub"
TICKETS = "https://www.glistrr.com/events/e/{slug}"
VENUES = {"union bar": "The Union Bar"}  # anything else is Mandela Hall


class MandelaHall(Adapter):
    name = "mandela"
    authority = 1
    licence = "QUB Students' Union's public box office page on glistrr.com; robots.txt allows it."

    def fetch(self, http: Http) -> list[RawEvent]:
        return parse(http.get_text(PAGE))


def _events(html: str) -> list[dict]:
    start = html.find("var events = [")
    if start < 0:
        return []
    events, _ = json.JSONDecoder().raw_decode(html[start + len("var events = ") :])
    return events


def _price(value: object) -> float | None:
    try:
        return float(str(value))
    except ValueError:
        return None


def parse(html: str) -> list[RawEvent]:
    out = []
    for e in _events(html):
        try:
            date, time = to_london(datetime.strptime(str(e["start"]), "%Y-%m-%d %H:%M:%S %z"))
        except (KeyError, ValueError):
            continue
        cats = [str(c.get("slug")) for c in e.get("categories") or []]
        if "live-music" in cats:
            hint: bool | None = True
        elif "club-night" in cats or "comedy" in cats:
            hint = False
        else:
            hint = None
        lo, hi = _price(e.get("tickets_from")), _price(e.get("tickets_max"))
        venue_raw = str(e.get("venue_name") or "")
        venue = next((v for k, v in VENUES.items() if k in venue_raw.lower()), "Mandela Hall")
        lat, _, lng = str(e.get("venue_coordinates") or "").partition(",")
        url = TICKETS.format(slug=e.get("slug"))
        out.append(
            RawEvent(
                source="mandela",
                source_key=f"mandela:{e.get('id')}",
                source_url=url,
                title=str(e.get("name") or "").strip(),
                venue_name=venue,
                date=date,
                start_time=time,
                price_min=lo or None,
                price_max=hi if hi and lo and hi > lo else None,
                free=lo == 0 and hi == 0,
                status="sold_out" if e.get("tickets_available") == "S" else "on_sale",
                age_restriction=f"{e['min_age']}+" if e.get("min_age") else None,
                tickets=[("Glistrr", url)],
                categories=cats,
                is_music_hint=hint,
                lat=float(lat) if lat and lng else None,
                lng=float(lng) if lat and lng else None,
                address=str(e.get("venue_address") or "") or None,
            )
        )
    return [e for e in out if e.title]
