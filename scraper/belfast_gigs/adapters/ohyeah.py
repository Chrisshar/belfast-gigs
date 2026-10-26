"""Oh Yeah Music Centre (Gordon Street) from its Squarespace events page.

One page lists every upcoming event with title, date, times, categories and, for events held
elsewhere, the venue. robots.txt disallows the ?format=json/ical exports, so the HTML is read.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from ..dates import parse_time
from ..http import Http, parse_html
from ..models import RawEvent
from .base import Adapter

BASE = "https://www.ohyeahbelfast.com"
PAGE = f"{BASE}/events"
VENUE = "Oh Yeah Music Centre"
NOT_MUSIC = {"fairs & exhibitions", "workshops", "club nights", "talks", "tours", "film", "courses", "networking"}


class OhYeah(Adapter):
    name = "ohyeah"
    authority = 1
    licence = "Public events page on ohyeahbelfast.com; robots.txt only disallows the ?format= exports."

    def fetch(self, http: Http) -> list[RawEvent]:
        return parse(http.get_text(PAGE))


def parse(html: str) -> list[RawEvent]:
    out = []
    for art in parse_html(html).css("article.eventlist-event--upcoming"):
        link = art.css("a.eventlist-title-link")
        dates = art.css("time.event-date::attr(datetime)").getall()
        if not (link and dates):
            continue
        href = str(link[0].attrib.get("href", ""))
        url = href if href.startswith("http") else BASE + href
        cats = [c.strip().lower() for c in art.css(".eventlist-cats a::text").getall()]
        start = art.css("time.event-time-localized-start::text, time.event-time-localized::text").getall()
        end = str(dates[-1])
        # An event that runs past midnight is one night, not a multi-day event.
        multi_day = end > str(dates[0]) and not (start and len(start) > 1 and (parse_time(str(start[-1])) or "") < "06:00")
        address = art.css(".eventlist-meta-address")
        place = re.sub(r"\(map\)", "", address[0].get_all_text(separator=" ")).strip() if address else ""
        maps = address[0].css("a::attr(href)").getall() if address else []
        street = parse_qs(urlsplit(str(maps[0])).query).get("q", [""])[0] if maps else ""
        other = set(cats) & NOT_MUSIC
        if "live music" in cats:
            hint: bool | None = None if other else True  # a walking tour with a short set: let Claude judge
        else:
            hint = False if other else None
        out.append(
            RawEvent(
                source="ohyeah",
                source_key=f"ohyeah:{href.rstrip('/').rsplit('/', 1)[-1]}",
                source_url=url,
                title=link[0].get_all_text(separator=" ").strip(),
                venue_name=place if place and "oh yeah" not in place.lower() else VENUE,
                date=str(dates[0]),
                end_date=end if multi_day else None,
                start_time=parse_time(str(start[0])) if start else None,
                address=street or None,
                tickets=[("Oh Yeah", url)],
                categories=cats,
                is_music_hint=hint,
            )
        )
    return out
