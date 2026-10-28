from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, EmailStr


class Role(str, Enum):
    candidate = "candidate"
    recruiter = "recruiter"
    organizer = "organizer"
    judge = "judge"
    admin = "admin"


class UserProfile(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    email: str
    full_name: str | None
    role: Role
    organization_id: UUID | None
    is_active: bool
    username: str | None = None


class MeResponse(BaseModel):
    onboarding_required: bool
    profile: UserProfile | None = None


# Roles a visitor may assign themselves at `POST /auth/signup`. Everything outside this
# set — `admin`, `organizer`, `judge` — is granted only by an existing admin through
# `PATCH /admin/users/{id}/role`.
#
# `SignupRequest.role` used to be the full `Role` enum, taken straight from the request
# body into `User(role=...)`. Since `Role` includes `admin`, anyone could POST
# `{"role": "admin"}` and receive a token that opened user management, role reassignment
# for every account, the audit log and the trusted-issuer registry. That made every
# `require_role` check in the codebase decorative: each one gated on a role the caller
# had picked for themselves. The signup form offered the choice outright.
#
# MUST stay in sync with SIGNUP_ROLES in apps/web/src/lib/constants.ts, which is what the
# form renders; tests/test_signup_roles.py asserts the two agree.
class SignupRole(str, Enum):
    candidate = "candidate"
    recruiter = "recruiter"


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    role: SignupRole
    username: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    profile: UserProfile


# --- Admin: user management + audit log (added alongside the admin routes in
# services/api/routers/admin.py; see .agents/decisions.md for scope notes) ---


class AdminUserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    email: str
    full_name: str | None
    role: Role
    organization_id: UUID | None
    is_active: bool


class RoleUpdateRequest(BaseModel):
    role: Role


class AuditLogOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    actor_user_id: UUID | None
    action: str
    target_type: str | None
    target_id: UUID | None
    created_at: datetime
