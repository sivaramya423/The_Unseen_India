"""Dataset loading and validation tests (no network, no API key needed)."""
import json
import tempfile
from pathlib import Path

from utils.data_loader import load_opportunities
from utils.validators import (check_question, clean_user_text, is_valid_url, validate_dataset,
                              validate_record)


def make_record(**overrides):
    record = {
        "id": "test-1", "name": "Test Record", "category": "Scholarships",
        "description": "A test record.", "official_source_url": "https://example.gov.in/",
        "source_name": "Example", "verification_status": "unverified", "last_verified": None,
    }
    record.update(overrides)
    return record


def write_temp(content: str) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    handle.write(content)
    handle.close()
    return Path(handle.name)


def test_real_dataset_loads_without_problems():
    records, problems = load_opportunities()
    assert problems == []
    assert len(records) >= 5


def test_every_real_record_has_source_url_and_honest_dates():
    records, _ = load_opportunities()
    for rec in records:
        assert is_valid_url(rec["official_source_url"]), rec["id"]
        if rec["verification_status"] == "unverified":
            assert rec["last_verified"] is None, rec["id"]
        else:
            assert rec["last_verified"], rec["id"]


def test_missing_file_gives_problem_not_crash():
    records, problems = load_opportunities(Path(tempfile.gettempdir()) / "does_not_exist_123.json")
    assert records == [] and problems


def test_malformed_json_gives_problem():
    records, problems = load_opportunities(write_temp("{not json"))
    assert records == [] and "valid JSON" in problems[0]


def test_empty_dataset_is_empty_list():
    records, problems = load_opportunities(write_temp("[]"))
    assert records == [] and problems == []


def test_non_list_dataset_rejected():
    records, problems = load_opportunities(write_temp('{"a": 1}'))
    assert records == [] and problems


def test_bad_records_skipped_good_kept():
    good = make_record()
    bad_no_url = make_record(id="bad-1", official_source_url="not a url")
    bad_type = "just a string"
    path = write_temp(json.dumps([good, bad_no_url, bad_type]))
    records, problems = load_opportunities(path)
    assert [r["id"] for r in records] == ["test-1"]
    assert len(problems) == 2


def test_duplicate_ids_skipped():
    records, problems = validate_dataset([make_record(), make_record()])
    assert len(records) == 1 and "duplicate" in problems[0]


def test_unverified_record_cannot_claim_verification_date():
    assert validate_record(make_record(last_verified="2026-01-01"))


def test_verified_record_needs_date():
    assert validate_record(make_record(verification_status="verified", last_verified=None))


def test_bad_status_and_date_format_rejected():
    assert validate_record(make_record(verification_status="great"))
    assert validate_record(make_record(verification_status="verified", last_verified="yesterday"))


def test_url_validation():
    assert is_valid_url("https://scholarships.gov.in/")
    assert not is_valid_url("ftp://x.org")
    assert not is_valid_url("")
    assert not is_valid_url(None)


def test_empty_user_input_is_rejected():
    assert check_question("")[0] is False
    assert check_question("   ")[0] is False
    assert check_question(None)[0] is False
    assert check_question("scholarships for engineering students")[0] is True


def test_clean_user_text_truncates_and_collapses():
    assert clean_user_text("  a   b \n c ") == "a b c"
    assert len(clean_user_text("x" * 5000)) == 1500
