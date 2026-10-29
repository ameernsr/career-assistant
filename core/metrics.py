"""IR metrics for RFP 10.2 (binary relevance). Unjudged items count as not relevant."""
from __future__ import annotations

import math


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return sum(1 for j in ranked[:k] if j in relevant) / k


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return sum(1 for j in ranked[:k] if j in relevant) / max(1, len(relevant))


def mrr(ranked: list[str], relevant: set[str]) -> float:
    return next((1 / i for i, j in enumerate(ranked, 1) if j in relevant), 0.0)


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(1 / math.log2(i + 1) for i, j in enumerate(ranked[:k], 1) if j in relevant)
    idcg = sum(1 / math.log2(i + 1) for i in range(1, min(k, len(relevant)) + 1))
    return dcg / idcg if idcg else 0.0
