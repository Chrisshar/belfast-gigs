from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from belfast_gigs.models import RawEvent
from belfast_gigs.paths import VENUES_DIR

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 25, 17, 0, tzinfo=UTC)


def load_json(*parts: str):
    return json.loads(FIXTURES.joinpath(*parts).read_text(encoding="utf-8"))


def load_text(*parts: str) -> str:
    return FIXTURES.joinpath(*parts).read_text(encoding="utf-8")


def raw(**kw) -> RawEvent:
    defaults = dict(
        source="venue",
        source_key="venue:1",
        title="Example Act",
        venue_name="Ulster Hall",
        date="2026-11-14",
        is_music_hint=True,
    )
    return RawEvent(**{**defaults, **kw})


@pytest.fixture
def site(tmp_path: Path) -> dict[str, Path]:
    """A throwaway copy of the real venues, plus empty gigs/ and data/ dirs."""
    venues = tmp_path / "venues"
    shutil.copytree(VENUES_DIR, venues)
    (tmp_path / "gigs").mkdir()
    (tmp_path / "data").mkdir()
    return {"venues": venues, "gigs": tmp_path / "gigs", "data": tmp_path / "data"}
