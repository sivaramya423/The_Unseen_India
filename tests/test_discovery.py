"""Matching and ranking tests."""
from services.discovery_engine import (build_profile, detect_level, detect_state, is_profile_empty,
                                       rank_opportunities, retrieve_for_question, search_records)
from utils.data_loader import load_opportunities

RECORDS, _ = load_opportunities()
EXAMPLE = ("I am studying AI and Data Science in Tamil Nadu. My family has limited income, and I want "
           "to learn new skills, but I don't know which programmes are available.")


def ids(ranked):
    return [r["record"]["id"] for r in ranked]


def test_empty_input_gives_no_results():
    profile = build_profile(free_text="")
    assert is_profile_empty(profile)
    assert rank_opportunities(RECORDS, profile) == []
    assert rank_opportunities(RECORDS, build_profile(free_text=None)) == []


def test_empty_dataset_gives_no_results():
    assert rank_opportunities([], build_profile(free_text=EXAMPLE)) == []
    assert search_records([], "scholarship") == []


def test_profile_reads_state_and_concepts_from_text():
    profile = build_profile(free_text=EXAMPLE)
    assert profile["state"] == "Tamil Nadu"
    assert "scholarship" in profile["interests"] and "skills" in profile["interests"]


def test_detect_helpers():
    assert detect_state("I live in tamilnadu") == "Tamil Nadu"
    assert detect_state("nothing here") == ""
    assert detect_level("I am doing my B.Tech") == "undergraduate"
    assert detect_level("help me please") == ""


def test_state_specific_record_ranks_first_for_its_state():
    ranked = rank_opportunities(RECORDS, build_profile(free_text=EXAMPLE))
    assert ranked[0]["record"]["id"] == "naan-mudhalvan"
    assert ranked[0]["reasons"]


def test_scores_are_sorted_descending():
    scores = [r["score"] for r in rank_opportunities(RECORDS, build_profile(free_text=EXAMPLE))]
    assert scores == sorted(scores, reverse=True)


def test_record_for_another_state_is_excluded():
    ranked = rank_opportunities(RECORDS, build_profile(free_text="skills training", state="Kerala"))
    assert "naan-mudhalvan" not in ids(ranked)
    assert "skill-india-digital-hub" in ids(ranked)


def test_category_filter_adds_relevance():
    profile = build_profile(free_text="", category="Entrepreneurship")
    assert ids(rank_opportunities(RECORDS, profile))[0] == "startup-india"


def test_results_report_missing_eligibility():
    ranked = rank_opportunities(RECORDS, build_profile(free_text=EXAMPLE))
    for item in ranked:
        assert "eligibility" in item["missing_fields"]


def test_unrelated_query_returns_nothing():
    assert rank_opportunities(RECORDS, build_profile(free_text="qwertyuiop zzzz")) == []


def test_retrieval_only_returns_real_records():
    real_ids = {r["id"] for r in RECORDS}
    retrieved = retrieve_for_question(RECORDS, "Which skills courses are free in Tamil Nadu?", top_k=5)
    assert retrieved and all(item["record"]["id"] in real_ids for item in retrieved)
    assert len(retrieved) <= 5


def test_keyword_search():
    found = search_records(RECORDS, "scholarship")
    assert "national-scholarship-portal" in ids(found)
