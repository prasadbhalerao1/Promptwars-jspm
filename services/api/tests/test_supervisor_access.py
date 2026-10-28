"""`POST /supervisor/route` must apply the owning module's access rule to its subject.

The endpoint dispatches into the real Module 01/02 service functions: the
`candidate_score` node reads any `TalentScore` by candidate id, and `job_match` runs
`_run_matching_and_persist` — a *write* — against any `Job` row. Both subject ids came
from the request body behind nothing but `get_current_user`, so any signed-in user could
read any candidate's Talent Score and trigger persisted matching on a recruiter's job,
routing around `_job_owned_by`. Having no frontend caller is why it went unnoticed.
"""

from __future__ import annotations

import uuid
from importlib import import_module

import pytest
from fastapi import HTTPException

from packages.db.models import CandidateProfile, Job
from packages.shared_schemas.supervisor import SupervisorRouteRequest

supervisor_router = import_module("services.api.modules.supervisor.router")

from services.api.tests.conftest import FakeSession, make_user


async def test_candidate_cannot_route_for_another_candidate() -> None:
    intruder = make_user("candidate")
    victim_profile = CandidateProfile(id=uuid.uuid4(), user_id=uuid.uuid4())

    with pytest.raises(HTTPException) as exc:
        await supervisor_router._authorize_subjects(
            FakeSession([victim_profile]),
            SupervisorRouteRequest(raw_request="score?", candidate_id=victim_profile.id),
            intruder,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "cannot_route_for_other_candidates"


async def test_candidate_may_route_for_themselves() -> None:
    user = make_user("candidate")
    own_profile = CandidateProfile(id=uuid.uuid4(), user_id=user.id)

    await supervisor_router._authorize_subjects(
        FakeSession([own_profile]),
        SupervisorRouteRequest(raw_request="my score?", candidate_id=own_profile.id),
        user,
    )


@pytest.mark.parametrize("role", ["recruiter", "admin"])
async def test_recruiters_and_admins_may_look_up_candidates(role: str) -> None:
    """They evaluate candidates for a living; no per-candidate relationship exists to check."""
    await supervisor_router._authorize_subjects(
        FakeSession([]),
        SupervisorRouteRequest(raw_request="score?", candidate_id=uuid.uuid4()),
        make_user(role),
    )


async def test_non_recruiter_cannot_trigger_job_matching() -> None:
    with pytest.raises(HTTPException) as exc:
        await supervisor_router._authorize_subjects(
            FakeSession([]),
            SupervisorRouteRequest(raw_request="match", job_id=uuid.uuid4()),
            make_user("candidate"),
        )
    assert exc.value.status_code == 403


async def test_recruiter_cannot_match_someone_elses_job() -> None:
    stranger = make_user("recruiter")
    job = Job(id=uuid.uuid4(), posted_by_user_id=uuid.uuid4(), organization_id=uuid.uuid4())

    with pytest.raises(HTTPException) as exc:
        await supervisor_router._authorize_subjects(
            FakeSession([job]),
            SupervisorRouteRequest(raw_request="match", job_id=job.id),
            stranger,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "not_your_job_posting"


async def test_recruiter_may_match_their_own_job() -> None:
    owner = make_user("recruiter")
    job = Job(id=uuid.uuid4(), posted_by_user_id=owner.id, organization_id=None)

    await supervisor_router._authorize_subjects(
        FakeSession([job]),
        SupervisorRouteRequest(raw_request="match", job_id=job.id),
        owner,
    )


async def test_request_naming_no_subject_is_unrestricted() -> None:
    """A bare classification request touches no one's data and stays open."""
    await supervisor_router._authorize_subjects(
        FakeSession([]), SupervisorRouteRequest(raw_request="what can you do?"), make_user("candidate")
    )
