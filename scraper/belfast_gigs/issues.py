"""Keep GitHub issues in step with the scraper's health, so GitHub emails the repo owner.

- "Source broken: <name>": opened after BROKEN_AFTER failed runs in a row, closed when it recovers.
- "Review queue": one rolling issue listing every gig and venue flagged needs_review; closed when empty.

Runs only on GitHub Actions (needs GITHUB_TOKEN and GITHUB_REPOSITORY); elsewhere it does nothing.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import frontmatter

BROKEN_AFTER = 2
LABEL = "scraper"
REVIEW_TITLE = "Review queue"


class GitHub:
    def __init__(self) -> None:
        self.token = os.environ.get("GITHUB_TOKEN")
        self.repo = os.environ.get("GITHUB_REPOSITORY")
        self._open: dict[str, int] | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.repo)

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{self.repo}{path}",
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "belfast-gigs-scraper",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read() or b"null")

    def open_issues(self) -> dict[str, int]:
        if self._open is None:
            issues = self._request("GET", f"/issues?state=open&labels={LABEL}&per_page=100")
            self._open = {i["title"]: i["number"] for i in issues if "pull_request" not in i}
        return self._open

    def upsert(self, title: str, body: str) -> None:
        number = self.open_issues().get(title)
        if number is None:
            created = self._request("POST", "/issues", {"title": title, "body": body, "labels": [LABEL]})
            self.open_issues()[title] = created["number"]
        else:
            self._request("PATCH", f"/issues/{number}", {"body": body})

    def close(self, title: str, comment: str) -> None:
        number = self.open_issues().pop(title, None)
        if number is not None:
            self._request("POST", f"/issues/{number}/comments", {"body": comment})
            self._request("PATCH", f"/issues/{number}", {"state": "closed", "state_reason": "completed"})


def broken_source_body(name: str, health: dict) -> str:
    return (
        f"The **{name}** source has failed {health.get('consecutive_failures')} scrape runs in a row.\n\n"
        f"Last error: `{health.get('last_error', 'unknown')}`\n\n"
        "Gigs already listed from this source stay on the site while it's broken; they're only flagged or "
        "removed after the source runs cleanly again without them.\n\n"
        "Usual causes: the site changed its layout or URL, it's blocking the scraper, or it's down. "
        f"Try `python -m belfast_gigs run --dry-run --only {name}` locally to see the error. "
        "This issue closes itself when the source recovers."
    )


def review_body(gigs_dir: Path, venues_dir: Path, notes: list[str], llm_problems: list[str]) -> str | None:
    gigs, venues = [], []
    for path in sorted(gigs_dir.glob("*.md")):
        data, _ = frontmatter.read(path)
        if data.get("needs_review"):
            c = data.get("classification") or {}
            how = f"{c.get('method', '?')}, confidence {c.get('confidence', '?')}" if c else "flagged"
            gigs.append(f"- [ ] `{path.stem}`: {data.get('headliner')} at {data.get('venue')} ({how})")
    for path in sorted(venues_dir.glob("*.md")):
        data, _ = frontmatter.read(path)
        if data.get("needs_review"):
            venues.append(f"- [ ] `{path.stem}`: {data.get('name')}")
    if not (gigs or venues or llm_problems):
        return None
    parts = ["Things the scraper wasn't sure about. Fix them in the CMS (`/admin`) or the files, then untick "
             "**needs review**. The scraper won't flag a gig again once a human has cleared it.\n"]
    if llm_problems:
        parts += ["### Claude classification problems (last run)", *(f"- {p}" for p in llm_problems), ""]
    if gigs:
        parts += [f"### Gigs ({len(gigs)})", *gigs, ""]
    if notes:
        parts += ["Notes from the last run:", *(f"- {n}" for n in notes), ""]
    if venues:
        parts += [f"### Venues ({len(venues)})", "Check the name, address and aliases.", *venues, ""]
    return "\n".join(parts)


def sync(source_health: dict[str, dict], gigs_dir: Path, venues_dir: Path, notes: list[str], llm_problems: list[str], today: str) -> list[str]:
    """Returns a list of problems talking to GitHub (never raises: issues are a convenience)."""
    gh = GitHub()
    if not gh.enabled:
        return []
    problems = []
    try:
        for name, health in sorted(source_health.items()):
            title = f"Source broken: {name}"
            if health.get("consecutive_failures", 0) >= BROKEN_AFTER:
                gh.upsert(title, broken_source_body(name, health))
            elif health.get("consecutive_failures", 0) == 0:
                gh.close(title, f"Recovered: the {today} run scraped {health.get('last_count', 0)} listings.")
        body = review_body(gigs_dir, venues_dir, notes, llm_problems)
        if body:
            gh.upsert(REVIEW_TITLE, body)
        else:
            gh.close(REVIEW_TITLE, "Nothing left to review.")
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        problems.append(f"couldn't update GitHub issues: {exc}")
    return problems
