"""Knowledge Gap Detector.

Three situations are kept apart:
  1. ABSENT      - the information is not in our dataset.
  2. UNVERIFIED  - a value is stored but nobody has checked it against the source.
  3. Genuinely does not exist - this tool NEVER reports that. Without evidence we
     can only say "not in our dataset", which is not the same thing.
"""
from services.discovery_engine import build_profile, rank_opportunities
from utils.validators import CORE_FIELDS, clean_user_text, is_empty

KIND_ABSENT = "absent_from_dataset"
KIND_UNVERIFIED = "unverified"

NOT_PROOF_NOTE = ("'Not in our dataset' is not proof that something does not exist. "
                  "Only an official source can confirm that.")

# Words in a question -> which field the person is asking about
FIELD_TRIGGERS = {
    "deadline": [r"deadline", r"last date", r"due date", r"closing", r"\bwhen\b"],
    "eligibility": [r"eligib", r"qualify", r"criteria", r"who can", r"\bcan i\b"],
    "required_documents": [r"document", r"papers", r"certificate"],
    "benefits": [r"benefit", r"amount", r"stipend", r"how much", r"free", r"\bfees?\b"],
    "state_or_location": [r"\bwhere\b", r"\bstate\b", r"location"],
}


def _next_step(field: str, record: dict) -> str:
    label = CORE_FIELDS[field].lower()
    return (f"Open the official source ({record['official_source_url']}), look for the {label}, "
            "and record it together with the date you checked.")


def record_gaps(record: dict) -> list:
    """List the gaps for one record."""
    gaps = []
    verified_fields = set(record.get("verified_fields") or [])
    status = record.get("verification_status", "unverified")
    for field, label in CORE_FIELDS.items():
        if is_empty(record.get(field)):
            gaps.append({"field": field, "kind": KIND_ABSENT,
                         "message": f"{label} is not recorded in our dataset.",
                         "next_step": _next_step(field, record)})
        elif field not in verified_fields:
            gaps.append({"field": field, "kind": KIND_UNVERIFIED,
                         "message": f"{label} is recorded but has not been verified against the source.",
                         "next_step": _next_step(field, record)})
    if status == "unverified":
        gaps.append({"field": "record", "kind": KIND_UNVERIFIED,
                     "message": "The record itself has not been checked against its source.",
                     "next_step": "Open the source link and confirm the portal and description are correct."})
    return gaps


def coverage_table(records) -> list:
    """For each core field: how many records have it, are missing it, or have it verified."""
    rows = []
    total = len(records or [])
    for field, label in CORE_FIELDS.items():
        present = sum(1 for r in records or [] if not is_empty(r.get(field)))
        verified = sum(1 for r in records or []
                       if not is_empty(r.get(field)) and field in (r.get("verified_fields") or []))
        rows.append({"Field": label, "Records": total, "Has a value": present,
                     "Missing": total - present, "Value verified": verified})
    return rows


def detect_asked_fields(question: str) -> list:
    import re
    lowered = clean_user_text(question).lower()
    return [f for f, patterns in FIELD_TRIGGERS.items() if any(re.search(p, lowered) for p in patterns)]


def analyze_question(records, question: str) -> dict:
    """Say what the dataset can and cannot answer for a question.

    Returns {"ok", "message", "scope", "findings"}; each finding has kind, title,
    detail and next_step.
    """
    text = clean_user_text(question)
    if not text:
        return {"ok": False, "message": "Please type a question first.", "scope": [], "findings": []}
    if not records:
        return {"ok": False, "message": "The dataset is empty, so nothing can be checked.",
                "scope": [], "findings": []}

    profile = build_profile(free_text=text)
    ranked = rank_opportunities(records, profile, top_k=len(records))
    scope = [r["record"] for r in ranked]
    findings = []

    if profile["state"]:
        specific = [r for r in records if profile["state"].lower()
                    in [str(x).lower() for x in r.get("state_or_location", [])]]
        all_india = [r for r in records
                     if "all india" in [str(x).lower() for x in r.get("state_or_location", [])]]
        if not specific:
            findings.append({
                "kind": KIND_ABSENT,
                "title": f"No record in our dataset is specific to {profile['state']}.",
                "detail": f"{len(all_india)} all-India record(s) may still apply. {NOT_PROOF_NOTE}",
                "next_step": f"Check the official {profile['state']} government portals and add verified records."})
        else:
            names = ", ".join(r["name"] for r in specific)
            findings.append({
                "kind": "info", "title": f"{len(specific)} record(s) are specific to {profile['state']}.",
                "detail": names, "next_step": "Review each record's gaps below."})

    if not scope:
        findings.append({
            "kind": KIND_ABSENT,
            "title": "Our dataset has no records matching this question.",
            "detail": "This describes our dataset only. " + NOT_PROOF_NOTE,
            "next_step": "Search the official portals directly, then add what you find as new records."})
        return {"ok": True, "message": "", "scope": [], "findings": findings}

    asked = detect_asked_fields(text) or ["eligibility", "deadline"]
    for field in asked:
        label = CORE_FIELDS[field]
        with_value = [r for r in scope if not is_empty(r.get(field))]
        verified = [r for r in with_value if field in (r.get("verified_fields") or [])]
        if not with_value:
            findings.append({
                "kind": KIND_ABSENT,
                "title": f"{label}: not recorded for any of the {len(scope)} related record(s).",
                "detail": "Our dataset cannot answer this part of the question. " + NOT_PROOF_NOTE,
                "next_step": "Use each record's official source link to find this and record it."})
        elif len(verified) < len(with_value):
            findings.append({
                "kind": KIND_UNVERIFIED,
                "title": f"{label}: recorded for {len(with_value)} record(s), verified for {len(verified)}.",
                "detail": "Treat unverified values as leads, not answers.",
                "next_step": "Confirm the value on the official source before relying on it."})
        else:
            findings.append({
                "kind": "info", "title": f"{label}: verified for all {len(with_value)} related record(s).",
                "detail": "", "next_step": "Still check the official source for recent changes."})
    return {"ok": True, "message": "", "scope": scope, "findings": findings}
