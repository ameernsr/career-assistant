import pytest

from core.roadmap import compute_roadmap
from core.taxonomy import Taxonomy


@pytest.fixture
def tax(mini_dict):
    return Taxonomy.from_dict(mini_dict)


def test_beginner_junior_gets_targets_plus_prerequisites_in_order(tax):
    rm = compute_roadmap(tax, "data_analyst", "junior", known=set(), not_known=set())
    assert rm.stages == [
        ["computer_basics", "statistics"],
        ["excel", "relational_db"],
        ["sql_basics"],
    ]
    assert rm.known == []


def test_target_levels_are_cumulative(tax):
    rm = compute_roadmap(tax, "data_analyst", "mid", known=set(), not_known=set())
    assert rm.stages == [
        ["computer_basics", "statistics"],
        ["excel", "python_basics", "relational_db"],
        ["pandas", "sql_basics"],
        ["bi_tools"],
    ]


def test_knowing_a_concept_implies_its_prerequisites(tax):
    rm = compute_roadmap(tax, "data_analyst", "junior", known={"sql_basics"}, not_known=set())
    assert rm.stages == [["excel", "statistics"]]
    assert rm.known == ["computer_basics", "relational_db", "sql_basics"]


def test_explicit_not_known_beats_implicit_prerequisite(tax):
    # Knows SQL, but says «پایگاه داده‌ی رابطه‌ای بلد نیستم»: relational_db must come back.
    rm = compute_roadmap(tax, "data_analyst", "junior", known={"sql_basics"}, not_known={"relational_db"})
    assert rm.stages == [["excel", "relational_db", "statistics"]]
    assert "relational_db" not in rm.known


def test_correction_i_dont_know_excel_puts_it_back(tax):
    # A-08: «من اکسل بلد نیستم» after excel was marked known.
    rm = compute_roadmap(tax, "data_analyst", "junior", known={"excel", "sql_basics"}, not_known={"excel"})
    assert ["excel", "statistics"] in rm.stages


def test_unknown_concept_ids_are_ignored(tax):
    rm = compute_roadmap(tax, "data_analyst", "junior", known={"sql_basics", "made_up_skill"}, not_known={"also_fake"})
    assert rm.stages == [["excel", "statistics"]]
    assert "made_up_skill" not in rm.known


def test_unknown_role_raises_clear_error(tax):
    from core.taxonomy import TaxonomyError

    with pytest.raises(TaxonomyError, match="pilot"):
        compute_roadmap(tax, "pilot", "junior", known=set(), not_known=set())


def test_roadmap_for_arbitrary_targets_b10(tax):
    from core.roadmap import compute_roadmap_for_targets

    # A job asks for bi_tools; the user knows excel → still needs sql chain + bi.
    rm = compute_roadmap_for_targets(tax, {"bi_tools"}, known={"excel"}, not_known=set(), label="job:42")
    assert rm.role_id == "job:42"
    assert rm.stages == [["relational_db"], ["sql_basics"], ["bi_tools"]]


def test_summary_names_exactly_the_roadmap_concepts(tax):
    from core.summary import summarize

    rm = compute_roadmap(tax, "data_analyst", "junior", known={"sql_basics"}, not_known=set())
    text = summarize(rm, tax)
    assert "تحلیلگر داده" in text and "اکسل" in text and "آمار" in text
    for cid in tax.concepts:  # A-09: nothing outside the roadmap is mentioned
        if cid not in {"excel", "statistics"}:
            assert tax.concepts[cid]["name_fa"] not in text
