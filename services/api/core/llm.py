"""Unified Multi-Provider LLM Gateway.

Enables seamless switching between LLM providers (Anthropic Claude, OpenAI GPT-4o,
Groq/xAI Grok, Google Gemini, or any OpenAI-compatible API endpoint) using a single,
clean interface across all agent modules.

Providers:
- "anthropic": Uses anthropic SDK (default model: claude-3-5-sonnet / claude-3-5-haiku)
- "openai": Uses openai SDK (default model: gpt-4o / gpt-4o-mini)
- "grok"/"groq": Uses openai SDK against Groq's OpenAI-compatible endpoint
  ("https://api.groq.com/openai/v1", e.g. llama-3.3-70b-versatile) when the configured
  key looks like a Groq key (`gsk_...`) or the provider is explicitly "groq"; against
  xAI's endpoint ("https://api.x.ai/v1", grok-2-1212) otherwise. Groq is this
  repo's test-time provider (see `.env`'s `LLM_PROVIDER=grok` + `GROK_API_KEY=gsk_...`)
  so CI/local testing doesn't depend on a paid Anthropic key.
- "gemini": Uses openai SDK with Google OpenAI compatibility ("https://generativelanguage.googleapis.com/v1beta/openai/")
- "openai_compatible": Uses custom base_url (e.g. Ollama, vLLM, DeepSeek, LocalAI)

Every completion made through `generate_completion`/`generate_structured` is wrapped in
a Langfuse `generation` observation (model, token usage, input/output) — see
`services.api.core.tracing.start_llm_generation`. Agent tool code should call these
functions rather than instantiating a provider SDK client directly, so tracing and
provider-switching both stay centralized here.
"""

import asyncio
import functools
import json
import logging
import random
from typing import Any

from services.api.core.config import get_settings
from services.api.core.tracing import start_llm_generation

logger = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    """Base class for every reason an LLM call could not produce a usable result.

    Kept as the base of the whole hierarchy below on purpose: a large amount of agent
    code already does `except LLMUnavailable`, and every one of those handlers should
    keep catching every failure mode. The subclasses add the distinction that was
    missing — callers (and `_call_with_retry`) need to tell "slow down and try again"
    apart from "the account is out of credit", because retrying the latter burns money
    and wall-clock for a guaranteed failure.
    """

    #: Whether re-issuing the identical request could plausibly succeed. Consulted by
    #: `_call_with_retry`; overridden per subclass rather than branched on by type.
    retryable: bool = False


class LLMNotConfigured(LLMUnavailable):
    """No API key, or the provider rejected the credentials.

    Never retryable — the key will not become valid between two attempts, and an
    authentication failure retried three times is three times the log noise for the
    same outcome.
    """


class LLMQuotaExhausted(LLMUnavailable):
    """The account is out of credit / over its billing quota (HTTP 402, `insufficient_quota`).

    Deliberately NOT retryable, and deliberately distinct from `LLMRateLimited` even
    though providers signal both with similar-looking errors. A rate limit clears in
    seconds; an exhausted quota clears when somebody pays. Retrying it wastes the
    user's time and produces a misleading "temporarily unavailable" message for a
    condition that is neither temporary nor self-healing.
    """


class LLMRateLimited(LLMUnavailable):
    """Provider returned 429. Retryable after a delay.

    `retry_after` carries the provider's own advice when it sent a Retry-After header —
    always preferable to our exponential backoff guess, since the provider knows when
    the window actually resets.
    """

    retryable = True

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMTimeout(LLMUnavailable):
    """The request exceeded `llm_timeout_seconds` or the connection dropped."""

    retryable = True


class LLMOverloaded(LLMUnavailable):
    """Provider-side capacity error (Anthropic 529, or any 5xx). Usually transient."""

    retryable = True


class LLMInvalidOutput(LLMUnavailable):
    """The model replied, but not with output matching the requested schema.

    Retryable exactly once in practice (bounded by `llm_max_retries`): resampling often
    fixes a malformed tool call, but a schema the model consistently cannot satisfy is a
    prompt bug that retrying will not solve.
    """

    retryable = True


def _classify_provider_error(exc: Exception, provider: str) -> LLMUnavailable:
    """Translate a provider SDK exception into this module's taxonomy.

    The Anthropic and OpenAI SDKs expose the same error class *names* (`RateLimitError`,
    `AuthenticationError`, `APITimeoutError`, ...), and the OpenAI client is what this
    gateway uses for Groq/xAI/Gemini/Ollama too, so matching on `type(exc).__name__`
    covers all five providers without importing every SDK eagerly.

    Status code and message are both consulted because quota exhaustion is not a
    distinct exception class in either SDK — OpenAI reports it as a 429 with an
    `insufficient_quota` code, which is precisely the case that must NOT be retried
    despite arriving as a rate-limit error.
    """
    name = type(exc).__name__
    status = getattr(exc, "status_code", None)
    text = str(exc).lower()

    quota_markers = ("insufficient_quota", "exceeded your current quota", "billing", "credit balance")
    if status == 402 or any(marker in text for marker in quota_markers):
        return LLMQuotaExhausted(f"{provider} quota/credit exhausted: {exc}")

    if name in {"AuthenticationError", "PermissionDeniedError"} or status in {401, 403}:
        return LLMNotConfigured(f"{provider} rejected the configured credentials: {exc}")

    if name == "RateLimitError" or status == 429:
        retry_after = None
        headers = getattr(getattr(exc, "response", None), "headers", None)
        if headers is not None:
            try:
                raw = headers.get("retry-after")
                retry_after = float(raw) if raw is not None else None
            except (TypeError, ValueError):
                retry_after = None
        return LLMRateLimited(f"{provider} rate limit hit: {exc}", retry_after=retry_after)

    if name in {"APITimeoutError", "APIConnectionError"}:
        return LLMTimeout(f"{provider} call timed out or could not connect: {exc}")

    if name in {"OverloadedError", "InternalServerError"} or (status is not None and status >= 500):
        return LLMOverloaded(f"{provider} is overloaded or erroring: {exc}")

    return LLMUnavailable(f"{provider} call failed: {exc}")


async def _call_with_retry(operation, *, provider: str, what: str):
    """Run one provider SDK call, translating and retrying failures.

    `operation` is a zero-arg callable performing the blocking SDK call; it is run via
    `asyncio.to_thread` so a slow round-trip never blocks the event loop (and with it
    every other in-flight request).

    Retries only what can plausibly succeed on a second identical attempt — see the
    `retryable` flag on each error class. Backoff is exponential with jitter; the jitter
    matters because a provider outage makes many concurrent agent calls fail at the same
    instant, and un-jittered backoff would send them all back in a synchronized wave.

    A provider-supplied `Retry-After` always wins over the computed delay: the provider
    knows when its window resets and we are guessing.
    """
    settings = get_settings()
    attempts = max(0, settings.llm_max_retries) + 1
    last_error: LLMUnavailable | None = None

    for attempt in range(attempts):
        try:
            return await asyncio.to_thread(operation)
        except LLMUnavailable as exc:
            # Raised by the caller's own validation (e.g. schema checks), already typed.
            last_error = exc
        except Exception as exc:  # noqa: BLE001 - every provider failure is classified below
            last_error = _classify_provider_error(exc, provider)

        if not last_error.retryable or attempt == attempts - 1:
            raise last_error

        delay = settings.llm_retry_base_delay_seconds * (2**attempt)
        retry_after = getattr(last_error, "retry_after", None)
        if retry_after is not None:
            delay = max(delay, float(retry_after))
        delay += random.uniform(0, settings.llm_retry_base_delay_seconds)

        logger.warning(
            "LLM_RETRY %s attempt=%d/%d delay=%.1fs reason=%s",
            what, attempt + 1, attempts, delay, type(last_error).__name__,
        )
        await asyncio.sleep(delay)

    raise last_error if last_error else LLMUnavailable(f"{what} failed with no recorded error")


def validated_score(raw: Any, *, lo: float = 0.0, hi: float = 100.0) -> float | None:
    """Coerce a model-supplied score onto the documented scale, or return None.

    Every scoring prompt's JSON schema *describes* its field as "0-100", but a schema
    description is prose, not a constraint — providers routinely answer on a 0-10 or 0-1
    scale, and nothing rejected it. `float(result["score"])` was written straight to DB
    columns at six sites, so a model answering `8.5` persisted an 8.5/100 rating, and
    that value then fed recruiter matching, salary prediction and hackathon composites.

    Returns None (never raises) for null/non-numeric input, because these call sites sit
    inside nodes whose documented failure mode is "degrade to an N/A sub-score with an
    honest rationale". A ValueError escaping here would instead crash the node — the
    exact failure the callers' `except` blocks were not written to catch.
    """
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value != value or value in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return round(max(lo, min(hi, value)), 1)


def validate_structured(result: dict[str, Any], parameters: dict[str, Any], schema_name: str) -> dict[str, Any]:
    """Check a structured result against the `required`/`type` parts of its own schema.

    Tool-calling makes providers *usually* honor the schema, so this is a cheap guard
    against the residual case rather than a full JSON-Schema validator. It catches the
    two failures that actually reach the DB: a missing required key (which becomes a
    `KeyError` deep inside a node) and a field of the wrong JSON type.

    Raises `LLMInvalidOutput`, which is retryable — resampling frequently fixes a
    malformed tool call.
    """
    if not isinstance(result, dict):
        raise LLMInvalidOutput(f"'{schema_name}' returned {type(result).__name__}, expected an object.")

    missing = [key for key in parameters.get("required", []) if key not in result]
    if missing:
        raise LLMInvalidOutput(f"'{schema_name}' output is missing required field(s): {sorted(missing)}.")

    json_types: dict[str, tuple[type, ...]] = {
        "string": (str,),
        "number": (int, float),
        "integer": (int,),
        "boolean": (bool,),
        "array": (list,),
        "object": (dict,),
    }
    for key, spec in (parameters.get("properties") or {}).items():
        if key not in result or result[key] is None:
            continue
        expected = json_types.get(spec.get("type"))
        # bool is a subclass of int in Python, so a `true` would silently pass a
        # "number" check without this guard.
        if expected and (not isinstance(result[key], expected) or (expected != (bool,) and isinstance(result[key], bool))):
            raise LLMInvalidOutput(
                f"'{schema_name}' field '{key}' should be {spec.get('type')}, got {type(result[key]).__name__}."
            )
    return result


@functools.lru_cache(maxsize=1)
def get_llm_client() -> tuple[str, Any]:
    """Resolves and returns (provider_name, client_instance).

    Raises LLMUnavailable if no valid API key is present for the chosen provider.

    Cached as a process-level singleton for the same reason `get_embedder()` is: a fresh
    `anthropic.Anthropic(...)` / `openai.OpenAI(...)` builds a new httpx client with its
    own empty connection pool, so constructing one per call meant every single LLM call
    in the app paid a full TCP+TLS handshake and reused nothing. The provider SDK clients
    are thread-safe and intended to be long-lived, and the settings this reads from are
    themselves `lru_cache`d, so there is no per-request state to vary on.

    `LLMUnavailable` (missing API key) is raised before any client is constructed, and
    `lru_cache` does not cache exceptions — a call that fails on a missing key will
    re-evaluate normally once the key is configured.
    """
    settings = get_settings()
    provider = (settings.llm_provider or "anthropic").lower()

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMNotConfigured("ANTHROPIC_API_KEY is not configured.")
        import anthropic

        return ("anthropic", anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=settings.llm_timeout_seconds))

    if provider == "openai":
        if not settings.openai_api_key:
            raise LLMNotConfigured("OPENAI_API_KEY is not configured.")
        import openai

        return ("openai", openai.OpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds))

    if provider in {"grok", "groq"}:
        api_key = settings.grok_api_key or settings.openai_api_key
        if not api_key:
            raise LLMNotConfigured("GROK_API_KEY / GROQ_API_KEY is not configured.")
        import openai

        # Groq keys start with 'gsk_', xAI keys start with 'xai-'
        if api_key.startswith("gsk_") or provider == "groq":
            base_url = settings.llm_base_url or "https://api.groq.com/openai/v1"
        else:
            base_url = settings.llm_base_url or "https://api.x.ai/v1"

        return ("grok", openai.OpenAI(api_key=api_key, base_url=base_url, timeout=settings.llm_timeout_seconds))

    if provider == "gemini":
        api_key = settings.gemini_api_key or settings.openai_api_key
        if not api_key:
            raise LLMNotConfigured("GEMINI_API_KEY is not configured.")
        import openai

        base_url = settings.llm_base_url or "https://generativelanguage.googleapis.com/v1beta/openai/"
        return ("gemini", openai.OpenAI(api_key=api_key, base_url=base_url, timeout=settings.llm_timeout_seconds))

    if provider in {"openai_compatible", "ollama", "local"}:
        import openai

        base_url = settings.llm_base_url or "http://localhost:11434/v1"
        api_key = settings.openai_api_key or "ollama"
        return ("openai_compatible", openai.OpenAI(api_key=api_key, base_url=base_url, timeout=settings.llm_timeout_seconds))

    raise LLMUnavailable(f"Unsupported LLM provider: {provider}")


async def generate_completion(
    prompt: str,
    system_prompt: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
    is_fast: bool = False,
    response_json: bool = False,
    agent_name: str | None = None,
    max_tokens: int | None = None,
) -> Any:
    """Unified free-form completion function that works transparently across
    Anthropic, OpenAI, Groq/Grok, Gemini, and OpenAI-compatible providers.

    Prefer `generate_structured` for anything that needs schema-constrained output
    (the overwhelming majority of this codebase's LLM calls) — it handles the
    Anthropic-vs-OpenAI tool-calling schema differences for you. This function is for
    the rare free-text/narrative case.

    The underlying provider SDKs are used synchronously and run via `asyncio.to_thread`
    so a slow LLM round-trip doesn't block the event loop (and every other in-flight
    request) for the duration of the call.
    """
    settings = get_settings()
    provider, client = get_llm_client()
    model = settings.llm_model_fast if is_fast else settings.llm_model_judgment

    logger.info("LLM_COMPLETION provider=%s model=%s prompt_len=%d", provider, model, len(prompt))

    with start_llm_generation(
        name=agent_name or "generate-completion",
        model=model,
        input_data={"system": system_prompt, "prompt": prompt},
        metadata={"provider": provider},
    ) as generation:
        if provider == "anthropic":
            messages = [{"role": "user", "content": prompt}]
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens or settings.llm_max_tokens_default,
                "messages": messages,
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            if tools:
                kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

            res = await _call_with_retry(
                lambda: client.messages.create(**kwargs),
                provider=provider,
                what=agent_name or 'generate-completion',
            )
            output: Any = None
            if tools:
                for block in res.content:
                    if block.type == "tool_use":
                        output = block.input
                        break
            if output is None:
                output = res.content[0].text if res.content else ""

            usage = getattr(res, "usage", None)
            generation.update(
                output=output,
                usage_details={"input": usage.input_tokens, "output": usage.output_tokens} if usage else None,
            )
            return output

        # OpenAI / Grok / Gemini / OpenAI-compatible provider logic
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens or settings.llm_max_tokens_default,
        }
        if response_json:
            kwargs["response_format"] = {"type": "json_object"}

        res = await _call_with_retry(
            lambda: client.chat.completions.create(**kwargs),
            provider=provider,
            what=agent_name or 'generate-completion',
        )
        content = res.choices[0].message.content or ""

        output = content
        if response_json:
            try:
                output = json.loads(content)
            except Exception:
                output = content

        usage = getattr(res, "usage", None)
        generation.update(
            output=output,
            usage_details={"input": usage.prompt_tokens, "output": usage.completion_tokens} if usage else None,
        )
        return output


async def generate_structured(
    schema_name: str,
    schema_description: str,
    parameters: dict[str, Any],
    prompt: str,
    system_prompt: str | None = None,
    is_fast: bool = False,
    max_tokens: int | None = None,
    temperature: float | None = None,
    agent_name: str | None = None,
) -> dict[str, Any]:
    """Provider-agnostic schema-constrained completion.

    `parameters` is a JSON-schema `object` spec (the same shape as Anthropic's
    `input_schema` / OpenAI's `parameters`) — e.g.
    `{"type": "object", "properties": {...}, "required": [...]}`.

    Translates it to each provider's native tool-calling format under the hood
    (Anthropic `tools`/`tool_choice`, OpenAI-style `tools=[{"type":"function",...}]`)
    so callers write the schema once. Raises `LLMUnavailable` if the model doesn't
    return the requested structured output, or the provider call fails.

    Every call is wrapped in a Langfuse `generation` observation (model, token usage,
    input/output) via `start_llm_generation`, nested under whatever `start_agent_trace`
    span is active — see `services.api.core.tracing`.

    The underlying provider SDKs are used synchronously and run via `asyncio.to_thread`
    so a slow LLM round-trip doesn't block the event loop (and every other in-flight
    request) for the duration of the call.
    """
    settings = get_settings()
    provider, client = get_llm_client()
    model = settings.llm_model_fast if is_fast else settings.llm_model_judgment
    max_tokens = max_tokens or settings.llm_max_tokens_default

    with start_llm_generation(
        name=agent_name or schema_name,
        model=model,
        input_data={"system": system_prompt, "prompt": prompt} if system_prompt else {"prompt": prompt},
        metadata={"provider": provider, "schema": schema_name},
    ) as generation:
        if provider == "anthropic":
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [
                    {
                        "name": schema_name,
                        "description": schema_description,
                        "input_schema": parameters,
                    }
                ],
                "tool_choice": {"type": "tool", "name": schema_name},
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            if temperature is not None:
                kwargs["temperature"] = temperature

            response = await _call_with_retry(
                lambda: client.messages.create(**kwargs),
                provider=provider,
                what=agent_name or schema_name,
            )

            result = None
            for block in response.content:
                if block.type == "tool_use" and block.name == schema_name:
                    result = block.input
                    break
            if result is None:
                raise LLMInvalidOutput(f"Model did not return structured '{schema_name}' output.")

            result = validate_structured(result, parameters, schema_name)
            usage = getattr(response, "usage", None)
            generation.update(
                output=result,
                usage_details={"input": usage.input_tokens, "output": usage.output_tokens} if usage else None,
            )
            return result

        # OpenAI / Grok(Groq) / Gemini / OpenAI-compatible — OpenAI function-calling schema
        messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + [
            {"role": "user", "content": prompt}
        ]
        completion_kwargs: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if temperature is not None:
            completion_kwargs["temperature"] = temperature

        tool_spec = [
            {
                "type": "function",
                "function": {
                    "name": schema_name,
                    "description": schema_description,
                    "parameters": parameters,
                },
            }
        ]
        response = await _call_with_retry(
            lambda: client.chat.completions.create(
                **completion_kwargs,
                tools=tool_spec,
                tool_choice={"type": "function", "function": {"name": schema_name}},
            ),
            provider=provider,
            what=agent_name or schema_name,
        )

        message = response.choices[0].message
        result = None
        for call in message.tool_calls or []:
            if call.function.name == schema_name:
                try:
                    result = json.loads(call.function.arguments)
                except json.JSONDecodeError as exc:
                    raise LLMInvalidOutput(f"Model returned malformed structured output for '{schema_name}'.") from exc
                break
        if result is None:
            raise LLMInvalidOutput(f"Model did not return structured '{schema_name}' output.")

        result = validate_structured(result, parameters, schema_name)
        usage = getattr(response, "usage", None)
        generation.update(
            output=result,
            usage_details={"input": usage.prompt_tokens, "output": usage.completion_tokens} if usage else None,
        )
        return result
