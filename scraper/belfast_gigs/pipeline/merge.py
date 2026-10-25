"""Group this run's listings into gigs, so one show listed by the venue and Ticketmaster is one gig."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import Classification, Status
from ..text import clean_url
from .classify import REVIEW_BELOW, Verdict
from .genres import genres_for
from .match import MATCH, REVIEW, Facts, norm_act, score
from .normalise import Prepared


@dataclass
class Scored:
    prepared: Prepared
    verdict: Verdict
    authority: int
    backfill: bool  # from a source's first-ever run
    genres: list[str] = field(default_factory=list)  # from Claude, when it checked this listing

    @property
    def facts(self) -> Facts:
        p = self.prepared
        return Facts(p.group, p.raw.date, p.raw.end_date, p.room, p.time, p.headliner)


@dataclass
class Candidate:
    """One gig as this run sees it, built from one or more sources' listings."""

    events: list[Scored]
    review_notes: list[str] = field(default_factory=list)

    @property
    def primary(self) -> Scored:
        return self.events[0]

    @property
    def facts(self) -> Facts:
        return self.primary.facts

    @property
    def keys(self) -> list[str]:
        return [e.prepared.raw.source_key for e in self.events]

    @property
    def adapters(self) -> set[str]:
        return {e.prepared.raw.source for e in self.events}

    @property
    def fingerprint(self) -> str:
        f = self.facts
        return f"{f.group}|{f.date}|{norm_act(f.headliner)}"

    @property
    def classification(self) -> Classification:
        return max((e.verdict for e in self.events), key=lambda v: v.classification.confidence).classification

    @property
    def reason(self) -> str:
        return max(self.events, key=lambda e: e.verdict.classification.confidence).verdict.reason

    @property
    def needs_review(self) -> bool:
        return bool(self.review_notes) or self.classification.confidence < REVIEW_BELOW

    @property
    def backfill(self) -> bool:
        return all(e.backfill for e in self.events)

    def fields(self, excluded_ticket_urls: set[str] = frozenset()) -> dict[str, Any]:
        """Gig frontmatter values, taking each from the most authoritative source that has it."""
        evs = [e.prepared for e in self.events]

        def first(attr: str) -> Any:
            return next((getattr(p.raw, attr) for p in evs if getattr(p.raw, attr) not in (None, "")), None)

        tickets, seen_urls = [], set()
        for p in evs:
            for provider, raw_url in p.raw.tickets:
                url = clean_url(raw_url)
                if url not in seen_urls and url not in excluded_ticket_urls:
                    seen_urls.add(url)
                    tickets.append({"source": provider, "url": url})
        statuses = {p.status for p in evs}
        status: Status = next((s for s in ("cancelled", "postponed", "rescheduled", "sold_out") if s in statuses), "on_sale")  # type: ignore[assignment]
        prices = [p.raw for p in evs if p.raw.price_min is not None]
        main = evs[0]
        return {
            "title": main.title,
            "headliner": main.headliner,
            "support": next((p.support for p in evs if p.support), []),
            "venue": main.venue.slug,
            "room": next((p.room for p in evs if p.room), None),
            "date": main.raw.date,
            "end_date": main.raw.end_date,
            "doors_time": first("doors_time"),
            "start_time": first("start_time"),
            "price_min": prices[0].price_min if prices else None,
            "price_max": prices[0].price_max if prices else None,
            "free": any(p.raw.free for p in evs),
            "status": status,
            "age_restriction": first("age_restriction"),
            "genres": genres_for([c for p in evs for c in p.raw.categories], main.title, [g for e in self.events for g in e.genres]),
            "tickets": tickets,
            # No `url: null`: Zod's .optional() accepts a missing key but not null.
            "sources": [
                {"name": p.raw.source, "key": p.raw.source_key, **({"url": p.raw.source_url} if p.raw.source_url else {})}
                for p in evs
            ],
            "classification": self.classification.model_dump(),
            "needs_review": self.needs_review,
        }


def cluster(items: list[Scored]) -> list[Candidate]:
    candidates: list[Candidate] = []
    for item in sorted(items, key=lambda s: (s.authority, s.prepared.raw.date, s.prepared.raw.source_key)):
        best, best_score = None, 0.0
        for cand in candidates:
            sc = score(cand.facts, item.facts)
            if sc > best_score:
                best, best_score = cand, sc
        if best is not None and best_score >= MATCH:
            best.events.append(item)
            continue
        cand = Candidate([item])
        if best is not None and best_score >= REVIEW:
            note = f"Might be the same gig as '{best.primary.prepared.title}' ({best.primary.prepared.raw.source_key}), score {best_score:.0f}"
            cand.review_notes.append(note)
        candidates.append(cand)
    return candidates
