"""The only module that talks to the network. Polite by construction:

- robots.txt is checked before every request (Scrapling's fetchers don't do this);
- requests identify the bot and never impersonate a browser fingerprint;
- at least MIN_DELAY seconds between requests to the same host;
- responses are cached for the length of one run.
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlencode, urlsplit

from protego import Protego
from scrapling.fetchers import FetcherSession
from scrapling.parser import Selector

USER_AGENT = "Mozilla/5.0 (compatible; BelfastGigsBot/1.0; +https://github.com/Chrisshar/belfast-gigs)"
MIN_DELAY = 2.0


class RobotsDisallowed(Exception):
    pass


class HttpError(Exception):
    def __init__(self, url: str, status: int):
        super().__init__(f"HTTP {status} for {url}")
        self.url, self.status = url, status


class Http:
    def __init__(self, min_delay: float = MIN_DELAY):
        self.min_delay = min_delay
        self._robots: dict[str, Protego | bool] = {}
        self._last_request: dict[str, float] = {}
        self._cache: dict[str, str] = {}
        self._manager = FetcherSession(
            impersonate=None,  # no browser fingerprint spoofing
            stealthy_headers=False,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-GB,en;q=0.8"},
            timeout=30,
            retries=2,
            retry_delay=3,
        )
        self._session = None

    def __enter__(self) -> Http:
        self._session = self._manager.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        self._manager.__exit__(*exc)
        self._session = None

    def _throttle(self, host: str) -> None:
        wait = self._last_request.get(host, 0) + self.min_delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request[host] = time.monotonic()

    def _raw_get(self, url: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
        assert self._session is not None, "use Http as a context manager"
        self._throttle(urlsplit(url).netloc)
        resp = self._session.get(url, headers=headers or {})
        return resp.status, resp.body.decode(resp.encoding or "utf-8", errors="replace")

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            status, body = self._raw_get(f"{origin}/robots.txt")
            if status >= 500:
                rules: Protego | bool = False  # server trouble: back off rather than guess
            elif status >= 400:
                rules = True  # no robots.txt means no restrictions
            else:
                # Protego follows RFC 9309, wildcards and "$" included; Python's own
                # urllib.robotparser doesn't, and reads "Allow: /js/*/*/data?*$" wrongly.
                rules = Protego.parse(body)
            self._robots[origin] = rules
        rules = self._robots[origin]
        return rules if isinstance(rules, bool) else rules.can_fetch(url, USER_AGENT)

    def get_text(self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> str:
        full = f"{url}?{urlencode(params, doseq=True)}" if params else url
        if full in self._cache:
            return self._cache[full]
        if not self.allowed(full):
            raise RobotsDisallowed(full)
        status, body = self._raw_get(full, headers)
        if status >= 400:
            raise HttpError(_redact(full), status)
        self._cache[full] = body
        return body

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return json.loads(self.get_text(url, params, headers={"Accept": "application/json"}))


def parse_html(html: str, url: str = "") -> Selector:
    """Parse HTML for CSS selection (.css(), .get_all_text(), .attrib). Adapters use this
    rather than importing Scrapling, so a Scrapling upgrade only touches this file."""
    return Selector(html, url=url)


def _redact(url: str) -> str:
    """Keep API keys out of logs and error messages."""
    for key in ("apikey", "api_key", "key"):
        if f"{key}=" in url:
            head, _, tail = url.partition(f"{key}=")
            url = head + f"{key}=REDACTED" + ("&" + tail.split("&", 1)[1] if "&" in tail else "")
    return url
