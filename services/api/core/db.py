import functools
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.core.config import get_settings

T = TypeVar("T")

settings = get_settings()

_connect_args = {}
if settings.database_ssl_required:
    # asyncpg's `ssl` kwarg, not libpq's `sslmode` query param (asyncpg doesn't parse that).
    # statement_cache_size=0 avoids "prepared statement already exists" errors against a
    # PgBouncer-style transaction pooler. Unused by the local setup, which sets
    # DATABASE_SSL_REQUIRED=false; kept for a future TLS/pooled deployment.
    _connect_args = {"ssl": True, "statement_cache_size": 0}

engine = create_async_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=settings.db_pool_recycle_seconds,
    pool_pre_ping=True,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def without_db_connection(db: AsyncSession, work: Callable[[], Awaitable[T]]) -> T:
    """Runs `work()` with `db`'s pooled connection released back to the pool.

    A request handler's session is checked out for the whole request. When the handler
    then awaits something slow that doesn't touch the database — an LLM round trip, a
    LangGraph invocation, a GitHub crawl — that connection sits idle-but-held for the
    entire call. With `db_pool_size=20`, twenty concurrent AI-interview turns is enough
    to exhaust the pool, at which point *every* endpoint in the app blocks on
    `pool_timeout` (30s) waiting for a connection, including trivial reads that would
    have returned instantly. That is the "one slow feature freezes the whole app"
    failure mode.

    `session.close()` here returns the connection to the pool but keeps the session
    usable: SQLAlchemy transparently acquires a fresh connection on the next statement.
    So callers continue using `db` normally afterwards.

    Two constraints on the caller, both of which the alternative (holding the
    connection) would not have:
      - Flush or commit any pending writes *before* calling this. Closing discards an
        open transaction, so unflushed changes would be silently lost.
      - Don't hold ORM objects you expect to stay usable across the call and rely on
        lazy attribute loads afterwards. The sessionmaker sets `expire_on_commit=False`,
        so already-loaded attributes stay valid, which is what every current caller
        needs — they read plain values out of the model before the slow call.
    """
    await db.close()
    return await work()
