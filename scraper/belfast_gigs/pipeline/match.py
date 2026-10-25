"""Is listing A the same gig as listing B? Used to merge sources within a run and to find the
existing file a freshly scraped gig belongs to.

Candidates must be in the same venue group with overlapping dates. Then:
- hard non-matches: different rooms; start times over 2 hours apart; "tribute" in only one name;
- otherwise score the normalised headliners (0-100). MATCH or above is the same gig; REVIEW to
  MATCH is kept separate and flagged so a human can merge it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from ..text import squash

MATCH = 90
REVIEW = 75

_NOISE = re.compile(
    r"\b(the|live|in concert|tour|world tour|uk tour|irish tour|\d{4}|plus|special guests?|support|"
    r"presents?|an evening with|anniversary|years of hits|celebrating|official)\b"
)


@dataclass
class Facts:
    group: str
    date: str
    end_date: str | None
    room: str | None
    time: str | None
    headliner: str


def norm_act(name: str) -> str:
    s = squash(name)
    s = _NOISE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip() or squash(name)


def name_score(a: str, b: str) -> float:
    na, nb = norm_act(a), norm_act(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 100.0
    score = max(fuzz.ratio(na, nb), fuzz.token_sort_ratio(na, nb))
    # token_set_ratio says 100 whenever one name's words are a subset of the other's, so
    # "ash" would equal "ash tree session". Only trust it once the shorter name has 2+ words.
    if min(len(na.split()), len(nb.split())) >= 2:
        score = max(score, fuzz.token_set_ratio(na, nb))
    # "Westlife 25" vs "Westlife": a whole-word prefix is a strong signal.
    short, long_ = sorted((na, nb), key=len)
    if long_.startswith(short + " ") and len(short) >= 4:
        score = max(score, 92.0)
    return score


def _minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _overlap(a: Facts, b: Facts) -> bool:
    return a.date <= (b.end_date or b.date) and b.date <= (a.end_date or a.date)


def score(a: Facts, b: Facts) -> float:
    """0 when they can't be the same gig, else the headliner similarity."""
    if a.group != b.group or not _overlap(a, b):
        return 0.0
    if a.room and b.room and squash(a.room) != squash(b.room):
        return 0.0
    if a.time and b.time and abs(_minutes(a.time) - _minutes(b.time)) > 120:
        return 0.0
    if ("tribute" in a.headliner.lower()) != ("tribute" in b.headliner.lower()):
        return 0.0
    return name_score(a.headliner, b.headliner)
