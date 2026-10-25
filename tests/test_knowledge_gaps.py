"""Knowledge gap detector tests."""
from services.knowledge_gap_detector import (KIND_ABSENT, KIND_UNVERIFIED, analyze_question,
                                             coverage_table, record_gaps)
from utils.data_loader import load_opportunities

RECORDS, _ = load_opportunities()


def by_id(record_id):
    return next(r for r in RECORDS if r["id"] == record_id)


def test_missing_eligibility_and_deadline_are_reported_as_absent():
    gaps = record_gaps(by_id("national-scholarship-portal"))
    absent = {g["field"] for g in gaps if g["kind"] == KIND_ABSENT}
    assert {"eligibility", "deadline", "benefits"} <= absent
    assert all(g["next_step"] for g in gaps)


def test_present_but_unchecked_value_is_unverified_not_absent():
    record = dict(by_id("naan-mudhalvan"), eligibility="Some rule", verified_fields=[])
    kinds = {g["field"]: g["kind"] for g in record_gaps(record)}
    assert kinds["eligibility"] == KIND_UNVERIFIED


def test_verified_field_has_no_gap():
    fields = {g["field"] for g in record_gaps(by_id("naan-mudhalvan"))}
    assert "benefits" not in fields


def test_unverified_record_flagged_as_a_whole():
    assert any(g["field"] == "record" for g in record_gaps(by_id("swayam")))


def test_empty_question_and_empty_dataset():
    assert analyze_question(RECORDS, "")["ok"] is False
    assert analyze_question([], "deadline for scholarships")["ok"] is False


def test_deadline_question_reports_absence_without_claiming_nonexistence():
    result = analyze_question(RECORDS, "Is a deadline available for scholarships in Tamil Nadu?")
    assert result["ok"]
    absent = [f for f in result["findings"] if f["kind"] == KIND_ABSENT]
    assert absent
    text = " ".join(f["title"] + f["detail"] for f in absent).lower()
    assert "not proof" in text
    assert "does not exist" not in text.replace("not proof that something does not exist", "")


def test_group_with_no_specific_records_is_a_dataset_gap():
    result = analyze_question(RECORDS, "scholarships for students in Kerala")
    titles = " ".join(f["title"] for f in result["findings"])
    assert "No record in our dataset is specific to Kerala" in titles


def test_question_matching_nothing_is_dataset_gap():
    result = analyze_question(RECORDS, "qwertyuiop zzzz deadline")
    assert result["ok"] and result["scope"] == []
    assert result["findings"][0]["kind"] == KIND_ABSENT


def test_coverage_table_counts():
    rows = {r["Field"]: r for r in coverage_table(RECORDS)}
    assert rows["Deadline"]["Has a value"] == 0
    assert rows["Benefits"]["Value verified"] == 1
