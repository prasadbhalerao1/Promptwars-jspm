from typing import Any
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import User
from packages.shared_schemas.users import Role
from services.api.core.config import get_settings
from services.api.core.db import get_db


async def _verify_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc


class AuthContext:
    """Result of verifying a request's bearer token.

    `user` is None when the token is valid but no `users` row exists yet for this
    user ID — should not occur in normal operation with custom signup.
    """

    def __init__(self, user_id: str, user: User | None) -> None:
        self.user_id = user_id
        self.user = user


async def get_auth_context(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token")

    token = authorization.removeprefix("Bearer ").strip()
    claims = await _verify_token(token)
    user_id_str = claims["sub"]

    try:
        user_id = UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    result = await db.execute(select(User).where(User.id == user_id))
    return AuthContext(user_id=user_id_str, user=result.scalar_one_or_none())


async def get_current_user(ctx: AuthContext = Depends(get_auth_context)) -> User:
    if ctx.user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="onboarding_required")
    # Deactivation has to be enforced here, not only at login. Tokens are valid for
    # `jwt_expiry_seconds` (7 days) and are never consulted against the database
    # afterwards, so checking `is_active` only in the login handler meant deactivating an
    # account revoked nothing: the user kept full access with their existing token until
    # it expired on its own. Because every protected route resolves through this
    # dependency, one check covers all of them.
    if not ctx.user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account_disabled")
    return ctx.user


def require_role(*roles: Role | str):
    allowed = {r.value if isinstance(r, Role) else r for r in roles}

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_role")
        return user

    return dependency
