"""Venue lookup: map whatever a source calls a venue onto a src/content/venues/<slug>.md entry."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import frontmatter
from .paths import VENUES_DIR
from .text import slugify, squash

BELFAST = (54.5973, -5.9301)
GREATER_BELFAST_KM = 15
_BT_POSTCODE = re.compile(r"\bBT\d{1,2}\s*\d[A-Z]{2}\b", re.I)


@dataclass
class Venue:
    slug: str
    name: str
    aliases: list[str] = field(default_factory=list)
    group: str | None = None
    rooms: list[str] = field(default_factory=list)
    area: str = "Belfast"
    music_only: bool = False
    needs_review: bool = False

    @property
    def group_key(self) -> str:
        return self.group or self.slug


def _key(name: str) -> str:
    """Comparison key: 'The Belfast Empire, Belfast' -> 'belfast empire'."""
    k = squash(name)
    k = re.sub(r"^the ", "", k)
    k = re.sub(r" (belfast|northern ireland|ni|uk)$", "", k)
    k = re.sub(r" (belfast|northern ireland|ni|uk)$", "", k)
    return k.strip()


def km_from_belfast(lat: float, lng: float) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*BELFAST, lat, lng))
    a = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def in_greater_belfast(address: str | None, lat: float | None, lng: float | None) -> bool:
    if lat is not None and lng is not None:
        return km_from_belfast(lat, lng) <= GREATER_BELFAST_KM
    return bool(address and (_BT_POSTCODE.search(address) or re.search(r"\bbelfast\b", address, re.I)))


class VenueIndex:
    def __init__(self, venues: list[Venue], directory: Path = VENUES_DIR):
        self.directory = directory
        self.by_slug = {v.slug: v for v in venues}
        self._names: dict[str, Venue] = {}
        self._rooms: dict[str, tuple[Venue, str]] = {}
        for v in venues:
            self._index(v)
        self.created: list[Venue] = []

    def _index(self, v: Venue) -> None:
        for room in v.rooms:
            self._rooms[_key(room)] = (v, room)
        for name in (v.name, v.slug.replace("-", " "), *v.aliases):
            self._names.setdefault(_key(name), v)

    @classmethod
    def load(cls, directory: Path = VENUES_DIR) -> VenueIndex:
        venues = []
        for path in sorted(directory.glob("*.md")):
            data, _ = frontmatter.read(path)
            venues.append(
                Venue(
                    slug=path.stem,
                    name=data["name"],
                    aliases=data.get("aliases") or [],
                    group=data.get("group"),
                    rooms=data.get("rooms") or [],
                    area=data.get("area") or "Belfast",
                    music_only=bool(data.get("music_only")),
                    needs_review=bool(data.get("needs_review")),
                )
            )
        return cls(venues, directory)

    def resolve(self, name: str, room: str | None = None) -> tuple[Venue, str | None] | None:
        key = _key(name)
        if key in self._rooms:  # e.g. "Limelight 2" is a room of the Limelight
            venue, matched_room = self._rooms[key]
            return venue, room or matched_room
        venue = self._names.get(key)
        return (venue, room) if venue else None

    def create_stub(self, name: str, address: str | None, write: bool) -> Venue:
        """A venue we've never seen, inside greater Belfast: add it, flagged for a human to check."""
        slug = slugify(re.sub(r",.*$", "", name))
        base, n = slug, 2
        while slug in self.by_slug:
            slug, n = f"{base}-{n}", n + 1
        venue = Venue(slug=slug, name=name.split(",")[0].strip(), needs_review=True)
        self.by_slug[slug] = venue
        self._index(venue)
        self.created.append(venue)
        if write:
            data = {"name": venue.name, "aliases": [name] if name != venue.name else [], "area": "Belfast", "needs_review": True}
            if address:
                data["address"] = address
            frontmatter.write(self.directory / f"{slug}.md", data, "Created automatically by the scraper. Check the details and add aliases.\n")
        return venue
