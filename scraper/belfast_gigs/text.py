"""Small text helpers shared by venue matching, title cleanup and fuzzy matching."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def fold(s: str) -> str:
    """Lower-case, strip accents, unify apostrophes and dashes."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower().replace("&", " and ")


def squash(s: str) -> str:
    """fold() then keep only letters/digits separated by single spaces."""
    return re.sub(r"[^a-z0-9]+", " ", fold(s).replace("'", "")).strip()


def slugify(s: str, max_len: int = 60) -> str:
    slug = squash(s).replace(" ", "-")
    return slug[:max_len].rstrip("-") or "untitled"


_PROVIDERS = {
    "ticketmaster": "Ticketmaster",
    "shine.tickets": "Shine",
    "glistrr": "Glistrr",
    "eventbrite": "Eventbrite",
    "skiddle": "Skiddle",
    "seetickets": "See Tickets",
    "ticketsolve": "Ticketsolve",
    "ticketsource": "TicketSource",
    "citizenticket": "Citizen Ticket",
    "wegottickets": "WeGotTickets",
    "dice.fm": "DICE",
    "fixr": "Fixr",
    "tickettailor": "Ticket Tailor",
    "waterfront.co.uk": "Waterfront box office",
    "theo2belfast": "The O2 Belfast",
}


_TRACKING = re.compile(r"^(_ga|_gl|utm_\w+|queueittoken|fbclid|gclid|mc_\w+)$", re.I)


def clean_url(url: str) -> str:
    """Drop analytics and queue tokens: they're per-visitor, change every run, and leak session data."""
    parts = urlsplit(str(url).strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING.match(k)]
    return urlunsplit(parts._replace(query=urlencode(query)))


def ticket_provider(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    for needle, name in _PROVIDERS.items():
        if needle in host:
            return name
    return host.removeprefix("www.") or "Tickets"
