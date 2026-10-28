"""A recruiter may only read reports for interviews they own.

`GET /interview-sessions/{id}/report` required the `recruiter` role and nothing else,
then returned the report plus the full transcript for any session id — so any recruiter
could read any candidate's interview transcript and hiring recommendation on the
platform. The sibling list route (`/interview-definitions/{id}/attempts`) has always
scoped through `_definition_owned_by`; this route was the gap in that pattern.
"""

from __future__ import annotations

import uuid
from importlib import import_module

import pytest
from fastapi import HTTPException

from packages.db.models import InterviewDefinition, InterviewSession

assessments_router = import_module("services.api.modules.assessments.router")

from services.api.tests.conftest import FakeSession, make_user


def _session(definition_id: uuid.UUID | None) -> InterviewSession:
    return InterviewSession(
        id=uuid.uuid4(), candidate_id=uuid.uuid4(), interview_definition_id=definition_id, state={}
    )


async def test_recruiter_who_owns_the_definition_is_allowed() -> None:
    owner = make_user("recruiter")
    definition = InterviewDefinition(id=uuid.uuid4(), created_by_user_id=owner.id)
    session = _session(definition.id)

    # session lookup -> definition lookup -> report lookup -> transcript lookup
    db = FakeSession([session, definition, None])
    with pytest.raises(HTTPException) as exc:
        await assessments_router.get_interview_report(
            session_id=session.id, user=owner, db=db
        )
    # Passed both access checks and failed only on there being no report yet, which is
    # what distinguishes "allowed" from "refused" here.
    assert exc.value.status_code == 404
    assert exc.value.detail == "interview_report_not_found"


async def test_recruiter_from_another_org_is_refused() -> None:
    stranger = make_user("recruiter", email="stranger@example.com")
    definition = InterviewDefinition(id=uuid.uuid4(), created_by_user_id=uuid.uuid4())
    session = _session(definition.id)

    with pytest.raises(HTTPException) as exc:
        await assessments_router.get_interview_report(
            session_id=session.id, user=stranger, db=FakeSession([session, definition])
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "not_your_interview_definition"


async def test_self_practice_session_has_no_recruiter_owner() -> None:
    """A session with no definition was started by a candidate practising alone.

    Nobody owns it in the recruiter sense, so it is refused rather than left readable by
    every recruiter — the "no owner means open to all" default is exactly how these gaps
    appear.
    """
    recruiter = make_user("recruiter")
    session = _session(None)

    with pytest.raises(HTTPException) as exc:
        await assessments_router.get_interview_report(
            session_id=session.id, user=recruiter, db=FakeSession([session])
        )
    assert exc.value.status_code == 403


async def test_unknown_session_is_404() -> None:
    with pytest.raises(HTTPException) as exc:
        await assessments_router.get_interview_report(
            session_id=uuid.uuid4(), user=make_user("recruiter"), db=FakeSession([None])
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "interview_session_not_found"
