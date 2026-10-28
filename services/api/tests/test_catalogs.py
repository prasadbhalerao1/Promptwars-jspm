"""The curated catalogs must be database-backed without becoming a hard dependency.

Moving `ROLE_SKILL_TAXONOMY` and `SKILL_DESCRIPTIONS` into tables makes them editable
without a deploy, which was the point. It also introduces a failure mode they never had
as literals: if the database is unreachable, or the catalog migration has not been
applied, career guidance would break entirely.

So the contract these tests pin is two-sided — the catalog reads from the database when
it can, and degrades to the exact seed data the code shipped with when it cannot. A
freshly-seeded database and a database-less process must behave identically, which is
also why `scripts/seed_db.py` seeds from the same constants the fallback uses.
"""

from __future__ import annotations

import pytest

from services.agents import catalogs
from services.agents.candidate_intelligence.tools.role_taxonomy import (
    ROLE_SKILL_TAXONOMY,
    ROLE_SKILL_TAXONOMY_SEED,
)
from services.agents.recruitment.tools.skill_descriptions import (
    SKILL_DESCRIPTIONS_SEED,
    describe_skill,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Each test starts from a cold cache; the TTL cache is process-wide otherwise."""
    catalogs.refresh_catalogs()
    yield
    catalogs.refresh_catalogs()


# --- seed integrity ------------------------------------------------------------------


def test_role_seed_is_non_trivial() -> None:
    assert len(ROLE_SKILL_TAXONOMY_SEED) >= 5
    for role, skills in ROLE_SKILL_TAXONOMY_SEED.items():
        assert skills, f"{role} has no required skills"
        for skill_name, weight in skills:
            assert skill_name == skill_name.strip().lower(), f"{role}/{skill_name} not normalized"
            assert 0.0 <= weight <= 1.0, f"{role}/{skill_name} weight {weight} out of range"


def test_skill_description_seed_is_non_trivial() -> None:
    assert len(SKILL_DESCRIPTIONS_SEED) >= 20
    for skill_name, description in SKILL_DESCRIPTIONS_SEED.items():
        assert skill_name == skill_name.strip().lower()
        assert description.strip()


# --- fallback behaviour --------------------------------------------------------------


def _break_db(monkeypatch) -> None:
    def _unreachable():
        raise OSError("connection refused")

    monkeypatch.setattr(catalogs, "_sync_engine", _unreachable)


def test_role_taxonomy_falls_back_to_seed_when_db_is_down(monkeypatch) -> None:
    _break_db(monkeypatch)
    assert catalogs.role_skill_taxonomy() == ROLE_SKILL_TAXONOMY_SEED


def test_skill_descriptions_fall_back_to_seed_when_db_is_down(monkeypatch) -> None:
    _break_db(monkeypatch)
    assert catalogs.skill_descriptions() == SKILL_DESCRIPTIONS_SEED


def test_describe_skill_works_without_a_database(monkeypatch) -> None:
    """The embedding path must not break just because the catalog table is missing."""
    _break_db(monkeypatch)
    assert describe_skill("python") == SKILL_DESCRIPTIONS_SEED["python"]


def test_unknown_skill_returns_its_own_name(monkeypatch) -> None:
    """An unglossed skill still embeds — as its bare name, which is weaker but valid."""
    _break_db(monkeypatch)
    assert describe_skill("some-brand-new-framework") == "some-brand-new-framework"


def test_avatar_blacklist_is_empty_rather_than_fatal_when_db_is_down(monkeypatch) -> None:
    """No recorded placeholder avatars is a legitimate state, not a degraded one."""
    _break_db(monkeypatch)
    assert catalogs.default_avatar_hashes() == set()


def test_empty_table_is_treated_as_unseeded_not_as_an_empty_catalog(monkeypatch) -> None:
    """A migrated-but-unseeded database must not silently produce a zero-role taxonomy.

    Serving `{}` would make every role lookup fail with a confusing "unknown role"
    rather than pointing at the real problem, so an empty result falls back to the seed.
    """
    monkeypatch.setattr(catalogs, "_cached", lambda key, loader, fallback: fallback)
    assert catalogs.role_skill_taxonomy() == ROLE_SKILL_TAXONOMY_SEED


# --- consumer compatibility ----------------------------------------------------------


def test_taxonomy_view_supports_every_way_consumers_use_it(monkeypatch) -> None:
    """`ROLE_SKILL_TAXONOMY` is indexed, iterated, `in`-tested, sorted and used as a
    `max()` key across skill_gap.py and candidates/router.py. Swapping a dict literal
    for a DB-backed view must not break any of those."""
    _break_db(monkeypatch)
    taxonomy = catalogs.role_skill_taxonomy()

    role = next(iter(taxonomy))
    assert isinstance(taxonomy[role], list)
    assert role in taxonomy
    assert sorted(taxonomy)
    assert max(taxonomy, key=lambda r: len(taxonomy[r]))
    assert len(taxonomy) == len(ROLE_SKILL_TAXONOMY_SEED)


def test_module_level_taxonomy_matches_the_catalog() -> None:
    assert dict(ROLE_SKILL_TAXONOMY) == dict(catalogs.role_skill_taxonomy())


# --- schema ---------------------------------------------------------------------------


def test_catalog_tables_are_registered_in_metadata() -> None:
    """The migration and the models must describe the same tables."""
    from packages.db.models import Base

    for table in ("role_skill_requirements", "skill_descriptions", "default_avatar_hashes"):
        assert table in Base.metadata.tables


def test_role_requirement_key_is_role_plus_skill() -> None:
    """skill_gap.py derives a deterministic Qdrant point id from (role, skill_name), so
    that pair must be unique or the vector collection accumulates duplicate points."""
    from packages.db.models import RoleSkillRequirement

    assert {c.name for c in RoleSkillRequirement.__table__.primary_key.columns} == {"role", "skill_name"}
