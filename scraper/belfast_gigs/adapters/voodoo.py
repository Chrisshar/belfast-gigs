"""Voodoo (Fountain Street), from its Wix sitemap and server-rendered event pages.

The upcoming-events grid needs JavaScript, but every event has a page under /events/<slug> that
is plain HTML, listed in a sitemap with a lastmod date. The sitemap also lists past events, so
only the most recently edited pages are fetched; anything already past is dropped.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..dates import parse_time
from ..http import Http, parse_html
from ..models import RawEvent
from ..text import recase, ticket_provider
from .base import Adapter
from .wix import event_urls

SITE = "https://www.voodoobelfast.com"
VENUE = "Voodoo"
RECENT_PAGES = 30
_DATE = re.compile(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*\|\s*(\d{1,2}:\d{2}\s*[AP]M)?", re.I)
_TICKETS = re.compile(r"skiddle|fixr|ticketmaster|eventbrite|dice\.fm|seetickets|tickettailor|ticketsource", re.I)


class Voodoo(Adapter):
    name = "voodoo"
    authority = 1
    licence = "Public pages on voodoobelfast.com; robots.txt only disallows ?lightbox=."

    def fetch(self, http: Http) -> list[RawEvent]:
        events = [parse_event(url, http.get_text(url)) for url in event_urls(http, SITE, RECENT_PAGES)]
        return [e for e in events if e]


def parse_event(url: str, html: str) -> RawEvent | None:
    page = parse_html(html)
    text = re.sub(r"\s+", " ", page.get_all_text(separator=" | ")).replace("​", "")
    m = _DATE.search(text)
    if not m:
        return None
    try:
        date = datetime.strptime(f"{m[1]} {m[2][:3]} {m[3]}", "%d %b %Y").date().isoformat()
    except ValueError:
        return None
    title_m = re.search(r"Back to Upcoming Events \| (.+?) \|", text)
    title = (title_m[1] if title_m else "").strip(" |")
    if not title:
        heading = page.css("h1, h2")
        title = heading[0].get_all_text(separator=" ").strip() if heading else ""
    if not title:
        return None
    after = text[m.end():]
    price = re.search(r"£\s?(\d+(?:\.\d{2})?)", after[:200])
    free = bool(re.search(r"\bfree\b", after[:120], re.I)) and not price
    links = list(dict.fromkeys(str(h) for h in page.css("a::attr(href)").getall() if _TICKETS.search(str(h))))
    return RawEvent(
        source="voodoo",
        source_key=f"voodoo:{url.rstrip('/').rsplit('/', 1)[-1]}",
        source_url=url,
        title=recase(title),
        venue_name=VENUE,
        date=date,
        start_time=parse_time(m[4]) if m[4] else None,
        price_min=float(price[1]) if price else None,
        free=free,
        tickets=[(ticket_provider(u), u) for u in links],
        is_music_hint=None,  # gigs and club nights share the listing
    )
