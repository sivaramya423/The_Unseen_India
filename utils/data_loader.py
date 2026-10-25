"""Load and normalise the opportunity dataset."""
import json
from pathlib import Path

import config
from utils.validators import LIST_FIELDS, OPTIONAL_TEXT_FIELDS, validate_dataset


def normalize_record(record):
    """Return a cleaned copy: lists are lists, blank strings become None."""
    if not isinstance(record, dict):
        return record
    rec = dict(record)
    for field in LIST_FIELDS:
        value = rec.get(field)
        if value is None:
            rec[field] = []
        elif isinstance(value, str):
            rec[field] = [value.strip()] if value.strip() else []
        elif isinstance(value, list):
            rec[field] = [str(v).strip() for v in value if str(v).strip()]
    for field in OPTIONAL_TEXT_FIELDS:
        value = rec.get(field)
        if isinstance(value, str):
            rec[field] = value.strip() or None
    for field in ("id", "name", "category", "description", "source_name", "official_source_url"):
        if isinstance(rec.get(field), str):
            rec[field] = rec[field].strip()
    rec.setdefault("record_type", "programme")
    return rec


def load_opportunities(path=None) -> tuple:
    """Return (records, problems). Never raises for bad or missing data."""
    file_path = Path(path) if path else config.DATA_PATH
    if not file_path.exists():
        return [], [f"Dataset file not found: {file_path.name}"]
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        return [], [f"Could not read dataset file: {type(exc).__name__}"]
    except json.JSONDecodeError as exc:
        return [], [f"Dataset is not valid JSON (line {exc.lineno}, column {exc.colno})."]
    if not isinstance(raw, list):
        return [], ["Dataset must be a JSON list of records."]
    normalized = [normalize_record(item) for item in raw]
    return validate_dataset(normalized)
