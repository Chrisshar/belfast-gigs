"""Crescent Arts Centre (University Road) from its Events & Live Gigs page.

Each card is schema.org Event markup: title, start date and time, price, and a category label
("gig", "trad session", "late night art", ...). Gigs and trad sessions are music; art nights and
celebrations are not; festival cards are left to the rules and Claude.
"""

from __future__ import annotations

from ..http import Http, parse_html
from ..models import RawEvent
from ..text import recase
from .base import Adapter

SITE = "https://www.crescentarts.org"
PAGE = f"{SITE}/events"
VENUE = "Crescent Arts Centre"
MUSIC = {"gig", "trad session"}
NOT_MUSIC = {"late night art", "celebration", "course", "workshop", "exhibition"}


class Crescent(Adapter):
    name = "crescent"
    authority = 1
    licence = "Public events page on crescentarts.org; robots.txt allows it."

    def fetch(self, http: Http) -> list[RawEvent]:
        return parse(http.get_text(PAGE))


def _meta(card, prop: str) -> str:
    found = card.css(f"meta[itemprop={prop}]::attr(content)").get()
    return str(found).strip() if found else ""


def parse(html: str) -> list[RawEvent]:
    out = []
    for card in parse_html(html).css("article[itemtype*=Event]"):
        title_el = card.css("[itemprop=name]")
        start = _meta(card, "startDate")
        path = _meta(card, "url")
        if not (title_el and len(start) >= 16 and path):
            continue
        title = title_el[0].get_all_text(separator=" ").strip()
        cat_el = card.css("a.catLink")
        category = cat_el[0].get_all_text(separator=" ").strip().lower() if cat_el else ""
        price_el = card.css("[itemprop=price]")
        try:
            price = float(price_el[0].get_all_text().strip()) if price_el else None
        except ValueError:
            price = None
        footer = card.css(".card-footer")[0].get_all_text(separator=" ") if card.css(".card-footer") else ""
        url = path if path.startswith("http") else SITE + path
        hint = True if category in MUSIC else False if category in NOT_MUSIC else None
        out.append(
            RawEvent(
                source="crescent",
                source_key=f"crescent:{path.rstrip('/').rsplit('/', 1)[-1]}",
                source_url=url,
                title=recase(title),
                venue_name=VENUE,
                date=start[:10],
                start_time=start[11:16],
                price_min=price or None,
                status="sold_out" if "sold out" in footer.lower() or "fully booked" in footer.lower() else "on_sale",
                tickets=[("Crescent Arts Centre", url)],
                categories=[category] if category else [],
                is_music_hint=hint,
            )
        )
    return out
