"""The Belfast Empire Music Hall: the /music-hall/ listing plus each gig's page for price and tickets.

The listing is static HTML (an Essential Grid that pages itself in the browser), with a sortable
date attribute on each item. The gig page adds the price and the Ticketmaster link.
"""

from __future__ import annotations

import re

from ..dates import parse_time
from ..http import Http, parse_html
from ..models import RawEvent
from ..text import recase, ticket_provider
from .base import Adapter

LISTING = "https://www.thebelfastempire.com/music-hall/"
VENUE = "The Belfast Empire Music Hall"
_TICKETS = re.compile(r"ticketmaster|eventbrite|skiddle|seetickets|ticketsolve|citizenticket|dice\.fm|fixr|tickettailor|ticketsource", re.I)


class Empire(Adapter):
    name = "empire"
    authority = 1
    licence = "Public pages on thebelfastempire.com; robots.txt only disallows /opt-in-thank-you/."

    def fetch(self, http: Http) -> list[RawEvent]:
        events = []
        for item in parse_listing(http.get_text(LISTING)):
            events.append(with_detail(item, http.get_text(item.source_url)) if item.source_url else item)
        return events


def parse_listing(html: str) -> list[RawEvent]:
    out, seen = [], set()
    for li in parse_html(html).css("li.eg-music-listings-page-skin3-wrapper"):
        sort = str(li.attrib.get("data-egl-music_hall_sort", ""))
        links = [str(h) for h in li.css("a::attr(href)").getall() if "/music-hall/" in h and h.rstrip("/") != LISTING.rstrip("/")]
        title = li.css(".eg-music-listings-page-skin3-element-0")
        if not (re.fullmatch(r"\d{8}", sort) and links and title) or links[0] in seen:
            continue
        seen.add(links[0])
        time = li.css(".eg-music-listings-page-skin3-element-3")
        out.append(
            RawEvent(
                source="empire",
                source_key=f"empire:{links[0].rstrip('/').rsplit('/', 1)[-1]}",
                source_url=links[0],
                title=recase(title[0].get_all_text(separator=" ").strip()),
                venue_name=VENUE,
                date=f"{sort[:4]}-{sort[4:6]}-{sort[6:]}",
                start_time=parse_time(time[0].get_all_text(separator=" ")) if time else None,
                is_music_hint=True,  # the Music Hall's own gig listing; themed party nights are caught by the rules
            )
        )
    return out


def with_detail(event: RawEvent, html: str) -> RawEvent:
    page = parse_html(html)
    text = re.sub(r"\s+", " ", page.get_all_text(separator=" | "))
    price = re.search(r"£\s?(\d+(?:\.\d{2})?)", text)
    if price:
        event.price_min = float(price[1])
    if re.search(r"\bsold\s*out\b", text, re.I) and not re.search(r"\bbuy tickets\b", text, re.I):
        event.status = "sold_out"
    links = list(dict.fromkeys(str(h) for h in page.css("a::attr(href)").getall() if _TICKETS.search(str(h))))
    event.tickets = [(ticket_provider(u), u) for u in links]
    return event
