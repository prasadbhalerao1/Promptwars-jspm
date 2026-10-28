"""A candidate may not take over another team's hackathon entry.

`_upsert_team` matches on team *name* and rebuilds the roster from the payload: it
deletes every existing member and re-adds whatever the caller sent, then repoints the
team's repo/deck. `POST /hackathons/{id}/submissions` ran that with no ownership check at
all, so any candidate could overwrite any team in any hackathon just by submitting under
its name. (The webhook route next door already required a shared secret for the same
primitive — the authenticated path was the unguarded one.)

`judge_score` rides along on the shared `TeamSubmissionInput` shape because the organizer
CSV and platform webhook may carry a score already; a candidate must never set it on
their own submission.
"""

from __future__ import annotations

import uuid
from importlib import import_module

import pytest
from fastapi import HTTPException

from packages.db.models import CandidateProfile, HackathonTeam
from packages.shared_schemas.hackathon import TeamSubmissionInput

hackathons_router = import_module("services.api.modules.hackathons.router")

from services.api.tests.conftest import FakeSession, make_user


def _payload(**overrides) -> TeamSubmissionInput:
    return TeamSubmissionInput(team_name=overrides.pop("team_name", "Team Rocket"), **overrides)


async def test_non_member_cannot_overwrite_an_existing_team(monkeypatch) -> None:
    user = make_user("candidate")
    profile = CandidateProfile(id=uuid.uuid4(), user_id=user.id)
    existing = HackathonTeam(id=uuid.uuid4(), hackathon_id=uuid.uuid4(), team_name="Team Rocket")

    monkeypatch.setattr(hackathons_router, "_get_hackathon_or_404", _ok_hackathon)
    upsert = _spy_upsert()
    monkeypatch.setattr(hackathons_router, "_upsert_team", upsert)

    # profile lookup -> existing-team lookup -> membership lookup (empty)
    db = FakeSession([profile, existing, []])
    with pytest.raises(HTTPException) as exc:
        await hackathons_router.submit_direct(
            hackathon_id=existing.hackathon_id, body=_payload(), user=user, db=db
        )
    assert exc.value.status_code == 409
    assert exc.value.detail == "team_name_taken"
    assert not upsert.calls, "must refuse before _upsert_team can delete the roster"


async def test_member_may_update_their_own_team(monkeypatch) -> None:
    user = make_user("candidate")
    profile = CandidateProfile(id=uuid.uuid4(), user_id=user.id)
    existing = HackathonTeam(id=uuid.uuid4(), hackathon_id=uuid.uuid4(), team_name="Team Rocket")

    monkeypatch.setattr(hackathons_router, "_get_hackathon_or_404", _ok_hackathon)
    upsert = _spy_upsert(returns=existing)
    monkeypatch.setattr(hackathons_router, "_upsert_team", upsert)

    # profile -> existing team -> membership (present) -> already-listed check (present)
    db = FakeSession([profile, existing, [(uuid.uuid4(),)], [(uuid.uuid4(),)]])
    team = await hackathons_router.submit_direct(
        hackathon_id=existing.hackathon_id, body=_payload(), user=user, db=db
    )
    assert team is existing
    assert upsert.calls, "an actual member must still be able to resubmit"


async def test_new_team_name_is_created_and_submitter_joined(monkeypatch) -> None:
    user = make_user("candidate")
    profile = CandidateProfile(id=uuid.uuid4(), user_id=user.id)
    created = HackathonTeam(id=uuid.uuid4(), hackathon_id=uuid.uuid4(), team_name="Fresh Team")

    monkeypatch.setattr(hackathons_router, "_get_hackathon_or_404", _ok_hackathon)
    monkeypatch.setattr(hackathons_router, "_upsert_team", _spy_upsert(returns=created))

    # profile -> no existing team -> not already listed
    db = FakeSession([profile, None, []])
    await hackathons_router.submit_direct(
        hackathon_id=created.hackathon_id, body=_payload(team_name="Fresh Team"), user=user, db=db
    )
    # The submitter is added to the roster they just created; otherwise a candidate who
    # never connected GitHub would be locked out of their own next submission.
    assert any(getattr(o, "candidate_id", None) == profile.id for o in db.added)


async def test_candidate_supplied_judge_score_is_stripped(monkeypatch) -> None:
    user = make_user("candidate")
    profile = CandidateProfile(id=uuid.uuid4(), user_id=user.id)
    created = HackathonTeam(id=uuid.uuid4(), hackathon_id=uuid.uuid4(), team_name="Fresh Team")

    monkeypatch.setattr(hackathons_router, "_get_hackathon_or_404", _ok_hackathon)
    upsert = _spy_upsert(returns=created)
    monkeypatch.setattr(hackathons_router, "_upsert_team", upsert)

    db = FakeSession([profile, None, []])
    await hackathons_router.submit_direct(
        hackathon_id=created.hackathon_id,
        body=_payload(team_name="Fresh Team", judge_score=10.0),
        user=user,
        db=db,
    )
    assert upsert.last_payload.judge_score is None, "a candidate must not score themselves"


async def test_user_without_candidate_profile_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(hackathons_router, "_get_hackathon_or_404", _ok_hackathon)
    with pytest.raises(HTTPException) as exc:
        await hackathons_router.submit_direct(
            hackathon_id=uuid.uuid4(),
            body=_payload(),
            user=make_user("candidate"),
            db=FakeSession([None]),
        )
    assert exc.value.status_code == 403


async def _ok_hackathon(_db, _hackathon_id):
    return object()


def _spy_upsert(returns=None):
    class _Spy:
        def __init__(self) -> None:
            self.calls = 0
            self.last_payload = None

        async def __call__(self, _db, _hackathon_id, payload):
            self.calls += 1
            self.last_payload = payload
            return returns, 1

    return _Spy()
