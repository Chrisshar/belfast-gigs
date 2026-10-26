"""Data shapes shared across the scraper. Gig mirrors the Zod schema in src/content.config.ts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .dates import as_date_str

# Keep in sync with src/content.config.ts.
GENRES = (
    "Rock",
    "Indie/Alternative",
    "Punk/Hardcore",
    "Metal",
    "Pop",
    "Hip-Hop/Rap",
    "Electronic",
    "Folk/Trad",
    "Country/Americana",
    "Jazz/Blues",
    "Soul/R&B/Funk",
    "Singer-Songwriter",
    "Tribute/Covers",
    "World",
    "Contemporary/New Music",
)
Status = Literal["on_sale", "sold_out", "cancelled", "postponed", "rescheduled"]


@dataclass
class RawEvent:
    """One listing as a source reports it, before normalising, classifying or merging."""

    source: str  # adapter name
    source_key: str  # stable id within that source (event id or page URL)
    title: str
    venue_name: str
    date: str  # YYYY-MM-DD, London
    source_url: str | None = None
    headliner: str | None = None  # when the source separates it
    support: list[str] = field(default_factory=list)
    room: str | None = None
    end_date: str | None = None
    doors_time: str | None = None
    start_time: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    free: bool = False
    status: Status = "on_sale"
    age_restriction: str | None = None
    tickets: list[tuple[str, str]] = field(default_factory=list)  # (provider, url)
    categories: list[str] = field(default_factory=list)  # source's own tags, lower-cased
    is_music_hint: bool | None = None  # True/False when the source itself says so
    lat: float | None = None
    lng: float | None = None
    address: str | None = None
    attraction_key: str | None = None  # Ticketmaster attraction id, for collapsing package listings
    backfill: bool = False  # an old listing the source only now let us find: kept out of Just announced


class Classification(BaseModel):
    is_music: bool
    confidence: float = Field(ge=0, le=1)
    method: Literal["rules", "llm", "manual"]


class Ticket(BaseModel):
    source: str
    url: str


class Source(BaseModel):
    name: str
    key: str
    url: str | None = None


class Gig(BaseModel):
    """Frontmatter of one src/content/gigs/<slug>.md file."""

    model_config = ConfigDict(extra="allow")  # never drop fields a human or the CMS added

    id: str
    title: str
    headliner: str
    support: list[str] = []
    venue: str
    room: str | None = None
    date: str
    end_date: str | None = None
    doors_time: str | None = None
    start_time: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    currency: Literal["GBP"] = "GBP"
    free: bool = False
    status: Status = "on_sale"
    age_restriction: str | None = None
    genres: list[str] = []
    tickets: list[Ticket] = []
    sources: list[Source] = []
    first_seen: str
    updated_at: str | None = None
    backfill: bool = False
    classification: Classification | None = None
    needs_review: bool = False
    locked_fields: list[str] = []

    @field_validator("date", "end_date", mode="before")
    @classmethod
    def _dates_as_strings(cls, v: object) -> str | None:
        return as_date_str(v)

    @field_validator("first_seen", "updated_at", mode="before")
    @classmethod
    def _timestamps_as_strings(cls, v: object) -> str | None:
        if v is None or v == "":
            return None
        if hasattr(v, "isoformat"):
            from .dates import iso_utc

            return iso_utc(v)  # type: ignore[arg-type]
        return str(v)

    @field_validator("doors_time", "start_time", mode="before")
    @classmethod
    def _times_as_strings(cls, v: object) -> str | None:
        if v is None or v == "":
            return None
        if isinstance(v, int):  # YAML 1.1 reads unquoted 19:30 as sexagesimal 1170
            return f"{v // 60:02d}:{v % 60:02d}"
        return str(v)


# Fields the scraper may overwrite on an existing gig (subject to locked_fields).
SCRAPED_SCALARS = (
    "title",
    "headliner",
    "room",
    "date",
    "end_date",
    "doors_time",
    "start_time",
    "price_min",
    "price_max",
    "free",
    "status",
    "age_restriction",
)
# List fields are merged, never auto-locked (a human tweak would otherwise freeze them for good).
SCRAPED_LISTS = ("support", "genres", "tickets", "sources")

# Frontmatter key order on disk.
KEY_ORDER = (
    "id",
    "title",
    "headliner",
    "support",
    "venue",
    "room",
    "date",
    "end_date",
    "doors_time",
    "start_time",
    "price_min",
    "price_max",
    "currency",
    "free",
    "status",
    "age_restriction",
    "genres",
    "tickets",
    "sources",
    "first_seen",
    "updated_at",
    "backfill",
    "classification",
    "needs_review",
    "locked_fields",
)
