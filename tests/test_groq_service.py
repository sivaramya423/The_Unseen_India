"""Groq service tests. No real key and no network: clients are fakes."""
import config
from services.discovery_engine import retrieve_for_question
from services.groq_service import (ask_question, check_connection, classify_error, find_unknown_urls)
from utils.data_loader import load_opportunities

RECORDS, _ = load_opportunities()
RETRIEVED = retrieve_for_question(RECORDS, "skills courses in Tamil Nadu", top_k=3)
FAKE_KEY = "gsk_FAKEKEY1234567890"


class FakeHTTPError(Exception):
    def __init__(self, status_code, message="boom"):
        super().__init__(message)
        self.status_code = status_code


class NotFoundError(FakeHTTPError):
    pass


class APIConnectionError(Exception):
    pass


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class FakeClient:
    """Mimics client.chat.completions.create and client.models.list."""

    def __init__(self, reply="Answer [naan-mudhalvan]", error=None, models=("m1", "m2")):
        self.calls = 0
        self._reply, self._error, self._models = reply, error, models
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls += 1
                outer.last_kwargs = kwargs
                if outer._error:
                    raise outer._error
                return _Response(outer._reply)

        class _Chat:
            completions = _Completions()

        class _Models:
            def list(self):
                if outer._error:
                    raise outer._error

                class _R:
                    data = [type("M", (), {"id": m}) for m in outer._models]
                return _R()

        self.chat, self.models = _Chat(), _Models()


def with_env(key, model, func):
    """Run func with GROQ_* values forced (restores afterwards)."""
    import os
    old = (os.environ.get("GROQ_API_KEY"), os.environ.get("GROQ_MODEL"))
    try:
        for name, value in (("GROQ_API_KEY", key), ("GROQ_MODEL", model)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        return func()
    finally:
        for name, value in zip(("GROQ_API_KEY", "GROQ_MODEL"), old):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_missing_api_key_does_not_crash():
    result = with_env("", None, lambda: ask_question("skills in Tamil Nadu", RETRIEVED))
    assert result.ok is False and result.error_kind == "no_api_key"
    assert ".env" in result.message


def test_connection_check_without_key_is_friendly():
    result = with_env("", None, check_connection)
    assert result.ok is False and result.error_kind == "no_api_key"


def test_empty_question_and_no_records_never_call_the_api():
    client = FakeClient()
    assert ask_question("", RETRIEVED, client=client).error_kind == "empty_question"
    assert ask_question("anything", [], client=client).error_kind == "no_records"
    assert client.calls == 0


def test_success_returns_text_and_dataset_sources():
    client = FakeClient()
    result = with_env(FAKE_KEY, "my-model", lambda: ask_question("skills", RETRIEVED, client=client))
    assert result.ok and "Answer" in result.text
    assert client.calls == 1
    assert client.last_kwargs["model"] == "my-model"
    real_urls = {r["official_source_url"] for r in RECORDS}
    assert result.sources and all(s["url"] in real_urls for s in result.sources)


def test_prompt_contains_records_and_grounding_rules():
    client = FakeClient()
    with_env(FAKE_KEY, "m", lambda: ask_question("skills", RETRIEVED, client=client))
    messages = client.last_kwargs["messages"]
    assert "ONLY the records" in messages[0]["content"]
    assert RETRIEVED[0]["record"]["id"] in messages[1]["content"]


def test_invented_url_in_answer_is_flagged():
    client = FakeClient(reply="Go to https://totally-made-up.example/scheme now")
    result = with_env(FAKE_KEY, "m", lambda: ask_question("skills", RETRIEVED, client=client))
    assert result.ok and result.warnings
    assert find_unknown_urls("see https://totally-made-up.example", result.sources)


def run_error(error):
    client = FakeClient(error=error)
    return with_env(FAKE_KEY, "bad-model", lambda: ask_question("skills", RETRIEVED, client=client)), client


def test_each_error_type_is_classified_and_one_call_only():
    cases = [
        (FakeHTTPError(401, "invalid key"), "auth"),
        (NotFoundError(404, "The model `bad-model` does not exist"), "model_not_found"),
        (NotFoundError(404, "Not found"), "endpoint_not_found"),
        (FakeHTTPError(429, "slow down"), "rate_limit"),
        (FakeHTTPError(400, "bad"), "bad_request"),
        (FakeHTTPError(503, "down"), "server"),
        (APIConnectionError("no route"), "network"),
        (TimeoutError("slow"), "timeout"),
        (ValueError("weird"), "unknown"),
    ]
    for error, expected in cases:
        result, client = run_error(error)
        assert result.ok is False, expected
        assert result.error_kind == expected, (expected, result.error_kind)
        assert client.calls == 1  # no retry loop in our code
        assert result.message


def test_api_key_never_appears_in_error_messages():
    error = FakeHTTPError(400, f"request failed for key {FAKE_KEY}")
    result, _ = run_error(error)
    assert FAKE_KEY not in result.message
    kind, message = classify_error(error, "m", FAKE_KEY)
    assert FAKE_KEY not in message


def test_empty_model_answer_is_reported():
    result = with_env(FAKE_KEY, "m", lambda: ask_question("skills", RETRIEVED, client=FakeClient(reply="")))
    assert result.ok is False and result.error_kind == "empty_response"


def test_connection_check_reports_model_availability():
    ok = with_env(FAKE_KEY, "m1", lambda: check_connection(client=FakeClient()))
    assert ok.ok and ok.details["model_available"] is True
    missing = with_env(FAKE_KEY, "zzz", lambda: check_connection(client=FakeClient()))
    assert missing.ok and missing.details["model_available"] is False and "NOT" in missing.message
    failed = with_env(FAKE_KEY, "m", lambda: check_connection(client=FakeClient(error=FakeHTTPError(401))))
    assert failed.ok is False and failed.error_kind == "auth"


def test_model_comes_from_environment():
    assert with_env(FAKE_KEY, "custom/model", config.get_model) == "custom/model"
    assert with_env(FAKE_KEY, "", config.get_model) == config.DEFAULT_MODEL
