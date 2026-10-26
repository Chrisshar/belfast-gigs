"""Shared by venue sites built on Wix (Voodoo, Mandela Hall): event pages are found through the
site's dynamic-events sitemap, which lists past events too, so only the most recently edited
pages are fetched."""

from __future__ import annotations

import re

from ..http import Http


def event_urls(http: Http, site: str, limit: int) -> list[str]:
    index = http.get_text(f"{site}/sitemap.xml")
    events_map = next((u for u in re.findall(r"<loc>([^<]+)</loc>", index) if "dynamic-events" in u), None)
    return recent_event_urls(http.get_text(events_map), limit) if events_map else []


def recent_event_urls(sitemap: str, limit: int) -> list[str]:
    entries = re.findall(r"<url>\s*<loc>([^<]+)</loc>(?:\s*<lastmod>([^<]+)</lastmod>)?", sitemap)
    entries = [(u, m) for u, m in entries if "/events/" in u]
    entries.sort(key=lambda e: e[1], reverse=True)
    return [u for u, _ in entries[:limit]]
