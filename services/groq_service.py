"""Groq access with clear, beginner-friendly error handling.

* Uses the official `groq` Python SDK (it builds the correct URL itself).
* The key and model come from environment variables (see config.py).
* The key is never printed, logged or returned. Error text is redacted.
* One request per call; the SDK is limited to a single automatic retry.
"""
import re
from dataclasses import dataclass, field

import config

SYSTEM_PROMPT = """You are the evidence-based assistant for THE UNSEEN INDIA.
Rules you must follow:
1. Use ONLY the records provided under RECORDS. Never add schemes, programmes, URLs, deadlines, amounts or eligibility rules that are not in those records.
2. Cite records by their id in square brackets, for example [naan-mudhalvan].
3. If the records do not contain enough information, say so plainly.
4. Never say a person is definitely eligible. Say what is unknown and what they should check.
5. Portal-directory records are not specific schemes; describe them as portals.
6. Mention each record's verification status when it matters, and treat unverified information as unconfirmed.
7. Finish by advising the person to confirm details on the official source before applying.
Write in simple English, in short paragraphs or a short list."""


@dataclass
class GroqResult:
    ok: bool
    text: str = ""
    error_kind: str = ""
    message: str = ""
    model: str = ""
    warnings: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    details: dict = field(default_factory=dict)


class GroqSetupError(Exception):
    """Raised when the client cannot be created (no key or SDK missing)."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


def _redact(text: str, api_key: str = "") -> str:
    text = str(text)
    if api_key:
        text = text.replace(api_key, "[hidden]")
    return re.sub(r"gsk_[A-Za-z0-9]+", "[hidden]", text)


def classify_error(exc, model: str = "", api_key: str = "") -> tuple:
    """Turn an SDK or network exception into (kind, helpful message)."""
    name = type(exc).__name__
    status = getattr(exc, "status_code", None)
    detail = _redact(str(exc), api_key)[:200]
    if name == "APITimeoutError" or isinstance(exc, TimeoutError):
        return "timeout", "The request timed out. Check your internet connection and try again in a moment."
    if status == 401 or name == "AuthenticationError":
        return "auth", ("Groq rejected the API key (401). Check GROQ_API_KEY in your .env file: "
                        "no spaces or quotes, and the key must still be active in the Groq console.")
    if status == 403 or name == "PermissionDeniedError":
        return "permission", ("Your key is not allowed to use this model or feature (403). "
                              "Try another model from `python scripts/check_groq.py`.")
    if status == 404 or name == "NotFoundError":
        if "model" in detail.lower():
            return "model_not_found", (
                f"Groq says the model '{model}' does not exist or your key cannot use it (404). "
                "Run `python scripts/check_groq.py` to list the models your key can use, then set "
                "GROQ_MODEL in .env to one of them and restart the app.")
        return "endpoint_not_found", (
            "Groq returned 404 for the URL. This usually means a wrong base URL or path. "
            "Do not set a custom base URL; let the official `groq` SDK choose it. "
            "Also check that the `groq` package is up to date (`python -m pip install -U groq`).")
    if status == 429 or name == "RateLimitError":
        return "rate_limit", ("Groq says you have sent too many requests or used your quota (429). "
                              "Wait a minute and try again, or check your usage limits in the Groq console.")
    if status == 400 or name == "BadRequestError":
        return "bad_request", f"Groq could not process the request (400): {detail}"
    if (isinstance(status, int) and status >= 500) or name == "InternalServerError":
        return "server", "Groq had a problem on its side (5xx). Try again later."
    if name == "APIConnectionError" or isinstance(exc, (ConnectionError, OSError)):
        return "network", ("Could not reach Groq. Check your internet connection, VPN or proxy, "
                           "and that your firewall allows Python.")
    return "unknown", f"Unexpected error ({name}): {detail}"


def build_client(api_key=None):
    """Create a Groq client or raise GroqSetupError('no_api_key' / 'sdk_missing')."""
    key = config.get_api_key() if api_key is None else api_key
    if not key:
        raise GroqSetupError("no_api_key")
    try:
        from groq import Groq
    except ImportError as exc:
        raise GroqSetupError("sdk_missing") from exc
    return Groq(api_key=key, timeout=config.REQUEST_TIMEOUT_SECONDS, max_retries=1)


SETUP_MESSAGES = {
    "no_api_key": ("No Groq API key found. Create a file named .env next to app.py, add the line "
                   "GROQ_API_KEY=your_key, and restart. Search, connections, gaps and comparison still work."),
    "sdk_missing": "The `groq` package is not installed. Run: python -m pip install -r requirements.txt",
}


def _context_for(records_or_ranked) -> tuple:
    """Build the RECORDS block and the list of source dicts from ranked results or records."""
    blocks, sources = [], []
    for item in records_or_ranked:
        rec = item["record"] if "record" in item else item
        sources.append({"id": rec["id"], "name": rec["name"], "url": rec["official_source_url"],
                        "status": rec.get("verification_status", "unverified")})
        def show(value):
            return value if not (value is None or value == [] or value == "") else "NOT RECORDED"
        blocks.append("\n".join([
            f"[{rec['id']}] {rec['name']}",
            f"  type: {rec.get('record_type', 'programme')}; category: {rec['category']}",
            f"  description: {rec['description']}",
            f"  target audience: {show(rec.get('target_audience'))}",
            f"  location: {show(rec.get('state_or_location'))}",
            f"  eligibility: {show(rec.get('eligibility'))}",
            f"  benefits: {show(rec.get('benefits'))}",
            f"  deadline: {show(rec.get('deadline'))}",
            f"  required documents: {show(rec.get('required_documents'))}",
            f"  verification status: {rec.get('verification_status')}; last verified: {show(rec.get('last_verified'))}",
            f"  official source: {rec['official_source_url']}",
        ]))
    return "\n\n".join(blocks), sources


def find_unknown_urls(text: str, sources: list) -> list:
    """URLs in the AI answer that are not source links from the retrieved records."""
    allowed = {s["url"].rstrip("/").lower() for s in sources}
    found = re.findall(r"https?://[^\s)\]>\"']+", text or "")
    return [u for u in found if u.rstrip("/.,;").lower() not in allowed]


def ask_question(question: str, retrieved: list, client=None, model: str = "") -> GroqResult:
    """Answer a question using ONLY the retrieved records. Never raises."""
    question = (question or "").strip()
    model = model or config.get_model()
    if not question:
        return GroqResult(False, error_kind="empty_question", message="Please type a question first.")
    if not retrieved:
        return GroqResult(False, error_kind="no_records", model=model, message=(
            "No records in our dataset matched this question, so the AI was not asked. "
            "Asking it anyway could produce invented answers."))
    api_key = config.get_api_key()
    try:
        client = client or build_client()
    except GroqSetupError as exc:
        return GroqResult(False, error_kind=exc.kind, message=SETUP_MESSAGES[exc.kind], model=model)

    context, sources = _context_for(retrieved)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": f"RECORDS:\n{context}\n\nQUESTION: {question}"}],
            temperature=0.2,
            max_completion_tokens=config.MAX_COMPLETION_TOKENS,
        )
        text = (response.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001 - every failure must become a friendly message
        kind, message = classify_error(exc, model, api_key)
        return GroqResult(False, error_kind=kind, message=message, model=model, sources=sources)
    if not text:
        return GroqResult(False, error_kind="empty_response", model=model, sources=sources,
                          message="The model returned an empty answer. Try again or choose another model.")
    warnings = []
    unknown = find_unknown_urls(text, sources)
    if unknown:
        warnings.append("The AI mentioned link(s) that are not in the retrieved records: "
                        + ", ".join(unknown) + ". Do not trust them. Use the source links listed below.")
    return GroqResult(True, text=text, model=model, warnings=warnings, sources=sources)


def check_connection(client=None, model: str = "") -> GroqResult:
    """Safe connectivity test: lists models; never shows the key; sends no chat request."""
    model = model or config.get_model()
    api_key = config.get_api_key()
    try:
        client = client or build_client()
    except GroqSetupError as exc:
        return GroqResult(False, error_kind=exc.kind, message=SETUP_MESSAGES[exc.kind], model=model)
    try:
        response = client.models.list()
        data = getattr(response, "data", response)
        model_ids = sorted(str(getattr(m, "id", m)) for m in data)
    except Exception as exc:  # noqa: BLE001
        kind, message = classify_error(exc, model, api_key)
        return GroqResult(False, error_kind=kind, message=message, model=model)
    available = model in model_ids
    message = (f"Connected to Groq. {len(model_ids)} models are visible to your key. "
               + (f"Your configured model '{model}' is in the list." if available else
                  f"Your configured model '{model}' is NOT in the list. Set GROQ_MODEL to one of the models below."))
    return GroqResult(True, message=message, model=model, details={"models": model_ids, "model_available": available})
