"""Turn a source's RawEvent into a Prepared event: venue resolved, title cleaned, acts split."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import RawEvent, Status
from ..venues import Venue, VenueIndex, in_greater_belfast

_STATUS_WORDS: list[tuple[re.Pattern, Status]] = [
    (re.compile(r"\bsold[\s-]*out\b", re.I), "sold_out"),
    (re.compile(r"\bcancell?ed\b", re.I), "cancelled"),
    (re.compile(r"\bpostponed\b", re.I), "postponed"),
    (re.compile(r"\b(rescheduled|new date|date changed?|moved to)\b", re.I), "rescheduled"),
]
# A status word with whatever wraps it: "(SOLD OUT)", "- SOLD OUT", "**CANCELLED**", "SOLD OUT:".
_STATUS_CHUNK = re.compile(
    r"[\s\-–—:|*(\[]*\b(sold[\s-]*out|cancell?ed|postponed|rescheduled|new date|date changed?)\b[^\w(]*?[)\]*!:]*",
    re.I,
)
_LEAD_IN = re.compile(r"^(an evening with|a night with|in conversation with|.{0,40}\bpresents?:?)\s+", re.I)
_SUPPORT_SPLIT = re.compile(r"\s+(?:\+|w/|with special guests?|supported by|support from|plus special guests?)\s+", re.I)
_GUESTS = re.compile(r"(very )?(special )?guests?|support|tba|tbc", re.I)
_HEADLINE_END =re.compile(r"\s+[-–—|]\s+|:\s+|\s+\(")
_PASS = re.compile(r"\b(weekend|day|season|festival|camping)\s+(pass|ticket)s?\b", re.I)


@dataclass
class Prepared:
    raw: RawEvent
    venue: Venue
    room: str | None
    title: str
    headliner: str
    support: list[str]
    status: Status
    notes: list[str] = field(default_factory=list)

    @property
    def group(self) -> str:
        return self.venue.group_key

    @property
    def time(self) -> str | None:
        return self.raw.start_time or self.raw.doors_time


def clean_title(title: str) -> tuple[str, Status | None]:
    status = next((s for pat, s in _STATUS_WORDS if pat.search(title)), None)
    cleaned = _STATUS_CHUNK.sub(" ", title) if status else title
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -–—:|*")
    return cleaned or title.strip(), status


def split_acts(title: str) -> tuple[str, list[str]]:
    """'An Evening With Ash + Pillow Queens' -> ('Ash', ['Pillow Queens'])."""
    t = _LEAD_IN.sub("", title).strip()
    parts = _SUPPORT_SPLIT.split(t)
    head = parts[0]
    support = [p.strip() for p in parts[1:] if p.strip() and not _GUESTS.fullmatch(p.strip())]
    head = _HEADLINE_END.split(head, maxsplit=1)[0].strip()
    return head or title, support


def is_pass(title: str) -> bool:
    return bool(_PASS.search(title))


def prepare(raw: RawEvent, venues: VenueIndex, *, create_stubs: bool, write_stubs: bool) -> Prepared | None:
    """None means the venue is outside greater Belfast (or unknown with no location to check)."""
    resolved = venues.resolve(raw.venue_name, raw.room)
    if resolved is None:
        if not create_stubs or not in_greater_belfast(raw.address, raw.lat, raw.lng):
            return None
        resolved = venues.create_stub(raw.venue_name, raw.address, write=write_stubs), raw.room
    venue, room = resolved
    title, status_from_title = clean_title(raw.title)
    if raw.headliner:
        headliner, support = clean_title(raw.headliner)[0], list(raw.support)
    else:
        headliner, title_support = split_acts(title)
        support = list(raw.support) or title_support
    status: Status = raw.status if raw.status != "on_sale" else (status_from_title or "on_sale")
    return Prepared(raw=raw, venue=venue, room=room, title=title, headliner=headliner, support=support, status=status)
