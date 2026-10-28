"""Avatar-interview routes: state guards, TruGen failure mapping, and the no-answers rule.

The handlers run for real against `FakeSession`; only the TruGen client is replaced, so
no test reaches the network. Ownership itself is covered by
`test_interview_session_access.py` (both routes go through `_session_owned_by`); here it
is stubbed to hand back a session the caller owns.
"""

from __future__ import annotations

import uuid
from importlib import import_module

import pytest
from fastapi import HTTPException

from packages.db.models import CandidateProfile, InterviewSession
from services.api.core import trugen
from services.api.tests.conftest import FakeSession

assessments_router = import_module("services.api.modules.assessments.router")


def _avatar_session(status: str = "in_progress", **state) -> InterviewSession:
    session = InterviewSession(
        id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        state={
            "mode": "avatar",
            "topic_plan": ["REST API design", "Database indexing"],
            "job_context": {
                "role_title": "Backend Engineer",
                "job_description": "Build FastAPI services on Postgres.",
                "years_experience": 3,
            },
            **state,
        },
    )
    session.status = status
    return session


@pytest.fixture
def owned(monkeypatch):
    """Make `_session_owned_by` return the given session for the caller."""

    def install(session: InterviewSession) -> CandidateProfile:
        profile = CandidateProfile(id=session.candidate_id, user_id=uuid.uuid4())

        async def stub(_db, _session_id, _user):
            return session, profile

        monkeypatch.setattr(assessments_router, "_session_owned_by", stub)
        return profile

    return install


@pytest.fixture
def fake_trugen(monkeypatch):
    calls = {"create": 0, "token": 0, "delete": []}

    async def create_interview_agent(**kwargs):
        calls["create"] += 1
        calls["create_kwargs"] = kwargs
        return "agent-1"

    async def create_conversation_token(**kwargs):
        calls["token"] += 1
        return {"token": "jwt", "conversation_id": f"conv-{calls['token']}"}

    async def delete_agent(agent_id):
        calls["delete"].append(agent_id)

    monkeypatch.setattr(trugen, "create_interview_agent", create_interview_agent)
    monkeypatch.setattr(trugen, "create_conversation_token", create_conversation_token)
    monkeypatch.setattr(trugen, "delete_agent", delete_agent)
    return calls


async def test_classic_session_cannot_mint_an_avatar_token(owned, candidate) -> None:
    session = _avatar_session()
    session.state = {**session.state, "mode": "classic"}
    owned(session)

    with pytest.raises(HTTPException) as exc:
        await assessments_router.avatar_session_token(session.id, candidate, FakeSession())
    assert exc.value.status_code == 409
    assert exc.value.detail == "not_an_avatar_session"


async def test_finished_session_cannot_reconnect(owned, candidate, fake_trugen) -> None:
    session = _avatar_session(status="completed")
    owned(session)

    with pytest.raises(HTTPException) as exc:
        await assessments_router.avatar_session_token(session.id, candidate, FakeSession())
    assert exc.value.status_code == 409
    assert fake_trugen["create"] == 0


async def test_first_token_creates_a_grounded_agent_and_records_the_conversation(
    owned, candidate, fake_trugen
) -> None:
    session = _avatar_session()
    owned(session)

    minted = await assessments_router.avatar_session_token(session.id, candidate, FakeSession())

    assert minted == {"token": "jwt", "conversation_id": "conv-1"}
    prompt = fake_trugen["create_kwargs"]["system_prompt"]
    # The interviewer is grounded in this role, not a generic persona.
    assert "Backend Engineer" in prompt
    assert "Build FastAPI services on Postgres." in prompt
    assert "Database indexing" in prompt
    assert session.state["trugen_agent_id"] == "agent-1"
    assert session.state["trugen_conversation_ids"] == ["conv-1"]


async def test_reconnect_reuses_the_agent_and_appends_the_conversation(
    owned, candidate, fake_trugen
) -> None:
    session = _avatar_session(trugen_agent_id="agent-1", trugen_conversation_ids=["conv-0"])
    owned(session)

    await assessments_router.avatar_session_token(session.id, candidate, FakeSession())

    assert fake_trugen["create"] == 0
    assert session.state["trugen_conversation_ids"] == ["conv-0", "conv-1"]


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (trugen.TrugenBusy("slot taken"), 429, "avatar_busy"),
        (trugen.TrugenUnavailable("down"), 503, "avatar_interviews_unavailable"),
    ],
)
async def test_trugen_failures_map_to_retryable_errors(
    monkeypatch, owned, candidate, fake_trugen, error, status_code, detail
) -> None:
    session = _avatar_session()
    owned(session)

    async def failing_token(**_kwargs):
        raise error

    monkeypatch.setattr(trugen, "create_conversation_token", failing_token)
    db = FakeSession()

    with pytest.raises(HTTPException) as exc:
        await assessments_router.avatar_session_token(session.id, candidate, db)
    assert (exc.value.status_code, exc.value.detail) == (status_code, detail)
    # The agent was created before minting failed; it is kept so a retry reuses it
    # instead of creating a second one.
    assert session.state["trugen_agent_id"] == "agent-1"
    assert db.committed


async def test_ending_without_any_answer_is_refused_and_not_scored(
    monkeypatch, owned, candidate, fake_trugen
) -> None:
    session = _avatar_session(trugen_agent_id="agent-1", trugen_conversation_ids=["conv-1"])
    owned(session)

    async def only_the_interviewer_spoke(_saved):
        return [
            {"role": "agent", "text": "Hi, thanks for joining."},
            {"role": "candidate", "text": assessments_router._AVATAR_KICKOFF},
        ]

    async def run_now(_db, work):
        return await work()

    monkeypatch.setattr(assessments_router, "_collect_avatar_transcript", only_the_interviewer_spoke)
    monkeypatch.setattr(assessments_router, "without_db_connection", run_now)

    with pytest.raises(HTTPException) as exc:
        await assessments_router.end_interview(session.id, candidate, FakeSession())
    assert exc.value.status_code == 409
    assert exc.value.detail == "interview_transcript_empty"
    # Still open, so the candidate can reconnect and answer; the agent is not deleted.
    assert session.status == "in_progress"
    assert fake_trugen["delete"] == []


async def test_unreachable_transcript_is_a_gateway_error(monkeypatch, owned, candidate) -> None:
    session = _avatar_session(trugen_conversation_ids=["conv-1"])
    owned(session)

    async def unreachable(_db, _work):
        raise trugen.TrugenUnavailable("down")

    monkeypatch.setattr(assessments_router, "without_db_connection", unreachable)

    with pytest.raises(HTTPException) as exc:
        await assessments_router.end_interview(session.id, candidate, FakeSession())
    assert exc.value.status_code == 502
    assert exc.value.detail == "avatar_transcript_unavailable"
