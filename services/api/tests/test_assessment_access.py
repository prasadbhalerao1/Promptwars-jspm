"""Assessment creation, submission and submission-reads must all stay owner-scoped.

Three separate gaps, all in the same chain:

- `create_assessment` took `job_id` from the body unchecked, so a recruiter could attach
  an assessment to another recruiter's posting — which also redirected who
  `_require_submission_access` would later admit.
- `submit_assessment` accepted any assessment id, unlike `get_assessment` which enforces
  assignment. A candidate could submit against someone else's assessment, or against an
  unassigned template.
- `_require_submission_access` returned early (allowing the read) whenever the owning job
  could not be resolved, so submissions against templates were readable by every
  recruiter on the platform.
"""

from __future__ import annotations

import uuid
from importlib import import_module

import pytest
from fastapi import HTTPException

from packages.db.models import Assessment, CandidateProfile, Job, Submission

assessments_router = import_module("services.api.modules.assessments.router")

from services.api.tests.conftest import FakeSession, make_user


def _profile_stub(profile: CandidateProfile):
    async def _stub(_db, _user):
        return profile

    return _stub


# --- create_assessment ---------------------------------------------------------------


async def test_cannot_attach_assessment_to_another_recruiters_job() -> None:
    stranger = make_user("recruiter")
    job = Job(id=uuid.uuid4(), posted_by_user_id=uuid.uuid4(), organization_id=uuid.uuid4())

    with pytest.raises(HTTPException) as exc:
        await assessments_router.create_assessment(
            body=_CreateBody(job_id=job.id), user=stranger, db=FakeSession([job])
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "not_your_job_posting"


async def test_template_without_job_id_is_still_allowed() -> None:
    """`job_id=None` is the documented reusable-template case and must keep working."""
    db = FakeSession([])
    created = await assessments_router.create_assessment(
        body=_CreateBody(job_id=None), user=make_user("recruiter"), db=db
    )
    assert created.job_id is None
    assert db.committed


# --- submit_assessment ---------------------------------------------------------------


async def test_candidate_cannot_submit_against_someone_elses_assessment(monkeypatch) -> None:
    user = make_user("candidate")
    profile = CandidateProfile(id=uuid.uuid4(), user_id=user.id)
    assessment = Assessment(id=uuid.uuid4(), candidate_id=uuid.uuid4(), type="coding", spec={})
    monkeypatch.setattr(assessments_router, "_get_or_create_profile", _profile_stub(profile))

    with pytest.raises(HTTPException) as exc:
        await assessments_router.submit_assessment(
            assessment_id=assessment.id,
            body=_SubmitBody(),
            background_tasks=None,
            user=user,
            db=FakeSession([assessment]),
        )
    assert exc.value.status_code == 404


async def test_candidate_cannot_submit_against_an_unassigned_template(monkeypatch) -> None:
    """Templates have no assignee, and their submissions have no owning recruiter."""
    user = make_user("candidate")
    profile = CandidateProfile(id=uuid.uuid4(), user_id=user.id)
    template = Assessment(id=uuid.uuid4(), candidate_id=None, type="coding", spec={})
    monkeypatch.setattr(assessments_router, "_get_or_create_profile", _profile_stub(profile))

    with pytest.raises(HTTPException) as exc:
        await assessments_router.submit_assessment(
            assessment_id=template.id,
            body=_SubmitBody(),
            background_tasks=None,
            user=user,
            db=FakeSession([template]),
        )
    assert exc.value.status_code == 404


# --- _require_submission_access ------------------------------------------------------


@pytest.mark.parametrize(
    "script,label",
    [
        ([None], "assessment missing"),
        ([Assessment(id=uuid.uuid4(), candidate_id=None, job_id=None, type="c", spec={})], "template"),
        (
            [Assessment(id=uuid.uuid4(), candidate_id=None, job_id=uuid.uuid4(), type="c", spec={}), None],
            "dangling job",
        ),
    ],
)
async def test_unresolvable_owner_is_refused_not_allowed(script, label) -> None:
    submission = Submission(id=uuid.uuid4(), assessment_id=uuid.uuid4(), candidate_id=uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        await assessments_router._require_submission_access(
            FakeSession(script), submission, make_user("recruiter")
        )
    assert exc.value.status_code == 403, f"{label} must refuse, not fall through"


async def test_owning_recruiter_may_read_the_submission() -> None:
    owner = make_user("recruiter")
    job = Job(id=uuid.uuid4(), posted_by_user_id=owner.id, organization_id=None)
    assessment = Assessment(id=uuid.uuid4(), candidate_id=uuid.uuid4(), job_id=job.id, type="c", spec={})
    submission = Submission(id=uuid.uuid4(), assessment_id=assessment.id, candidate_id=uuid.uuid4())

    await assessments_router._require_submission_access(
        FakeSession([assessment, job]), submission, owner
    )


async def test_org_mate_may_read_the_submission() -> None:
    org_id = uuid.uuid4()
    colleague = make_user("recruiter", organization_id=org_id)
    job = Job(id=uuid.uuid4(), posted_by_user_id=uuid.uuid4(), organization_id=org_id)
    assessment = Assessment(id=uuid.uuid4(), candidate_id=uuid.uuid4(), job_id=job.id, type="c", spec={})
    submission = Submission(id=uuid.uuid4(), assessment_id=assessment.id, candidate_id=uuid.uuid4())

    await assessments_router._require_submission_access(
        FakeSession([assessment, job]), submission, colleague
    )


class _CreateBody:
    def __init__(self, job_id) -> None:
        self.job_id = job_id
        self.candidate_id = None
        self.type = "coding"
        self.spec = {}


class _SubmitBody:
    code_or_answers = {"code": "print(1)"}
    test_results: list = []
