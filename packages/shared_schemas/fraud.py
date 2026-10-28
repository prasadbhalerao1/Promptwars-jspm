"""Module 6 (Trust & Fraud Prevention) shared Pydantic schemas — doc/SRS/06 §6.

Following this repo's established convention (`packages/shared_schemas/hackathon.py`,
`.../recruitment.py`, etc.): the only place schemas shared between `services/api` and
`services/agents` get defined."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

SUBJECT_TYPES = ("certificate", "submission", "profile", "resume")
FLAG_STATUSES = ("raised", "under_review", "upheld", "dismissed")
CONFIDENCE_LABELS = ("low", "medium", "high")


# --- Verification checks (FR-1/FR-2/FR-4/FR-5) ---


class VerificationSignalResponse(BaseModel):
    signal_type: str
    score: float | None
    confidence_label: str
    evidence: str | list[str]


class VerificationCheckResponse(BaseModel):
    """Returned by all three `POST /verification/.../check` endpoints. `flag` is populated
    only if the verdict crossed the flag-raising threshold — a clean check returns
    `flag: null`, never a bare boolean, so the caller can still see the underlying signals
    either way (doc 06 §7's "every flag cites specific evidence" extended to "every check
    surfaces its signals, flagged or not")."""

    subject_type: str
    subject_id: UUID
    signals: list[VerificationSignalResponse]
    flag: "FraudFlagResponse | None"


# --- Fraud flags (FR-6/FR-7/FR-8) ---


class FraudFlagResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    subject_type: str
    subject_id: UUID
    candidate_id: UUID | None
    flag_type: str
    status: str
    evidence: dict
    raised_at: datetime
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None


class FlagReviewRequest(BaseModel):
    """`PATCH /flags/{id}/review`. `status` must be 'upheld' or 'dismissed' — a reviewer
    moves a flag OUT of the review queue, never back to 'raised'. `review_notes` is
    required (non-empty) when `status == 'upheld'`, enforced in the router (doc 06 §7:
    "every upheld decision requires review_notes — an unexplained adverse action is not
    permitted by this design"), not just as a frontend nicety."""

    status: str
    review_notes: str | None = None


class DisputeSubmitRequest(BaseModel):
    candidate_statement: str
    supporting_files: list[UUID] = []


class DisputeResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    fraud_flag_id: UUID
    candidate_id: UUID
    candidate_statement: str | None
    supporting_files: list | None
    submitted_at: datetime


class DisputeReviewAssist(BaseModel):
    """Dispute Review Agent output — ASSISTIVE ONLY (doc 06 §4: "cannot itself close a
    dispute"). `available=False` when Sonnet couldn't run (e.g. no API key) — the review
    endpoint still functions without this, it's a nice-to-have summary layer."""

    available: bool
    candidate_context_summary: str | None = None
    points_of_agreement_or_conflict: list[str] = []


class FraudFlagDetailResponse(BaseModel):
    flag: FraudFlagResponse
    dispute: DisputeResponse | None
    dispute_review_assist: DisputeReviewAssist


class FraudReviewQueueEntry(BaseModel):
    flag: FraudFlagResponse
    candidate_headline: str | None
    candidate_github_username: str | None
    has_dispute: bool


# --- Authenticity score (FR-6) ---


class AuthenticityScoreResponse(BaseModel):
    model_config = {"from_attributes": True}

    candidate_id: UUID
    score: float
    components: dict | None
    computed_at: datetime


# --- Trusted issuer registry (FR-1) ---

TRUST_TIERS = ("platform", "university", "employer", "community")


class TrustedIssuerResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    aliases: list[str] | None
    verification_url_template: str | None
    trust_tier: str
    notes: str | None
    added_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class TrustedIssuerCreateRequest(BaseModel):
    name: str
    aliases: list[str] | None = None
    verification_url_template: str | None = None
    trust_tier: str = "platform"
    notes: str | None = None


class TrustedIssuerUpdateRequest(BaseModel):
    """All fields optional — PATCH semantics, only supplied fields are updated."""

    name: str | None = None
    aliases: list[str] | None = None
    verification_url_template: str | None = None
    trust_tier: str | None = None
    notes: str | None = None
