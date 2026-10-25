"""Knowledge connection tests."""
from services.knowledge_connections import (METHOD_DESCRIPTION, all_connections, compare_records,
                                            find_connections)
from utils.data_loader import load_opportunities

RECORDS, _ = load_opportunities()


def by_id(record_id):
    return next(r for r in RECORDS if r["id"] == record_id)


def test_identical_attributes_score_high_and_explain_why():
    result = compare_records(by_id("skill-india-digital-hub"), by_id("skill-india-digital-hub"))
    assert result["score"] > 0.9
    assert result["reasons"]


def test_unrelated_records_have_no_shared_attributes():
    a = {"skills_or_interests": ["a"], "category": "X"}
    b = {"skills_or_interests": ["b"], "category": "Y"}
    result = compare_records(a, b)
    assert result["score"] == 0 and result["shared"] == {}


def test_find_connections_sorted_and_explained():
    connections = find_connections(RECORDS, "naan-mudhalvan", top_k=5)
    assert connections
    scores = [c["score"] for c in connections]
    assert scores == sorted(scores, reverse=True)
    assert all(c["reasons"] for c in connections)
    assert all(c["record"]["id"] != "naan-mudhalvan" for c in connections)


def test_skills_neighbours_include_skill_india():
    names = [c["record"]["id"] for c in find_connections(RECORDS, "naan-mudhalvan", top_k=5)]
    assert "skill-india-digital-hub" in names


def test_unknown_id_and_empty_dataset():
    assert find_connections(RECORDS, "nope") == []
    assert find_connections([], "x") == []
    assert all_connections([]) == []


def test_all_connections_pairs_are_distinct():
    pairs = all_connections(RECORDS, min_score=0.2)
    keys = {tuple(sorted((p["a"]["id"], p["b"]["id"]))) for p in pairs}
    assert len(keys) == len(pairs)


def test_method_is_described_honestly():
    assert "not machine learning" in METHOD_DESCRIPTION
