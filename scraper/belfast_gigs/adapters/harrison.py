"""The Harrison Chambers of Distinction (Malone Road): the Squarespace /music page plus each event page.

The /music page is a summary block of upcoming and recent music events. Each event page carries
schema.org Event data with the times. Squarespace labels those times "+0000" but they are the local
clock time (the page shows the same 20:00), so the offset is ignored.
robots.txt forbids Squarespace's ?format=json and ?format=ical feeds, so this reads HTML only.
"""

from __future__ import annotations

import json
import re
import time

from ..http import Http, parse_html
from ..models import RawEvent
from ..text import ticket_provider
from .base import Adapter

SITE = "https://www.chambersofdistinction.com"
LISTING = f"{SITE}/music"
VENUE = "The Harrison Chambers of Distinction"
_TICKETS = re.compile(r"ticketsource|eventbrite|citizenticket|ticketmaster|skiddle|fixr|tickettailor|ticketsolve|seetickets|dice\.fm", re.I)
_SERIES = re.compile(r"^blue room sessions?\s*[:\-–]\s*", re.I)
_LOCAL = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})")


class Harrison(Adapter):
    name = "harrison"
    authority = 1
    licence = "Public pages on chambersofdistinction.com; robots.txt allows event pages (not the JSON/iCal feeds)."

    def fetch(self, http: Http) -> list[RawEvent]:
        events = []
        now_ms = time.time() * 1000
        for item in parse_listing(http.get_text(LISTING)):
            # Squarespace marks only upcoming events with an end timestamp; the page also lists
            # recent past ones. Skip those rather than fetch their pages.
            if not item["ends_ms"] or item["ends_ms"] < now_ms:
                continue
            event = parse_event(item, http.get_text(SITE + item["path"]))
            if event:
                events.append(event)
        return events


def parse_listing(html: str) -> list[dict]:
    items, seen = [], set()
    for el in parse_html(html).css(".summary-item-record-type-event"):
        links = el.css(".summary-title a::attr(href)").getall() or el.css("a::attr(href)").getall()
        if not links or str(links[0]) in seen:
            continue
        seen.add(str(links[0]))
        title = el.css(".summary-title a")
        excerpt = el.css(".summary-excerpt")
        ends = el.attrib.get("data-upcoming-event-end") or ""
        items.append(
            {
                "path": str(links[0]),
                "title": title[0].get_all_text(separator=" ").strip() if title else "",
                "excerpt": excerpt[0].get_all_text(separator=" ").strip() if excerpt else "",
                "ends_ms": int(ends) if ends.isdigit() else None,
            }
        )
    return items


def _event_jsonld(html: str) -> dict | None:
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for it in data if isinstance(data, list) else data.get("@graph", [data]):
            if isinstance(it, dict) and it.get("@type") == "Event":
                return it
    return None


def parse_event(item: dict, html: str) -> RawEvent | None:
    ld = _event_jsonld(html)
    start = _LOCAL.match((ld or {}).get("startDate") or "")
    if not start:
        return None
    end = _LOCAL.match((ld or {}).get("endDate") or "")
    title = item["title"] or re.sub(r"\s+—\s+The Harrison.*$", "", (ld or {}).get("name", "")).strip()
    tickets = [str(h) for h in parse_html(html).css("a::attr(href)").getall() if _TICKETS.search(str(h))]
    series = _SERIES.match(title)
    text = f"{title} {item['excerpt']}"
    return RawEvent(
        source="harrison",
        source_key=f"harrison:{item['path'].rstrip('/').rsplit('/', 1)[-1]}",
        source_url=SITE + item["path"],
        title=title,
        headliner=title[series.end():].strip() if series else None,
        venue_name=VENUE,
        room="Blue Room" if "blue room" in text.lower() else None,
        date=start[1],
        end_date=end[1] if end and end[1] != start[1] and end[2] > "06:00" else None,  # past midnight isn't a second day
        start_time=start[2],
        tickets=[(ticket_provider(t), t) for t in dict.fromkeys(tickets)],
        is_music_hint=True,  # the venue's own music listing (the odd DJ night is caught by the rules)
    )
