"""Command line.

  python -m belfast_gigs run [--dry-run] [--only SOURCE ...] [--no-llm] [--save FILE]
  python -m belfast_gigs apply FILE

A run has two halves. collect() fetches, normalises and classifies (network and Claude calls);
finish() writes gigs, venues and state into whatever checkout is on disk. `run --save` keeps the
collected half, so CI can reset to a newer main after a push conflict and `apply` it again
without re-scraping or paying for Claude twice.
"""

from __future__ import annotations

import argparse
import pickle
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .adapters import ADAPTERS, MissingCredentials
from .dates import iso_utc, london_today, now_utc
from .http import Http
from .issues import sync as sync_issues
from .llm import Classifier, fingerprint
from .paths import DATA_DIR, GIGS_DIR, VENUES_DIR
from .pipeline.classify import classify, with_llm
from .pipeline.merge import Scored, cluster
from .pipeline.normalise import is_pass, prepare
from .pipeline.write import apply
from .report import Report, SourceResult
from .state import State
from .venues import VenueIndex

CACHE_DAYS = 60


@dataclass
class Collected:
    now: datetime
    report: Report
    scored: list[Scored] = field(default_factory=list)
    healthy: set[str] = field(default_factory=set)
    rejected_keys: set[str] = field(default_factory=set)  # listings judged not to be gigs this run
    source_health: dict[str, dict] = field(default_factory=dict)  # only the adapters that ran
    stubs: list[tuple[str, str, str | None]] = field(default_factory=list)  # (slug, name, address)
    llm_cache: dict[str, dict] = field(default_factory=dict)
    llm_usage: dict[str, dict] = field(default_factory=dict)
    llm_usage_file: str = ""


def collect(
    only: list[str] | None = None,
    *,
    dry_run: bool = False,
    use_llm: bool = True,
    venues_dir: Path = VENUES_DIR,
    data_dir: Path = DATA_DIR,
    now: datetime | None = None,
    http: Http | None = None,
) -> Collected:
    now = now or now_utc()
    today = london_today(now)
    state = State.load(data_dir)
    venues = VenueIndex.load(venues_dir)
    classifier = Classifier(data_dir, today[:7], enabled=use_llm)
    out = Collected(now=now, report=Report(dry_run=dry_run))
    report = out.report
    pending = []  # (prepared, rules verdict, adapter, forced music?, first_run, fingerprint)
    listings: dict[str, dict] = {}

    own_http = http is None
    http = http or Http()
    if own_http:
        http.__enter__()
    try:
        for name in only or list(ADAPTERS):
            adapter = ADAPTERS[name]()
            health = dict(state.source_health.get(name, {"runs_ok": 0, "consecutive_failures": 0}))
            first_run = health.get("runs_ok", 0) == 0
            try:
                raw_events = adapter.fetch(http)
            except MissingCredentials as exc:
                report.sources.append(SourceResult(name, "skipped", detail=str(exc)))
                continue
            except Exception as exc:  # one broken source must not stop the run
                raw_events, error = [], f"{type(exc).__name__}: {exc}"[:300]
            else:
                error = None if raw_events else "returned no events"
            health["last_run"] = iso_utc(now)
            health["last_count"] = len(raw_events)
            if error:
                health["consecutive_failures"] = health.get("consecutive_failures", 0) + 1
                health["last_error"] = error
                report.sources.append(SourceResult(name, "failed", 0, error))
                out.source_health[name] = health
                continue
            health["runs_ok"] = health.get("runs_ok", 0) + 1
            health["consecutive_failures"] = 0
            health.pop("last_error", None)
            out.source_health[name] = health
            out.healthy.add(name)
            report.sources.append(SourceResult(name, "ok", len(raw_events), "first run: gigs marked as backfill" if first_run else ""))

            for raw in raw_events:
                if (raw.end_date or raw.date) < today:
                    report.dropped_past += 1
                    continue
                if is_pass(raw.title) or state.overrides.blocked(raw.title):
                    report.dropped_blocked += 1
                    continue
                prepared = prepare(raw, venues, create_stubs=True, write_stubs=False)
                if prepared is None:
                    report.out_of_area[raw.venue_name] += 1
                    continue
                forced = adapter.always_music or state.overrides.allowed(raw.title)
                verdict = classify(prepared, always_music=forced)
                if raw.is_music_hint is False and not forced:
                    report.not_music[verdict.reason] += 1  # the source itself says so: no need to ask Claude
                    out.rejected_keys.add(raw.source_key)
                    continue
                fp = fingerprint(raw.source_key, raw.title, prepared.venue.name, raw.date)
                listings[fp] = {
                    "title": raw.title,
                    "support_listed": raw.support,
                    "venue": prepared.venue.name,
                    "date": raw.date,
                    "source_tags": raw.categories,
                }
                pending.append((prepared, verdict, adapter, forced, first_run, fp))
    finally:
        if own_http:
            http.__exit__(None, None, None)

    llm = classifier.classify(listings, today) if listings else {}
    for prepared, rules_verdict, adapter, forced, first_run, fp in pending:
        verdict = with_llm(rules_verdict, llm.get(fp), forced)
        if not verdict.publish:
            report.not_music[verdict.reason.split(" (")[0]] += 1
            out.rejected_keys.add(prepared.raw.source_key)
            continue
        found = llm.get(fp)
        if found and found.get("headliner") and not prepared.raw.headliner:
            prepared.headliner = found["headliner"]
            prepared.support = prepared.support or found.get("support", [])
        out.scored.append(Scored(prepared, verdict, adapter.authority, first_run, list(found.get("genres", [])) if found else []))

    report.llm = {
        "calls": classifier.calls,
        "checked": len(listings),
        "month_cost": classifier.month_usage["cost_usd"],
        "skipped": classifier.skipped_reason,
    }
    report.llm_errors = classifier.errors
    classifier.prune_cache((now - timedelta(days=CACHE_DAYS)).date().isoformat())
    classifier.save(cache=False)  # spend is recorded now, whatever happens next
    out.llm_cache, out.llm_usage, out.llm_usage_file = classifier.cache, classifier.usage, classifier.usage_path.name
    out.stubs = [(v.slug, v.name, next((p.raw.address for p, *_ in pending if p.venue is v), None)) for v in venues.created]
    return out


def finish(
    collected: Collected,
    *,
    dry_run: bool = False,
    gigs_dir: Path = GIGS_DIR,
    venues_dir: Path = VENUES_DIR,
    data_dir: Path = DATA_DIR,
) -> Report:
    """Write a collected run into the checkout on disk. Safe to repeat on a fresher checkout."""
    state = State.load(data_dir)
    state.source_health.update(collected.source_health)
    venues = VenueIndex.load(venues_dir)
    for slug, name, address in collected.stubs:
        if slug not in venues.by_slug:
            venues.create_stub(name, address, write=not dry_run, slug=slug)
    report = collected.report
    report.stub_venues = [f"{name} (src/content/venues/{slug}.md)" for slug, name, _ in collected.stubs]
    candidates = cluster(collected.scored)
    report.candidates = len(candidates)
    report.changes = apply(
        candidates,
        state,
        venues,
        gigs_dir,
        now=collected.now,
        healthy_adapters=collected.healthy,
        rejected_keys=collected.rejected_keys,
        dry_run=dry_run,
    )
    if not dry_run:
        state.save(data_dir)
        classifier = Classifier(data_dir, london_today(collected.now)[:7], enabled=False)
        classifier.cache = collected.llm_cache
        classifier.usage = collected.llm_usage
        classifier.save(cache=True)
        report.issue_problems = sync_issues(
            state.source_health,
            gigs_dir,
            venues_dir,
            report.changes.review,
            collected.report.llm_errors,
            london_today(collected.now),
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="belfast_gigs")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="scrape all sources and update src/content/gigs")
    run_p.add_argument("--dry-run", action="store_true", help="fetch and report, but write no gigs or state")
    run_p.add_argument("--only", nargs="+", choices=sorted(ADAPTERS), help="run just these sources")
    run_p.add_argument("--no-llm", action="store_true", help="don't ask Claude; rules only")
    run_p.add_argument("--save", type=Path, help="also save the collected results here, for `apply`")
    apply_p = sub.add_parser("apply", help="write previously collected results into the current checkout")
    apply_p.add_argument("file", type=Path)
    bench_p = sub.add_parser("benchmark", help="coverage check: compare saved Songkick/Eventbrite pages with the site")
    bench_p.add_argument("inbox", type=Path, help="folder of pages saved from your browser")
    args = parser.parse_args(argv)

    if args.command == "benchmark":
        from . import benchmark

        if not args.inbox.is_dir():
            parser.error(f"{args.inbox} is not a folder")
        sys.stdout.write(benchmark.report(benchmark.check(args.inbox)))
        return 0
    if args.command == "run":
        collected = collect(args.only, dry_run=args.dry_run, use_llm=not args.no_llm)
        if args.save:
            args.save.write_bytes(pickle.dumps(collected))
        report = finish(collected, dry_run=args.dry_run)
    else:
        report = finish(pickle.loads(args.file.read_bytes()))
    sys.stdout.write(report.publish())
    ran = [s for s in report.sources if s.status != "skipped"]
    return 1 if ran and all(s.status == "failed" for s in ran) else 0


if __name__ == "__main__":
    sys.exit(main())
