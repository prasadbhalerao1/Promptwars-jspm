"""A candidate may only act on their own interview session.

`GET /interview-sessions/{id}` checked that `session.candidate_id` belonged to the
caller. `POST .../turn` and `POST .../end` did not: they loaded the session by UUID and
never compared it to anyone. Any candidate holding a session id could therefore answer
questions into someone else's interview, and `/end` could force-finalize it — writing an
`InterviewReport` whose technical/communication ratings and hiring recommendation a
recruiter later reads as an assessment of the victim.

All three now route through `_session_owned_by`, so these tests target that helper: it is
the single place the rule lives, and a route that stops using it fails the route-level
test below.
"""

from __future__ import annotations

import uuid
from importlib import import_module

import pytest
from fastapi import HTTPException

from packages.db.models import CandidateProfile, InterviewSession
# `import ...assessments.router` binds the APIRouter object, not the module: the
# package `__init__` does `from ...router import router`, so the submodule attribute is
# shadowed. import_module returns the module itself, which is what monkeypatch needs.
assessments_router = import_module("services.api.modules.assessments.router")
from services.api.tests.conftest import FakeSession


def _session_for(candidate_id: uuid.UUID, status: str = "in_progress") -> InterviewSession:
    session = InterviewSession(id=uuid.uuid4(), candidate_id=candidate_id, state={})
    session.status = status
    return session


@pytest.fixture
def owner_profile() -> CandidateProfile:
    return CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4())


async def test_owner_may_load_their_session(monkeypatch, candidate, owner_profile) -> None:
    session = _session_for(owner_profile.id)
    monkeypatch.setattr(
        assessments_router, "_get_or_create_profile", _profile_stub(owner_profile)
    )

    loaded, profile = await assessments_router._session_owned_by(
        FakeSession([session]), session.id, candidate
    )
    assert loaded is session
    assert profile is owner_profile


async def test_stranger_is_refused(monkeypatch, other_candidate, owner_profile) -> None:
    session = _session_for(owner_profile.id)
    intruder_profile = CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
    monkeypatch.setattr(
        assessments_router, "_get_or_create_profile", _profile_stub(intruder_profile)
    )

    with pytest.raises(HTTPException) as exc:
        await assessments_router._session_owned_by(
            FakeSession([session]), session.id, other_candidate
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "not_your_interview_session"


async def test_missing_session_is_404(monkeypatch, candidate, owner_profile) -> None:
    monkeypatch.setattr(
        assessments_router, "_get_or_create_profile", _profile_stub(owner_profile)
    )
    with pytest.raises(HTTPException) as exc:
        await assessments_router._session_owned_by(
            FakeSession([None]), uuid.uuid4(), candidate
        )
    assert exc.value.status_code == 404


@pytest.mark.parametrize("route_name", ["interview_turn", "end_interview", "get_interview_session"])
async def test_mutating_routes_enforce_ownership(monkeypatch, other_candidate, route_name) -> None:
    """Each candidate-facing session route must refuse a non-owner.

    Asserted per-route, not just on the helper, because the original bug was precisely
    that two routes did not call the helper. Every one of these must 403 before it
    reaches any LLM/graph work.
    """
    owner_profile = CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
    intruder_profile = CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4())
    session = _session_for(owner_profile.id)
    monkeypatch.setattr(
        assessments_router, "_get_or_create_profile", _profile_stub(intruder_profile)
    )

    route = getattr(assessments_router, route_name)
    kwargs = {"session_id": session.id, "user": other_candidate, "db": FakeSession([session])}
    if route_name == "interview_turn":
        kwargs["body"] = _AnswerStub()

    with pytest.raises(HTTPException) as exc:
        await route(**kwargs)
    assert exc.value.status_code == 403
    assert exc.value.detail == "not_your_interview_session"


class _AnswerStub:
    answer_text = "an answer the intruder should never get to submit"


def _profile_stub(profile: CandidateProfile):
    async def _stub(_db, _user):
        return profile

    return _stub
