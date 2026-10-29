"""Role/concept taxonomy: the shared skill vocabulary of both modules (A-02, A-03)."""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from core.text_fa import skill_key

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "taxonomy.json"


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
