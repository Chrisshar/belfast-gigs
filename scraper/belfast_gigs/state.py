"""Scraper state committed in data/ (not part of the site build).

- seen.json: per gig id, when a source last listed it and how many healthy runs in a row missed it
- snapshots.json: per gig id, the values the scraper last wrote (a difference means a human edited)
- tombstones.json: gigs a human deleted, or that vanished from every source, so they aren't re-added
- source_health.json: per adapter, successful runs and consecutive failures
- page_cache.json: per adapter, what each event page said when last read (sources read a page at a time)
- overrides.yaml: hand-maintained blocklist and ticket-link excludes
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .paths import DATA_DIR

_FILES = ("seen", "snapshots", "tombstones", "source_health", "page_cache")


@dataclass
class Overrides:
    block_titles: list[re.Pattern] = field(default_factory=list)
    allow_titles: list[re.Pattern] = field(default_factory=list)
    exclude_ticket_urls: set[str] = field(default_factory=set)

    def blocked(self, title: str) -> bool:
        return any(p.search(title) for p in self.block_titles)

    def allowed(self, title: str) -> bool:
        return any(p.search(title) for p in self.allow_titles)


@dataclass
class State:
    seen: dict[str, dict[str, Any]] = field(default_factory=dict)
    snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    tombstones: list[dict[str, Any]] = field(default_factory=list)
    source_health: dict[str, dict[str, Any]] = field(default_factory=dict)
    page_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    overrides: Overrides = field(default_factory=Overrides)

    @classmethod
    def load(cls, data_dir: Path = DATA_DIR) -> State:
        state = cls()
        for name in _FILES:
            path = data_dir / f"{name}.json"
            if path.exists():
                setattr(state, name, json.loads(path.read_text(encoding="utf-8")))
        ov_path = data_dir / "overrides.yaml"
        if ov_path.exists():
            raw = yaml.safe_load(ov_path.read_text(encoding="utf-8")) or {}
            state.overrides = Overrides(
                block_titles=[re.compile(p, re.I) for p in raw.get("block_titles") or []],
                allow_titles=[re.compile(p, re.I) for p in raw.get("allow_titles") or []],
                exclude_ticket_urls=set(raw.get("exclude_ticket_urls") or []),
            )
        return state

    def save(self, data_dir: Path = DATA_DIR) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        for name in _FILES:
            value = getattr(self, name)
            text = json.dumps(value, indent=1, sort_keys=isinstance(value, dict), ensure_ascii=False) + "\n"
            (data_dir / f"{name}.json").write_text(text, encoding="utf-8", newline="\n")

    def find_tombstone(self, keys: list[str], fingerprint: str) -> dict[str, Any] | None:
        wanted = set(keys)
        return next((t for t in self.tombstones if wanted & set(t.get("keys", [])) or t.get("fingerprint") == fingerprint), None)

    def first_successful_run(self, adapter: str) -> bool:
        return self.source_health.get(adapter, {}).get("runs_ok", 0) == 0
