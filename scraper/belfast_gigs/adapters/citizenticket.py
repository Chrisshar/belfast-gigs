"""Citizen Ticket, for chosen organisers: event pages found through the site's sitemap.

Organiser pages load their event list with JavaScript, but every event page is in sitemap.xml
and is plain HTML. The pages' schema.org data gives the wrong date (the same one for every event),
so the date, time and price come from the visible text instead.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..dates import parse_time
from ..http import Http, parse_html
from ..models import RawEvent
from .base import Adapter

SITE = "https://www.citizenticket.com"
# Organiser slug -> prefix to strip from titles for the headliner. Add organisers here.
ORGANISERS = {
    "dock-street-jazz-club": re.compile(r"^dock street jazz club\s*[:\-–]\s*", re.I),
}
_DATE = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*\|\s*"
    r"(\d{1,2}(?::\d{2})?\s*[ap]m)(?:\s*(?:&hyphen;|-|–)\s*(\d{1,2}(?::\d{2})?\s*[ap]m))?\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
    re.I,
)
_PRICE = re.compile(r"£(\d+(?:\.\d{2})?)\s*\+\s*£[\d.]+\s*booking fee", re.I)
_COUNTRY = re.compile(r"\s*\((?:US|UK|IE|CA|FR|DE|NL|IT|ES|NZ|AU|NO|SE|DK|BE|PL|ROI|NI)\)", re.I)


class CitizenTicket(Adapter):
    name = "citizenticket"
    authority = 3
    licence = "Public event pages on citizenticket.com; robots.txt only disallows /ajax."

    def fetch(self, http: Http) -> list[RawEvent]:
        sitemap = http.get_text(f"{SITE}/sitemap.xml")
        events = []
        for url in event_urls(sitemap):
            event = parse_event(url, http.get_text(url))
            if event:
                events.append(event)
        return events


def event_urls(sitemap: str) -> list[str]:
    urls = re.findall(r"<loc>([^<]+)</loc>", sitemap)
    return [u for u in urls if any(f"/events/{org}/" in u for org in ORGANISERS)]


def parse_event(url: str, html: str) -> RawEvent | None:
    org = re.search(r"/events/([^/]+)/", url)[1]
    page = parse_html(html)
    text = re.sub(r"\s+", " ", page.get_all_text(separator=" | "))
    m = _DATE.search(text)
    if not m:
        return None
    day, month, year, start, _end, venue, address = m.groups()
    try:
        date = datetime.strptime(f"{day} {month[:3]} {year}", "%d %b %Y").date().isoformat()
    except ValueError:
        return None
    titles = page.css("title")
    title = re.sub(r"\s*-\s*Buy tickets.*$", "", titles[0].get_all_text().strip()) if titles else ""
    if not title:
        return None
    headliner = _COUNTRY.sub("", ORGANISERS[org].sub("", title)).strip()
    price = _PRICE.search(text)
    sold_out = "sold out" in text.lower() and "buy tickets" not in text.lower()
    return RawEvent(
        source="citizenticket",
        source_key=f"citizenticket:{url.rstrip('/').rsplit('/', 2)[-2]}/{url.rstrip('/').rsplit('/', 1)[-1]}",
        source_url=url,
        title=title,
        headliner=headliner or title,
        venue_name=venue.strip(),
        address=address.strip(),
        date=date,
        start_time=parse_time(start),
        price_min=float(price[1]) if price else None,
        status="sold_out" if sold_out else "on_sale",
        tickets=[("Citizen Ticket", url)],
        categories=["jazz"] if "jazz" in org else [],
        is_music_hint=True,
    )
