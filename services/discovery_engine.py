"""Rule-based discovery: turns a description of a person into ranked records.

No LLM is used here. Every point a record earns is listed as a plain-language
reason, so the ranking can be inspected and explained.
"""
import re

from utils.validators import clean_user_text, is_empty, missing_core_fields

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
    "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh",
    "Lakshadweep", "Puducherry",
]
STATE_ALIASES = {"tamilnadu": "Tamil Nadu", "orissa": "Odisha", "pondicherry": "Puducherry"}

EDUCATION_LEVELS = ["school", "diploma", "undergraduate", "postgraduate", "doctoral"]
LEVEL_PATTERNS = {
    "school": [r"\bschool\b", r"\bclass (9|10|11|12)\b", r"\b(10|12)th\b", r"higher secondary"],
    "diploma": [r"\bdiploma\b", r"polytechnic", r"\biti\b"],
    "undergraduate": [r"undergrad", r"\bb\.?tech\b", r"\bb\.e\b", r"\bb\.?sc\b", r"\bb\.?com\b",
                      r"bachelor", r"\bcollege\b", r"\bdegree\b", r"engineering"],
    "postgraduate": [r"postgrad", r"\bm\.?tech\b", r"\bm\.?sc\b", r"\bmba\b", r"\bmasters?\b"],
    "doctoral": [r"\bphd\b", r"doctora", r"research scholar"],
}

# Plain-language ideas mapped to the tags used in the dataset.
CONCEPTS = {
    "financial need": ([r"low income", r"limited income", r"financial", r"afford", r"\bfees?\b",
                        r"funding", r"scholarship"], ["scholarship", "financial aid"]),
    "skills": ([r"\bskills?\b", r"\blearn", r"training", r"\bcourses?\b", r"upskill", r"certificat"],
               ["skills", "training", "courses"]),
    "jobs": ([r"\bjobs?\b", r"career", r"placement", r"employ", r"\bintern"], ["jobs", "careers"]),
    "apprenticeship": ([r"apprentice"], ["apprenticeship"]),
    "entrepreneurship": ([r"startup", r"entrepreneur", r"\bbusiness"], ["entrepreneurship", "startup"]),
    "documents": ([r"\bdocuments?\b", r"certificate"], ["documents"]),
    "government schemes": ([r"\bschemes?\b", r"\bgovernment\b", r"\bbenefits?\b"], ["scheme discovery"]),
    "technology": ([r"\bai\b", r"data science", r"machine learning", r"coding", r"programming",
                    r"software", r"technology", r"computer"], ["technology"]),
}

STOPWORDS = set("""a an and are as at be but by can for from have help how i if in into is it its
me my of on or our so some than that the their them then there these they this to up us was we
what when where which who will with would you your am do does did dont don't know want need
has don doesn isn looking find discover studying study student students interested about like new also any
available programmes programs opportunities opportunity relevant overlooked""".split())

# Rule points
W_STATE = 3.0
W_ALL_INDIA = 1.0
W_LEVEL = 2.5
W_CATEGORY = 2.0
W_INTEREST = 1.5
CAP_INTEREST = 4.5
W_TEXT = 0.5
CAP_TEXT = 2.0
W_AUDIENCE = 1.0


def tokenize(text) -> list:
    """Lower-case content words (stopwords and 1-letter tokens removed)."""
    words = re.findall(r"[a-z0-9][a-z0-9+.#-]*", clean_user_text(text).lower())
    return [w.strip(".-") for w in words if len(w.strip(".-")) > 1 and w.strip(".-") not in STOPWORDS]


def detect_state(text):
    lowered = clean_user_text(text).lower()
    for alias, state in STATE_ALIASES.items():
        if alias in lowered:
            return state
    # Longest names first so "Andaman and Nicobar Islands" wins over shorter matches.
    for state in sorted(INDIAN_STATES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(state.lower()) + r"\b", lowered):
            return state
    return ""


def detect_level(text):
    lowered = clean_user_text(text).lower()
    for level in reversed(EDUCATION_LEVELS):  # most advanced first
        if any(re.search(p, lowered) for p in LEVEL_PATTERNS[level]):
            return level
    return ""


def detect_concepts(text) -> tuple:
    """Return (concept names found, dataset tags they map to)."""
    lowered = clean_user_text(text).lower()
    names, tags = [], []
    for name, (patterns, mapped) in CONCEPTS.items():
        if any(re.search(p, lowered) for p in patterns):
            names.append(name)
            tags.extend(t for t in mapped if t not in tags)
    return names, tags


def build_profile(free_text="", education_level="", state="", interests=None,
                  category="", eligibility_notes="") -> dict:
    """Combine typed form fields with what can be read from free text.

    Form fields win over guesses made from free text.
    """
    text = clean_user_text(free_text)
    notes = clean_user_text(eligibility_notes)
    combined = f"{text} {notes}".strip()
    concept_names, concept_tags = detect_concepts(combined)
    typed_interests = [clean_user_text(i).lower() for i in (interests or []) if clean_user_text(i)]
    all_interests = list(dict.fromkeys(typed_interests + concept_tags))
    return {
        "free_text": text,
        "eligibility_notes": notes,
        "education_level": (education_level or "").lower() or detect_level(combined),
        "state": state or detect_state(combined),
        "interests": all_interests,
        "concepts": concept_names,
        "category": category or "",
        "query_tokens": tokenize(combined),
    }


def is_profile_empty(profile: dict) -> bool:
    return not (profile.get("education_level") or profile.get("state") or profile.get("interests")
                or profile.get("category") or profile.get("query_tokens"))


def _lower_list(values) -> list:
    return [str(v).lower() for v in (values or [])]


def score_record(record: dict, profile: dict) -> dict:
    """Score one record. Returns score, reasons and, if ruled out, a reason why."""
    score, reasons = 0.0, []
    locations = _lower_list(record.get("state_or_location"))
    all_india = any(loc == "all india" for loc in locations)
    state = profile.get("state", "")

    if state:
        if state.lower() in locations:
            score += W_STATE
            reasons.append(f"Listed for {state}, which matches your state.")
        elif all_india:
            score += W_ALL_INDIA
            reasons.append("Listed as all-India, so it may apply in your state.")
        elif locations:
            return {"score": 0.0, "reasons": [], "excluded": "Listed only for "
                    + ", ".join(record["state_or_location"]) + "."}

    level = profile.get("education_level", "")
    levels = _lower_list(record.get("education_levels"))
    if level and (level in levels or "any" in levels):
        score += W_LEVEL
        reasons.append(f"Education level '{level}' fits this record's audience labels "
                       "(labels are for matching, not confirmed eligibility).")

    if profile.get("category") and profile["category"] == record.get("category"):
        score += W_CATEGORY
        reasons.append(f"Category matches '{record['category']}'.")

    tags = _lower_list(record.get("skills_or_interests"))
    shared = [i for i in profile.get("interests", []) if i in tags]
    if shared:
        score += min(CAP_INTEREST, W_INTEREST * len(shared))
        reasons.append("Shares interests: " + ", ".join(shared) + ".")

    haystack = set(tokenize(" ".join([record.get("name", ""), record.get("description", ""),
                                      " ".join(tags)])))
    state_words = set(tokenize(state))
    hits = [t for t in dict.fromkeys(profile.get("query_tokens", []))
            if t in haystack and t not in state_words and t not in shared]
    if hits:
        score += min(CAP_TEXT, W_TEXT * len(hits))
        reasons.append("Words from your text appear in the record: " + ", ".join(hits[:6]) + ".")

    audience_words = set(tokenize(" ".join(record.get("target_audience") or [])))
    if audience_words & set(profile.get("query_tokens", [])):
        score += W_AUDIENCE
        reasons.append("Target audience overlaps with how you described yourself.")

    return {"score": score, "reasons": reasons, "excluded": ""}


def strength_label(score: float) -> str:
    if score >= 8:
        return "Strong match"
    if score >= 4:
        return "Moderate match"
    return "Weak match"


def rank_opportunities(records, profile: dict, top_k: int = 10) -> list:
    """Rank records for a profile. Empty profile or records give an empty list."""
    if not records or is_profile_empty(profile):
        return []
    results = []
    for record in records:
        scored = score_record(record, profile)
        if scored["score"] > 0:
            results.append({
                "record": record,
                "score": scored["score"],
                "strength": strength_label(scored["score"]),
                "reasons": scored["reasons"],
                "missing_fields": missing_core_fields(record),
            })
    status_rank = {"verified": 0, "partially_verified": 1, "unverified": 2}
    results.sort(key=lambda r: (-r["score"],
                                status_rank.get(r["record"].get("verification_status"), 3),
                                r["record"].get("name", "")))
    return results[:top_k]


def search_records(records, query: str, top_k: int = 10) -> list:
    """Plain keyword search over name, description, tags and audience."""
    tokens = list(dict.fromkeys(tokenize(query)))
    if not tokens or not records:
        return []
    results = []
    for record in records:
        text = " ".join([record.get("name", ""), record.get("description", ""),
                         " ".join(record.get("skills_or_interests") or []),
                         " ".join(record.get("target_audience") or []),
                         record.get("category", "")])
        words = set(tokenize(text))
        hits = [t for t in tokens if t in words]
        if hits:
            results.append({"record": record, "score": float(len(hits)),
                            "strength": strength_label(len(hits)),
                            "reasons": ["Keyword match: " + ", ".join(hits) + "."],
                            "missing_fields": missing_core_fields(record)})
    results.sort(key=lambda r: (-r["score"], r["record"].get("name", "")))
    return results[:top_k]


def retrieve_for_question(records, question: str, top_k: int = 5) -> list:
    """Records the assistant may use as evidence for a question.

    Uses profile ranking first and fills remaining slots with keyword hits.
    """
    profile = build_profile(free_text=question)
    ranked = rank_opportunities(records, profile, top_k=top_k)
    seen = {r["record"]["id"] for r in ranked}
    for extra in search_records(records, question, top_k=top_k):
        if len(ranked) >= top_k:
            break
        if extra["record"]["id"] not in seen:
            ranked.append(extra)
            seen.add(extra["record"]["id"])
    return ranked


def distinct_categories(records) -> list:
    return sorted({r["category"] for r in records if not is_empty(r.get("category"))})
