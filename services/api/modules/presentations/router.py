"""
Presentation & Pitch Deck Controller.
Handles Deck Uploads, Multi-Agent Rubric Scoring, Plagiarism Checking, and Presentation Reports.
"""
import asyncio
import logging
import uuid

import cloudinary.exceptions
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import AgentRun, File, PlagiarismMatch, Presentation, PresentationScore, Slide, User
from packages.shared_schemas.presentations import (
    AIContentSignal,
    PlagiarismMatchOut,
    PresentationReportResponse,
    PresentationStatusResponse,
    PresentationUploadResponse,
    RubricScore,
    SlideOut,
)
from services.agents.ppt_analyzer.graph import get_graph
from services.agents.ppt_analyzer.state import PitchAnalysisState
from services.agents.ppt_analyzer.tools.extraction import UnsupportedDeckFormat, detect_format
from services.api.core.config import Settings, get_settings
from services.api.core.db import async_session, get_db
from services.api.core.queue import TASK_ANALYZE_PRESENTATION, enqueue
from services.api.core.rbac import get_current_user, require_role
from services.api.core.storage import StorageUnavailable, upload_file
from services.api.core.tracing import start_agent_trace

logger = logging.getLogger("presentations")

router = APIRouter(prefix="/presentations", tags=["Pitch Decks & Presentations"])


async def _get_presentation_or_404(db: AsyncSession, presentation_id: uuid.UUID) -> Presentation:
    result = await db.execute(select(Presentation).where(Presentation.id == presentation_id))
    presentation = result.scalar_one_or_none()
    if presentation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="presentation_not_found")
    return presentation


# Roles that legitimately review decks they don't own — hackathon judging/organizing and
# recruiter evaluation. Everyone else may only read their own upload.
_DECK_REVIEWER_ROLES = frozenset({"judge", "organizer", "recruiter", "admin"})


async def _get_owned_presentation_or_404(
    db: AsyncSession, presentation_id: uuid.UUID, user: User
) -> Presentation:
    """Fetch a presentation, enforcing read access.

    Without this, any authenticated user could read any other candidate's deck, scores,
    and plagiarism matches by guessing a UUID. 404 rather than 403 for non-owners so the
    endpoint doesn't confirm that someone else's presentation ID exists.
    """
    presentation = await _get_presentation_or_404(db, presentation_id)
    if presentation.owner_user_id == user.id or user.role in _DECK_REVIEWER_ROLES:
        return presentation
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="presentation_not_found")


def _log_agent_run(
    db: AsyncSession,
    agent_name: str,
    presentation_id: uuid.UUID,
    input_ref: dict,
    output: dict,
    model_used: str | None,
    trace_id: str | None = None,
) -> None:
    db.add(
        AgentRun(
            agent_name=agent_name,
            subject_type="presentation",
            subject_id=presentation_id,
            input_ref=input_ref,
            output=output,
            model_used=model_used,
            langfuse_trace_id=trace_id,
        )
    )


@router.post("/upload", response_model=PresentationUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_presentation(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    linked_repo: str | None = Form(default=None),
    problem_statement: str | None = Form(default=None),
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> PresentationUploadResponse:
    settings = get_settings()

    try:
        detect_format(file.filename, file.content_type)
    except UnsupportedDeckFormat as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    file_bytes = await file.read()
    max_bytes = settings.presentation_max_file_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"file_too_large: max {settings.presentation_max_file_size_mb}MB",
        )

    presentation = Presentation(
        owner_user_id=user.id,
        linked_repo=linked_repo,
        problem_statement=problem_statement,
        status="processing",
    )
    db.add(presentation)
    await db.commit()
    await db.refresh(presentation)

    # The actual analysis (slide extraction/OCR, multi-agent rubric scoring, plagiarism
    # check) previously ran inline here, blocking this response for 15-40+ seconds with
    # no progress feedback beyond a static "Uploading and analyzing…" button label. The
    # frontend (pitch-deck/[id]/page.tsx) already polls on status=="processing", and
    # /status and /report both already handle a still-processing row gracefully — so the
    # only change needed is to actually return as soon as the row exists, and let
    # _analyze_presentation finish the work after the response is sent.
    await enqueue(
        TASK_ANALYZE_PRESENTATION,
        presentation.id,
        user.id,
        file_bytes,
        file.filename,
        file.content_type,
        linked_repo,
        background_tasks=background_tasks,
        fallback=_analyze_presentation,
        job_id=f"deck:{presentation.id}",
    )

    return PresentationUploadResponse(presentation_id=presentation.id, status=presentation.status)


async def _analyze_presentation(
    presentation_id: uuid.UUID,
    owner_user_id: uuid.UUID,
    file_bytes: bytes,
    file_name: str | None,
    file_content_type: str | None,
    linked_repo: str | None,
) -> None:
    """Runs the full multi-agent analysis (slide extraction/OCR, rubric scoring,
    plagiarism check, AI-content heuristic) and persists the result. Scheduled as a
    FastAPI `BackgroundTask` from `upload_presentation` so the upload request can return
    as soon as the file is validated and stored, instead of blocking the HTTP response
    on this whole pipeline (previously 15-40+ seconds with zero progress feedback on the
    upload button). Opens its own session — same "never hold a request-scoped session
    past the request" pattern as `event_consumer.run_polling_loop` — and never raises:
    any failure is recorded as `status="failed"` on the row so `/status` and `/report`
    still resolve, rather than leaving the presentation stuck in `"processing"` forever.
    """
    settings = get_settings()
    async with async_session() as db:
        result = await db.execute(select(Presentation).where(Presentation.id == presentation_id))
        presentation = result.scalar_one_or_none()
        if presentation is None:
            logger.error("presentation %s vanished before analysis could run", presentation_id)
            return

        status_detail: str | None = None
        try:
            # cloudinary.uploader.upload is a blocking network call, and BackgroundTasks
            # share the request event loop — keep it off the loop.
            public_url, storage_key = await asyncio.to_thread(
                upload_file,
                file_bytes,
                public_id=f"presentations/{presentation.id}",
                resource_type="raw",
            )
            db.add(
                File(
                    owner_user_id=owner_user_id,
                    storage_key=storage_key,
                    public_url=public_url,
                    file_type="ppt",
                )
            )
            await db.flush()
        except StorageUnavailable as exc:
            status_detail = f"file_storage_unavailable: {exc}"
        except cloudinary.exceptions.Error as exc:
            status_detail = f"file_storage_unavailable: {exc}"

        try:
            await _run_and_persist_analysis(
                db,
                presentation,
                file_bytes=file_bytes,
                file_name=file_name,
                file_content_type=file_content_type,
                linked_repo=linked_repo,
                owner_user_id=owner_user_id,
                status_detail=status_detail,
                settings=settings,
            )
        except Exception:
            logger.exception("ppt analysis failed for presentation %s", presentation_id)
            presentation.status = "failed"
            presentation.status_detail = "analysis_error: see server logs"
            await db.commit()


async def _run_and_persist_analysis(
    db: AsyncSession,
    presentation: Presentation,
    *,
    file_bytes: bytes,
    file_name: str | None,
    file_content_type: str | None,
    linked_repo: str | None,
    owner_user_id: uuid.UUID,
    status_detail: str | None,
    settings: Settings,
) -> None:
    initial_state: PitchAnalysisState = {
        "presentation_id": str(presentation.id),
        "file_bytes": file_bytes,
        "file_name": file_name,
        "file_content_type": file_content_type,
        "linked_repo": linked_repo,
        "problem_statement": presentation.problem_statement,
        "requirement_coverage": None,
        "rubric_breakdown": None,
        "normalized_pptx_bytes": None,
        "normalization_error": None,
        "slides": [],
        "slide_images": {},
        "extraction_error": None,
        "slide_ocr_notes": [],
        "slide_embeddings": None,
        "plagiarism_matches": [],
        "plagiarism_checked": True,
        "presentation_quality": None,
        "innovation_business": None,
        "technical_feasibility": None,
        "ai_content_signal": None,
        "scores": {},
        "overall_score": None,
        "renormalized_scores": [],
        "summary": None,
        "suggestions": [],
    }

    with start_agent_trace(
        "ppt_analyzer.analyze",
        input_data={"file_name": file_name, "linked_repo": linked_repo},
        user_id=str(owner_user_id),
        tags=["ppt-analyzer"],
    ) as trace:
        result_state = await get_graph().ainvoke(initial_state)
        trace.update(output={"overall_score": result_state.get("overall_score")})

    for slide in result_state.get("slides", []):
        ocr_note = next(
            (n for n in result_state.get("slide_ocr_notes", []) if n["index"] == slide["index"]), None
        )
        db.add(
            Slide(
                presentation_id=presentation.id,
                slide_index=slide["index"],
                title=slide.get("title"),
                body=slide.get("body"),
                notes=slide.get("notes"),
                has_image=slide.get("has_image", False),
                ocr_text=(ocr_note or {}).get("ocr_text") or (ocr_note or {}).get("diagram_summary"),
            )
        )

    scores = result_state.get("scores", {})
    presentation_quality = scores.get("presentation_quality", {})
    innovation = scores.get("innovation", {})
    business_potential = scores.get("business_potential", {})
    technical_feasibility = scores.get("technical_feasibility", {})
    ai_content_signal = result_state.get("ai_content_signal") or {}

    db.add(
        PresentationScore(
            presentation_id=presentation.id,
            problem_statement=result_state.get("problem_statement") or presentation.problem_statement,
            requirement_coverage=result_state.get("requirement_coverage"),
            rubric_breakdown=result_state.get("rubric_breakdown"),
            innovation_score=innovation.get("value"),
            technical_feasibility_score=technical_feasibility.get("value"),
            presentation_quality_score=presentation_quality.get("value"),
            business_potential_score=business_potential.get("value"),
            overall_pitch_score=result_state.get("overall_score"),
            renormalized_scores=result_state.get("renormalized_scores", []),
            summary=result_state.get("summary"),
            suggestions=result_state.get("suggestions", []),
            ai_content_signal=ai_content_signal,
            plagiarism_checked=result_state.get("plagiarism_checked", True),
        )
    )

    for match in result_state.get("plagiarism_matches", []):
        matched_id = match.get("matched_presentation_id")
        if not matched_id:
            continue
        try:
            matched_uuid = uuid.UUID(str(matched_id))
        except ValueError:
            continue
        db.add(
            PlagiarismMatch(
                presentation_id=presentation.id,
                matched_presentation_id=matched_uuid,
                slide_index=match["slide_index"],
                similarity=match["similarity"],
            )
        )

    _log_agent_run(
        db, "ppt_problem_solution_clarity_agent", presentation.id,
        {"slide_count": len(result_state.get("slides", []))}, presentation_quality, settings.llm_model_judgment,
        trace_id=trace.trace_id,
    )
    _log_agent_run(
        db, "ppt_innovation_business_impact_agent", presentation.id,
        {"slide_count": len(result_state.get("slides", []))},
        {"innovation": innovation, "business_potential": business_potential},
        settings.llm_model_judgment,
        trace_id=trace.trace_id,
    )
    _log_agent_run(
        db, "ppt_technical_feasibility_agent", presentation.id,
        {"linked_repo": linked_repo}, technical_feasibility, settings.llm_model_judgment,
        trace_id=trace.trace_id,
    )
    _log_agent_run(
        db, "ppt_ai_content_heuristic_agent", presentation.id,
        {"slide_count": len(result_state.get("slides", []))}, ai_content_signal, None,
        trace_id=trace.trace_id,
    )
    _log_agent_run(
        db, "ppt_aggregation_agent", presentation.id,
        scores, {"overall_score": result_state.get("overall_score"), "renormalized": result_state.get("renormalized_scores", [])}, None,
        trace_id=trace.trace_id,
    )

    extraction_error = result_state.get("extraction_error")
    if extraction_error and not result_state.get("slides"):
        presentation.status = "failed"
        presentation.status_detail = extraction_error
    else:
        presentation.status = "done"
        presentation.status_detail = status_detail or extraction_error

    await db.commit()


@router.get("/{presentation_id}/status", response_model=PresentationStatusResponse)
async def get_status(
    presentation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PresentationStatusResponse:
    presentation = await _get_owned_presentation_or_404(db, presentation_id, user)
    return PresentationStatusResponse(presentation_id=presentation.id, status=presentation.status)


@router.get("/{presentation_id}/report", response_model=PresentationReportResponse)
async def get_report(
    presentation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PresentationReportResponse:
    presentation = await _get_owned_presentation_or_404(db, presentation_id, user)

    slides_result = await db.execute(
        select(Slide).where(Slide.presentation_id == presentation_id).order_by(Slide.slide_index)
    )
    slides = [SlideOut.model_validate(s) for s in slides_result.scalars().all()]

    score_result = await db.execute(
        select(PresentationScore)
        .where(PresentationScore.presentation_id == presentation_id)
        .order_by(PresentationScore.computed_at.desc())
        .limit(1)
    )
    score = score_result.scalar_one_or_none()

    matches_result = await db.execute(
        select(PlagiarismMatch).where(PlagiarismMatch.presentation_id == presentation_id)
    )
    matches = [PlagiarismMatchOut.model_validate(m) for m in matches_result.scalars().all()]

    if score is None:
        return PresentationReportResponse(
            presentation_id=presentation.id,
            status=presentation.status,
            linked_repo=presentation.linked_repo,
            problem_statement=presentation.problem_statement,
            slides=slides,
            scores={},
            overall_pitch_score=None,
            renormalized_scores=[],
            summary=None,
            suggestions=[],
            ai_content_signal=None,
            plagiarism_matches=matches,
            # No score row yet: the analysis has not finished, so the check has not run.
            # The UI keys off `status` here, but claiming a completed check would be a
            # lie in the one state where it is most obviously untrue.
            plagiarism_checked=False,
            computed_at=None,
            requirement_coverage=None,
            rubric_breakdown=None,
        )

    scores = {
        "innovation": RubricScore(value=score.innovation_score),
        "technical_feasibility": RubricScore(value=score.technical_feasibility_score),
        "presentation_quality": RubricScore(value=score.presentation_quality_score),
        "business_potential": RubricScore(value=score.business_potential_score),
    }
    ai_signal = AIContentSignal(**score.ai_content_signal) if score.ai_content_signal else None

    return PresentationReportResponse(
        presentation_id=presentation.id,
        status=presentation.status,
        linked_repo=presentation.linked_repo,
        problem_statement=score.problem_statement or presentation.problem_statement,
        slides=slides,
        scores=scores,
        overall_pitch_score=score.overall_pitch_score,
        renormalized_scores=score.renormalized_scores or [],
        summary=score.summary,
        suggestions=score.suggestions or [],
        ai_content_signal=ai_signal,
        plagiarism_matches=matches,
        plagiarism_checked=score.plagiarism_checked,
        computed_at=score.computed_at,
        requirement_coverage=score.requirement_coverage,
        rubric_breakdown=score.rubric_breakdown,
    )


@router.get("/{presentation_id}/plagiarism-matches", response_model=list[PlagiarismMatchOut])
async def get_plagiarism_matches(
    presentation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlagiarismMatchOut]:
    await _get_owned_presentation_or_404(db, presentation_id, user)
    result = await db.execute(select(PlagiarismMatch).where(PlagiarismMatch.presentation_id == presentation_id))
    return [PlagiarismMatchOut.model_validate(m) for m in result.scalars().all()]
