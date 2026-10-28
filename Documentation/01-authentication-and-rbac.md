# Authentication & Role-Based Access Control

## What it does

Every user (candidate, recruiter, organizer, judge, admin) signs up and logs in with an
email/password pair. The API issues a self-contained JWT on successful login; the frontend
stores it and attaches it as a bearer token on every request. Role enforcement happens on
the server, per-endpoint, via a FastAPI dependency — not by trusting anything the client sends.

This is a fully custom auth system. There is no third-party identity provider anywhere in
the live request path.

## How it works

### Signup and login

`services/api/modules/users/router.py`:
- `POST /auth/signup` (line 28) — creates a `User` row with a bcrypt password hash and the
  requested role, then returns an access token.
- `POST /auth/login` (line 71) — looks up the user by email, verifies the password, returns
  an access token.

### Password hashing

`services/api/core/security.py:7-17`:

```python
def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False
```

Plain `bcrypt` (the `bcrypt` package directly, not `passlib`), a fresh salt per password via
`bcrypt.gensalt()`. `verify_password` fails closed — any exception (malformed hash, wrong
encoding) returns `False` rather than propagating.

### JWT issuance

`create_access_token` (`security.py:20-24`) builds a token via `python-jose`:

```python
def create_access_token(user_id: str, settings: Any) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(seconds=settings.jwt_expiry_seconds)
    claims = {"sub": user_id, "exp": expire, "iat": now}
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
```

The token is a minimal, self-contained credential: subject (user ID), issued-at, and
expiry — no roles or other claims baked in, so a role change takes effect on the very next
request instead of waiting for a token to expire.

Config (`services/api/core/config.py:29-31`): `jwt_secret_key` (required, no default),
`jwt_algorithm` (default `HS256`), `jwt_expiry_seconds` (default `604800`, i.e. 7 days).

### Request verification and role enforcement

`services/api/core/rbac.py` is the single source of truth for who's making a request and
what they're allowed to do:

- `_verify_token` (`rbac.py:15-20`) — decodes the JWT with `jose.jwt.decode`, raising
  `401 invalid_token` on any `JWTError` (expired, malformed, wrong signature).
- `get_auth_context` (`rbac.py:35-52`) — a FastAPI dependency that reads the
  `Authorization: Bearer <token>` header, verifies it, pulls the `sub` claim as a UUID, and
  looks up the matching `User` row. Missing/malformed header → `401 missing_bearer_token`.
  Non-UUID subject → `401 invalid_token`.
- `get_current_user` (`rbac.py:55-58`) — requires that a `User` row actually exists for the
  token's subject; if the token is valid but there's no DB row (shouldn't happen in normal
  signup flow, but the code guards it anyway), it responds `403 onboarding_required` rather
  than treating a phantom user as authenticated.
- `require_role(*roles)` (`rbac.py:61-69`) — a dependency *factory*. Each router declares
  which roles may call an endpoint with `Depends(require_role(Role.recruiter))`, and the
  returned dependency 403s (`insufficient_role`) if `user.role` isn't in the allowed set.
  This pattern is used per-endpoint across every module router (candidates, recruitment,
  assessments, fraud, hackathons, etc.) — there's no central route table, each endpoint
  states its own required role(s) inline.

### Onboarding

`GET /me` returns `onboarding_required`, and every workspace layout redirects to
`/onboarding` when it is true. Two distinct situations set it:

- **No `users` row for a valid token.** Shouldn't happen with self-hosted signup, but
  `get_auth_context` guards it.
- **A candidate whose profile is incomplete** (`_candidate_onboarding_incomplete` in
  `services/api/modules/users/router.py`): missing `full_name`, `headline`, `location`,
  or a first `education` entry carrying both `institution` and `degree`.

The second check is what makes the flag meaningful. It previously returned `False`
whenever a `users` row existed — a state signup makes unreachable — so the flag was
effectively always false and `/onboarding` was unreachable. The check is deliberately
read-only: `/me` is called on nearly every page load and must not create a profile row
as a side effect.

Only candidates are gated. Other roles have no profile fields to collect and are
complete as soon as the account exists.

The wizard itself (`apps/web/src/components/onboarding/OnboardingWizard.tsx`) is three
steps — identity, background, connect — and writes through `PATCH /candidates/me` after
each one, so a refresh or an OAuth detour never loses typed answers. College and degree
are not columns: that endpoint folds them into the first entry of the `education` JSONB
array as `institution`/`degree`.

GitHub is required-but-skippable. A hard block would strand users whenever OAuth is
misconfigured or rate-limited, so skipping is allowed and the gap keeps surfacing on the
`/home` hub's profile-completeness meter until it's connected.

`/onboarding` deliberately lives outside every route group. Those layouts are what
redirect *to* it, so a route inside one would redirect to itself.

### Frontend

`apps/web/src/components/AuthProvider.tsx` calls `${API_URL}/auth/login` and
`${API_URL}/auth/signup` directly via `fetch` — no auth SDK. The returned JWT is stored in
`localStorage` under the `access_token` key and attached as a bearer token on subsequent API
calls. There are no auth cookies and no Next.js `middleware.ts` anywhere in the app.

`CurrentUserProvider.tsx` wraps `AuthProvider` and fetches `GET /me` exactly once, then
shares that result across every route-group layout that needs it — before this existed,
each role's route-group layout independently called `/me` on mount, which meant redundant
calls on every navigation between layouts.

### Route protection is two layers, and only one of them is real security

- **Client-side (UX only).** Each role's route group has its own `layout.tsx` —
  `(admin)/layout.tsx`, `(recruiter)/layout.tsx`, etc. — that checks
  `me.profile.role !== "admin"` (or the equivalent for that group) and redirects if it
  doesn't match. This exists purely so a candidate never even sees a flash of the admin UI
  before being bounced; it has zero enforcement value because it's client-side JavaScript a
  user fully controls.
- **Server-side (the actual gate).** Every protected endpoint's `require_role(...)`
  dependency is what actually stops a request. A recruiter with a valid JWT hitting an
  admin-only endpoint gets a `403` from the API regardless of what the frontend renders.

## Rate limiting

`services/api/core/rate_limit.py` implements an in-memory, fixed-window rate limiter as
ASGI middleware (`RateLimitMiddleware`):

- **Not Redis-backed.** The module docstring states this directly: it's sized for
  hackathon-demo scale (≤20 users, single API process, no horizontal scaling), and adding a
  Redis dependency for this alone wasn't judged worth it — `redis_url` isn't even a config
  setting in this codebase.
- **Bucketing key.** Best-effort: it decodes (without verifying) the JWT's `sub` claim to
  bucket by user ID when a bearer token is present, falling back to client IP otherwise.
  The docstring is explicit that this is safe precisely because it's only a bucket-selection
  heuristic — `rbac.py`'s `get_current_user` still does full signature verification
  afterward, so a forged token can only land in the wrong bucket, never bypass
  authorization.
- **Window and limit.** Fixed 60-second window, `RATE_LIMIT_PER_MINUTE` requests per window
  (config default `60`, `rate_limit_per_minute` in `config.py:77`). `limit <= 0` is an
  explicit "disabled" escape hatch, not a bug.
- **Exempt path.** `/health` is always exempt so uptime checks never see a `429`.
- Overflow returns `429 {"detail": "rate_limit_exceeded"}`.

This is a real, working middleware (not a stale claim) — verified directly against
`services/api/core/rate_limit.py` for this doc. It's an in-process counter, so per-process
state resets on restart and doesn't share state across multiple API processes; that's a
known, acceptable limitation at the scale this was built for, not an oversight.

## Key design decisions and why

**No third-party identity provider.** Custom email+password plus a hand-rolled JWT is a
small surface area to reason about, has zero external dependency/outage risk for the core
login flow, and avoids per-seat identity-provider pricing at hackathon scale. The tradeoff,
named honestly: no built-in MFA, no social login, no managed session revocation — anything
beyond password auth would need to be built.

**Roles live in the DB row, not in the token.** Baking `role` into the JWT claims would mean
a role change (e.g., promoting a user to admin) wouldn't take effect until the old token
expired — up to 7 days later with the default `jwt_expiry_seconds`. Looking the user row up
on every request costs one indexed query but makes role changes take effect immediately.

**Client-side route guards are explicitly just UX, not security.** The route-group
`layout.tsx` checks exist to avoid a flash of the wrong UI, not to gate access — every
actually-sensitive operation is re-checked with `require_role` server-side. This is stated
here explicitly so nobody mistakes the frontend redirect for the security boundary.

**`onboarding_required` as a distinct 403 rather than folding into a generic 401.** A valid
token with no matching `User` row is a different situation from "not authenticated at all" —
it signals the frontend to route the user into an onboarding flow rather than back to login.

## Limitations

- No MFA, no password reset flow visible in this router, no session revocation (a JWT
  remains valid until it expires — there's no server-side blacklist).
- Rate limiting is per-process, in-memory — doesn't survive a restart and doesn't coordinate
  across multiple API processes if the deployment ever scaled horizontally.
- No refresh-token rotation; a single long-lived (7-day) access token is the only credential.
- Auth is entirely self-hosted: bcrypt hashing plus HS256 JWTs issued by this API. There
  is no external identity provider, no SDK, and no third-party call in the sign-in path.
  (Stray "Clerk" naming from an earlier iteration was removed on 2026-08-16, along with
  the e2e tests that had been written against a hosted Clerk sign-in widget.)

## Where this lives

| Component | Path |
|---|---|
| Password hashing | `services/api/core/security.py` |
| JWT issuance | `services/api/core/security.py::create_access_token` |
| Token verification / auth context / role dependency | `services/api/core/rbac.py` |
| Signup / login endpoints | `services/api/modules/users/router.py` |
| JWT config (secret, algorithm, expiry) | `services/api/core/config.py` |
| Rate limiting middleware | `services/api/core/rate_limit.py` |
| Frontend auth provider (login/signup, token storage) | `apps/web/src/components/AuthProvider.tsx` |
| Frontend shared current-user cache | `apps/web/src/components/CurrentUserProvider.tsx` |
| Onboarding completeness check | `services/api/modules/users/router.py::_candidate_onboarding_incomplete` |
| Onboarding wizard | `apps/web/src/components/onboarding/OnboardingWizard.tsx`, `apps/web/src/app/onboarding/page.tsx` |
| Shared sidebar + role gate | `apps/web/src/components/common/WorkspaceShell.tsx` |
| Client-side route guards (UX only, per role) | `apps/web/src/app/(admin)/layout.tsx`, `(recruiter)/layout.tsx`, `(candidate)/layout.tsx`, `(organizer)/layout.tsx`, `(judge)/layout.tsx` |
| DB model | `packages/db/models/user.py::User` |
