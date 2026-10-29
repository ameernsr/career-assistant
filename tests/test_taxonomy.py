import pytest

from core.taxonomy import Taxonomy, TaxonomyError


def _concept(d, cid):
    return next(c for c in d["concepts"] if c["id"] == cid)


def test_cycle_is_rejected_with_its_path(mini_dict):
    # computer_basics → excel already exists; adding excel → computer_basics closes a loop.
    _concept(mini_dict, "computer_basics")["prerequisites"] = ["excel"]
    with pytest.raises(TaxonomyError) as err:
        Taxonomy.from_dict(mini_dict)
    msg = str(err.value)
    assert "cycle" in msg.lower()
    assert "computer_basics" in msg and "excel" in msg


def test_dangling_prerequisite_is_rejected(mini_dict):
    _concept(mini_dict, "pandas")["prerequisites"].append("numpy")  # numpy is not defined
    with pytest.raises(TaxonomyError, match="numpy"):
        Taxonomy.from_dict(mini_dict)


def test_role_referencing_unknown_concept_is_rejected(mini_dict):
    mini_dict["roles"][0]["levels"]["senior"].append("spark")
    with pytest.raises(TaxonomyError, match="spark"):
        Taxonomy.from_dict(mini_dict)


def test_duplicate_concept_id_is_rejected(mini_dict):
    mini_dict["concepts"].append({"id": "excel", "name_fa": "x", "name_en": "x", "aliases": [], "prerequisites": []})
    with pytest.raises(TaxonomyError, match="excel"):
        Taxonomy.from_dict(mini_dict)


def test_valid_taxonomy_loads(mini_dict):
    tax = Taxonomy.from_dict(mini_dict)
    assert "data_analyst" in tax.roles


@pytest.mark.parametrize(
    "text, expected",
    [
        ("excel", "excel"),                 # id
        ("Excel", "excel"),                 # English name, other case
        ("اکسل", "excel"),                  # Persian name
        ("اكسل", "excel"),                  # Arabic kaf (common in pasted text)
        ("  Microsoft Excel ", "excel"),    # alias with spaces
        ("Power BI", "bi_tools"),
        ("پایتون", "python_basics"),
        ("SQL", "sql_basics"),
    ],
)
def test_resolve_maps_names_and_aliases_to_id(mini_dict, text, expected):
    assert Taxonomy.from_dict(mini_dict).resolve(text) == expected


def test_resolve_unknown_returns_none(mini_dict):
    tax = Taxonomy.from_dict(mini_dict)
    assert tax.resolve("Kubernetes") is None
    assert tax.resolve("") is None


def test_load_taxonomy_reads_json_file(tmp_path, mini_dict):
    import json

    from core.taxonomy import load_taxonomy

    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps(mini_dict, ensure_ascii=False), encoding="utf-8")
    assert load_taxonomy(path).resolve("آمار") == "statistics"


def test_real_taxonomy_meets_rfp_minimums():
    """A-02 guard on the team's real file: ≥10 roles, ≥3 domains, junior/mid/senior each, valid DAG."""
    from core.taxonomy import DEFAULT_PATH, load_taxonomy

    if not DEFAULT_PATH.exists():
        pytest.skip("data/taxonomy.json not written yet (P1)")
    tax = load_taxonomy()
    assert len(tax.roles) >= 10
    assert len({r["domain"] for r in tax.roles.values()}) >= 3
    for rid, role in tax.roles.items():
        assert set(role["levels"]) == {"junior", "mid", "senior"}, rid
