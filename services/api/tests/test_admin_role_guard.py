"""The last admin must not be demotable.

`admin` is not self-assignable at signup, so demoting the only admin leaves nobody able
to reach `/admin/*` — including the endpoint that would grant the role back. Recovery
would need direct database access.
"""

from __future__ import annotations

import uuid
from importlib import import_module

import pytest
from fastapi import HTTPException

from packages.shared_schemas.users import Role, RoleUpdateRequest

admin_router = import_module("services.api.modules.admin.router")

from services.api.tests.conftest import FakeSession, make_user


class _AdminSession(FakeSession):
    """FakeSession plus `get()`/`scalar()`, which the admin route uses."""

    def __init__(self, target, admin_count: int) -> None:
        super().__init__([])
        self._target = target
        self._admin_count = admin_count

    async def get(self, _model, _pk):
        return self._target

    async def scalar(self, *_args, **_kwargs):
        return self._admin_count


async def test_demoting_the_only_admin_is_refused() -> None:
    target = make_user("admin")
    with pytest.raises(HTTPException) as exc:
        await admin_router.update_user_role(
            user_id=target.id,
            payload=RoleUpdateRequest(role=Role.candidate),
            admin=target,
            db=_AdminSession(target, admin_count=0),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail == "cannot_demote_last_admin"


async def test_demoting_one_of_several_admins_is_allowed() -> None:
    target = make_user("admin")
    updated = await admin_router.update_user_role(
        user_id=target.id,
        payload=RoleUpdateRequest(role=Role.candidate),
        admin=make_user("admin", email="other-admin@example.com"),
        db=_AdminSession(target, admin_count=1),
    )
    assert updated.role == "candidate"


async def test_promoting_to_admin_is_unaffected() -> None:
    target = make_user("candidate")
    updated = await admin_router.update_user_role(
        user_id=target.id,
        payload=RoleUpdateRequest(role=Role.admin),
        admin=make_user("admin"),
        db=_AdminSession(target, admin_count=0),
    )
    assert updated.role == "admin"


async def test_unknown_user_is_404() -> None:
    with pytest.raises(HTTPException) as exc:
        await admin_router.update_user_role(
            user_id=uuid.uuid4(),
            payload=RoleUpdateRequest(role=Role.candidate),
            admin=make_user("admin"),
            db=_AdminSession(None, admin_count=5),
        )
    assert exc.value.status_code == 404
