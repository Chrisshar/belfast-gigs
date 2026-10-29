"""Is this a gig? Rules first; whatever the rules can't settle is published flagged for review
(Phase 2 sends those to Claude Haiku before falling back to the flag).

In scope: live music, including tribute/covers acts, trad sessions, open mics and small-venue
contemporary/new-classical concerts. Out: DJ/club nights, party nights (themed, decade, student and
day parties, even with a band on), orchestral/opera/choral, comedy, theatre, panto, quizzes, talks,
film, family shows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import Classification
from .normalise import Prepared

_BLOCK = re.compile(
    r"\b("
    r"comedy|comedian|stand[\s-]?up|improv|sketch show|"
    r"theatre|musical theatre|the musical|play|pantomime|panto|"
    r"quiz|bingo|bingo loco|"
    r"club ?night|dj|djs|dj set|b2b|rave|"
    r"orchestra|orchestral|symphony|philharmonic|opera|choir|choral|"
    r"talk|talks|lecture|in conversation|q&a|podcast|spoken word|poetry|book launch|"
    r"workshop|class|masterclass|"
    r"kids|children'?s|family show|toddler|"
    # Not "cinema", "circus" or "magic": too many band names (Two Door Cinema Club, The Magic Numbers).
    r"film|screening|"
    r"magician|magic show|hypnotist|wrestling|drag|burlesque|cabaret|"
    r"market|fair|tasting|brunch"
    r")\b",
    re.I,
)
# Strong signals outweigh a blocklist word ("Comedy club open mic" is still an open mic);
# weak ones only count when nothing says otherwise ("Live: Stand-Up Tour" is comedy).
_STRONG = re.compile(
    r"\b(tribute|covers? band|trad session|traditional session|open mic|live music|"
    r"album launch|ep launch|single launch|unplugged|songwriter)\b",
    re.I,
)
_WEAK = re.compile(r"\b(band|acoustic|session|singer|gig|concert|in concert|live|tour)\b", re.I)
# Party and club nights. Venues list these with their gigs (often with a covers band on), so
# they're dropped even when the source says music; only a strong gig signal saves one
# ("Tom Gee: EP Launch Party", "Exhibition Party: The Outcasts plus special guests").
_PARTY = re.compile(
    r"(?<!dinner )\bpart(y|ies)\b|"
    r"\b(halloween|hallowe'?en|christmas|xmas|headbanger\w*|masked|masquerade) ball\b|"
    r"\bstudents?\b|\bday (rave|fever)\b|\bsilent disco\b|\bdisco night\b|\bthemed\b|"
    r"\bemo (fest|night)\b|\bnought(y|ie|ies)\b|"
    # Decade nights: "80's / 90's", "90’s – 00’s".
    r"\b\d0['’]?s\s*[-–/&+]\s*\d0['’]?s\b",
    re.I,
)
_STRONG_PARTY = re.compile(r"\b(album launch|ep launch|single launch|special guests?|plus support|\+ support)\b", re.I)

REVIEW_BELOW = 0.7


@dataclass
class Verdict:
    classification: Classification
    reason: str
    party: bool = False  # rejected as a party/club night: Claude needs to be sure to bring it back

    @property
    def publish(self) -> bool:
        return self.classification.is_music

    @property
    def needs_review(self) -> bool:
        return self.classification.confidence < REVIEW_BELOW


def classify(p: Prepared, always_music: bool = False) -> Verdict:
    text = " ".join([p.title, p.raw.title, *p.raw.categories])
    blocked = _BLOCK.search(text)

    def v(is_music: bool, confidence: float, reason: str) -> Verdict:
        return Verdict(Classification(is_music=is_music, confidence=confidence, method="rules"), reason)

    if always_music:
        return v(True, 0.95, "source lists only music")
    if p.raw.is_music_hint is False:
        return v(False, 0.95, "source marks it as non-music")
    party = _PARTY.search(text)
    if party and not _STRONG_PARTY.search(text):
        verdict = v(False, 0.85, f"party night: title says '{party.group(0)}'")
        verdict.party = True
        return verdict
    if p.raw.is_music_hint is True:
        if blocked:
            return v(True, 0.5, f"music source, but title says '{blocked.group(0)}'")
        return v(True, 0.9, "source lists it as music")
    if p.venue.music_only:
        return v(True, 0.85, "music-only venue")
    strong = _STRONG.search(text)
    if strong:
        return v(True, 0.8 if not blocked else 0.6, f"title says '{strong.group(0)}'")
    if blocked:
        return v(False, 0.85, f"title says '{blocked.group(0)}'")
    weak = _WEAK.search(text)
    if weak:
        return v(True, 0.75, f"title says '{weak.group(0)}'")
    # Can't tell: publish (missing a gig is worse than a stray listing) but flag it.
    return v(True, 0.5, "no clear signal")


OVERRULE_SOURCE_AT = 0.9


def with_llm(rules: Verdict, llm: dict | None, always_music: bool = False) -> Verdict:
    """Claude's verdict replaces the rules' (it knows the acts), except for music-only sources.

    When the source itself listed it as music, Claude needs to be sure to drop it (an orchestra
    touring an arena); a less certain "no" (a tribute show it mistook for the film) is published
    and flagged for a human instead. Missing a gig is worse than a stray listing.
    """
    if llm is None or always_music:
        return rules
    confidence = round(float(llm["confidence"]), 2)
    if rules.party and llm["is_music"] and confidence < OVERRULE_SOURCE_AT:
        return rules
    source_said_music = rules.classification.is_music and rules.classification.confidence >= 0.9
    if not llm["is_music"] and source_said_music and confidence < OVERRULE_SOURCE_AT:
        return Verdict(Classification(is_music=True, confidence=0.5, method="llm"), f"source says music, Claude doubts it ({confidence})")
    if llm["is_music"] and source_said_music:
        # Claude often doesn't know local acts; agreeing with the source is enough.
        confidence = max(confidence, rules.classification.confidence)
    what = "a gig" if llm["is_music"] else "not a gig"
    return Verdict(Classification(is_music=llm["is_music"], confidence=confidence, method="llm"), f"Claude: {what} ({confidence})")
