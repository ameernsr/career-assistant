"""Role/concept taxonomy: the shared skill vocabulary of both modules (A-02, A-03)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import networkx as nx

from core.text_fa import fa_normalize, skill_key

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "taxonomy.json"

# Aliases too ambiguous to search for inside running text (fine as exact requirement phrases).
TEXT_SCAN_STOPWORDS = {
    "go", "rest", "net", "ts", "js", "ml", "bi", "api", "web", "http", "https", "content", "growth", "brand",
    "marketing", "network", "interview", "tax", "audit", "shell", "cache", "container", "reporting", "dashboard",
    "security", "programming", "algorithm", "algorithms", "english", "math", "storytelling", "stakeholder",
    "budgeting", "forecasting", "recruitment", "recruiting", "screening", "sourcing", "compensation", "accounting",
    "مصاحبه", "شبکه", "محتوا", "برند", "امنیت", "بودجه", "مالیات", "انگلیسی", "وب", "کش", "صف پیام",
}


class TaxonomyError(ValueError):
    """The taxonomy file is inconsistent (cycle, dangling id, duplicate)."""


class Taxonomy:
    def __init__(self, roles: dict[str, dict], concepts: dict[str, dict], graph: nx.DiGraph):
        self.roles = roles
        self.concepts = concepts
        self.graph = graph  # edge prerequisite → dependent
        self._lookup: dict[str, str] = {}
        for cid, c in concepts.items():
            for name in [cid, c.get("name_fa", ""), c.get("name_en", ""), *c.get("aliases", [])]:
                if name:
                    self._lookup.setdefault(skill_key(name), cid)

    @classmethod
    def from_dict(cls, data: dict) -> "Taxonomy":
        concepts: dict[str, dict] = {}
        for c in data["concepts"]:
            if c["id"] in concepts:
                raise TaxonomyError(f"duplicate concept id: {c['id']}")
            concepts[c["id"]] = c
        roles = {r["id"]: r for r in data["roles"]}
        graph = nx.DiGraph()
        graph.add_nodes_from(concepts)
        for cid, c in concepts.items():
            for pre in c.get("prerequisites", []):
                if pre not in concepts:
                    raise TaxonomyError(f"{cid}: unknown prerequisite {pre}")
                graph.add_edge(pre, cid)
        for rid, r in roles.items():
            for level, ids in r["levels"].items():
                for cid in ids:
                    if cid not in concepts:
                        raise TaxonomyError(f"role {rid}/{level}: unknown concept {cid}")
        tax = cls(roles, concepts, graph)
        tax.check_dag()
        return tax

    def find_in_text(self, text: str) -> set[str]:
        """Concept ids whose names/aliases appear as whole words in free text (job ads, resumes)."""
        if not hasattr(self, "_text_rx"):
            names: dict[str, str] = {}
            for cid, c in self.concepts.items():
                for name in [c.get("name_fa", ""), c.get("name_en", ""), *c.get("aliases", [])]:
                    n = fa_normalize(name).lower()
                    if len(n) >= 2 and n not in TEXT_SCAN_STOPWORDS:
                        names.setdefault(n, cid)
            alternation = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
            self._text_rx = re.compile(rf"(?<![\w.#+])(?:{alternation})(?![\w#+])")
            self._text_names = names
        return {self._text_names[m] for m in self._text_rx.findall(fa_normalize(text or "").lower())}

    def resolve(self, text: str) -> str | None:
        """Map a free-text skill mention (any language, alias, spelling) to a concept id, or None."""
        return self._lookup.get(skill_key(text or "")) or None

    def check_dag(self) -> None:
        try:
            cycle = nx.find_cycle(self.graph)
        except nx.NetworkXNoCycle:
            return
        path = " → ".join([u for u, _ in cycle] + [cycle[0][0]])
        raise TaxonomyError(f"prerequisite cycle: {path}")


def load_taxonomy(path: Path | str = DEFAULT_PATH) -> Taxonomy:
    """Load and validate data/taxonomy.json. Raises TaxonomyError on any inconsistency."""
    return Taxonomy.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
