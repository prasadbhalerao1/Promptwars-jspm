"""DB-backed access to the curated catalogs, with a bounded in-process cache.

These three datasets (role requirement sets, skill glosses, default-avatar hashes) moved
out of Python literals so that extending them is an operational action rather than a code
change. That move has one real constraint: their consumers are **synchronous** functions
deep inside agent tools (`skill_gap.analyze_skill_gaps`, `embeddings.skill_text`,
`photo_hash.is_default_avatar`), several of which run inside `asyncio.to_thread` for
CPU-bound embedding work. Handing them an `AsyncSession` would mean rewriting those call
chains as async and threading a session through every graph node — a much larger and
riskier change than the one being made here.

So this module opens its own short-lived **synchronous** connection, using the sync
psycopg driver already present for Alembic, and caches the result. The catalogs are
curated data that changes when a human edits them, not per-request state, so a TTL cache
is a good fit; `refresh_catalogs()` exists for tests and for an admin edit that needs to
take effect immediately.

Falling back to the seed data is deliberate. If the database is unreachable, or the
migration has not been applied yet, career guidance degrading to "unknown role" would be
a worse failure than serving the same defaults the code shipped with for months. The
fallback is logged once per process so it is visible rather than silent.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from services.api.core.config import get_settings

logger = logging.getLogger(__name__)

# Curated data changes on human edits, not on traffic, so a long TTL is appropriate.
# Short enough that an admin edit lands within a few minutes without a restart.
_CACHE_TTL_SECONDS = 300

# Seconds to wait for a catalog connection before falling back to seed data. The
# fallback is a correct, fully-functional path, so waiting longer buys nothing.
_CONNECT_TIMEOUT_SECONDS = 3

_lock = threading.Lock()
_cache: dict[str, tuple[float, Any]] = {}
_engine = None
_fallback_warned: set[str] = set()


def _sync_engine():
    """Lazily build a sync engine from the async DATABASE_URL.

    The app's engine is asyncpg-based and unusable from a sync context. Rather than add
    a second URL setting, the driver prefix is rewritten the same way Alembic's env.py
    already does for migrations.
    """
    global _engine
    if _engine is None:
        url = get_settings().database_url
        for async_driver, sync_driver in (("postgresql+asyncpg", "postgresql+psycopg"), ("postgres://", "postgresql+psycopg://")):
            url = url.replace(async_driver, sync_driver)
        # A short connect timeout is essential, not a nicety: this module is imported at
        # module scope by agent tools, so without it an unreachable database makes
        # `import` itself hang for the OS-level TCP timeout (minutes) rather than
        # falling back to the seed. pool_pre_ping because these connections are opened
        # rarely and may have been reaped by the server in between.
        _engine = create_engine(
            url,
            pool_size=2,
            max_overflow=2,
            pool_pre_ping=True,
            connect_args={"connect_timeout": _CONNECT_TIMEOUT_SECONDS},
        )
    return _engine


def _cached(key: str, loader, fallback):
    """Return `loader()`'s result, cached for `_CACHE_TTL_SECONDS`, else `fallback`."""
    now = time.monotonic()
    with _lock:
        entry = _cache.get(key)
        if entry is not None and now - entry[0] < _CACHE_TTL_SECONDS:
            return entry[1]

    try:
        with Session(_sync_engine()) as session:
            value = loader(session)
    except Exception as exc:  # noqa: BLE001 - a missing catalog must not break scoring
        if key not in _fallback_warned:
            _fallback_warned.add(key)
            logger.warning(
                "Catalog %r unavailable from the database (%s) — using built-in seed data. "
                "Apply the catalog migration and run scripts/seed_db.py to make it editable.",
                key, exc,
            )
        return fallback

    # An empty table means the migration ran but seeding did not. Serving an empty
    # taxonomy would make every role lookup fail, so treat it the same as unavailable.
    if not value:
        if key not in _fallback_warned:
            _fallback_warned.add(key)
            logger.warning("Catalog %r is empty — using built-in seed data. Run scripts/seed_db.py.", key)
        return fallback

    with _lock:
        _cache[key] = (now, value)
    return value


def refresh_catalogs() -> None:
    """Drop the cache so the next read re-queries. For tests and admin edits."""
    with _lock:
        _cache.clear()


def role_skill_taxonomy() -> dict[str, list[tuple[str, float]]]:
    """`{role: [(skill_name, weight), ...]}` — FR-4.1 target-role requirement sets."""
    from services.agents.candidate_intelligence.tools.role_taxonomy import ROLE_SKILL_TAXONOMY_SEED

    def load(session: Session) -> dict[str, list[tuple[str, float]]]:
        from packages.db.models import RoleSkillRequirement

        rows = session.execute(
            select(RoleSkillRequirement).order_by(
                RoleSkillRequirement.role, RoleSkillRequirement.weight.desc()
            )
        ).scalars().all()
        taxonomy: dict[str, list[tuple[str, float]]] = {}
        for row in rows:
            taxonomy.setdefault(row.role, []).append((row.skill_name, row.weight))
        return taxonomy

    return _cached("role_skill_taxonomy", load, ROLE_SKILL_TAXONOMY_SEED)


def skill_descriptions() -> dict[str, str]:
    """`{skill_name: one-sentence gloss}` — context for skill embeddings."""
    from services.agents.recruitment.tools.skill_descriptions import SKILL_DESCRIPTIONS_SEED

    def load(session: Session) -> dict[str, str]:
        from packages.db.models import SkillDescription

        rows = session.execute(select(SkillDescription)).scalars().all()
        return {row.skill_name: row.description for row in rows}

    return _cached("skill_descriptions", load, SKILL_DESCRIPTIONS_SEED)


def default_avatar_hashes() -> set[str]:
    """Perceptual hashes of placeholder avatars, excluded from duplicate-photo scoring.

    Unlike the other two, an empty result here is a legitimate state — a fresh
    deployment has not identified any yet — so this does not fall back or warn.
    """
    def load(session: Session) -> set[str]:
        from packages.db.models import DefaultAvatarHash

        return {row.phash for row in session.execute(select(DefaultAvatarHash)).scalars().all()}

    now = time.monotonic()
    with _lock:
        entry = _cache.get("default_avatar_hashes")
        if entry is not None and now - entry[0] < _CACHE_TTL_SECONDS:
            return entry[1]
    try:
        with Session(_sync_engine()) as session:
            value = load(session)
    except Exception:  # noqa: BLE001 - absence of the table means "none known yet"
        return set()
    with _lock:
        _cache["default_avatar_hashes"] = (now, value)
    return value
