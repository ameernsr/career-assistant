import pytest

from core.conversation import MAX_QUESTIONS, ConversationState, TurnExtraction, known_sets, next_turn
from core.llm import LLMError
from core.schemas import ConceptClaim, ProfileDelta, UserProfile
from core.taxonomy import Taxonomy


@pytest.fixture
def tax(mini_dict):
    return Taxonomy.from_dict(mini_dict)


class FakeLLM:
    """Stands in for core.llm.LLM: returns queued objects (or raises queued exceptions) from chat_json."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def chat_json(self, messages, model_cls, **_):
        self.prompts.append(messages)
        r = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(r, Exception):
            raise r
        assert isinstance(r, model_cls), f"expected {model_cls.__name__}"
        return r


def test_everything_in_first_message_ends_without_questions(tax):
    llm = FakeLLM(TurnExtraction(target_role="data_analyst", target_level="junior", current_level="none",
                                 claims=[ConceptClaim(concept_id="excel", proficiency="used")], enough_info=True))
    reply, st = next_turn(ConversationState(), "دانشجوام، اکسل کار کردم، می‌خوام تحلیلگر داده‌ی جونیور بشم", llm, tax)
    assert st.done and st.questions_asked == 0
    assert st.profile.target_role == "data_analyst"


def test_never_more_than_six_questions(tax):
    llm = FakeLLM(TurnExtraction(target_role="data_analyst", target_level="junior", next_question="سؤال بعدی؟"))
    st = ConversationState()
    for i in range(MAX_QUESTIONS + 1):
        _, st = next_turn(st, f"جواب {i}", llm, tax)
    assert MAX_QUESTIONS == 6
    assert st.questions_asked == MAX_QUESTIONS and st.done


def test_unknown_role_and_concepts_are_dropped(tax):
    llm = FakeLLM(TurnExtraction(target_role="pilot", unsupported_role="خلبان", target_level="junior",
                                 claims=[ConceptClaim(concept_id="flying", proficiency="proficient"),
                                         ConceptClaim(concept_id="excel", proficiency="used")],
                                 next_question="کدام نقش؟"))
    reply, st = next_turn(ConversationState(), "می‌خوام خلبان بشم", llm, tax)
    assert st.profile.target_role is None
    assert [c.concept_id for c in st.profile.claims] == ["excel"]
    assert "پوشش" in reply and "تحلیلگر داده" in reply  # offers the supported roles


def test_heard_is_not_known_and_current_level_counts(tax):
    p = UserProfile(target_role="data_analyst", target_level="mid", current_level="junior",
                    claims=[ConceptClaim(concept_id="pandas", proficiency="heard")], not_known=["sql_basics"])
    known, not_known = known_sets(p, tax)
    assert "pandas" not in known
    assert {"excel", "statistics"} <= known  # junior concepts of the target role
    assert "sql_basics" in not_known and "sql_basics" not in known


def test_correction_after_roadmap_updates_profile(tax):
    st = ConversationState(done=True, profile=UserProfile(
        target_role="data_analyst", target_level="junior",
        claims=[ConceptClaim(concept_id="excel", proficiency="used")]))
    llm = FakeLLM(ProfileDelta(remove_known=["excel", "made_up"]))
    reply, st = next_turn(st, "من اکسل بلد نیستم", llm, tax)
    assert "excel" in st.profile.not_known and "made_up" not in st.profile.not_known
    assert all(c.concept_id != "excel" for c in st.profile.claims)
    assert st.done and reply


def test_llm_failure_falls_back_to_fixed_question(tax):
    llm = FakeLLM(LLMError("سرویس هوش مصنوعی فعلاً در دسترس نیست."))
    reply, st = next_turn(ConversationState(), "سلام", llm, tax)
    assert "در دسترس نیست" in reply and "؟" in reply
    assert st.questions_asked == 1 and not st.done


def test_later_not_known_overrides_earlier_claim(tax):
    llm = FakeLLM(
        TurnExtraction(target_role="data_analyst", claims=[ConceptClaim(concept_id="statistics", proficiency="used")],
                       next_question="سطح؟"),
        TurnExtraction(not_known=["statistics"], next_question="ابزار؟"),
    )
    _, st = next_turn(ConversationState(), "آمار بلدم", llm, tax)
    _, st = next_turn(st, "راستش آمار بلد نیستم", llm, tax)
    assert all(c.concept_id != "statistics" for c in st.profile.claims)
    assert "statistics" in st.profile.not_known


# ---- direct skill editing (idea from Amir's prototype, A-08) ----
def test_skill_selection_adds_and_removes_known(tax):
    from core.conversation import apply_skill_selection

    p = UserProfile(target_role="data_analyst", target_level="junior",
                    claims=[ConceptClaim(concept_id="excel", proficiency="used")])
    known, _ = known_sets(p, tax)
    apply_skill_selection(p, selected={"statistics"}, previously_known=known, tax=tax)
    known, not_known = known_sets(p, tax)
    assert "statistics" in known and "excel" not in known and "excel" in not_known


# ---- fallback extraction when the LLM is down (idea from Amir's prototype, NF-06) ----
def test_fallback_still_extracts_role_and_skills(tax):
    llm = FakeLLM(LLMError("سرویس هوش مصنوعی فعلاً در دسترس نیست."))
    _, st = next_turn(ConversationState(), "می‌خوام تحلیلگر داده بشم، با اکسل کار کردم ولی SQL رو فقط شنیدم", llm, tax)
    assert st.profile.target_role == "data_analyst"
    claims = {c.concept_id: c.proficiency for c in st.profile.claims}
    assert claims.get("excel") == "used"
    assert claims.get("sql_basics") == "heard"


def test_fallback_does_not_match_short_tokens_inside_words(tax):
    # Amir's keyword fallback mapped "html" to the ML role because "html" contains "ml".
    llm = FakeLLM(LLMError("قطع"))
    _, st = next_turn(ConversationState(), "من html بلدم", llm, tax)
    assert st.profile.target_role is None


def test_not_known_also_removes_inferred_dependents(tax):
    # "I'm a senior data analyst but I don't know SQL": skills built on SQL that were only inferred from the
    # level cannot count as known either (BI tools, data modeling depend on SQL in the mini taxonomy).
    p = UserProfile(target_role="data_analyst", target_level="senior", current_level="senior", not_known=["sql_basics"])
    known, not_known = known_sets(p, tax)
    assert "sql_basics" not in known
    assert "bi_tools" not in known and "data_modeling" not in known
    assert "excel" in known and "statistics" in known  # unrelated inferred skills stay


def test_explicit_claim_survives_not_known_of_its_prerequisite(tax):
    # The user explicitly said they use BI tools: keep it (their word), even though they deny SQL.
    p = UserProfile(target_role="data_analyst", target_level="senior", current_level="senior",
                    claims=[ConceptClaim(concept_id="bi_tools", proficiency="used")], not_known=["sql_basics"])
    known, _ = known_sets(p, tax)
    assert "bi_tools" in known and "data_modeling" not in known
