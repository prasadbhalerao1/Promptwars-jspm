"""TruGen video-avatar interviews — the REST half (agents, session tokens, transcripts).

The browser half is `@trugen/js-sdk`: it takes the short-lived token minted here and opens
a WebRTC session straight to TruGen, so the API key never leaves this process.

One agent is created per interview session rather than one shared agent. The interviewer
has to be grounded in *this* role's JD and topic plan, and the per-session `context` field
TruGen accepts is stored on the conversation but not documented as reaching the LLM — the
system prompt is the only channel known to. The agent is deleted when the session ends.

The trial plan allows one live conversation at a time, and a conversation that is minted
but never joined keeps that slot until TruGen expires it. `TrugenBusy` exists so callers
can tell the candidate to retry or fall back to the classic interview instead of 500ing.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from services.api.core.config import get_settings

logger = logging.getLogger(__name__)


class TrugenUnavailable(RuntimeError):
    """TRUGEN_API_KEY/TRUGEN_AVATAR_ID aren't configured, or TruGen returned an error."""


class TrugenBusy(TrugenUnavailable):
    """TruGen refused a new conversation because the plan's concurrent-session limit is hit."""


def trugen_enabled() -> bool:
    settings = get_settings()
    return bool(settings.trugen_api_key and settings.trugen_avatar_id)


def _client() -> httpx.AsyncClient:
    settings = get_settings()
    if not trugen_enabled():
        raise TrugenUnavailable("TRUGEN_API_KEY and TRUGEN_AVATAR_ID must both be set.")
    return httpx.AsyncClient(
        base_url=settings.trugen_base_url,
        headers={"X-API-Key": settings.trugen_api_key},
        timeout=settings.trugen_http_timeout_seconds,
    )


def _raise_for(response: httpx.Response, action: str) -> None:
    if response.is_success:
        return
    body = response.text[:300]
    if "concurrent session limit" in body.lower():
        raise TrugenBusy("Another avatar interview is already running. Try again in a minute.")
    logger.warning("TruGen %s failed: %s %s", action, response.status_code, body)
    raise TrugenUnavailable(f"TruGen {action} failed ({response.status_code}).")


async def create_interview_agent(
    *, name: str, system_prompt: str, greeting: str, max_duration_seconds: int
) -> str:
    """Create a private interviewer agent and return its id."""
    settings = get_settings()
    body: dict[str, Any] = {
        "agent_name": name[:80],
        "agent_system_prompt": system_prompt,
        # The platform default prompt is written for a support assistant; layered on top
        # of an interviewer it invites the agent to be "helpful" by answering questions.
        "default_system_prompt": False,
        "config": {"timeout": max_duration_seconds},
        "avatars": [
            {
                "avatar_key_id": settings.trugen_avatar_id,
                "timeout": max_duration_seconds,
                "welcome_message": {"messages": [greeting], "wait_time": 1},
                "exit_message": {
                    "messages": ["We're at time. Thank you for your answers, you can end the interview now."],
                    "max_call_duration": max_duration_seconds,
                },
                # Candidates pause to think. `deliberate` waits longer before treating a
                # pause as the end of an answer, so the interviewer doesn't cut them off.
                "turn_handling": "deliberate",
                "interruptability": "low",
            }
        ],
        # Only the transcript is needed; recording the candidate's video is a privacy
        # cost with no use in scoring.
        "record": False,
        "is_public": False,
    }
    async with _client() as client:
        response = await client.post("/ext/agent", json=body)
    _raise_for(response, "agent creation")
    return response.json()["id"]


async def delete_agent(agent_id: str) -> None:
    """Best effort: a leaked agent costs nothing until someone mints a token for it."""
    try:
        async with _client() as client:
            response = await client.delete(f"/ext/agent/{agent_id}")
        if not response.is_success:
            logger.warning("TruGen agent %s not deleted: %s", agent_id, response.status_code)
    except (httpx.HTTPError, TrugenUnavailable):
        logger.warning("TruGen agent %s not deleted", agent_id, exc_info=True)


async def create_conversation_token(
    *, agent_id: str, user_id: str, user_name: str, context: dict[str, Any]
) -> dict[str, str]:
    """Mint a 5-minute browser token. Returns `{"token", "conversation_id"}`.

    `user_id` is our interview session id; TruGen echoes it back on the conversation
    record, which keeps a conversation traceable to the session that started it.
    """
    async with _client() as client:
        response = await client.post(
            "/auth/conversation",
            headers={"X-Agent-Id": agent_id},
            json={
                "agentId": agent_id,
                "userName": user_name or "Candidate",
                "userId": user_id,
                "context": context,
                "metaData": {},
            },
        )
    _raise_for(response, "session token")
    data = response.json()
    return {"token": data["token"], "conversation_id": data["conversationId"]}


async def fetch_transcript(conversation_id: str) -> tuple[str, list[dict[str, str]]]:
    """Return `(status, turns)` for a conversation, turns as `{"role", "text"}` in spoken order.

    Roles are mapped onto the classic interview's vocabulary (`agent`/`candidate`) so the
    report agent reads both modes identically. Tool-call and empty entries are dropped.
    """
    async with _client() as client:
        response = await client.get(f"/ext/conversation/{conversation_id}")
    _raise_for(response, "transcript fetch")
    data = response.json()
    # List order, not `timestamp`: a timestamp marks when speech *started*, so a candidate
    # who begins talking over the greeting sorts ahead of it and the Q/A pairing scrambles.
    entries = data.get("transcript") or []
    turns = [
        {"role": "agent" if e.get("role") == "assistant" else "candidate", "text": e["content"].strip()}
        for e in entries
        if e.get("type", "message") == "message"
        and e.get("role") in ("assistant", "user")
        and (e.get("content") or "").strip()
    ]
    return str(data.get("status") or ""), turns
