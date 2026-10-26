"""The Duncairn (Antrim Road) from its Squarespace /live-music page plus each event's page.

/live-music lists only music, with dates; each event page adds the start time and the
Ticketsolve link. robots.txt disallows the ?format=json/ical exports, so the HTML is read.
"""

from __future__ import annotations

import re

from ..http import Http, parse_html
from ..models import RawEvent
from ..text import ticket_provider
from .base import Adapter

BASE = "https://www.theduncairn.com"
PAGE = f"{BASE}/live-music"
VENUE = "The Duncairn"
_DATE = re.compile(r"([A-Z][a-z]+) (\d{1,2}), (\d{4})")
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


class Duncairn(Adapter):
    name = "duncairn"
    authority = 1
    always_music = True  # /live-music is the venue's own music listing
    licence = "Public pages on theduncairn.com; robots.txt only disallows the ?format= exports."

    def fetch(self, http: Http) -> list[RawEvent]:
        return [with_detail(e, http.get_text(e.source_url)) if e.source_url else e for e in parse_listing(http.get_text(PAGE))]


def parse_listing(html: str) -> list[RawEvent]:
    out, seen = [], set()
    for item in parse_html(html).css(".summary-item-record-type-event"):
        href = next((str(h) for h in item.css("a::attr(href)").getall() if "/events/" in str(h)), None)
        title = item.css(".summary-title")
        m = _DATE.search(item.get_all_text(separator=" | "))
        if not (href and title and m and m[1] in _MONTHS) or href in seen:
            continue
        seen.add(href)
        out.append(
            RawEvent(
                source="duncairn",
                source_key=f"duncairn:{href.rstrip('/').rsplit('/', 1)[-1]}",
                source_url=href if href.startswith("http") else BASE + href,
                title=title[0].get_all_text(separator=" ").strip(),
                venue_name=VENUE,
                date=f"{m[3]}-{_MONTHS.index(m[1]) + 1:02d}-{int(m[2]):02d}",
                is_music_hint=True,
            )
        )
    return out


def with_detail(event: RawEvent, html: str) -> RawEvent:
    page = parse_html(html)
    start = page.css("time.event-time-24hr-start::text").getall()
    if start and re.fullmatch(r"\d{2}:\d{2}", str(start[0]).strip()):
        event.start_time = str(start[0]).strip()
    links = [str(h) for h in page.css("a::attr(href)").getall() if "ticketsolve" in str(h)]
    event.tickets = [(ticket_provider(u), u) for u in dict.fromkeys(links)] or [("The Duncairn", event.source_url or BASE)]
    text = page.get_all_text(separator=" ")
    if re.search(r"\b18\s*\+", text):
        event.age_restriction = "18+"
    if re.search(r"\bsold\s*out\b", text, re.I):
        event.status = "sold_out"
    return event
