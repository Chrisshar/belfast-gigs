"""The Belfast Empire Music Hall: the /music-hall/ listing plus each gig's page for price and tickets.

The listing is static HTML (an Essential Grid that pages itself in the browser), with a sortable
date attribute on each item. The gig page adds the price and the Ticketmaster link.

The grid only draws its first gigs; the rest wait behind a "Load More" button, and the page lists
their post IDs in its script (`loadMoreItems`). Each of those IDs opens its gig page at /?p=<id>,
which carries the date as "Wed 16 Dec | 7.30PM" (no year, so the weekday settles it).
"""

from __future__ import annotations

import re

from ..dates import infer_date, london_today, parse_time
from ..http import Http, parse_html
from ..models import RawEvent
from ..text import recase, ticket_provider
from .base import Adapter

SITE = "https://www.thebelfastempire.com"
LISTING = f"{SITE}/music-hall/"
VENUE = "The Belfast Empire Music Hall"
_TICKETS = re.compile(r"ticketmaster|eventbrite|skiddle|seetickets|ticketsolve|citizenticket|dice\.fm|fixr|tickettailor|ticketsource", re.I)


class Empire(Adapter):
    name = "empire"
    authority = 1
    licence = "Public pages on thebelfastempire.com; robots.txt only disallows /opt-in-thank-you/."

    def fetch(self, http: Http) -> list[RawEvent]:
        html = http.get_text(LISTING)
        events = []
        for item in parse_listing(html):
            events.append(with_detail(item, http.get_text(item.source_url)) if item.source_url else item)
        today = london_today()
        # The first time the hidden gigs are read they are old listings found late, not news.
        known = self.cache.get("hidden_ids")  # None until the first run that reads them
        ids = hidden_ids(html)
        for post_id in ids:
            found = parse_gig_page(http.get_text(f"{SITE}/?p={post_id}"), today)
            if found and found.date >= today:
                found.backfill = known is None
                events.append(found)
        self.cache["hidden_ids"] = ids
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


def hidden_ids(html: str) -> list[str]:
    """Post IDs of the gigs behind "Load More": in the script's list, but not drawn in the grid."""
    start = html.find("loadMoreItems:")
    end = html.find("row:", start)
    wanted = list(dict.fromkeys(re.findall(r"\[\s*(\d{3,7})\s*,\s*\[", html[start:end] if start >= 0 and end > start else "")))
    drawn = set(re.findall(r"eg-post-id-(\d+)", html))
    return [i for i in wanted if i not in drawn]


_GIG_LINE = re.compile(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (\d{1,2}) ([A-Za-z]{3}) \| (\d{1,2}(?:[.:]\d{2})?\s?[AP]M)?", re.I)


def parse_gig_page(html: str, today: str) -> RawEvent | None:
    page = parse_html(html)
    url = str(page.css("link[rel=canonical]::attr(href)").get() or "")
    text = re.sub(r"\s+", " ", page.get_all_text(separator=" | "))
    text = text.split("Share This Event")[0]  # past it is the "Upcoming Events" strip
    m = _GIG_LINE.search(text)
    if not (url and m):
        return None
    date = infer_date(int(m[2]), m[3], today, m[1])
    if not date:
        return None
    event = RawEvent(
        source="empire",
        source_key=f"empire:{url.rstrip('/').rsplit('/', 1)[-1]}",
        source_url=url,
        title=recase(page.css("title")[0].get_all_text().split("|")[0].strip()),
        venue_name=VENUE,
        date=date,
        start_time=parse_time(m[4]) if m[4] else None,
        is_music_hint=True,
    )
    return with_detail(event, html)


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
