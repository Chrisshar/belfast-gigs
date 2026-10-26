"""Apply this run's gigs to src/content/gigs.

Identity: a scraped gig finds its file by source key first (Ticketmaster id, venue event id), then by
fuzzy match within the venue group and date. Files are never renamed, so a rescheduled gig keeps its
slug, id and first_seen.

Human edits win: if a field's current value differs from what the scraper last wrote
(data/snapshots.json), a human changed it, so it goes into locked_fields and is left alone.
A future gig whose file has disappeared was deleted by a human and is tombstoned, never re-added.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import frontmatter
from ..dates import iso_utc, london_today
from ..models import KEY_ORDER, SCRAPED_LISTS, SCRAPED_SCALARS
from ..state import State
from ..text import slugify
from ..venues import VenueIndex
from .match import MATCH, REVIEW, Facts, norm_act, score
from .merge import Candidate

MAX_DELETIONS = 5  # more apparent human deletions than this in one run smells like a broken checkout
REVIEW_AFTER_MISSES = 4
REMOVE_AFTER_MISSES = 8
# needs_review is scraper-set but human-cleared, so it behaves like a scalar for locking.
LOCKABLE = (*SCRAPED_SCALARS, "needs_review")


@dataclass
class GigFile:
    path: Path
    data: dict[str, Any]
    body: str

    @property
    def id(self) -> str:
        return str(self.data.get("id", ""))

    def facts(self, venues: VenueIndex) -> Facts | None:
        venue = venues.by_slug.get(str(self.data.get("venue")))
        if not venue or not self.data.get("date"):
            return None
        return Facts(
            venue.group_key,
            str(self.data["date"]),
            _s(self.data.get("end_date")),
            _s(self.data.get("room")),
            _s(self.data.get("start_time") or self.data.get("doors_time")),
            str(self.data.get("headliner") or self.data.get("title") or ""),
        )


@dataclass
class Changes:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: int = 0
    pruned: list[str] = field(default_factory=list)
    vanished: list[str] = field(default_factory=list)
    reclassified: list[str] = field(default_factory=list)  # removed: now judged not to be a gig
    flagged_missing: list[str] = field(default_factory=list)
    human_deleted: list[str] = field(default_factory=list)
    suppressed: list[str] = field(default_factory=list)  # tombstoned, so not re-added
    newly_locked: list[str] = field(default_factory=list)
    review: list[str] = field(default_factory=list)
    deletion_valve_tripped: bool = False


def _s(v: Any) -> str | None:
    return None if v in (None, "") else str(v)


def _empty(v: Any) -> bool:
    return v in (None, "", [], False, {})


def _norm(v: Any) -> Any:
    """Compare values the way a human would: formatting-only differences are not edits."""
    if _empty(v):
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if hasattr(v, "isoformat"):  # YAML hands back unquoted dates as date objects
        return v.isoformat()
    if isinstance(v, (list, dict)):
        return json.dumps(v, sort_keys=True, default=str)
    return str(v).strip()


def _ordered(data: dict[str, Any]) -> dict[str, Any]:
    """Fixed key order, and no empty optional values (the CMS omits them too)."""
    out = {k: data[k] for k in KEY_ORDER if k in data and not _empty(data[k])}
    out.update({k: v for k, v in data.items() if k not in out and k not in KEY_ORDER and not _empty(v)})
    return out


def load_gigs(gigs_dir: Path) -> dict[str, GigFile]:
    gigs = {}
    for path in sorted(gigs_dir.glob("*.md")):
        data, body = frontmatter.read(path)
        if data.get("id"):
            gigs[str(data["id"])] = GigFile(path, data, body)
    return gigs


def _snapshot(data: dict[str, Any], hand_added: bool = False) -> dict[str, Any]:
    keep = (*LOCKABLE, *SCRAPED_LISTS, "venue")
    snap = {k: data.get(k) for k in keep}
    if hand_added:
        snap["_hand_added"] = True  # keep "fill gaps only" for this gig on every later run
    return snap


def _tombstone(gig: GigFile, venues: VenueIndex, reason: str) -> dict[str, Any]:
    facts = gig.facts(venues)
    return {
        "id": gig.id,
        "keys": [s["key"] for s in gig.data.get("sources") or [] if isinstance(s, dict) and s.get("key")],
        "fingerprint": f"{facts.group}|{facts.date}|{norm_act(facts.headliner)}" if facts else "",
        "date": gig.data.get("date"),
        "first_seen": gig.data.get("first_seen"),
        "backfill": bool(gig.data.get("backfill")),
        "reason": reason,
    }


def _new_slug(gigs_dir: Path, date: str, venue: str, headliner: str, taken: set[str]) -> str:
    base = f"{date}-{venue}-{slugify(headliner, 40)}"
    slug, n = base, 2
    while slug in taken or (gigs_dir / f"{slug}.md").exists():
        slug, n = f"{base}-{n}", n + 1
    taken.add(slug)
    return slug


def apply(
    candidates: list[Candidate],
    state: State,
    venues: VenueIndex,
    gigs_dir: Path,
    *,
    now,
    healthy_adapters: set[str],
    dry_run: bool,
    rejected_keys: set[str] = frozenset(),
) -> Changes:
    changes = Changes()
    today = london_today(now)
    stamp = iso_utc(now)
    gigs = load_gigs(gigs_dir)

    # 1. Past gigs go first, so they don't count as vanished or deleted.
    for gid, gig in list(gigs.items()):
        last_day = str(gig.data.get("end_date") or gig.data.get("date") or "")
        if last_day and last_day < today:
            changes.pruned.append(gig.path.stem)
            if not dry_run:
                gig.path.unlink()
            del gigs[gid]
            state.seen.pop(gid, None)
            state.snapshots.pop(gid, None)
    state.tombstones = [t for t in state.tombstones if str(t.get("date", "")) >= today]

    # 2. Future gigs the scraper wrote whose file is gone: a human deleted them.
    deleted = [gid for gid, snap in state.snapshots.items() if gid not in gigs and str(snap.get("date") or "") >= today]
    if len(deleted) > MAX_DELETIONS:
        changes.deletion_valve_tripped = True
    else:
        for gid in deleted:
            snap = state.snapshots.pop(gid)
            state.seen.pop(gid, None)
            keys = [s["key"] for s in snap.get("sources") or [] if isinstance(s, dict) and s.get("key")]
            venue = venues.by_slug.get(str(snap.get("venue")))
            fp = f"{venue.group_key if venue else snap.get('venue')}|{snap.get('date')}|{norm_act(str(snap.get('headliner') or ''))}"
            state.tombstones.append({"id": gid, "keys": keys, "fingerprint": fp, "date": snap.get("date"), "reason": "deleted"})
            changes.human_deleted.append(f"{snap.get('date')} {snap.get('headliner')}")

    # 3. Match each candidate to an existing file, or create one.
    by_key = {s["key"]: gid for gid, g in gigs.items() for s in g.data.get("sources") or [] if isinstance(s, dict) and s.get("key")}
    matched: set[str] = set()
    taken_slugs: set[str] = set()
    for cand in candidates:
        tomb = state.find_tombstone(cand.keys, cand.fingerprint)
        if tomb and tomb.get("reason") == "deleted":
            changes.suppressed.append(f"{cand.facts.date} {cand.facts.headliner}")
            continue
        fields = cand.fields(state.overrides.exclude_ticket_urls)
        gid = next((by_key[k] for k in cand.keys if k in by_key and by_key[k] not in matched), None)
        if gid is None:
            best, best_score = None, 0.0
            for other_id, gig in gigs.items():
                facts = gig.facts(venues)
                if other_id in matched or facts is None:
                    continue
                sc = score(cand.facts, facts)
                if sc > best_score:
                    best, best_score = other_id, sc
            if best is not None and best_score >= MATCH:
                gid = best
            elif best is not None and best_score >= REVIEW:
                fields["needs_review"] = True
                changes.review.append(f"{cand.facts.date} {cand.facts.headliner}: might duplicate {gigs[best].path.stem}")

        hand_added = False
        if gid is None:
            gid = str(tomb["id"]) if tomb else str(uuid.uuid4())
            data = {"id": gid, **fields, "first_seen": tomb.get("first_seen", stamp) if tomb else stamp, "updated_at": stamp}
            if (tomb.get("backfill") if tomb else cand.backfill):
                data["backfill"] = True
            if tomb:
                state.tombstones.remove(tomb)
            slug = _new_slug(gigs_dir, fields["date"], fields["venue"], fields["headliner"], taken_slugs)
            gig = GigFile(gigs_dir / f"{slug}.md", _ordered(data), "")
            gigs[gid] = gig
            changes.created.append(slug)
            changed = True
        else:
            gig = gigs[gid]
            snap = state.snapshots.get(gid)
            hand_added = snap is None or bool(snap.get("_hand_added"))
            changed = _update(gig, fields, None if hand_added else snap, stamp, changes, state.overrides.exclude_ticket_urls)
            if changed:
                changes.updated.append(gig.path.stem)
            else:
                changes.unchanged += 1
        if gig.data.get("needs_review"):
            changes.review.extend(f"{gig.path.stem}: {n}" for n in cand.review_notes)
            if cand.classification.confidence < 0.7:
                changes.review.append(f"{gig.path.stem}: not sure it's a gig ({cand.reason})")
        matched.add(gid)
        state.seen[gid] = {"last_seen": stamp, "misses": 0}
        state.snapshots[gid] = _snapshot(gig.data, hand_added=hand_added)
        # Unchanged files stay byte-for-byte as they are, so a CMS save isn't followed by a
        # formatting-only commit (the CMS indents lists and orders keys its own way).
        if changed and not dry_run:
            frontmatter.write(gig.path, gig.data, gig.body)

    # 4a. Gigs the scraper added that its sources (or Claude) now say aren't gigs. A human who
    #     edited the gig, or added it, has the final say, so those stay.
    for gid, gig in list(gigs.items()):
        keys = {s.get("key") for s in gig.data.get("sources") or [] if isinstance(s, dict)}
        snap = state.snapshots.get(gid)
        if gid in matched or not keys or not keys <= rejected_keys or snap is None or snap.get("_hand_added") or gig.data.get("locked_fields"):
            continue
        changes.reclassified.append(gig.path.stem)
        # Remembered, so if it's judged a gig again later it returns with its own id and
        # first_seen instead of showing up as newly announced.
        state.tombstones.append(_tombstone(gig, venues, "reclassified"))
        del gigs[gid]
        state.seen.pop(gid, None)
        state.snapshots.pop(gid, None)
        if not dry_run:
            gig.path.unlink()

    # 4b. Gigs every one of their (healthy) sources stopped listing: flag, then remove.
    for gid, gig in list(gigs.items()):
        if gid in matched:
            continue
        sources = {s.get("name") for s in gig.data.get("sources") or [] if isinstance(s, dict)}
        if not sources or not sources <= healthy_adapters:
            continue  # hand-added, or a source that didn't run cleanly this time
        entry = state.seen.setdefault(gid, {"last_seen": None, "misses": 0})
        entry["misses"] = entry.get("misses", 0) + 1
        if entry["misses"] >= REMOVE_AFTER_MISSES:
            state.tombstones.append(_tombstone(gig, venues, "vanished"))
            changes.vanished.append(gig.path.stem)
            state.seen.pop(gid, None)
            state.snapshots.pop(gid, None)
            if not dry_run:
                gig.path.unlink()
        elif entry["misses"] >= REVIEW_AFTER_MISSES and not gig.data.get("needs_review") and "needs_review" not in (gig.data.get("locked_fields") or []):
            gig.data["needs_review"] = True
            gig.data = _ordered(gig.data)
            state.snapshots[gid] = _snapshot(gig.data)
            changes.flagged_missing.append(gig.path.stem)
            if not dry_run:
                frontmatter.write(gig.path, gig.data, gig.body)
    return changes


def _update(
    gig: GigFile,
    new: dict[str, Any],
    snap: dict[str, Any] | None,
    stamp: str,
    changes: Changes,
    excluded_ticket_urls: set[str] = frozenset(),
) -> bool:
    data = dict(gig.data)
    locked = list(data.get("locked_fields") or [])
    for f in LOCKABLE:
        if f in locked:
            continue
        cur, val = data.get(f), new.get(f)
        if snap is None:
            # Added by hand in the CMS: fill gaps, never overwrite.
            if _empty(cur) and not _empty(val):
                data[f] = val
            continue
        if _norm(cur) != _norm(snap.get(f)):
            locked.append(f)  # a human changed it since we last wrote it
            changes.newly_locked.append(f"{gig.path.stem}: {f}")
            continue
        data[f] = val
    for f in ("support", "genres"):
        cur = data.get(f)
        if snap is None or _norm(cur) == _norm(snap.get(f)):
            if _empty(cur) or snap is not None:
                data[f] = new.get(f) or []
    for f, ident in (("tickets", "url"), ("sources", "key")):
        merged = list(data.get(f) or [])
        known = {item.get(ident) for item in merged if isinstance(item, dict)}
        merged += [item for item in new.get(f) or [] if item.get(ident) not in known]
        if f == "tickets":
            merged = [t for t in merged if not (isinstance(t, dict) and t.get("url") in excluded_ticket_urls)]
        data[f] = merged
    if "classification" not in locked:
        data["classification"] = new.get("classification")
    data["locked_fields"] = locked
    before = _ordered({k: v for k, v in gig.data.items() if k != "updated_at"})
    after = _ordered({k: v for k, v in data.items() if k != "updated_at"})
    if json.dumps(before, sort_keys=True, default=str) == json.dumps(after, sort_keys=True, default=str):
        return False
    data["updated_at"] = stamp
    gig.data = _ordered(data)
    return True
