"""Ulster Hall and Waterfront Hall (Belfast City Council venues) from the shared what's-on listing.

ulsterhall.co.uk/what-s-on/page/N/ lists both halls. Each card carries the venue and the genre as
classes, the date as text and a sold-out flag. Event pages give no start time (and the price only
in schema.org data), so the listing alone is used; tickets are the event page itself.
robots.txt disallows the filtered /what-s-on/results/ URLs, so pages are walked and filtered here.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..http import Http, HttpError, parse_html
from ..models import RawEvent
from .base import Adapter

PAGE = "https://www.ulsterhall.co.uk/what-s-on/page/{n}/"
MAX_PAGES = 40
VENUES = {
    "ulsterHall": ("Ulster Hall", None),
    "waterfrontHall": ("Waterfront Hall", "Main Auditorium"),
    "waterfrontStudio": ("Waterfront Hall", "Studio"),
}
NOT_MUSIC = {"comedy", "theatre", "family", "sport", "dance", "an-audience-with", "talks", "film", "spoken-word"}


class UlsterHall(Adapter):
    name = "ulsterhall"
    authority = 1
    licence = "Public listing on ulsterhall.co.uk; robots.txt allows /what-s-on/page/N/."

    def fetch(self, http: Http) -> list[RawEvent]:
        events, n = [], 1
        while n <= MAX_PAGES:
            try:
                page = parse_page(http.get_text(PAGE.format(n=n)))
            except HttpError as e:
                if e.status == 404 and n > 1:  # walked past the last page
                    break
                raise
            if not page:
                break
            events.extend(page)
            n += 1
        return events


def _date(text: str) -> str | None:
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m[1]} {m[2][:3]} {m[3]}", "%d %b %Y").date().isoformat()
    except ValueError:
        return None


def parse_page(html: str) -> list[RawEvent]:
    out = []
    for slot in parse_html(html).css("a.slot"):
        href = str(slot.attrib.get("href", ""))
        title_el = slot.css("h3")
        date_el = slot.css("p.date")
        venue_el = slot.css("span.venue")
        if not (href and title_el and date_el and venue_el):
            continue
        date = _date(date_el[0].get_all_text(separator=" "))
        venue_class = next((c for c in str(venue_el[0].attrib.get("class", "")).split() if c in VENUES), None)
        if not date or not venue_class:
            continue
        venue, room = VENUES[venue_class]
        genre_el = slot.css("span.genre")
        genres = [c for c in str(genre_el[0].attrib.get("class", "")).split() if c != "genre"] if genre_el else []
        status_el = slot.css("span.slot__status")
        sold_out = bool(status_el) and "-sold-out" in str(status_el[0].attrib.get("class", ""))
        if "music" in genres:
            hint: bool | None = True
        elif set(genres) & NOT_MUSIC:
            hint = False
        else:
            hint = None
        out.append(
            RawEvent(
                source="ulsterhall",
                source_key=f"ulsterhall:{href.rstrip('/').rsplit('/', 1)[-1]}",
                source_url=href,
                title=title_el[0].get_all_text(separator=" ").strip(),
                venue_name=venue,
                room=room,
                date=date,
                status="sold_out" if sold_out else "on_sale",
                tickets=[("Box office", href)],
                categories=genres,
                is_music_hint=hint,
            )
        )
    return out
