"""robots.txt matcher with `*` and `$` wildcard support (Google/RFC 9309 rules).

The stdlib urllib.robotparser ignores wildcards, so rules like `Disallow: *?*` (Jobvision,
IranTalent) would silently be treated as allowed. We implement the spec ourselves:
- consecutive User-agent lines share one group,
- the most specific matching group wins (our token, else `*`),
- the longest matching rule wins; Allow wins a tie.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass
class _Group:
    agents: list[str] = field(default_factory=list)
    rules: list[tuple[bool, str]] = field(default_factory=list)  # (allow, pattern)
    crawl_delay: float | None = None


def _pattern_to_regex(pattern: str) -> re.Pattern:
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in pattern)
    return re.compile("^" + regex + ("$" if anchored else ""))


class RobotsRules:
    def __init__(self, text: str | None, available: bool = True):
        self.available = available
        self.groups: list[_Group] = []
        self.sitemaps: list[str] = []
        if text:
            self._parse(text)

    def _parse(self, text: str) -> None:
        current: _Group | None = None
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if current is None or not last_was_agent:
                    current = _Group()
                    self.groups.append(current)
                current.agents.append(value.lower())
                last_was_agent = True
                continue
            last_was_agent = False
            if key == "sitemap":
                self.sitemaps.append(value)
            elif current is None:
                continue
            elif key in ("allow", "disallow"):
                if value:  # empty Disallow means allow everything
                    current.rules.append((key == "allow", value))
            elif key == "crawl-delay":
                try:
                    current.crawl_delay = float(value)
                except ValueError:
                    pass

    def _group_for(self, agent: str) -> _Group | None:
        agent = agent.lower()
        best, best_len = None, -1
        for g in self.groups:
            for a in g.agents:
                if a == "*" and best_len < 0:
                    best, best_len = g, 0
                elif a != "*" and a in agent and len(a) > best_len:
                    best, best_len = g, len(a)
        return best

    def can_fetch(self, agent: str, url: str) -> bool:
        if not self.available:
            return False  # robots.txt unreachable (5xx / blocked): stay out
        group = self._group_for(agent)
        if group is None:
            return True
        parts = urlsplit(url)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        verdict, longest = True, -1
        for allow, pattern in group.rules:
            if _pattern_to_regex(pattern).match(path):
                if len(pattern) > longest or (len(pattern) == longest and allow):
                    verdict, longest = allow, len(pattern)
        return verdict

    def crawl_delay(self, agent: str) -> float | None:
        group = self._group_for(agent)
        return group.crawl_delay if group else None
