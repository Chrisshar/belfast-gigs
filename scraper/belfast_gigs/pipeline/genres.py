"""Map source tags (Ticketmaster genre/subGenre, venue categories) and title words to our taxonomy."""

from __future__ import annotations

import re

from ..models import GENRES

_TAG_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"tribute|covers?"), "Tribute/Covers"),
    (re.compile(r"punk|hardcore|emo|ska"), "Punk/Hardcore"),
    (re.compile(r"metal|grindcore|doom"), "Metal"),
    (re.compile(r"indie|alternative|alt[\s-]rock|shoegaze|post[\s-]punk|new wave"), "Indie/Alternative"),
    (re.compile(r"\brock\b|grunge|psych|garage|classic rock"), "Rock"),
    (re.compile(r"hip[\s-]?hop|rap\b|grime|drill"), "Hip-Hop/Rap"),
    (re.compile(r"electronic|dance|techno|house|drum and bass|dnb|edm|trance|synth"), "Electronic"),
    (re.compile(r"folk|trad|irish|celtic|ceili|bluegrass"), "Folk/Trad"),
    (re.compile(r"country|americana|old[\s-]time"), "Country/Americana"),
    (re.compile(r"jazz|blues|swing"), "Jazz/Blues"),
    (re.compile(r"soul|r\s?&\s?b|r and b|funk|motown|gospel|disco"), "Soul/R&B/Funk"),
    (re.compile(r"singer[\s-]?songwriter|acoustic|open mic"), "Singer-Songwriter"),
    (re.compile(r"world|latin|reggae|afro|african|k-pop|flamenco"), "World"),
    (re.compile(r"contemporary classical|new music|minimalis|experimental|avant"), "Contemporary/New Music"),
    (re.compile(r"\bpop\b|boy ?band|girl ?group"), "Pop"),
]


def genres_for(tags: list[str], title: str) -> list[str]:
    found: list[str] = []
    for text in [*tags, title]:
        t = text.lower()
        for pattern, genre in _TAG_MAP:
            if pattern.search(t) and genre not in found:
                found.append(genre)
    assert all(g in GENRES for g in found)
    return found[:3]
