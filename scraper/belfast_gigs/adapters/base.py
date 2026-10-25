from __future__ import annotations

from typing import ClassVar

from ..http import Http
from ..models import RawEvent


class MissingCredentials(Exception):
    """The adapter needs a key that isn't configured. Reported as skipped, not broken."""


class Adapter:
    name: ClassVar[str]
    # Lower wins when merging fields from several sources: a venue's own site knows its gigs best.
    authority: ClassVar[int] = 10
    # Every event from this source is music (e.g. a music-only promoter).
    always_music: ClassVar[bool] = False
    # Licence/terms note, shown in the README and report.
    licence: ClassVar[str] = ""

    def fetch(self, http: Http) -> list[RawEvent]:
        raise NotImplementedError
