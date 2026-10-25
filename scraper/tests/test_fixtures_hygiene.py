"""Fixtures are pages captured from venue and ticket sites. Those pages can carry the sites' own
browser keys (e.g. a Google Maps embed key), which secret scanning flags once committed.
Redact them when capturing: replace the key with REDACTED-THIRD-PARTY-KEY."""

import re

from conftest import FIXTURES

KEY_PATTERNS = re.compile(
    r"AIza[0-9A-Za-z_\-]{30,}"  # Google API keys
    r"|sk-ant-[0-9A-Za-z_\-]{10,}"  # Anthropic
    r"|sk_live_[0-9A-Za-z]{10,}|pk_live_[0-9A-Za-z]{10,}"  # Stripe
    r"|gh[pousr]_[0-9A-Za-z]{30,}"  # GitHub
    r"|AKIA[0-9A-Z]{16}"  # AWS
    r"|xox[abpr]-[0-9A-Za-z-]{10,}"  # Slack
)


def test_no_keys_in_fixtures():
    found = []
    for path in FIXTURES.rglob("*"):
        if path.is_file():
            for m in KEY_PATTERNS.finditer(path.read_text(encoding="utf-8", errors="ignore")):
                found.append(f"{path.relative_to(FIXTURES)}: {m.group(0)[:8]}…")
    assert not found, "Redact these before committing: " + ", ".join(found)
