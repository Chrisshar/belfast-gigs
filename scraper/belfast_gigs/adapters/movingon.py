"""Moving On Music, a promoter of contemporary, jazz, folk and new-classical shows around Belfast.

Its WordPress REST API lists the What's On child pages (no key needed); each page has a line like
"THU 19 NOV | THE EMPIRE, BELFAST | 7.30PM | £17.50" and a Citizen Ticket link. Shows are music,
but choral and orchestral ones still go through the rules and Claude.
The site answers 406 to short user agents; the scraper's full one is fine.
"""

from __future__ import annotations

import json
import re

from ..dates import infer_date, london_today, parse_time
from ..http import Http, parse_html
from ..models import RawEvent
from ..text import ticket_provider
from .base import Adapter

PAGES = "https://www.movingonmusic.com/wp-json/wp/v2/pages"
WHATS_ON = 6  # parent page id of /whats-on/
_LINE = re.compile(
    r"\b(MON|TUE|WED|THU|FRI|SAT|SUN)[A-Z]*\s+(\d{1,2})\s+([A-Z]{3})[A-Z]*\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*(?:\|\s*([^|]+))?(?:\||$)",
    re.I,
)
_TICKETS = re.compile(r"citizenticket|eventbrite|ticketsolve|ticketmaster|tickettailor|ticketsource|waterfront\.co\.uk", re.I)


class MovingOnMusic(Adapter):
    name = "movingon"
    authority = 1
    licence = "Public pages and WordPress REST API on movingonmusic.com; robots.txt allows both."

    def fetch(self, http: Http) -> list[RawEvent]:
        pages = json.loads(http.get_text(PAGES, {"parent": WHATS_ON, "per_page": 50, "_fields": "id,link,title"}))
        today = london_today()
        events = [parse_page(str(p["link"]), http.get_text(str(p["link"])), today) for p in pages]
        return [e for e in events if e]


def parse_page(url: str, html: str, today: str) -> RawEvent | None:
    page = parse_html(html)
    text = re.sub(r"\s+", " ", page.get_all_text(separator=" | "))
    m = _LINE.search(text)
    if not m:
        return None
    date = infer_date(int(m[2]), m[3], today, m[1])
    if not date:
        return None
    place = m[4].strip()
    venue = re.sub(r",\s*BELFAST$", "", place, flags=re.I).split(",")
    title_el = page.css("h1")
    title = title_el[0].get_all_text(separator=" ").strip() if title_el else ""
    if not title:
        return None
    prices = [float(p) for p in re.findall(r"£\s?(\d+(?:\.\d{1,2})?)", m[6] or "")]
    links = [str(h) for h in page.css("a::attr(href)").getall() if _TICKETS.search(str(h)) and not str(h).endswith((".png", ".jpg"))]
    return RawEvent(
        source="movingon",
        source_key=f"movingon:{url.rstrip('/').rsplit('/', 1)[-1]}",
        source_url=url,
        title=title,
        # "DRAWING OFFICE ONE, TITANIC HOTEL": the room comes first, the venue last.
        venue_name=venue[-1].strip().title(),
        room=venue[0].strip().title() if len(venue) > 1 else None,
        address=place.title() if re.search(r"belfast", place, re.I) else None,
        date=date,
        start_time=parse_time(m[5]),
        price_min=min(prices) if prices else None,
        price_max=max(prices) if len(set(prices)) > 1 else None,
        tickets=[(ticket_provider(u), u) for u in dict.fromkeys(links)],
        is_music_hint=True,
    )
