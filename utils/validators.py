"""Validation helpers for dataset records and user input."""
import re
from datetime import datetime
from urllib.parse import urlparse

REQUIRED_TEXT_FIELDS = [
    "id",
    "name",
    "category",
    "description",
    "official_source_url",
    "source_name",
    "verification_status",
]
LIST_FIELDS = [
    "target_audience",
    "education_levels",
    "state_or_location",
    "skills_or_interests",
    "required_documents",
    "missing_information",
    "verified_fields",
]
OPTIONAL_TEXT_FIELDS = [
    "eligibility",
    "benefits",
    "deadline",
    "last_verified",
    "verification_note",
]
VALID_STATUSES = {"verified", "partially_verified", "unverified"}
MAX_INPUT_CHARS = 1500

# Fields we check for gaps. "label" is what users see.
CORE_FIELDS = {
    "eligibility": "Eligibility criteria",
    "deadline": "Deadline",
    "benefits": "Benefits",
    "required_documents": "Required documents",
    "state_or_location": "Location / state applicability",
}


def is_valid_url(url) -> bool:
    """True for http(s) URLs that have a host name."""
    if not isinstance(url, str) or not url.strip():
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _is_date(value) -> bool:
    try:
        datetime.strptime(str(value), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def is_empty(value) -> bool:
    """True when a record value carries no information."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def missing_core_fields(record: dict) -> list:
    """Names of core fields that are empty in this record."""
    return [f for f in CORE_FIELDS if is_empty(record.get(f))]


def validate_record(record) -> list:
    """Return a list of problems (empty list means the record is valid)."""
    if not isinstance(record, dict):
        return ["record is not an object"]
    problems = []
    for field in REQUIRED_TEXT_FIELDS:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"missing or empty required field '{field}'")
    for field in LIST_FIELDS:
        value = record.get(field)
        if value is not None and not isinstance(value, list):
            problems.append(f"field '{field}' must be a list")
    if "official_source_url" in record and not is_valid_url(record.get("official_source_url")):
        problems.append("official_source_url is not a valid http(s) URL")
    status = record.get("verification_status")
    if isinstance(status, str) and status not in VALID_STATUSES:
        problems.append(f"verification_status must be one of {sorted(VALID_STATUSES)}")
    last_verified = record.get("last_verified")
    if status == "unverified" and last_verified:
        problems.append("an unverified record must not have a last_verified date")
    if status in ("verified", "partially_verified"):
        if not last_verified:
            problems.append("a verified or partially verified record needs a last_verified date")
    if last_verified and not _is_date(last_verified):
        problems.append("last_verified must look like YYYY-MM-DD")
    return problems


def validate_dataset(records) -> tuple:
    """Split a raw list into (valid_records, problems). Never raises."""
    if not isinstance(records, list):
        return [], ["dataset must be a JSON list of records"]
    valid, problems, seen_ids = [], [], set()
    for index, record in enumerate(records):
        label = record.get("id", f"#{index}") if isinstance(record, dict) else f"#{index}"
        errors = validate_record(record)
        if errors:
            problems.append(f"Record {label} skipped: " + "; ".join(errors))
            continue
        if record["id"] in seen_ids:
            problems.append(f"Record {label} skipped: duplicate id")
            continue
        seen_ids.add(record["id"])
        valid.append(record)
    return valid, problems


def clean_user_text(text, max_chars: int = MAX_INPUT_CHARS) -> str:
    """Strip, collapse whitespace and truncate user input. None becomes ''."""
    if text is None:
        return ""
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    return cleaned[:max_chars]


def check_question(text) -> tuple:
    """Return (ok, message). Used before any search or API call."""
    cleaned = clean_user_text(text)
    if not cleaned:
        return False, "Please type a question or describe your situation first."
    if len(cleaned) < 3:
        return False, "That is too short to search with. Add a few more words."
    return True, ""
