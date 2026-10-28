# Security

TRACE handles candidate evidence and recruiter decisions, so access rules are enforced on the
server and covered by tests. This page lists the protections that exist in the code.

## Authentication and authorization

- **Server-side role checks.** Every protected endpoint declares its role through
  `require_role(...)` (`services/api/core/rbac.py`). The frontend's route gating is UX only;
  authorization lives in the API.
- **Ownership checks, not just role checks.** A candidate can act only on their own interview
  sessions (`_session_owned_by`), and recruiters only on jobs their organization owns
  (`_job_owned_by`). Tests: `test_interview_session_access.py`, `test_job_visibility.py`,
  `test_assessment_access.py`, `test_interview_report_access.py`,
  `test_hackathon_submission_access.py`.
- **No self-assigned privileges.** Sign-up accepts only `candidate` and `recruiter`; admin,
  organizer and judge roles are granted by an admin (`test_signup_roles.py`,
  `test_admin_role_guard.py`).
- **Passwords** are hashed with bcrypt and a per-password salt (`services/api/core/security.py`).
- **JWT signing key** has no default: the API refuses to start without `JWT_SECRET_KEY`.

## Secrets

- All credentials come from environment variables (`services/api/core/config.py`);
  `.env` files are git-ignored and `.env.example` holds placeholders only.
- Third-party keys never reach the browser. For the video interviewer, the API mints a
  short-lived TruGen session token server-side (`services/api/core/trugen.py`).

## Abuse and data safety

- **Rate limiting** per user or IP, Redis-backed with a bounded in-memory fallback
  (`services/api/core/rate_limit.py`).
- **CORS** is an explicit allow-list from `CORS_ALLOWED_ORIGINS`.
- **Uploads** are validated for type and size before processing (`test_upload_validation.py`).
- **Human in the loop for fraud.** A fraud flag has no effect on a candidate's score until an
  admin upholds it, and the candidate can see and dispute it.
- **No candidate video is recorded.** Avatar interviews keep only the transcript used for scoring.

## Reporting a vulnerability

Please report security issues privately to the maintainers rather than opening a public issue.
