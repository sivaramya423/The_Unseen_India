"""Knowledge Connection Engine.

METHOD: weighted shared-attribute overlap. For each attribute we compute the
Jaccard similarity of the two records' value sets (shared / total distinct),
multiply by a fixed weight, and add the results. This is plain set arithmetic.
It is not machine learning and it understands nothing about meaning.
"""

METHOD_DESCRIPTION = (
    "Weighted shared-attribute overlap: for each attribute (audience, education level, "
    "location, skills and interests, category, required documents) we measure how many "
    "values two records share, multiply by a fixed weight, and add the results. "
    "This is simple set arithmetic, not machine learning."
)

WEIGHTS = {
    "skills_or_interests": 3.0,
    "target_audience": 2.0,
    "education_levels": 2.0,
    "state_or_location": 1.5,
    "category": 1.0,
    "required_documents": 1.0,
}
LABELS = {
    "skills_or_interests": "skills and interests",
    "target_audience": "target audience",
    "education_levels": "education level labels",
    "state_or_location": "location",
    "category": "category",
    "required_documents": "required documents",
}


def _values(record: dict, attribute: str) -> set:
    value = record.get(attribute)
    if value is None:
        return set()
    if isinstance(value, str):
        value = [value]
    return {str(v).strip().lower() for v in value if str(v).strip()}


def _jaccard(a: set, b: set) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def compare_records(a: dict, b: dict) -> dict:
    """Return score (0 to 1), shared values per attribute, and reasons."""
    total_weight = sum(WEIGHTS.values())
    weighted, shared, reasons = 0.0, {}, []
    for attribute, weight in WEIGHTS.items():
        va, vb = _values(a, attribute), _values(b, attribute)
        common = sorted(va & vb)
        if common:
            weighted += weight * _jaccard(va, vb)
            shared[attribute] = common
            reasons.append(f"Both list the same {LABELS[attribute]}: {', '.join(common)}.")
    return {"score": round(weighted / total_weight, 3), "shared": shared, "reasons": reasons}


def find_connections(records, record_id: str, top_k: int = 5, min_score: float = 0.1) -> list:
    """Records most connected to the record with this id (best first)."""
    source = next((r for r in records or [] if r.get("id") == record_id), None)
    if source is None:
        return []
    results = []
    for other in records:
        if other.get("id") == record_id:
            continue
        result = compare_records(source, other)
        if result["score"] >= min_score and result["shared"]:
            results.append({"record": other, **result})
    results.sort(key=lambda r: (-r["score"], r["record"].get("name", "")))
    return results[:top_k]


def all_connections(records, min_score: float = 0.2) -> list:
    """Every connected pair at or above min_score."""
    pairs = []
    items = list(records or [])
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            result = compare_records(items[i], items[j])
            if result["score"] >= min_score and result["shared"]:
                pairs.append({"a": items[i], "b": items[j], **result})
    pairs.sort(key=lambda p: -p["score"])
    return pairs
