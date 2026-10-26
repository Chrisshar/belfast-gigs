"""Weekly coverage check: which gigs on pages you saved yourself (Songkick, Eventbrite) aren't on the site?

`python -m belfast_gigs benchmark benchmark/inbox` reads every saved .html/.htm file, pulls the
events out of their schema.org data, and looks each one up in src/content/gigs with the same
venue aliases and name matching the scraper uses. Nothing is fetched and nothing is published:
the report only shows where coverage is thin.
"""

from __future__ import annotations

import html as htmllib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dates import as_date_str, london_today, parse_time
from .paths import DATA_DIR, GIGS_DIR
from .pipeline.match import MATCH, REVIEW, name_score, norm_act
from .pipeline.write import load_gigs
from .venues import VenueIndex

_LD = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)
_EVENT_TYPES = re.compile(r"Event$")


@dataclass
class Listed:
    name: str
    date: str
    venue: str
    time: str | None
    url: str | None
    file: str


@dataclass
class Result:
    listed: Listed
    verdict: str  # covered | maybe | removed | missing | unknown_venue
    detail: str = ""


def _walk(node: Any):
    if isinstance(node, list):
        for x in node:
            yield from _walk(x)
    elif isinstance(node, dict):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if any(isinstance(t, str) and _EVENT_TYPES.search(t) for t in types):
            yield node
        for key in ("@graph", "itemListElement", "item", "subEvent", "event", "events"):
            if key in node:
                yield from _walk(node[key])


def _venue_name(location: Any) -> str:
    if isinstance(location, list):
        location = location[0] if location else {}
    if isinstance(location, dict):
        return str(location.get("name") or "").strip()
    return str(location or "").strip()


def extract(html: str, file: str = "") -> list[Listed]:
    """Every event in a saved page's schema.org JSON-LD, one per name/date/venue."""
    out: dict[tuple[str, str, str], Listed] = {}
    for block in _LD.findall(html):
        try:
            data = json.loads(htmllib.unescape(block.strip()))
        except json.JSONDecodeError:
            continue
        for ev in _walk(data):
            name = htmllib.unescape(str(ev.get("name") or "")).strip()
            start = str(ev.get("startDate") or "")
            date = as_date_str(start[:10])
            if not (name and date):
                continue
            venue = htmllib.unescape(_venue_name(ev.get("location")))
            # Songkick names its events "Act @ Venue".
            if venue and name.lower().endswith(f" @ {venue.lower()}"):
                name = name[: -len(venue) - 3].strip() or name
            time = parse_time(start[11:16]) if len(start) >= 16 else None
            out.setdefault((name.lower(), date, venue.lower()), Listed(name, date, venue, time, ev.get("url"), file))
    return list(out.values())


def check(inbox: Path, today: str | None = None, gigs_dir: Path = GIGS_DIR, data_dir: Path = DATA_DIR) -> list[Result]:
    today = today or london_today()
    venues = VenueIndex.load()
    gigs = [g for g in load_gigs(gigs_dir).values()]
    facts = [(g, g.facts(venues)) for g in gigs]
    try:
        tombstones = json.loads((data_dir / "tombstones.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        tombstones = []
    listed: dict[tuple[str, str, str], Listed] = {}
    for path in sorted(inbox.glob("*.htm*")):
        for item in extract(path.read_text(encoding="utf-8", errors="replace"), path.name):
            if item.date >= today:
                listed.setdefault((item.name.lower(), item.date, item.venue.lower()), item)

    results = []
    for item in sorted(listed.values(), key=lambda i: (i.date, i.venue, i.name)):
        resolved = venues.resolve(item.venue) if item.venue else None
        group = resolved[0].group_key if resolved else None
        same_day = [(g, f) for g, f in facts if f and f.date <= item.date <= (f.end_date or f.date)]
        candidates = [(g, f) for g, f in same_day if f.group == group] if group else same_day
        best = max(((name_score(item.name, f.headliner), g) for g, f in candidates), key=lambda x: x[0], default=(0.0, None))
        if best[1] is not None and best[0] >= MATCH:
            results.append(Result(item, "covered", best[1].path.name))
            continue
        if best[1] is not None and best[0] >= REVIEW:
            results.append(Result(item, "maybe", f"{best[1].path.name} ({best[0]:.0f})"))
            continue
        fp_tail = f"|{item.date}|{norm_act(item.name)}"
        tomb = next((t for t in tombstones if str(t.get("fingerprint", "")).endswith(fp_tail)), None)
        if tomb:
            results.append(Result(item, "removed", str(tomb.get("reason"))))
        elif not resolved:
            results.append(Result(item, "unknown_venue"))
        else:
            results.append(Result(item, "missing", resolved[0].slug))
    return results


def report(results: list[Result]) -> str:
    counts = {v: sum(r.verdict == v for r in results) for v in ("covered", "maybe", "removed", "missing", "unknown_venue")}
    total = len(results)
    lines = [
        "# Coverage check",
        "",
        f"{total} upcoming events in the saved pages: {counts['covered']} on the site, {counts['maybe']} possible matches, "
        f"{counts['removed']} removed on purpose, {counts['missing']} missing at venues we know, "
        f"{counts['unknown_venue']} at venues we don't.",
    ]

    def section(title: str, verdict: str, show_detail: bool = False) -> None:
        rows = [r for r in results if r.verdict == verdict]
        if not rows:
            return
        lines.extend(["", f"## {title} ({len(rows)})"])
        by_venue: dict[str, list[Result]] = {}
        for r in rows:
            by_venue.setdefault(r.listed.venue or "(no venue)", []).append(r)
        for venue, items in sorted(by_venue.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            lines.append(f"\n### {venue} ({len(items)})")
            for r in items:
                extra = f" — {r.detail}" if show_detail and r.detail else ""
                when = f"{r.listed.date} {r.listed.time}" if r.listed.time else r.listed.date
                lines.append(f"- {when}: {r.listed.name}{extra} [{r.listed.file}]")

    section("Missing at venues we know", "missing")
    section("At venues the site doesn't know", "unknown_venue")
    section("Possible matches: check these are the same gig", "maybe", show_detail=True)
    section("Removed on purpose (not re-added)", "removed", show_detail=True)
    return "\n".join(lines) + "\n"
