"""python -m belfast_gigs run [--dry-run] [--only SOURCE ...]"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .adapters import ADAPTERS, MissingCredentials
from .dates import iso_utc, london_today, now_utc
from .http import Http
from .paths import DATA_DIR, GIGS_DIR, VENUES_DIR
from .pipeline.classify import classify
from .pipeline.merge import Scored, cluster
from .pipeline.normalise import is_pass, prepare
from .pipeline.write import apply
from .report import Report, SourceResult
from .state import State
from .venues import VenueIndex


def run(
    only: list[str] | None = None,
    *,
    dry_run: bool = False,
    gigs_dir: Path = GIGS_DIR,
    venues_dir: Path = VENUES_DIR,
    data_dir: Path = DATA_DIR,
    now: datetime | None = None,
    http: Http | None = None,
) -> Report:
    now = now or now_utc()
    today = london_today(now)
    state = State.load(data_dir)
    venues = VenueIndex.load(venues_dir)
    report = Report(dry_run=dry_run)
    names = only or list(ADAPTERS)
    healthy: set[str] = set()
    scored: list[Scored] = []

    own_http = http is None
    http = http or Http()
    if own_http:
        http.__enter__()
    try:
        for name in names:
            adapter = ADAPTERS[name]()
            health = state.source_health.setdefault(name, {"runs_ok": 0, "consecutive_failures": 0})
            first_run = health.get("runs_ok", 0) == 0
            try:
                raw_events = adapter.fetch(http)
            except MissingCredentials as exc:
                report.sources.append(SourceResult(name, "skipped", detail=str(exc)))
                continue
            except Exception as exc:  # one broken source must not stop the run
                health["consecutive_failures"] = health.get("consecutive_failures", 0) + 1
                health["last_error"] = f"{type(exc).__name__}: {exc}"[:300]
                report.sources.append(SourceResult(name, "failed", detail=health["last_error"]))
                continue
            health.update(last_run=iso_utc(now), last_count=len(raw_events))
            if raw_events:
                health["runs_ok"] = health.get("runs_ok", 0) + 1
                health["consecutive_failures"] = 0
                health.pop("last_error", None)
                healthy.add(name)
                detail = "first run: gigs marked as backfill" if first_run else ""
                report.sources.append(SourceResult(name, "ok", len(raw_events), detail))
            else:
                health["consecutive_failures"] = health.get("consecutive_failures", 0) + 1
                health["last_error"] = "returned no events"
                report.sources.append(SourceResult(name, "failed", 0, "returned no events"))
                continue

            for raw in raw_events:
                if (raw.end_date or raw.date) < today:
                    report.dropped_past += 1
                    continue
                if is_pass(raw.title) or state.overrides.blocked(raw.title):
                    report.dropped_blocked += 1
                    continue
                prepared = prepare(raw, venues, create_stubs=True, write_stubs=not dry_run)
                if prepared is None:
                    report.out_of_area[raw.venue_name] += 1
                    continue
                verdict = classify(prepared, always_music=adapter.always_music)
                if not verdict.publish:
                    report.not_music[verdict.reason] += 1
                    continue
                scored.append(Scored(prepared, verdict, adapter.authority, backfill=first_run))
    finally:
        if own_http:
            http.__exit__(None, None, None)

    report.stub_venues = [f"{v.name} (src/content/venues/{v.slug}.md)" for v in venues.created]
    candidates = cluster(scored)
    report.candidates = len(candidates)
    report.changes = apply(candidates, state, venues, gigs_dir, now=now, healthy_adapters=healthy, dry_run=dry_run)
    if not dry_run:
        state.save(data_dir)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="belfast_gigs")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="scrape all sources and update src/content/gigs")
    run_p.add_argument("--dry-run", action="store_true", help="fetch and report, but write nothing")
    run_p.add_argument("--only", nargs="+", choices=sorted(ADAPTERS), help="run just these sources")
    args = parser.parse_args(argv)

    if args.command == "run":
        report = run(args.only, dry_run=args.dry_run)
        sys.stdout.write(report.publish())
        broken = [s for s in report.sources if s.status == "failed"]
        return 1 if broken and len(broken) == len([s for s in report.sources if s.status != "skipped"]) else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
