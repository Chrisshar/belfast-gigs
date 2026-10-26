"""Read and write Markdown files with YAML frontmatter, deterministically.

Every string is written double-quoted, so dates ("2026-11-06") and times ("19:30") can never be
re-read as YAML dates or sexagesimal integers, and the output is stable across runs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style='"')


def _float(dumper: yaml.SafeDumper, value: float) -> yaml.ScalarNode:
    # 18.0 -> 18, 28.5 -> 28.5: what a human (or the CMS) would write.
    if value.is_integer():
        return dumper.represent_int(int(value))
    return dumper.represent_scalar("tag:yaml.org,2002:float", repr(value))


def _dict(dumper: yaml.SafeDumper, data: dict) -> yaml.MappingNode:
    # Keys stay plain (`date:` not `"date":`); only values get quoted.
    pairs = [(dumper.represent_scalar("tag:yaml.org,2002:str", str(k)), dumper.represent_data(v)) for k, v in data.items()]
    return yaml.MappingNode("tag:yaml.org,2002:map", pairs, flow_style=False)


_Dumper.add_representer(str, _str)
_Dumper.add_multi_representer(str, _str)  # str subclasses too (parsers hand back their own string types)
_Dumper.add_representer(float, _float)
_Dumper.add_representer(dict, _dict)


# The header ends at the next line that is just "---": a "---" inside a value (some ticket
# URLs have one) must not end it.
_FENCE = re.compile(r"---[ \t]*\r?\n(?P<fm>.*?)^---[ \t]*\r?$", re.S | re.M)


def read(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    m = _FENCE.match(text)
    if not m:
        return {}, text
    return yaml.safe_load(m["fm"]) or {}, text[m.end() :].lstrip("\r\n")


def dumps(data: dict[str, Any], body: str = "") -> str:
    fm = yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=False)
    out = f"---\n{fm}---\n"
    if body.strip():
        out += body if body.endswith("\n") else body + "\n"
    return out


def write(path: Path, data: dict[str, Any], body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(data, body), encoding="utf-8", newline="\n")
