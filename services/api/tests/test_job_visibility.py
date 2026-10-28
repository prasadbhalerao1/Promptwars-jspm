"""One definition of "jobs this recruiter may see", used by every call site.

`_job_owned_by` grants access on org membership *or* direct authorship, but the list and
aggregate endpoints each rebuilt that rule inline and two of them filtered on
`posted_by_user_id` alone. A recruiter in an organization therefore saw an org-mate's job
in `GET /jobs` while `GET /applications` returned no applicants for it and the analytics
endpoints omitted it — the same job visible or invisible depending on which endpoint
asked, even though fetching it by id worked.
"""

from __future__ import annotations

import uuid
from importlib import import_module

import pytest

recruitment_router = import_module("services.api.modules.recruitment.router")

from services.api.tests.conftest import make_user


def _rendered(clause) -> str:
    return str(clause.compile(compile_kwargs={"literal_binds": True}))


def _hex(value: uuid.UUID) -> str:
    """SQLAlchemy renders a bound UUID without hyphens, so compare on `.hex`."""
    return value.hex


def test_org_member_is_scoped_by_organization() -> None:
    org_id = uuid.uuid4()
    clause = recruitment_router._visible_jobs_clause(make_user("recruiter", organization_id=org_id))
    rendered = _rendered(clause)
    assert "organization_id" in rendered
    assert _hex(org_id) in rendered


def test_solo_recruiter_falls_back_to_authorship() -> None:
    user = make_user("recruiter", organization_id=None)
    rendered = _rendered(recruitment_router._visible_jobs_clause(user))
    assert "posted_by_user_id" in rendered
    assert _hex(user.id) in rendered


def test_visibility_matches_the_single_row_rule() -> None:
    """The list predicate must agree with `_job_owned_by`'s branches.

    `_job_owned_by` returns the job when `user.organization_id and job.organization_id ==
    user.organization_id`, else when `job.posted_by_user_id == user.id`. The clause has to
    key off the same two columns, or single-row and list access drift apart again.
    """
    org_user = make_user("recruiter", organization_id=uuid.uuid4())
    solo_user = make_user("recruiter", organization_id=None)
    assert "organization_id" in _rendered(recruitment_router._visible_jobs_clause(org_user))
    assert "posted_by_user_id" in _rendered(recruitment_router._visible_jobs_clause(solo_user))


def test_no_call_site_reimplements_the_rule() -> None:
    """Guards the regression directly: the inline `posted_by_user_id` filters are gone.

    `_job_owned_by` itself still compares that column on a single row, which is correct;
    what must not come back is a *query* filtering on it instead of using the clause.
    """
    import inspect

    source = inspect.getsource(recruitment_router)
    offenders = [
        line.strip()
        for line in source.splitlines()
        if "select(Job" in line and "posted_by_user_id" in line
    ]
    assert not offenders, f"call sites bypassing _visible_jobs_clause: {offenders}"
