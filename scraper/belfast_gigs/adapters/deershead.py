"""The Deer's Head Music Hall (Lower Garfield Street) from its /music-hall/ listing.

Each event block has the title, a date with no year ("28th October"), a time and a price, plus
an Eventbrite ticket link. The year is the next one that date falls on.
"""

from __future__ import annotations

import re

from ..dates import infer_date, london_today, parse_time
from ..http import Http, parse_html
from ..models import RawEvent
from ..text import clean_url, recase, ticket_provider
from .base import Adapter

PAGE = "https://www.thedeersheadbelfast.com/music-hall/"
VENUE = "The Deer's Head"


class DeersHead(Adapter):
    name = "deershead"
    authority = 1
    licence = "Public listing on thedeersheadbelfast.com; robots.txt allows /music-hall/."

    def fetch(self, http: Http) -> list[RawEvent]:
        return parse(http.get_text(PAGE), london_today())


def parse(html: str, today: str) -> list[RawEvent]:
    out = []
    for block in parse_html(html).css(".parent-event"):
        title = block.css("a.title")
        date_el = block.css(".date-block .date span")
        if not (title and date_el):
            continue
        m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)", date_el[0].get_all_text(separator=" "))
        date = infer_date(int(m[1]), m[2], today) if m else None
        if not date:
            continue
        url = str(title[0].attrib.get("href", ""))
        text = re.sub(r"\s+", " ", block.get_all_text(separator=" | "))
        after_date = text.split(m[0], 1)[-1]
        price = re.search(r"Tickets \| £?\s?(\d+(?:\.\d{1,2})?)", after_date)
        links = [str(h) for h in block.css("a::attr(href)").getall() if "thedeersheadbelfast.com" not in str(h)]
        out.append(
            RawEvent(
                source="deershead",
                source_key=f"deershead:{url.rstrip('/').rsplit('/', 1)[-1]}",
                source_url=url,
                title=recase(title[0].get_all_text(separator=" ").strip()),
                venue_name=VENUE,
                date=date,
                start_time=parse_time(after_date.split("|", 2)[1] if after_date.count("|") >= 2 else after_date),
                price_min=float(price[1]) or None if price else None,
                free=bool(price) and float(price[1]) == 0,
                tickets=[(ticket_provider(u), clean_url(u)) for u in dict.fromkeys(links)],
                is_music_hint=True,  # the Music Hall's gig listing; themed party nights are left to the rules
            )
        )
    return out
