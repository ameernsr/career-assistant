import pytest

from core.metrics import mrr, ndcg_at_k, precision_at_k, recall_at_k

# Ranked list of job ids and the set judged relevant (worked by hand).
RANKED = ["a", "b", "c", "d", "e", "f"]
RELEVANT = {"b", "d", "z"}  # z is relevant but never retrieved


def test_precision_at_5():
    assert precision_at_k(RANKED, RELEVANT, 5) == pytest.approx(2 / 5)


def test_recall_at_10_counts_all_relevant_items():
    assert recall_at_k(RANKED, RELEVANT, 10) == pytest.approx(2 / 3)


def test_mrr_uses_first_relevant_rank():
    assert mrr(RANKED, RELEVANT) == pytest.approx(1 / 2)
    assert mrr(["x", "y"], RELEVANT) == 0.0


def test_ndcg_at_10_binary_gains():
    # DCG = 1/log2(3) + 1/log2(5); IDCG (3 relevant) = 1/log2(2) + 1/log2(3) + 1/log2(4)
    dcg = 1 / 1.5849625 + 1 / 2.3219281
    idcg = 1 + 1 / 1.5849625 + 1 / 2
    assert ndcg_at_k(RANKED, RELEVANT, 10) == pytest.approx(dcg / idcg, abs=1e-6)
    assert ndcg_at_k(RANKED, set(), 10) == 0.0
