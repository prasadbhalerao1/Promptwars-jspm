"""The LLM gateway must fail in a typed, bounded, non-corrupting way.

Before this layer existed the gateway had no retry, no timeout, no output validation and
no quota handling. The consequences were concrete: one transient 429 permanently failed
an agent run, a hung provider socket held a request open indefinitely, and
`float(result["score"])` wrote whatever the model said straight into DB columns — so a
model answering `8.5` for a field documented as 0-100 persisted an 8.5/100 rating that
then fed recruiter matching, salary prediction and hackathon composites.
"""

from __future__ import annotations

import pytest

from services.api.core.llm import (
    LLMInvalidOutput,
    LLMNotConfigured,
    LLMOverloaded,
    LLMQuotaExhausted,
    LLMRateLimited,
    LLMTimeout,
    LLMUnavailable,
    _call_with_retry,
    _classify_provider_error,
    validate_structured,
    validated_score,
)


class _ProviderError(Exception):
    """Stand-in for an SDK exception: classification keys off name + status + message."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status


def _sdk_error(class_name: str, message: str, status: int | None = None) -> Exception:
    return type(class_name, (_ProviderError,), {})(message, status)


async def _no_sleep(_seconds: float) -> None:
    """Backoff is real time; these tests assert ordering and counts, not wall-clock."""
    return None


# --- classification ------------------------------------------------------------------


@pytest.mark.parametrize(
    "class_name,message,status,expected",
    [
        ("RateLimitError", "Rate limit reached", 429, LLMRateLimited),
        ("AuthenticationError", "invalid x-api-key", 401, LLMNotConfigured),
        ("PermissionDeniedError", "forbidden", 403, LLMNotConfigured),
        ("APITimeoutError", "Request timed out", None, LLMTimeout),
        ("APIConnectionError", "Connection error", None, LLMTimeout),
        ("OverloadedError", "Overloaded", 529, LLMOverloaded),
        ("InternalServerError", "server error", 500, LLMOverloaded),
    ],
)
def test_provider_errors_are_classified(class_name, message, status, expected) -> None:
    assert isinstance(_classify_provider_error(_sdk_error(class_name, message, status), "test"), expected)


@pytest.mark.parametrize(
    "message,status",
    [
        ("You exceeded your current quota, please check your billing details", 429),
        ("insufficient_quota", 429),
        ("Your credit balance is too low", 400),
        ("payment required", 402),
    ],
)
def test_quota_exhaustion_is_not_mistaken_for_a_rate_limit(message, status) -> None:
    """The distinction that matters most.

    Providers report an exhausted quota as a 429 — the same status as an ordinary rate
    limit. Retrying a rate limit is correct; retrying an exhausted quota burns the
    caller's wall-clock on a guaranteed failure and reports "temporarily unavailable"
    for a condition that is neither temporary nor self-healing.
    """
    error = _classify_provider_error(_sdk_error("RateLimitError", message, status), "test")
    assert isinstance(error, LLMQuotaExhausted)
    assert error.retryable is False


def test_unrecognized_errors_fall_back_to_the_base_type_and_do_not_retry() -> None:
    error = _classify_provider_error(_sdk_error("BadRequestError", "malformed", 400), "test")
    assert type(error) is LLMUnavailable
    assert error.retryable is False


def test_every_typed_error_is_catchable_as_llm_unavailable() -> None:
    """Existing agent code is full of `except LLMUnavailable`; all of it must keep working."""
    for cls in (LLMNotConfigured, LLMQuotaExhausted, LLMRateLimited, LLMTimeout, LLMOverloaded, LLMInvalidOutput):
        assert issubclass(cls, LLMUnavailable)


def test_retry_after_header_is_captured() -> None:
    exc = _sdk_error("RateLimitError", "slow down", 429)
    exc.response = type("R", (), {"headers": {"retry-after": "7"}})()
    assert _classify_provider_error(exc, "test").retry_after == 7.0


# --- retry loop ----------------------------------------------------------------------


async def test_transient_failure_is_retried_then_succeeds(monkeypatch) -> None:
    monkeypatch.setattr("services.api.core.llm.asyncio.sleep", _no_sleep)
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _sdk_error("RateLimitError", "slow down", 429)
        return "result"

    assert await _call_with_retry(flaky, provider="test", what="unit") == "result"
    assert attempts["n"] == 3


async def test_quota_exhaustion_is_never_retried(monkeypatch) -> None:
    monkeypatch.setattr("services.api.core.llm.asyncio.sleep", _no_sleep)
    attempts = {"n": 0}

    def out_of_credit():
        attempts["n"] += 1
        raise _sdk_error("RateLimitError", "You exceeded your current quota", 429)

    with pytest.raises(LLMQuotaExhausted):
        await _call_with_retry(out_of_credit, provider="test", what="unit")
    assert attempts["n"] == 1, "a billing failure must cost exactly one attempt"


async def test_bad_credentials_are_never_retried(monkeypatch) -> None:
    monkeypatch.setattr("services.api.core.llm.asyncio.sleep", _no_sleep)
    attempts = {"n": 0}

    def bad_key():
        attempts["n"] += 1
        raise _sdk_error("AuthenticationError", "invalid x-api-key", 401)

    with pytest.raises(LLMNotConfigured):
        await _call_with_retry(bad_key, provider="test", what="unit")
    assert attempts["n"] == 1


async def test_retries_are_bounded(monkeypatch) -> None:
    """A retry loop that cannot terminate is worse than no retry loop."""
    monkeypatch.setattr("services.api.core.llm.asyncio.sleep", _no_sleep)
    attempts = {"n": 0}

    def always_fails():
        attempts["n"] += 1
        raise _sdk_error("OverloadedError", "overloaded", 529)

    with pytest.raises(LLMOverloaded):
        await _call_with_retry(always_fails, provider="test", what="unit")

    from services.api.core.config import get_settings

    assert attempts["n"] == get_settings().llm_max_retries + 1


# --- score validation ----------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        (72, 72.0),
        (72.4, 72.4),
        ("85", 85.0),
        (850, 100.0),
        (-10, 0.0),
        (8.5, 8.5),
        (None, None),
        ("not a number", None),
        (True, None),
        (float("nan"), None),
        (float("inf"), None),
    ],
)
def test_validated_score_clamps_or_returns_none(raw, expected) -> None:
    assert validated_score(raw) == expected


def test_validated_score_never_raises() -> None:
    """Callers degrade to an N/A sub-score; a raised ValueError would crash the node."""
    for raw in (object(), [], {}, "", b"x"):
        assert validated_score(raw) is None


# --- structured-output validation ----------------------------------------------------


_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "number"}, "rationale": {"type": "string"}, "gaps": {"type": "array"}},
    "required": ["score", "rationale"],
}


def test_valid_output_passes_through_unchanged() -> None:
    payload = {"score": 80, "rationale": "solid", "gaps": []}
    assert validate_structured(payload, _SCHEMA, "demo") == payload


def test_missing_required_field_is_rejected() -> None:
    with pytest.raises(LLMInvalidOutput, match="missing required field"):
        validate_structured({"score": 80}, _SCHEMA, "demo")


def test_wrong_type_is_rejected() -> None:
    with pytest.raises(LLMInvalidOutput, match="should be number"):
        validate_structured({"score": "eighty", "rationale": "x"}, _SCHEMA, "demo")


def test_non_object_output_is_rejected() -> None:
    with pytest.raises(LLMInvalidOutput):
        validate_structured(["not", "an", "object"], _SCHEMA, "demo")


def test_null_optional_field_is_allowed() -> None:
    """Nullable fields are how agents report unknown values — that must stay legal."""
    assert validate_structured({"score": 80, "rationale": "x", "gaps": None}, _SCHEMA, "demo")


def test_invalid_output_is_retryable() -> None:
    """Resampling often fixes a malformed tool call, so this class must be retryable."""
    assert LLMInvalidOutput("x").retryable is True
