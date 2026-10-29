"""Deterministic learning roadmap (A-05): target concepts + prerequisites − known, in study order."""
from __future__ import annotations

import networkx as nx

from core.schemas import Roadmap
from core.taxonomy import Taxonomy, TaxonomyError

LEVELS = ["junior", "mid", "senior"]


def compute_roadmap(tax: Taxonomy, role_id: str, target_level: str, known: set[str], not_known: set[str]) -> Roadmap:
    if role_id not in tax.roles:
        raise TaxonomyError(f"unknown role: {role_id}")
    role = tax.roles[role_id]
    known = {c for c in known if c in tax.concepts}  # ids invented by the LLM are dropped (A-04)
    not_known = {c for c in not_known if c in tax.concepts}
    target: set[str] = set()
    for level in LEVELS[: LEVELS.index(target_level) + 1]:
        target |= set(role["levels"].get(level, []))
    closure = set(target)
    for cid in target:
        closure |= nx.ancestors(tax.graph, cid)
    effective_known = set(known)
    for cid in known:
        effective_known |= nx.ancestors(tax.graph, cid)  # team decision: knowing X implies X's prerequisites
    effective_known -= set(not_known)  # an explicit «بلد نیستم» always wins
    todo = closure - effective_known
    stages = [sorted(gen) for gen in nx.topological_generations(tax.graph.subgraph(todo))]
    return Roadmap(
        role_id=role_id, target_level=target_level, known=sorted(effective_known & closure), stages=stages
    )
