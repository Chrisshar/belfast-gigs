"""The Black Box (Hill Street) from its paged event listing.

Each card links to its category. Live music is kept as music; comedy, film, DJs, visual arts and
theatre are marked non-music; anything else (open mics under "Black Box Originals", festival
nights) is left to the rules and Claude. Every page repeats a strip of featured events, so cards
are de-duplicated by URL.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..dates import parse_time
from ..http import Http, HttpError, parse_html
from ..models import RawEvent
from .base import Adapter

PAGE = "https://www.blackboxbelfast.com/event/page/{n}/"
MAX_PAGES = 20
VENUE = "Black Box"
NOT_MUSIC = {"comedy", "film", "djs", "visual-arts", "theatre-spoken-word-science"}


class BlackBox(Adapter):
    name = "blackbox"
    authority = 1
    licence = "Public listing on blackboxbelfast.com; robots.txt allows /event/."

    def fetch(self, http: Http) -> list[RawEvent]:
        events: dict[str, RawEvent] = {}
        for n in range(1, MAX_PAGES + 1):
            try:
                page = parse_page(http.get_text(PAGE.format(n=n)))
            except HttpError as e:
                if e.status == 404 and n > 1:  # walked past the last page
                    break
                raise
            new = [e for e in page if e.source_key not in events]
            if not new:
                break
            events.update((e.source_key, e) for e in new)
        return list(events.values())


def _prices(text: str) -> list[float]:
    return [float(p) for p in re.findall(r"£\s?(\d+(?:\.\d{1,2})?)", text)]


def parse_page(html: str) -> list[RawEvent]:
    out = []
    for card in parse_html(html).css("article.card-event"):
        hrefs = [str(h) for h in card.css("a::attr(href)").getall()]
        url = next((h for h in hrefs if "/event/" in h), None)
        cats = [h.rstrip("/").rsplit("/", 1)[-1] for h in hrefs if "/events-categories/" in h]
        title = card.css("p.h4")
        smalls = [re.sub(r"\s+", " ", s.get_all_text(separator=" ")).strip() for s in card.css("small")]
        m = re.match(r"(\d{1,2}) ([A-Za-z]+),? (\d{4})(?:\s*@\s*(\S+))?", smalls[0]) if smalls else None
        if not (url and title and m):
            continue
        try:
            date = datetime.strptime(f"{m[1]} {m[2][:3]} {m[3]}", "%d %b %Y").date().isoformat()
        except ValueError:
            continue
        price_room = smalls[1] if len(smalls) > 1 else ""
        prices = _prices(price_room)
        room = "Green Room" if "green room" in price_room.lower() and "black box" not in price_room.lower() else None
        if "live-music" in cats:
            hint: bool | None = True
        elif set(cats) & NOT_MUSIC:
            hint = False
        else:
            hint = None
        out.append(
            RawEvent(
                source="blackbox",
                source_key=f"blackbox:{url.rstrip('/').rsplit('/', 1)[-1]}",
                source_url=url,
                title=title[0].get_all_text(separator=" ").strip(),
                venue_name=VENUE,
                room=room,
                date=date,
                start_time=parse_time(m[4]) if m[4] else None,
                price_min=min(prices) if prices else None,
                price_max=max(prices) if len(set(prices)) > 1 else None,
                free=not prices and price_room.lower().startswith("free"),
                tickets=[("Black Box", url)],
                categories=cats,
                is_music_hint=hint,
            )
        )
    return out
