import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import AuditLog


async def log_action(
    db: AsyncSession,
    actor_user_id: uuid.UUID,
    action: str,
    target_type: str | None = None,
    target_id: uuid.UUID | str | None = None,
) -> AuditLog:
    """Insert an `audit_logs` row for one admin/mutating action.

    Does NOT commit — the caller's existing transaction (already open for the
    mutation this call is auditing) is what commits, matching every other
    write-path in this repo (e.g. `users.py`'s onboarding, `recruitment.py`'s
    job/application writes). Calling `db.commit()` here would either be a
    premature partial commit or a silent no-op depending on call order, so it's
    left entirely to the caller.
    """
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
    )
    db.add(entry)
    await db.flush()
    return entry
