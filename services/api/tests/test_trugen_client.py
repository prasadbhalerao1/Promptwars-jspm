"""TruGen avatar-interview client: request shape, error mapping and transcript parsing.

Every test runs against `httpx.MockTransport`, so nothing here touches the real TruGen API
or needs a key. What is pinned:

* the interviewer prompt reaches the field the LLM actually reads (`persona_prompt`), the
  agent is private, and the candidate's video is not recorded;
* the plan's concurrent-session limit surfaces as `TrugenBusy` (which the router turns
  into a retryable 429) rather than a generic failure;
* transcripts keep spoken order and map onto the classic interview's role vocabulary, so
  the report agent scores both interview modes from identical input.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from services.api.core import trugen


def _settings(**overrides):
    values = {
        "trugen_api_key": "test-key",
        "trugen_avatar_id": "avatar-1",
        "trugen_base_url": "https://trugen.test/v1",
        "trugen_http_timeout_seconds": 5,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def mock_trugen(monkeypatch):
    """Route the client through a handler; returns the list of captured requests."""
    captured: list[httpx.Request] = []
    state: dict = {"handler": lambda request: httpx.Response(200, json={})}

    def transport_handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return state["handler"](request)

    settings = _settings()
    monkeypatch.setattr(trugen, "get_settings", lambda: settings)

    def client() -> httpx.AsyncClient:
        if not trugen.trugen_enabled():
            raise trugen.TrugenUnavailable("disabled")
        return httpx.AsyncClient(
            base_url=settings.trugen_base_url,
            headers={"X-API-Key": settings.trugen_api_key},
            transport=httpx.MockTransport(transport_handler),
        )

    monkeypatch.setattr(trugen, "_client", client)

    def set_handler(handler):
        state["handler"] = handler

    return SimpleNamespace(requests=captured, respond=set_handler)


@pytest.mark.parametrize(
    ("key", "avatar", "expected"),
    [("k", "a", True), ("", "a", False), ("k", "", False), ("", "", False)],
)
def test_enabled_requires_both_key_and_avatar(monkeypatch, key, avatar, expected):
    monkeypatch.setattr(trugen, "get_settings", lambda: _settings(trugen_api_key=key, trugen_avatar_id=avatar))
    assert trugen.trugen_enabled() is expected


def test_real_client_refuses_to_build_without_credentials(monkeypatch):
    monkeypatch.setattr(trugen, "get_settings", lambda: _settings(trugen_api_key=""))
    with pytest.raises(trugen.TrugenUnavailable):
        trugen._client()


async def test_agent_carries_prompt_in_persona_and_is_private(mock_trugen):
    mock_trugen.respond(lambda r: httpx.Response(200, json={"id": "agent-42"}))

    agent_id = await trugen.create_interview_agent(
        name="x" * 200,
        system_prompt="You are interviewing for Backend Engineer.",
        greeting="Hi there.",
        max_duration_seconds=300,
        conversational_context="Role: Backend Engineer",
    )

    assert agent_id == "agent-42"
    body = json.loads(mock_trugen.requests[0].content)
    avatar = body["avatars"][0]
    assert avatar["persona_prompt"] == "You are interviewing for Backend Engineer."
    assert avatar["avatar_key_id"] == "avatar-1"
    assert avatar["timeout"] == 300 and body["config"]["timeout"] == 300
    assert body["record"] is False
    assert body["is_public"] is False
    assert body["default_system_prompt"] is False
    assert len(body["agent_name"]) == 80
    assert mock_trugen.requests[0].headers["X-API-Key"] == "test-key"


async def test_concurrent_session_limit_maps_to_busy(mock_trugen):
    mock_trugen.respond(
        lambda r: httpx.Response(500, text="Error creating conversation: concurrent session limit reached")
    )
    with pytest.raises(trugen.TrugenBusy):
        await trugen.create_conversation_token(agent_id="a", user_id="s", user_name="", context={})


async def test_other_errors_are_unavailable_not_busy(mock_trugen):
    mock_trugen.respond(lambda r: httpx.Response(500, json={"error": "plan limit exceeded"}))
    with pytest.raises(trugen.TrugenUnavailable) as exc:
        await trugen.create_interview_agent(
            name="n", system_prompt="p", greeting="g", max_duration_seconds=300
        )
    assert not isinstance(exc.value, trugen.TrugenBusy)


async def test_token_request_targets_agent_and_maps_response(mock_trugen):
    mock_trugen.respond(
        lambda r: httpx.Response(200, json={"token": "jwt", "conversationId": "conv-1", "url": "ignored"})
    )

    minted = await trugen.create_conversation_token(
        agent_id="agent-9", user_id="session-1", user_name="", context={"k": "v"}
    )

    assert minted == {"token": "jwt", "conversation_id": "conv-1"}
    request = mock_trugen.requests[0]
    assert request.headers["X-Agent-Id"] == "agent-9"
    body = json.loads(request.content)
    assert body["userId"] == "session-1"
    assert body["userName"] == "Candidate"  # blank name falls back
    assert body["context"] == {"k": "v"}


async def test_transcript_keeps_spoken_order_and_maps_roles(mock_trugen):
    mock_trugen.respond(
        lambda r: httpx.Response(
            200,
            json={
                "status": "Ended",
                "transcript": [
                    # Timestamps deliberately out of order: list order is the spoken order.
                    {"role": "assistant", "type": "message", "content": " Tell me about indexing. ", "timestamp": "10:00:07"},
                    {"role": "user", "type": "message", "content": "I use B-tree indexes.", "timestamp": "10:00:04"},
                    {"role": "assistant", "type": "tool_call", "content": "lookup()"},
                    {"role": "user", "type": "message", "content": "   "},
                    {"role": "system", "type": "message", "content": "internal"},
                    {"role": "assistant", "content": "Thanks."},
                ],
            },
        )
    )

    status, turns = await trugen.fetch_transcript("conv-1")

    assert status == "Ended"
    assert turns == [
        {"role": "agent", "text": "Tell me about indexing."},
        {"role": "candidate", "text": "I use B-tree indexes."},
        {"role": "agent", "text": "Thanks."},
    ]


async def test_empty_transcript_is_an_empty_list(mock_trugen):
    mock_trugen.respond(lambda r: httpx.Response(200, json={"status": None, "transcript": None}))
    assert await trugen.fetch_transcript("conv-1") == ("", [])


async def test_conversation_lookup_filters_by_agent_and_sorts(mock_trugen):
    page_one = [
        {"id": f"other-{i}", "agent_id": "someone-else", "created_at": f"2026-10-28T09:{i:02d}"}
        for i in range(48)
    ] + [
        {"id": "second", "agent_id": "mine", "created_at": "2026-10-28T10:05"},
        {"id": "first", "agent_id": "mine", "created_at": "2026-10-28T10:01"},
    ]
    page_two = [{"id": "third", "agent_id": "mine", "created_at": "2026-10-28T10:09"}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=page_one if request.url.params["offset"] == "0" else page_two)

    mock_trugen.respond(handler)

    assert await trugen.conversation_ids_for_agent("mine") == ["first", "second", "third"]
    # A short second page ends paging instead of walking all `max_pages`.
    assert len(mock_trugen.requests) == 2


async def test_delete_agent_never_raises(mock_trugen):
    mock_trugen.respond(lambda r: httpx.Response(404, json={"error": "not found"}))
    await trugen.delete_agent("gone")  # logged, not raised

    def boom(request):
        raise httpx.ConnectError("down")

    mock_trugen.respond(boom)
    await trugen.delete_agent("gone")
