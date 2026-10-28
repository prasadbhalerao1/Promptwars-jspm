"""
Trust & Fraud Prevention Controller.
Handles Certificate Verification, Plagiarism Checking, Duplicate Profile Detection, Authenticity Scores, Flag Reviews, and Dispute Flow.
"""
import asyncio
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import (
    AgentRun,
    AuthenticityScore,
    CandidateProfile,
    Certification,
    Dispute,
    File,
    FraudFlag,
    Submission,
    TrustedIssuer,
    User,
    VerificationRecord,
)
from packages.shared_schemas.fraud import (
    AuthenticityScoreResponse,
    DisputeResponse,
    DisputeReviewAssist,
    DisputeSubmitRequest,
    FlagReviewRequest,
    FraudFlagDetailResponse,
    FraudFlagResponse,
    FraudReviewQueueEntry,
    TrustedIssuerCreateRequest,
    TrustedIssuerResponse,
    TrustedIssuerUpdateRequest,
    VerificationCheckResponse,
)
from services.agents.fraud.cert_graph import get_cert_graph
from services.agents.fraud.content_graph import get_content_graph
from services.agents.fraud.duplicate_graph import get_duplicate_graph
from services.agents.fraud.plagiarism_graph import get_plagiarism_graph
from services.agents.fraud.tools.aggregation import compute_authenticity_score
from services.agents.fraud.tools.dispute_review_llm import (
    DisputeReviewUnavailable,
    summarize_dispute_for_reviewer,
)
from services.agents.fraud.tools.photo_hash import compute_photo_hash
from services.agents.fraud.tools.report_llm import generate_fraud_risk_report
from services.api.core.audit import log_action
from services.api.core.config import get_settings
from services.api.core.db import get_db, without_db_connection
from services.api.core.rbac import get_current_user, require_role
from services.api.core.tracing import start_agent_trace

router = APIRouter(tags=["Trust & Fraud Prevention"])

_REVIEWER_ROLES = ("admin", "recruiter")

# Cap on simultaneous corpus image downloads during duplicate-profile detection — enough
# to hide per-request latency without opening a socket per candidate on a large platform.
_PHOTO_FETCH_CONCURRENCY = 8


async def _certification_or_404(db: AsyncSession, certification_id: uuid.UUID) -> Certification:
    result = await db.execute(select(Certification).where(Certification.id == certification_id))
    cert = result.scalar_one_or_none()
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="certificate_not_found")
    return cert


async def _submission_or_404(db: AsyncSession, submission_id: uuid.UUID) -> Submission:
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    submission = result.scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission_not_found")
    return submission


async def _fetch_trusted_issuers(db: AsyncSession) -> list[dict]:
    """Nodes stay DB-free (this codebase's universal convention) — the router fetches
    the full trusted-issuer registry once per certificate check and passes it into
    `context` for `nodes/issuer_lookup.py` to compare against."""
    result = await db.execute(select(TrustedIssuer))
    return [
        {
            "name": row.name,
            "aliases": row.aliases,
            "verification_url_template": row.verification_url_template,
            "trust_tier": row.trust_tier,
        }
        for row in result.scalars().all()
    ]


async def _candidate_profile_or_404(db: AsyncSession, candidate_id: uuid.UUID) -> CandidateProfile:
    result = await db.execute(select(CandidateProfile).where(CandidateProfile.id == candidate_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="candidate_not_found")
    return profile


async def _flag_or_404(db: AsyncSession, flag_id: uuid.UUID) -> FraudFlag:
    result = await db.execute(select(FraudFlag).where(FraudFlag.id == flag_id))
    flag = result.scalar_one_or_none()
    if flag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="flag_not_found")
    return flag


async def _latest_photo_files(
    db: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, File]:
    """Latest photo File per user, in one query.

    The duplicate-profile check needs this for the entire candidate corpus; the previous
    single-user helper was called in a loop, costing one round-trip per other candidate
    on top of the per-candidate image download that follows.
    """
    if not user_ids:
        return {}
    result = await db.execute(
        select(File)
        .where(File.owner_user_id.in_(user_ids), File.file_type == "photo")
        .order_by(File.owner_user_id, File.uploaded_at.desc())
    )
    latest: dict[uuid.UUID, File] = {}
    for row in result.scalars().all():
        latest.setdefault(row.owner_user_id, row)
    return latest


async def _fetch_and_hash_photo(
    client: httpx.AsyncClient, url: str
) -> str | None:
    """Downloads one image and perceptual-hashes it, or returns None on any failure.

    Hashing is CPU-bound (PIL decode + imagehash.phash) so it runs off the event loop.
    """
    try:
        resp = await client.get(url)
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    try:
        return await asyncio.to_thread(compute_photo_hash, resp.content)
    except Exception:  # noqa: BLE001 - a corrupt/unsupported image must not fail the check
        return None


def _profile_text(profile: CandidateProfile) -> str:
    parts = [profile.headline or ""]
    for exp in profile.experience or []:
        if isinstance(exp, dict):
            parts.append(" ".join(str(v) for v in exp.values() if isinstance(v, str)))
    for skill in profile.skills or []:
        if isinstance(skill, dict) and skill.get("name"):
            parts.append(str(skill["name"]))
    return " ".join(p for p in parts if p)


async def _persist_check_result(
    db: AsyncSession,
    *,
    subject_type: str,
    subject_id: uuid.UUID,
    candidate_id: uuid.UUID | None,
    signals: list[dict],
    verdict: dict,
    agent_name: str,
    trace_id: str | None = None,
) -> FraudFlag | None:
    for signal in signals:
        db.add(
            VerificationRecord(
                subject_type=subject_type,
                subject_id=subject_id,
                signal_type=signal["signal_type"],
                signal_score=signal.get("score"),
                confidence_label=signal["confidence_label"],
                evidence={"detail": signal["evidence"]},
            )
        )

    settings = get_settings()
    fraud_input = {"subject_type": subject_type, "subject_id": str(subject_id)}
    fraud_output = {"signals": signals, "verdict": verdict}
    db.add(
        AgentRun(
            agent_name=agent_name,
            subject_type=subject_type,
            subject_id=subject_id,
            input_ref=fraud_input,
            output=fraud_output,
            model_used=settings.llm_model_judgment,
            langfuse_trace_id=trace_id,
        )
    )

    flag: FraudFlag | None = None
    if verdict.get("should_flag"):
        existing = await db.execute(
            select(FraudFlag).where(
                FraudFlag.subject_type == subject_type,
                FraudFlag.subject_id == subject_id,
                FraudFlag.flag_type == verdict["flag_type"],
                FraudFlag.status.in_(("raised", "under_review")),
            )
        )
        flag = existing.scalar_one_or_none()
        if flag is None:
            evidence_items = verdict["evidence"] if isinstance(verdict["evidence"], list) else [verdict["evidence"]]
            report = await generate_fraud_risk_report(verdict["flag_type"], evidence_items)
            flag = FraudFlag(
                subject_type=subject_type,
                subject_id=subject_id,
                candidate_id=candidate_id,
                flag_type=verdict["flag_type"],
                status="raised",
                evidence={
                    "signal_evidence": evidence_items,
                    "confidence_label": verdict["confidence_label"],
                    "report_summary": report["summary"],
                    "report_cited_evidence": report["cited_evidence"],
                },
            )
            db.add(flag)
            await db.flush()

    return flag


@router.post("/verification/certificates/{certification_id}/check", response_model=VerificationCheckResponse)
async def check_certificate(
    certification_id: uuid.UUID,
    user: User = Depends(require_role(*_REVIEWER_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> VerificationCheckResponse:
    cert = await _certification_or_404(db, certification_id)

    image_url = None
    if cert.file_id:
        file_result = await db.execute(select(File).where(File.id == cert.file_id))
        file_row = file_result.scalar_one_or_none()
        image_url = file_row.public_url if file_row else None

    trusted_issuers = await _fetch_trusted_issuers(db)

    initial_state = {
        "subject_type": "certificate",
        "subject_id": str(certification_id),
        "context": {
            "issuer": cert.issuer,
            "title": cert.title,
            "credential_id": cert.credential_id,
            "ocr_confidence": cert.ocr_confidence,
            "certificate_image_url": image_url,
            "trusted_issuers": trusted_issuers,
        },
        "signals": [],
        "verdict": None,
    }
    with start_agent_trace(
        "fraud.cert_verification",
        input_data={"issuer": cert.issuer, "title": cert.title},
        user_id=str(user.id),
        tags=["fraud", "certificate"],
    ) as trace:
        result_state = await without_db_connection(
            db, lambda: get_cert_graph().ainvoke(initial_state)
        )
        trace.update(output=result_state["verdict"])

    flag = await _persist_check_result(
        db,
        subject_type="certificate",
        subject_id=certification_id,
        candidate_id=cert.candidate_id,
        signals=result_state["signals"],
        verdict=result_state["verdict"],
        agent_name="cert_verification_agent",
        trace_id=trace.trace_id,
    )
    await db.commit()
    if flag:
        await db.refresh(flag)

    return VerificationCheckResponse(
        subject_type="certificate",
        subject_id=certification_id,
        signals=result_state["signals"],
        flag=FraudFlagResponse.model_validate(flag) if flag else None,
    )


@router.post("/verification/submissions/{submission_id}/check", response_model=VerificationCheckResponse)
async def check_submission(
    submission_id: uuid.UUID,
    user: User = Depends(require_role(*_REVIEWER_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> VerificationCheckResponse:
    submission = await _submission_or_404(db, submission_id)
    code = (submission.code_or_answers or {}).get("code", "")

    corpus_result = await db.execute(
        select(Submission).where(
            Submission.assessment_id == submission.assessment_id, Submission.id != submission.id
        )
    )
    corpus = [
        (str(row.id), (row.code_or_answers or {}).get("code", ""))
        for row in corpus_result.scalars().all()
        if (row.code_or_answers or {}).get("code")
    ]

    candidate_profile = await _candidate_profile_or_404(db, submission.candidate_id)

    initial_state = {
        "subject_type": "submission",
        "subject_id": str(submission_id),
        "context": {
            "code": code,
            "corpus": corpus,
            "language_hint": "python",
            "candidate_github_username": candidate_profile.github_username,
        },
        "signals": [],
        "verdict": None,
    }
    with start_agent_trace(
        "fraud.plagiarism_detection",
        input_data={"submission_id": str(submission_id), "corpus_size": len(corpus)},
        user_id=str(user.id),
        tags=["fraud", "submission"],
    ) as trace:
        result_state = await without_db_connection(
            db, lambda: get_plagiarism_graph().ainvoke(initial_state)
        )
        trace.update(output=result_state["verdict"])

    flag = await _persist_check_result(
        db,
        subject_type="submission",
        subject_id=submission_id,
        candidate_id=submission.candidate_id,
        signals=result_state["signals"],
        verdict=result_state["verdict"],
        agent_name="plagiarism_detection_agent",
        trace_id=trace.trace_id,
    )
    await db.commit()
    if flag:
        await db.refresh(flag)

    return VerificationCheckResponse(
        subject_type="submission",
        subject_id=submission_id,
        signals=result_state["signals"],
        flag=FraudFlagResponse.model_validate(flag) if flag else None,
    )


@router.post("/verification/profiles/{candidate_id}/duplicate-check", response_model=VerificationCheckResponse)
async def check_profile_duplicate(
    candidate_id: uuid.UUID,
    user: User = Depends(require_role(*_REVIEWER_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> VerificationCheckResponse:
    profile = await _candidate_profile_or_404(db, candidate_id)
    profile_text = _profile_text(profile)

    other_profiles_result = await db.execute(select(CandidateProfile).where(CandidateProfile.id != candidate_id))
    other_profiles = list(other_profiles_result.scalars().all())

    text_corpus: list[tuple[str, str]] = [(str(p.id), _profile_text(p)) for p in other_profiles]

    target_photo_hash = None
    photo_corpus: list[tuple[str, str]] = []
    # All photo rows (subject + entire corpus) in ONE query — this used to be a
    # separate lookup per other candidate, and each of those preceded its own
    # sequential image download.
    photo_by_user = await _latest_photo_files(
        db, [profile.user_id] + [p.user_id for p in other_profiles]
    )
    subject_photo = photo_by_user.get(profile.user_id)

    async with httpx.AsyncClient(timeout=get_settings().photo_fetch_timeout_seconds) as client:
        if subject_photo and subject_photo.public_url:
            target_photo_hash = await _fetch_and_hash_photo(client, subject_photo.public_url)

        if target_photo_hash:
            corpus_targets = [
                (str(other.id), photo_by_user[other.user_id].public_url)
                for other in other_profiles
                if other.user_id in photo_by_user and photo_by_user[other.user_id].public_url
            ]
            # Fetch the corpus concurrently rather than one blocking download at a
            # time — this loop was the dominant cost of the whole check and scaled
            # linearly with the number of candidates on the platform. Bounded so a
            # large corpus can't open hundreds of sockets at once.
            semaphore = asyncio.Semaphore(_PHOTO_FETCH_CONCURRENCY)

            async def _bounded(url: str) -> str | None:
                async with semaphore:
                    return await _fetch_and_hash_photo(client, url)

            hashes = await asyncio.gather(*(_bounded(url) for _, url in corpus_targets))
            photo_corpus = [
                (candidate_id, photo_hash)
                for (candidate_id, _), photo_hash in zip(corpus_targets, hashes)
                if photo_hash
            ]

    dup_state = {
        "subject_type": "profile",
        "subject_id": str(candidate_id),
        "context": {
            "profile_text": profile_text,
            "text_corpus": text_corpus,
            "photo_hash": target_photo_hash,
            "photo_corpus": photo_corpus,
        },
        "signals": [],
        "verdict": None,
    }
    with start_agent_trace(
        "fraud.duplicate_profile_detection",
        input_data={"candidate_id": str(candidate_id), "text_corpus_size": len(text_corpus), "photo_corpus_size": len(photo_corpus)},
        user_id=str(user.id),
        tags=["fraud", "profile"],
    ) as dup_trace:
        # Photo hashing downloads and hashes the whole corpus over the network — by far
        # the longest connection hold in this router.
        dup_result = await without_db_connection(
            db, lambda: get_duplicate_graph().ainvoke(dup_state)
        )
        dup_trace.update(output=dup_result["verdict"])

    content_state = {
        "subject_type": "resume",
        "subject_id": str(candidate_id),
        "context": {"sections": [s for s in [profile.headline] + [str(e) for e in (profile.experience or [])] if s]},
        "signals": [],
        "verdict": None,
    }
    with start_agent_trace(
        "fraud.ai_content_detection",
        input_data={"candidate_id": str(candidate_id)},
        user_id=str(user.id),
        tags=["fraud", "resume"],
    ) as content_trace:
        content_result = await without_db_connection(
            db, lambda: get_content_graph().ainvoke(content_state)
        )
        content_trace.update(output=content_result["verdict"])

    dup_flag = await _persist_check_result(
        db,
        subject_type="profile",
        subject_id=candidate_id,
        candidate_id=candidate_id,
        signals=dup_result["signals"],
        verdict=dup_result["verdict"],
        agent_name="duplicate_profile_detection_agent",
        trace_id=dup_trace.trace_id,
    )
    await _persist_check_result(
        db,
        subject_type="resume",
        subject_id=candidate_id,
        candidate_id=candidate_id,
        signals=content_result["signals"],
        verdict=content_result["verdict"],
        trace_id=content_trace.trace_id,
        agent_name="ai_content_signal_agent",
    )
    await db.commit()
    if dup_flag:
        await db.refresh(dup_flag)

    all_signals = dup_result["signals"] + content_result["signals"]
    return VerificationCheckResponse(
        subject_type="profile",
        subject_id=candidate_id,
        signals=all_signals,
        flag=FraudFlagResponse.model_validate(dup_flag) if dup_flag else None,
    )


@router.get("/candidates/{candidate_id}/authenticity-score", response_model=AuthenticityScoreResponse)
async def get_authenticity_score(
    candidate_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthenticityScoreResponse:
    """Authenticity score for a candidate, derived from their upheld fraud flags.

    Open to any signed-in user, with candidates restricted to their own score below.
    This dependency used to spell out all five roles, which is the same thing as
    `get_current_user` but reads like a restriction — a reviewer has to enumerate the
    role list against `Role` to notice it excludes nobody. The ownership branch below is
    the actual access control.
    """
    profile = await _candidate_profile_or_404(db, candidate_id)
    if user.role == "candidate" and profile.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot_view_other_candidates_score")

    upheld_result = await db.execute(
        select(FraudFlag).where(FraudFlag.candidate_id == candidate_id, FraudFlag.status == "upheld")
    )
    upheld_flags = [{"id": str(f.id), "flag_type": f.flag_type} for f in upheld_result.scalars().all()]

    # Computed and returned, not persisted. This endpoint used to INSERT an
    # AuthenticityScore row on every call — so the table grew with page views rather than
    # with actual scoring events, and a candidate refreshing their flags page wrote
    # history that no one asked for. The score is a pure function of the upheld flags
    # (`compute_authenticity_score`), so recomputing on read is both cheap and always
    # current, where a stored row goes stale the moment a flag is upheld or overturned.
    computed = compute_authenticity_score(upheld_flags)
    return AuthenticityScoreResponse(
        candidate_id=candidate_id,
        score=computed["score"],
        components=computed["components"],
        computed_at=datetime.now(timezone.utc),
    )


@router.get("/candidates/{candidate_id}/flags", response_model=list[FraudFlagResponse])
async def get_candidate_flags(
    candidate_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FraudFlag]:
    """Fraud flags raised against a candidate.

    Same access rule as `get_authenticity_score` above: any signed-in user, except that
    a candidate may only read their own. See that docstring for why this is
    `get_current_user` rather than an all-roles `require_role` list.
    """
    profile = await _candidate_profile_or_404(db, candidate_id)
    if user.role == "candidate" and profile.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot_view_other_candidates_flags")

    result = await db.execute(
        select(FraudFlag).where(FraudFlag.candidate_id == candidate_id).order_by(FraudFlag.raised_at.desc())
    )
    return list(result.scalars().all())


@router.post("/flags/{flag_id}/dispute", response_model=DisputeResponse)
async def dispute_flag(
    flag_id: uuid.UUID,
    body: DisputeSubmitRequest,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> Dispute:
    flag = await _flag_or_404(db, flag_id)
    profile_result = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if profile is None or flag.candidate_id != profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_flag")
    if flag.status not in ("raised", "under_review"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="flag_already_resolved")

    dispute = Dispute(
        fraud_flag_id=flag_id,
        candidate_id=profile.id,
        candidate_statement=body.candidate_statement,
        supporting_files=[str(f) for f in body.supporting_files],
    )
    db.add(dispute)
    flag.status = "under_review"
    await db.commit()
    await db.refresh(dispute)
    return dispute


@router.get("/admin/fraud-review-queue", response_model=list[FraudReviewQueueEntry])
async def fraud_review_queue(
    user: User = Depends(require_role(*_REVIEWER_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[FraudReviewQueueEntry]:
    result = await db.execute(
        select(FraudFlag).where(FraudFlag.status.in_(("raised", "under_review"))).order_by(FraudFlag.raised_at.desc())
    )
    flags = list(result.scalars().all())

    candidate_ids = [f.candidate_id for f in flags if f.candidate_id]
    profiles_result = await db.execute(select(CandidateProfile).where(CandidateProfile.id.in_(candidate_ids)))
    profiles_by_id = {p.id: p for p in profiles_result.scalars().all()}

    flag_ids = [f.id for f in flags]
    disputes_result = await db.execute(select(Dispute.fraud_flag_id).where(Dispute.fraud_flag_id.in_(flag_ids)))
    flag_ids_with_disputes = {row[0] for row in disputes_result.all()}

    entries: list[FraudReviewQueueEntry] = []
    for flag in flags:
        profile = profiles_by_id.get(flag.candidate_id) if flag.candidate_id else None
        entries.append(
            FraudReviewQueueEntry(
                flag=FraudFlagResponse.model_validate(flag),
                candidate_headline=profile.headline if profile else None,
                candidate_github_username=profile.github_username if profile else None,
                has_dispute=flag.id in flag_ids_with_disputes,
            )
        )
    return entries


@router.get("/flags/{flag_id}", response_model=FraudFlagDetailResponse)
async def get_flag_detail(
    flag_id: uuid.UUID,
    user: User = Depends(require_role(*_REVIEWER_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> FraudFlagDetailResponse:
    flag = await _flag_or_404(db, flag_id)

    dispute_result = await db.execute(
        select(Dispute).where(Dispute.fraud_flag_id == flag_id).order_by(Dispute.submitted_at.desc()).limit(1)
    )
    dispute = dispute_result.scalar_one_or_none()

    assist = DisputeReviewAssist(available=False)
    if dispute is not None:
        summary = dispute.review_assist
        if summary is None:
            # Both values are read out of the ORM objects *before* the connection is
            # released, per without_db_connection's contract — the closure must not
            # trigger a lazy load once the session's connection is back in the pool.
            evidence = flag.evidence
            statement = dispute.candidate_statement or ""
            try:
                # Off the DB connection: this is a multi-second model call, and holding a
                # pooled connection open across it starves every other request.
                summary = await without_db_connection(
                    db,
                    lambda: summarize_dispute_for_reviewer(evidence, statement),
                )
                # Persisted so the next reviewer to open this flag reads it instead of
                # paying for the same summary again. Both inputs are immutable after
                # submission, so the cache can never go stale.
                dispute.review_assist = summary
                await db.commit()
            except DisputeReviewUnavailable:
                # No key configured, or the model declined — degrade to "unavailable"
                # rather than fabricating a summary. Deliberately not cached: the next
                # request should retry once a key exists.
                summary = None

        if summary is not None:
            assist = DisputeReviewAssist(
                available=True,
                candidate_context_summary=summary["candidate_context_summary"],
                points_of_agreement_or_conflict=summary["points_of_agreement_or_conflict"],
            )

    return FraudFlagDetailResponse(
        flag=FraudFlagResponse.model_validate(flag),
        dispute=DisputeResponse.model_validate(dispute) if dispute else None,
        dispute_review_assist=assist,
    )


@router.patch("/flags/{flag_id}/review", response_model=FraudFlagResponse)
async def review_flag(
    flag_id: uuid.UUID,
    body: FlagReviewRequest,
    user: User = Depends(require_role(*_REVIEWER_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> FraudFlag:
    if body.status not in ("upheld", "dismissed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_review_status")

    flag = await _flag_or_404(db, flag_id)

    if body.status == "upheld" and not (body.review_notes and body.review_notes.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="review_notes_required_for_upheld",
        )

    flag.status = body.status
    flag.review_notes = body.review_notes
    flag.reviewed_by = user.id
    flag.reviewed_at = datetime.now(timezone.utc)

    # Adjudicating a flag is the single most consequential privileged action in this
    # module — upholding one is what actually penalizes a candidate's authenticity score
    # — yet it was the only one not written to the audit log, while the comparatively
    # minor trusted-issuer CRUD below was. `reviewed_by`/`reviewed_at` on the row are not
    # a substitute: they hold only the *latest* reviewer, so a flag upheld, disputed and
    # then dismissed keeps no record of who upheld it. The audit log is append-only and
    # is where `/admin/audit-log` looks.
    await log_action(
        db,
        actor_user_id=user.id,
        action=f"fraud_flag_{body.status}",
        target_type="fraud_flag",
        target_id=flag.id,
    )
    await db.commit()
    await db.refresh(flag)
    return flag


# --- Trusted issuer registry (FR-1) — admin-only management of the known-issuer table
# that `services/agents/fraud/tools/issuer_lookup.py` checks certificates against. ---


async def _trusted_issuer_or_404(db: AsyncSession, issuer_id: uuid.UUID) -> TrustedIssuer:
    result = await db.execute(select(TrustedIssuer).where(TrustedIssuer.id == issuer_id))
    issuer = result.scalar_one_or_none()
    if issuer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trusted_issuer_not_found")
    return issuer


@router.get("/admin/trusted-issuers", response_model=list[TrustedIssuerResponse])
async def list_trusted_issuers(
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> list[TrustedIssuer]:
    result = await db.execute(select(TrustedIssuer).order_by(TrustedIssuer.name))
    return list(result.scalars().all())


@router.post("/admin/trusted-issuers", response_model=TrustedIssuerResponse, status_code=status.HTTP_201_CREATED)
async def create_trusted_issuer(
    body: TrustedIssuerCreateRequest,
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> TrustedIssuer:
    if body.trust_tier not in ("platform", "university", "employer", "community"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_trust_tier")

    existing = await db.execute(select(TrustedIssuer).where(TrustedIssuer.name == body.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="trusted_issuer_already_exists")

    issuer = TrustedIssuer(
        name=body.name,
        aliases=body.aliases,
        verification_url_template=body.verification_url_template,
        trust_tier=body.trust_tier,
        notes=body.notes,
        added_by_user_id=admin.id,
    )
    db.add(issuer)
    await log_action(
        db,
        actor_user_id=admin.id,
        action="trusted_issuer_added",
        target_type="trusted_issuer",
        target_id=issuer.id,
    )
    await db.commit()
    await db.refresh(issuer)
    return issuer


@router.patch("/admin/trusted-issuers/{issuer_id}", response_model=TrustedIssuerResponse)
async def update_trusted_issuer(
    issuer_id: uuid.UUID,
    body: TrustedIssuerUpdateRequest,
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> TrustedIssuer:
    issuer = await _trusted_issuer_or_404(db, issuer_id)

    if body.trust_tier is not None and body.trust_tier not in ("platform", "university", "employer", "community"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_trust_tier")

    if body.name is not None:
        issuer.name = body.name
    if body.aliases is not None:
        issuer.aliases = body.aliases
    if body.verification_url_template is not None:
        issuer.verification_url_template = body.verification_url_template
    if body.trust_tier is not None:
        issuer.trust_tier = body.trust_tier
    if body.notes is not None:
        issuer.notes = body.notes

    await log_action(
        db,
        actor_user_id=admin.id,
        action="trusted_issuer_updated",
        target_type="trusted_issuer",
        target_id=issuer.id,
    )
    await db.commit()
    await db.refresh(issuer)
    return issuer


@router.delete("/admin/trusted-issuers/{issuer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trusted_issuer(
    issuer_id: uuid.UUID,
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    issuer = await _trusted_issuer_or_404(db, issuer_id)
    await log_action(
        db,
        actor_user_id=admin.id,
        action="trusted_issuer_removed",
        target_type="trusted_issuer",
        target_id=issuer.id,
    )
    await db.delete(issuer)
    await db.commit()
