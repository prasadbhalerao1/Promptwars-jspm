"""Module 6 (Trust & Fraud Prevention) — doc/SRS/06, doc/multi-agent-architecture/06.

Schema copied verbatim from doc 06 §5/§6 (both doc sets agree on table names/shapes here
— no doc-set pick needed, unlike several earlier modules). `fraud_flags.evidence` is
NOT NULL at the DB layer per doc 06 §11's explicit non-functional requirement ("every
`fraud_flags` row must have non-null evidence — enforced at the DB/application layer, not
just convention") — the API layer (`services/api/routers/fraud.py`) also refuses to
construct a flag without a real evidence payload, so this is belt-and-suspenders, not
the only guard.

This is the highest ethical-risk-surface module in the platform (doc 06 §1) — `raised`
status must never affect anything automatically; only a human moving a flag to `upheld`
does. See `.agents/decisions.md`'s dated Module 06 entry for the aggregation formula
weight choices and any real ambiguity resolved while building this.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime, Float

from packages.db.models.base import Base

_SUBJECT_TYPES = "certificate,submission,profile,resume".split(",")
_CONFIDENCE_LABELS = "low,medium,high".split(",")
_FLAG_STATUSES = "raised,under_review,upheld,dismissed".split(",")


class VerificationRecord(Base):
    """One row per detection-agent signal computed, for EVERY check run — not just the
    ones that cross a flag-raising threshold. This is the full evidence trail an admin
    or a future audit can walk back through, independent of whether a `fraud_flags` row
    was ever created from it."""

    __tablename__ = "verification_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    signal_type: Mapped[str] = mapped_column(Text, nullable=False)
    signal_score: Mapped[float | None] = mapped_column(Float)
    confidence_label: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            f"subject_type IN ({', '.join(repr(s) for s in _SUBJECT_TYPES)})",
            name="ck_verification_records_subject_type",
        ),
        CheckConstraint(
            f"confidence_label IN ({', '.join(repr(c) for c in _CONFIDENCE_LABELS)})",
            name="ck_verification_records_confidence_label",
        ),
        Index("idx_verification_records_subject", "subject_type", "subject_id"),
    )


class FraudFlag(Base):
    """A flag raised for human review. `status='raised'` (the default) has ZERO effect
    on visibility/ranking/Talent Score anywhere else in the platform — only a human
    admin/recruiter moving it to `upheld` via `PATCH /flags/{id}/review` does, and that
    transition requires non-empty `review_notes` (enforced in the router, not just here).
    `evidence` is NOT NULL — no flag may be a bare accusation."""

    __tablename__ = "fraud_flags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    flag_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="raised")
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    raised_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    # Additive — the candidate this flag is about, so /candidates/{id}/flags and the
    # dispute flow can look flags up without re-deriving candidate_id from subject_type/
    # subject_id (which requires a different join per subject_type). Neither doc's SQL
    # has this column; without it a certificate-subject flag has no direct path back to
    # a candidate_id short of joining through `certifications.candidate_id`.
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id"))

    __table_args__ = (
        CheckConstraint(
            f"subject_type IN ({', '.join(repr(s) for s in _SUBJECT_TYPES)})",
            name="ck_fraud_flags_subject_type",
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in _FLAG_STATUSES)})",
            name="ck_fraud_flags_status",
        ),
        Index("idx_fraud_flags_subject", "subject_type", "subject_id"),
        Index("idx_fraud_flags_candidate", "candidate_id"),
        Index("idx_fraud_flags_status", "status"),
    )


class AuthenticityScore(Base):
    """FR-6 — "corroboration strength," 0-100, framed positively (doc 06 §5). One row per
    computation (append-only, matching every other module's score-history convention —
    e.g. `talent_scores`), not a mutable singleton, so a candidate's score history is
    visible over time as disputes resolve."""

    __tablename__ = "authenticity_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    components: Mapped[dict | None] = mapped_column(JSONB)
    computed_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_authenticity_scores_candidate_time", "candidate_id", "computed_at"),)


class DefaultAvatarHash(Base):
    """Perceptual hashes of well-known default/placeholder profile pictures.

    Two candidates both using the GitHub identicon are not evidence of a duplicate
    account, so these hashes are excluded before photo similarity is scored. The list
    shipped as an empty `set()` in `fraud/tools/photo_hash.py` carrying the comment
    "populate with real default-avatar hashes as they're identified in production" —
    which is precisely what a code literal cannot support, since every addition would
    need a developer and a redeploy. As a table, an admin adds one when they spot it.
    """

    __tablename__ = "default_avatar_hashes"

    phash: Mapped[str] = mapped_column(Text, primary_key=True)
    note: Mapped[str | None] = mapped_column(Text)


class TrustedIssuer(Base):
    """FR-1's known-issuer registry — replaces the previous hardcoded Python dict in
    `services/agents/fraud/tools/issuer_lookup.py` with a real, admin-manageable table.
    An issuer NOT in this table is now an explicit "unrecognized issuer" signal
    (`services/agents/fraud/nodes/cert_verdict.py`) contributing its own elevated-risk
    evidence, rather than silently falling through to Visual Forensics as if that were an
    equally strong verification path.

    `aliases` preserves the old dict's substring-matching flexibility (e.g. "AWS" should
    match a candidate-entered issuer of "Amazon Web Services (AWS)") without needing an
    exact string — `resolve_issuer` (issuer_lookup.py) checks the canonical `name` and
    every alias, case-insensitively, as a substring of the candidate's entered issuer
    text. `verification_url_template` is nullable: an issuer can be trusted/known without
    the platform having a URL-based verification path for it yet (falls through to Visual
    Forensics same as before, but WITHOUT the unrecognized-issuer penalty, since being
    "known" and being "URL-verifiable" are different facts)."""

    __tablename__ = "trusted_issuers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    aliases: Mapped[list | None] = mapped_column(JSONB)  # ["aws", "amazon web services"]
    verification_url_template: Mapped[str | None] = mapped_column(Text)  # "https://.../{credential_id}"
    trust_tier: Mapped[str] = mapped_column(Text, nullable=False, server_default="platform")
    notes: Mapped[str | None] = mapped_column(Text)
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "trust_tier IN ('platform','university','employer','community')",
            name="ck_trusted_issuers_trust_tier",
        ),
    )


class FraudDetectionConfig(Base):
    """Admin-configurable thresholds for fraud detection subgraphs. Instead of hardcoding
    thresholds scattered across agent code (e.g. SIMILARITY_FLAG_THRESHOLD = 0.75 in
    structural_similarity.py), store them in the database so admins can tune sensitivity
    per organization without code changes. Singleton per organization (or global if org_id
    is null for platform-wide defaults)."""

    __tablename__ = "fraud_detection_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    # Plagiarism detection: flag if structural/AST similarity exceeds this (0-1 scale)
    code_similarity_threshold: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.75")
    # Plagiarism: flag if text MinHash/Jaccard similarity exceeds this
    text_similarity_threshold: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.80")
    # OCR confidence below which visual forensics escalates suspicion to medium/high
    ocr_confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.55")
    # Photo hash Hamming distance threshold for duplicate detection (0-64, lower = stricter)
    photo_hash_max_distance: Mapped[int] = mapped_column(Float, nullable=False, server_default="4")
    # AI-content heuristic perplexity threshold (lower = more AI-like, triggers flag)
    ai_content_perplexity_threshold: Mapped[float] = mapped_column(Float, nullable=False, server_default="50")
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("code_similarity_threshold >= 0 AND code_similarity_threshold <= 1", name="ck_code_sim_range"),
        CheckConstraint("text_similarity_threshold >= 0 AND text_similarity_threshold <= 1", name="ck_text_sim_range"),
        CheckConstraint("ocr_confidence_threshold >= 0 AND ocr_confidence_threshold <= 1", name="ck_ocr_conf_range"),
        Index("idx_fraud_detection_configs_org", "org_id"),
    )


class Dispute(Base):
    """FR-8 — candidate's context/evidence submitted against a flag raised on their own
    profile. Submitting a dispute moves the flag's status to `under_review` (router-side
    effect, not stored redundantly here)."""

    __tablename__ = "disputes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fraud_flag_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fraud_flags.id"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False
    )
    candidate_statement: Mapped[str | None] = mapped_column(Text)
    supporting_files: Mapped[list | None] = mapped_column(JSONB)
    # Cached LLM reviewer-assist summary ({candidate_context_summary,
    # points_of_agreement_or_conflict}). Previously regenerated on every GET of the flag
    # detail page, so opening one flag twice cost two model calls — while holding a DB
    # connection — for a summary of two fields that never change after submission.
    # Written once, on first read; null means "not summarized yet".
    review_assist: Mapped[dict | None] = mapped_column(JSONB)
    submitted_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_disputes_flag", "fraud_flag_id"),)
