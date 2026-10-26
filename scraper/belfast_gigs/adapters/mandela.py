"""Queen's Students' Union venues (Mandela Hall, the Union Bar): the SU's Glistrr box office page,
plus mandelahall.com for shows that outside promoters sell through their own ticketing.

glistrr.com/events/l/qub embeds every event the SU sells as a JSON array (`var events = [...]`),
with categories, prices, sold-out status and ages, so the array is read directly.
mandelahall.com is a Wix site: its event pages (found through the sitemap) carry a line like
"Thursday | 5 Nov 2026 | 19:00 | DOORS: | SOLD OUT | TICKETS | £22". "SOLD OUT" is part of the
page template and shows on every event, so it's ignored. Shows on both are merged downstream.
The two are separate adapters: MandelaHall (Glistrr) and MandelaHallWeb (mandelahall.com).
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from ..dates import to_london
from ..http import Http, parse_html
from ..models import RawEvent
from ..text import recase
from .base import Adapter
from .wix import event_urls

PAGE = "https://glistrr.com/events/l/qub"
TICKETS = "https://www.glistrr.com/events/e/{slug}"
VENUES = {"union bar": "The Union Bar"}  # anything else is Mandela Hall
SITE = "https://www.mandelahall.com"
RECENT_PAGES = 40
_WIX_LINE = re.compile(r"\| (?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) \| (\d{1,2} [A-Za-z]{3} \d{4}) \| (\d{1,2}:\d{2})(.*?)< BACK \| ([^|]+)")


class MandelaHall(Adapter):
    name = "mandela"
    authority = 1
    licence = "QUB Students' Union's public box office page on glistrr.com; robots.txt allows it."

    def fetch(self, http: Http) -> list[RawEvent]:
        return parse(http.get_text(PAGE))


class MandelaHallWeb(Adapter):
    """A source of its own, so it has its own health record and its first run counts as backfill."""

    name = "mandelaweb"
    authority = 1
    licence = "Public pages on mandelahall.com; robots.txt allows them."

    def fetch(self, http: Http) -> list[RawEvent]:
        events = [parse_wix_event(url, http.get_text(url)) for url in event_urls(http, SITE, RECENT_PAGES)]
        return [e for e in events if e]


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


def parse_wix_event(url: str, html: str) -> RawEvent | None:
    text = re.sub(r"\s+", " ", parse_html(html).get_all_text(separator=" | ")).replace("​", "")
    m = _WIX_LINE.search(text)
    if not m:
        return None
    try:
        date = datetime.strptime(m[1], "%d %b %Y").date().isoformat()
    except ValueError:
        return None
    prices = [float(p) for p in re.findall(r"£\s?(\d+(?:\.\d{1,2})?)", m[3])]
    return RawEvent(
        source="mandelaweb",
        source_key=f"mandelaweb:{url.rstrip('/').rsplit('/', 1)[-1]}",
        source_url=url,
        title=recase(m[4].strip()),
        venue_name="Mandela Hall",
        date=date,
        start_time=m[2].zfill(5),
        price_min=min(prices) if prices else None,
        price_max=max(prices) if len(set(prices)) > 1 else None,
        tickets=[("Mandela Hall", url)],
        is_music_hint=None,  # gigs, comedy and quizzes share the listing
    )
