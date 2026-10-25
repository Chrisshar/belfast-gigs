"""Human-readable run summary: printed, and written to the GitHub Actions job summary when there."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field

from .pipeline.write import Changes


@dataclass
class SourceResult:
    name: str
    status: str  # ok | skipped | failed
    fetched: int = 0
    detail: str = ""


@dataclass
class Report:
    dry_run: bool
    sources: list[SourceResult] = field(default_factory=list)
    out_of_area: Counter = field(default_factory=Counter)
    stub_venues: list[str] = field(default_factory=list)
    dropped_past: int = 0
    dropped_blocked: int = 0
    not_music: Counter = field(default_factory=Counter)
    candidates: int = 0
    changes: Changes | None = None
    llm: dict = field(default_factory=dict)
    llm_errors: list[str] = field(default_factory=list)
    issue_problems: list[str] = field(default_factory=list)

    def summary(self) -> str:
        c = self.changes or Changes()
        head = "Dry run, nothing written" if self.dry_run else "Scrape"
        lines = [
            f"## {head}: +{len(c.created)} new, {len(c.updated)} updated, {len(c.pruned) + len(c.vanished) + len(c.reclassified)} removed",
            "",
            "| Source | Status | Listings | Detail |",
            "|---|---|---|---|",
            *(f"| {s.name} | {s.status} | {s.fetched} | {s.detail} |" for s in self.sources),
            "",
            f"- Gigs this run: {self.candidates} (unchanged: {c.unchanged})",
            f"- Dropped: {self.dropped_past} past, {self.dropped_blocked} blocked by overrides, "
            f"{sum(self.not_music.values())} not music, {sum(self.out_of_area.values())} outside greater Belfast",
        ]
        if self.llm:
            line = f"- Claude: {self.llm['calls']} call(s) for {self.llm['checked']} listing(s) not in the cache; ${self.llm['month_cost']:.4f} spent this month"
            if self.llm.get("skipped"):
                line += f" (stopped asking: {self.llm['skipped']})"
            lines.append(line)
        for problem in [*self.llm_errors, *self.issue_problems]:
            lines.append(f"- **Problem:** {problem}")
        if c.deletion_valve_tripped:
            lines.append("- **Safety valve:** too many gig files disappeared at once, so no deletions were recorded. Check the checkout.")
        sections = [
            ("New", c.created),
            ("Removed (past)", c.pruned),
            ("Removed (no source lists them any more)", c.vanished),
            ("Removed (now judged not to be a gig)", c.reclassified),
            ("Flagged: missing from sources", c.flagged_missing),
            ("Deleted by a human (won't be re-added)", c.human_deleted),
            ("Not re-added (deleted earlier)", c.suppressed),
            ("Fields locked after a human edit", c.newly_locked),
            ("Needs review", c.review),
            ("New venues to check", self.stub_venues),
            ("Non-music reasons", [f"{n} x {r}" for r, n in self.not_music.most_common(10)]),
            ("Unknown venues outside the area", [f"{n} x {v}" for v, n in self.out_of_area.most_common(10)]),
        ]
        for title, items in sections:
            if items:
                lines += ["", f"<details><summary>{title} ({len(items)})</summary>", "", *(f"- {i}" for i in items), "", "</details>"]
        return "\n".join(lines) + "\n"

    def publish(self) -> str:
        text = self.summary()
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(text)
        return text
