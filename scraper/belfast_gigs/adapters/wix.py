"""Shared by venue sites built on Wix (Voodoo, Mandela Hall): event pages are found through the
site's dynamic-events sitemap, which lists every event the site has ever had, past ones included.

Each page is read once and again only when its lastmod changes. What it said is kept in the
adapter's page cache (data/page_cache.json), so every upcoming event is reported on every run,
however long ago its page was edited. Pages are read newest first, at most MAX_FETCH a run; the
rest wait for the next run. Pages not edited for MAX_AGE_DAYS are taken to be past events.
"""

from __future__ import annotations

import html
import re
from dataclasses import asdict
from datetime import date, timedelta
from typing import Callable

from ..http import Http, HttpError
from ..models import RawEvent

MAX_FETCH = 100
MAX_AGE_DAYS = 365
# A page first read when it was last edited this long ago is an old listing found late, not news.
LATE_DAYS = 14


def events(
    http: Http,
    site: str,
    cache: dict[str, dict],
    parse: Callable[[str, str], RawEvent | None],
    today: date | None = None,
) -> list[RawEvent]:
    """Every upcoming event on the site. `cache` (page URL -> {"lastmod", "event"}) is updated in place."""
    today = today or date.today()
    index = http.get_text(f"{site}/sitemap.xml")
    events_map = next((u for u in re.findall(r"<loc>([^<]+)</loc>", index) if "dynamic-events" in u), None)
    if not events_map:
        return []
    oldest = (today - timedelta(days=MAX_AGE_DAYS)).isoformat()
    pages = [(u, m) for u, m in sitemap_entries(http.get_text(events_map)) if not m or m[:10] >= oldest]
    fresh: dict[str, dict] = {}
    found_late: set[str] = set()
    budget = MAX_FETCH
    for url, lastmod in pages:  # newest first
        hit = cache.get(url)
        if hit and hit.get("lastmod") == lastmod:
            fresh[url] = hit
        elif budget:
            budget -= 1
            try:
                event = parse(url, http.get_text(url))
            except HttpError as exc:
                if exc.status != 404:
                    raise
                event = None  # listed but gone: not read again unless the sitemap says it changed
            fresh[url] = {"lastmod": lastmod, "event": asdict(event) if event else None}
            if not hit and lastmod[:10] < (today - timedelta(days=LATE_DAYS)).isoformat():
                found_late.add(url)
        elif hit:
            fresh[url] = hit  # changed, but over this run's budget: keep the old version for now
    for entry in fresh.values():  # forget what past events said; their pages need no rereading
        if entry["event"] and (entry["event"]["end_date"] or entry["event"]["date"]) < today.isoformat():
            entry["event"] = None
    cache.clear()
    cache.update(fresh)
    out = []
    for url, entry in fresh.items():
        if entry["event"]:
            event = RawEvent(**{**entry["event"], "tickets": [tuple(t) for t in entry["event"]["tickets"]]})
            event.backfill = url in found_late
            out.append(event)
    return out


def sitemap_entries(sitemap: str) -> list[tuple[str, str]]:
    """(URL, lastmod) for each event page, most recently edited first."""
    entries = re.findall(r"<url>\s*<loc>([^<]+)</loc>(?:\s*<lastmod>([^<]+)</lastmod>)?", sitemap)
    entries = [(html.unescape(u), m) for u, m in entries if "/events/" in u]
    entries.sort(key=lambda e: e[1], reverse=True)
    return entries
