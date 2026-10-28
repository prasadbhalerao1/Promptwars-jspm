"""
User Controller & Authentication Endpoints.
Handles authentication (signup/login) and user profile retrieval.
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import CandidateProfile, User
from packages.shared_schemas.users import LoginRequest, MeResponse, SignupRequest, TokenResponse, UserProfile
from services.api.core.db import get_db
from services.api.core.rbac import AuthContext, get_auth_context
from services.api.core.security import create_access_token, hash_password, verify_password
from services.api.core.config import get_settings
from services.api.modules.candidates.router import _RESERVED_USERNAMES, _USERNAME_PATTERN

router = APIRouter(tags=["User Authentication"])


async def _candidate_onboarding_incomplete(db: AsyncSession, user: User) -> bool:
    """Whether a candidate still owes us the fields the /onboarding wizard collects.

    Read-only on purpose — `/me` is called on virtually every page load, so it must not
    create a profile row as a side effect (`_get_or_create_profile` would).

    College and degree are not columns: `PATCH /candidates/me` folds them into the first
    entry of the `education` JSONB array as `institution`/`degree`, so they are read back
    the same way.
    """
    if not user.full_name:
        return True

    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        return True
    if not profile.username or not profile.headline or not profile.location:
        return True

    education = profile.education or []
    first = education[0] if education else {}
    return not (first.get("institution") and first.get("degree"))


@router.get("/me", response_model=MeResponse)
async def me(
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """Returns the current authenticated user profile."""
    if ctx.user is None:
        return MeResponse(onboarding_required=True)

    # This route depends on `get_auth_context` rather than `get_current_user` so it can
    # still answer for a token whose `users` row has no profile yet (that is what
    # `onboarding_required` reports). That bypass also skips the `is_active` check
    # `get_current_user` performs, so it is repeated here: the frontend treats a
    # successful /me as "signed in and allowed", and without this a deactivated user
    # kept a working session — every data route 403s, but the shell renders as normal.
    if not ctx.user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account_disabled")

    # Previously this was hardcoded False whenever a `users` row existed — a state
    # signup makes unreachable, so `onboarding_required` was effectively always False
    # and the /onboarding wizard could never be reached. Only candidates have profile
    # fields to collect; the other roles are complete as soon as they have an account.
    onboarding_required = False
    candidate_username: str | None = None
    if ctx.user.role == "candidate":
        onboarding_required = await _candidate_onboarding_incomplete(db, ctx.user)
        cand_res = await db.execute(
            select(CandidateProfile.username).where(CandidateProfile.user_id == ctx.user.id)
        )
        candidate_username = cand_res.scalar_one_or_none()

    profile_out = UserProfile.model_validate(ctx.user)
    if candidate_username:
        profile_out.username = candidate_username

    return MeResponse(
        onboarding_required=onboarding_required,
        profile=profile_out,
    )


@router.post("/auth/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Registers a new user and returns an access token."""
    if payload.role.value == "candidate" and not (payload.username and payload.username.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing_username")

    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email_taken")

    # bcrypt is deliberately CPU-slow; thread it so it doesn't stall the event loop.
    password_hash = await asyncio.to_thread(hash_password, payload.password)

    user = User(
        email=payload.email,
        password_hash=password_hash,
        full_name=payload.full_name,
        role=payload.role.value,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    if payload.role.value == "candidate" and payload.username:
        username = payload.username.strip().lower()
        if not _USERNAME_PATTERN.match(username) or username in _RESERVED_USERNAMES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_username")
        existing_username = await db.execute(
            select(CandidateProfile).where(CandidateProfile.username == username)
        )
        if existing_username.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username_taken")
        db.add(CandidateProfile(user_id=user.id, username=username))

    await db.commit()
    await db.refresh(user)

    settings = get_settings()
    token = create_access_token(str(user.id), settings)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        profile=UserProfile.model_validate(user),
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticates a user and returns an access token."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    password_ok = user is not None and await asyncio.to_thread(
        verify_password, payload.password, user.password_hash
    )
    if not password_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account_disabled")

    settings = get_settings()
    token = create_access_token(str(user.id), settings)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        profile=UserProfile.model_validate(user),
    )
