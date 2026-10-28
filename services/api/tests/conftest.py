"""Shared fixtures for API-layer tests.

These tests exercise authorization decisions — who may read or write which row — without
a live database. The models are Postgres-specific (`JSONB`, `UUID(as_uuid=True)`), so
SQLite is not a usable stand-in, and requiring a running Postgres would mean the checks
that matter most only run when someone remembers to start a container.

Instead, `FakeSession` implements the narrow slice of `AsyncSession` the routers actually
use — `execute()` returning a result whose `scalar_one_or_none()` / `first()` / `all()`
answer from a caller-supplied script — so a handler can be invoked as a plain coroutine
with `db=FakeSession([...])`. That keeps these tests fast and dependency-free while still
running the real handler body, including the real `HTTPException`s.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from packages.db.models import User


class FakeResult:
    """Stands in for a SQLAlchemy `Result` over one scripted row (or list of rows)."""

    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        assert self._value is not None, "scalar_one() on an empty scripted result"
        return self._value

    def first(self) -> Any:
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value

    def all(self) -> list[Any]:
        if self._value is None:
            return []
        return self._value if isinstance(self._value, list) else [self._value]

    def scalars(self) -> "FakeResult":
        return self


class FakeSession:
    """Minimal async session: returns `results` in order, one per `execute()` call.

    Deliberately strict — running past the end of the script raises rather than quietly
    returning None, so a handler that grows an extra query fails the test loudly instead
    of silently taking a different branch.
    """

    def __init__(self, results: list[Any] | None = None) -> None:
        self._results = list(results or [])
        self.calls = 0
        self.added: list[Any] = []
        self.committed = False

    async def execute(self, *_args: Any, **_kwargs: Any) -> FakeResult:
        if self.calls >= len(self._results):
            raise AssertionError(
                f"unexpected DB query #{self.calls + 1}; script had {len(self._results)}"
            )
        value = self._results[self.calls]
        self.calls += 1
        return FakeResult(value)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def merge(self, obj: Any) -> Any:
        return obj

    async def get(self, _model: Any, _pk: Any) -> Any:
        return None


def make_user(role: str = "candidate", **overrides: Any) -> User:
    user = User(
        id=overrides.pop("id", uuid.uuid4()),
        email=overrides.pop("email", "someone@example.com"),
        password_hash="x",
        full_name=overrides.pop("full_name", "Some One"),
        role=role,
        is_active=overrides.pop("is_active", True),
    )
    for key, value in overrides.items():
        setattr(user, key, value)
    return user


@pytest.fixture
def candidate() -> User:
    return make_user("candidate")


@pytest.fixture
def other_candidate() -> User:
    return make_user("candidate", email="other@example.com")


@pytest.fixture
def recruiter() -> User:
    return make_user("recruiter", email="recruiter@example.com")
