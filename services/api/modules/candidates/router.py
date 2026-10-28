"""
Candidate Controller & Intelligence Endpoints.
Handles Candidate Profile Ingestion, Talent Score™ Calculation, GitHub Sync, and Career Guidance.
"""
import asyncio
import re
import secrets
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse
from github import Github
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.common.constants import truncate_error
from services.api.core.db import async_session

from packages.db.models import (
    AgentRun,
    Badge,
    CandidateProfile,
    CareerRecommendation,
    Certification,
    CourseCatalogEntry,
    File,
    GeneratedDocument,
    GithubSnapshot,
    HackathonRanking,
    HackathonTeamMember,
    TalentScore,
    User,
)
from packages.shared_schemas.candidates import (
    SUB_SCORE_NAMES,
    BadgeResponse,
    CandidateProfileResponse,
    CareerGuidanceResponse,
    CoverLetterGenerateRequest,
    DashboardResponse,
    EvidenceConfidence,
    GeneratedDocumentResponse,
    GithubSummary,
    HackathonExperienceRequest,
    GithubConnectRequest,
    LeetcodeConnectRequest,
    PortfolioPublishRequest,
    ProfileUpdateRequest,
    PublicPortfolioProject,
    ResumeGenerateRequest,
    SubScore,
    TalentScoreResponse,
)
from services.agents.candidate_intelligence.career_guidance_graph import get_career_guidance_graph
from services.agents.candidate_intelligence.document_state import DocumentBuilderState
from services.agents.candidate_intelligence.graph import get_graph
from services.agents.candidate_intelligence.resume_graph import get_resume_graph
from services.agents.candidate_intelligence.state import CandidateProfileState, CareerGuidanceState
from services.agents.candidate_intelligence.tools.document_generation import (
    DocumentGenerationUnavailable,
)
from services.agents.candidate_intelligence.tools.assessment_bridge import (
    assessment_score_population,
    latest_assessment_score,
)
from services.agents.candidate_intelligence.tools.github_calendar import (
    GithubCalendarUnavailable,
    fetch_github_calendar,
)
from services.agents.candidate_intelligence.tools.population import (
    commit_count_population,
)
from services.agents.candidate_intelligence.tools.leetcode import (
    LeetcodeUnavailable,
    fetch_leetcode_stats,
)
from services.agents.candidate_intelligence.tools.resume_pdf import (
    PdfGenerationUnavailable,
    render_resume_pdf,
)
from services.agents.candidate_intelligence.tools.role_taxonomy import ROLE_SKILL_TAXONOMY
from services.agents.candidate_intelligence.tools.roadmap import RoadmapGenerationUnavailable
from services.agents.candidate_intelligence.tools.skill_gap import CareerGuidanceUnavailable
from services.api.core.config import get_settings
from services.api.core.db import get_db, without_db_connection
from services.api.core.rbac import require_role
from services.api.core.storage import StorageUnavailable, upload_file
from services.api.core.tracing import start_agent_trace

_CAREER_RECOMMENDATION_TTL = timedelta(hours=get_settings().career_recommendation_ttl_hours)
_GITHUB_OAUTH_STATE_TTL_SECONDS = get_settings().github_oauth_state_ttl_seconds
# state -> (user_id, expires_at, return_path_key). The return key rides along in this
# same entry rather than a parallel dict so it is discarded by the same `.pop()` that
# consumes the state — a second map would leak an entry for every OAuth flow a user
# abandoned before GitHub redirected back.
_oauth_state_cache: dict[str, tuple[str, float, str]] = {}
# Third-party stats (GitHub calendar, LeetCode) are cached, not fetched live per view —
# this bounds how often a candidate can force a re-fetch of LeetCode's unofficial API.
_STATS_REFRESH_COOLDOWN = timedelta(minutes=get_settings().stats_refresh_cooldown_minutes)

# Caps on the two unbounded collections in the dashboard payload. Both were returned in
# full: every non-fork repo, and the entire append-only TalentScore history. The dashboard
# cannot render until the whole response arrives, so payload size is felt directly as
# time-to-first-paint.
_MAX_DASHBOARD_PROJECTS = get_settings().max_dashboard_projects
# The score chart plots a trend; older points are compressed to invisibility long before
# this. `latest_score` is selected separately, so trimming history never affects it.
_MAX_SCORE_HISTORY = get_settings().max_score_history

logger = logging.getLogger(__name__)

# Handles that would shadow a real route on the public portfolio (`/[username]` sits
# beside these paths), plus the role names, which must never be claimable as a personal
# handle because a profile at `/admin` reads as an official page.
#
# MUST stay in sync with RESERVED_USERNAMES in apps/web/src/lib/constants.ts. The client
# check is a courtesy that fails fast in the form; this set is the one that actually
# enforces, because the API is reachable directly. An earlier revision had six names
# ("home", "admin", "recruiter", "organizer", "judge", "settings") on the client only,
# so `POST /auth/signup` with username="admin" returned 201.
# tests/test_reserved_usernames.py asserts the two lists match.
_RESERVED_USERNAMES = {
    "api", "dashboard", "onboarding", "sign-in", "sign-up", "hackathons",
    "profile", "career", "resume-builder", "assessments", "interview", "my-flags",
    "applications", "jobs", "copilot", "pipeline", "analytics", "top-performers",
    "reports", "evaluations", "submissions", "fraud-review", "users", "audit-log",
    "candidates", "public", "me", "health",
    "home", "admin", "recruiter", "organizer", "judge", "settings",
}
_USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])?$")

router = APIRouter(prefix="/candidates", tags=["Candidate Intelligence & Talent Scoring"])


class FactCheckFailed(Exception):
    def __init__(self, document: GeneratedDocument) -> None:
        self.document = document
        super().__init__("Generated document failed the fact-check guardrail.")


@router.patch("/me", response_model=CandidateProfileResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    profile = await _get_or_create_profile(db, user)
    
    if body.full_name is not None:
        user.full_name = body.full_name
        db.add(user)

    if body.username is not None:
        username = body.username.strip().lower()
        if not _USERNAME_PATTERN.match(username) or username in _RESERVED_USERNAMES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_username")
        existing_username = await db.execute(
            select(CandidateProfile).where(
                CandidateProfile.username == username, CandidateProfile.id != profile.id
            )
        )
        if existing_username.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username_taken")
        profile.username = username
        
    if body.headline is not None:
        profile.headline = body.headline
    if body.location is not None:
        profile.location = body.location
        
    if body.college is not None or body.degree is not None:
        current_education = profile.education or []
        edu = dict(current_education[0]) if current_education else {}
        if body.college is not None:
            edu["institution"] = body.college
        if body.degree is not None:
            edu["degree"] = body.degree
        profile.education = [edu]
        
    await db.commit()
    await db.refresh(profile)
    return profile


@router.post("/me/hackathon-experience", response_model=CandidateProfileResponse)
async def add_hackathon_experience(
    body: HackathonExperienceRequest,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> CandidateProfile:
    """Add a hackathon experience entry (self-reported external hackathon) and trigger rescore."""
    import uuid

    profile = await _get_or_create_profile(db, user)

    current_exp = profile.hackathon_experience or []
    new_entry = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "result": body.result,
        "weight": body.weight,
        "date": body.date,
        "platform_hackathon_id": None,
    }
    current_exp.append(new_entry)
    profile.hackathon_experience = current_exp
    profile.ingestion_status = "processing"

    await db.commit()
    await db.refresh(profile)

    # Trigger background rescore
    background_tasks.add_task(
        _run_ingestion_background,
        profile.id,
        {},
        None,
    )

    return profile


@router.delete("/me/hackathon-experience/{entry_id}", response_model=CandidateProfileResponse)
async def remove_hackathon_experience(
    entry_id: str,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> CandidateProfile:
    """Remove a hackathon experience entry and trigger rescore."""
    profile = await _get_or_create_profile(db, user)

    current_exp = profile.hackathon_experience or []
    updated_exp = [e for e in current_exp if e.get("id") != entry_id]

    if len(updated_exp) == len(current_exp):
        raise HTTPException(status_code=404, detail="Hackathon experience entry not found")

    profile.hackathon_experience = updated_exp if updated_exp else None
    profile.ingestion_status = "processing"

    await db.commit()
    await db.refresh(profile)

    # Trigger background rescore
    background_tasks.add_task(
        _run_ingestion_background,
        profile.id,
        {},
        None,
    )

    return profile


async def _get_or_create_profile(db: AsyncSession, user: User) -> CandidateProfile:
    result = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


# Maps a graph node name to the phrase shown to the candidate while it runs. Keys must
# match the node names registered in `candidate_intelligence/graph.py`; an unmapped node
# simply leaves the stage unchanged rather than showing a raw identifier.
_INGESTION_STAGE_LABELS = {
    "resume_parser": "Reading your resume",
    "github_analysis": "Analyzing your GitHub repositories",
    "certificate_ocr": "Reading your certificates",
    "profile_merge": "Merging your profile",
    "talent_scoring": "Computing your Talent Score",
    "badge_assignment": "Awarding badges",
}


async def _ainvoke_with_stage_updates(
    db: AsyncSession, profile: CandidateProfile, initial_state: CandidateProfileState
) -> dict:
    """Runs the ingestion graph, recording each finished node as `ingestion_stage`.

    `astream(stream_mode="updates")` yields one event per node as it completes, so the
    stage the poller reports is real observed progress, not a timer-driven animation that
    could claim "computing Talent Score" while the run is actually stuck on GitHub.

    Each write is its own committed transaction, because the point is for a *different*
    request (the frontend's status poll) to read it while this one is still running —
    an uncommitted value would be invisible until the whole ingestion finished, which is
    precisely the problem this solves.

    Stage bookkeeping must never break ingestion: a failure to persist the label is
    logged and swallowed, and the graph result is returned regardless.

    `stream_mode=["updates", "values"]` is deliberate. "updates" carries the node names
    needed for progress; "values" carries the full reduced state after each step, and
    that is what the return value is taken from. Accumulating the "updates" deltas by
    hand would be wrong twice over: it would drop router-supplied inputs no node rewrites
    (the population lists, `hackathon_*`), and it would overwrite `conflicts` — an
    `operator.add`-reduced channel whose deltas are per-node fragments — instead of
    concatenating them, silently losing merge conflicts.
    """
    final_state: dict = {}
    async for stream_mode, chunk in get_graph().astream(
        initial_state, stream_mode=["updates", "values"]
    ):
        if stream_mode == "values":
            # Full reduced state after this step; the last one is the graph's result.
            final_state = chunk
            continue
        for node_name in chunk:
            label = _INGESTION_STAGE_LABELS.get(node_name)
            if label is None:
                continue
            try:
                profile.ingestion_stage = label
                await db.commit()
            except Exception:  # noqa: BLE001 - progress display must not fail ingestion
                logger.debug("Could not persist ingestion stage %r", label, exc_info=True)
                await db.rollback()
    return final_state


async def _run_ingestion_and_persist(
    db: AsyncSession, profile: CandidateProfile, state_overrides: dict
) -> CandidateProfile:
    # Population/assessment data for Talent Score v2's percentile normalization —
    # fetched here (the router owns the DB session) and injected into graph state so the
    # talent_scoring node stays DB-free, same convention as the rest of this module.
    # Only populations measured in the same units as the candidate's own value are
    # passed. Stars, leadership and open-source used to be ranked against other
    # candidates' finished 0-100 sub-scores, which compared a raw count to a score; those
    # now use their absolute scales until a raw-value population is stored.
    commit_population = await commit_count_population(db)
    assessment_score = await latest_assessment_score(db, profile.id)
    assessment_population = await assessment_score_population(db)

    # Fetch hackathon data: platform-run results from HackathonRanking/HackathonTeamMember
    # and self-reported from CandidateProfile.hackathon_experience
    hackathon_platform_results = []
    if profile.id:
        team_members = await db.execute(
            select(HackathonTeamMember.team_id).where(HackathonTeamMember.candidate_id == profile.id)
        )
        team_ids = list(team_members.scalars().all())
        if team_ids:
            # Single IN query rather than one SELECT per team membership — this runs on
            # every ingestion (resume upload, certificate upload, GitHub connect, and
            # every hackathon-experience edit), so the N+1 landed directly on the
            # user-visible "processing" wait.
            rankings = await db.execute(
                select(HackathonRanking).where(HackathonRanking.team_id.in_(team_ids))
            )
            hackathon_platform_results = [
                {
                    "rank": ranking.rank,
                    "composite_score": ranking.composite_score,
                    "hackathon_id": str(ranking.hackathon_id),
                }
                for ranking in rankings.scalars().all()
            ]

    hackathon_self_reported = profile.hackathon_experience or []

    initial_state: CandidateProfileState = {
        "candidate_id": str(profile.id),
        "user_id": str(profile.user_id),
        "raw_resume_bytes": None,
        "raw_resume_content_type": None,
        "resume_parsed": {
            "headline": profile.headline,
            "location": profile.location,
            "skills": profile.skills or [],
            "experience": profile.experience or [],
            "education": profile.education or [],
        }
        if not state_overrides.get("raw_resume_bytes")
        else None,
        "github_username": profile.github_username,
        "github_access_token": None,
        "github_raw": None,
        "certificate_file_bytes": None,
        "certificate_extracted": None,
        "merged_profile": None,
        "conflicts": [],
        "commit_population": commit_population,
        "star_population": [],
        "leadership_population": [],
        "contribution_population": [],
        "assessment_score": assessment_score,
        "assessment_population": assessment_population,
        "hackathon_platform_results": hackathon_platform_results,
        "hackathon_self_reported": hackathon_self_reported,
        "leetcode_stats": profile.leetcode_stats,
        "sub_scores": {},
        "overall_score": None,
        "renormalized_subscores": [],
        "confidence": None,
        "badges": [],
        **state_overrides,
    }

    with start_agent_trace(
        "candidate_intelligence.ingest",
        input_data={"github_username": profile.github_username, "has_resume": bool(state_overrides.get("raw_resume_bytes"))},
        user_id=str(profile.user_id),
        tags=["candidate-intelligence", "ingestion"],
    ) as trace:
        result_state = await _ainvoke_with_stage_updates(db, profile, initial_state)
        trace.update(output={"overall_score": result_state.get("overall_score")})

    merged = result_state["merged_profile"] or {}
    profile.github_username = merged.get("github_username") or profile.github_username
    profile.headline = merged.get("headline") or profile.headline
    profile.location = merged.get("location") or profile.location
    profile.skills = merged.get("skills") or profile.skills
    profile.experience = merged.get("experience") or profile.experience
    profile.education = merged.get("education") or profile.education
    profile.merged_conflicts = merged.get("merged_conflicts", [])

    github_raw = result_state.get("github_raw")
    if github_raw is not None:
        # Merged into (not replacing) github_stats — the GraphQL calendar fetch in
        # github_oauth_callback below also writes into this same JSONB column, and
        # ingestion can run standalone (resume-only) without a fresh calendar fetch.
        profile.github_stats = {
            **(profile.github_stats or {}),
            "owned_repo_count": github_raw.owned_repo_count,
            "external_contributions": github_raw.external_contributions,
            "pr_review_count": github_raw.pr_review_count,
            "commit_activity_weekly": github_raw.commit_activity_weekly,
        }
        # Clear previous repository snapshots for this candidate to ensure fresh state
        await db.execute(delete(GithubSnapshot).where(GithubSnapshot.candidate_id == profile.id))
        for repo in github_raw.repos:
            db.add(
                GithubSnapshot(
                    candidate_id=profile.id,
                    repo_full_name=repo.repo_full_name,
                    stars=repo.stars,
                    forks=repo.forks,
                    commit_count=repo.commit_count,
                    pr_count=repo.pr_count,
                    issue_count=repo.issue_count,
                    languages=repo.languages,
                    is_fork=repo.is_fork,
                    topics=repo.topics,
                    pushed_at=repo.pushed_at,
                )
            )

    certificate_extracted = result_state.get("certificate_extracted")
    if certificate_extracted is not None:
        db.add(
            Certification(
                candidate_id=profile.id,
                title=certificate_extracted.get("title"),
                credential_id=certificate_extracted.get("credential_id"),
                ocr_confidence=certificate_extracted.get("ocr_confidence"),
                verification_status="unverified",
            )
        )

    sub_scores: dict[str, SubScore] = result_state["sub_scores"]
    confidence = result_state.get("confidence")
    settings = get_settings()
    if sub_scores:
        score_row = TalentScore(
            candidate_id=profile.id,
            coding_ability=sub_scores["coding_ability"].value,
            problem_solving=sub_scores["problem_solving"].value,
            project_quality=sub_scores["project_quality"].value,
            innovation=sub_scores["innovation"].value,
            technical_consistency=sub_scores["technical_consistency"].value,
            community_participation=sub_scores["community_participation"].value,
            leadership=sub_scores["leadership"].value,
            open_source_contributions=sub_scores["open_source_contributions"].value,
            hackathon_performance=sub_scores["hackathon_performance"].value,
            overall=result_state["overall_score"],
            renormalized_subscores=result_state["renormalized_subscores"],
            confidence_available_signals=confidence.available_signals if confidence else None,
            confidence_expected_signals=confidence.expected_signals if confidence else None,
            confidence=confidence.confidence if confidence else None,
        )
        db.add(score_row)

        talent_scoring_input = {"github_username": profile.github_username}
        talent_scoring_output = {
            name: asdict(s) if hasattr(s, "__dataclass_fields__") else s.model_dump() for name, s in sub_scores.items()
        }
        db.add(
            AgentRun(
                agent_name="talent_scoring_agent",
                subject_type="candidate",
                subject_id=profile.id,
                input_ref=talent_scoring_input,
                output=talent_scoring_output,
                model_used=settings.llm_model_judgment,
                langfuse_trace_id=trace.trace_id,
            )
        )

    existing_badges = await db.execute(select(Badge.skill_name).where(Badge.candidate_id == profile.id))
    existing_skill_names = {row[0] for row in existing_badges.all()}
    for badge in result_state.get("badges", []):
        if badge["skill_name"] not in existing_skill_names:
            db.add(
                Badge(
                    candidate_id=profile.id,
                    skill_name=badge["skill_name"],
                    corroboration_sources=badge["corroboration_sources"],
                )
            )

    await db.commit()
    await db.refresh(profile)
    return profile


async def _run_ingestion_background(
    profile_id, state_overrides: dict, github_access_token: str | None = None
) -> None:
    """Runs `_run_ingestion_and_persist` outside the request/response cycle, in its own
    DB session (the request's session is closed by the time this executes). Ingestion
    involves dozens of blocking GitHub calls plus several LLM round-trips — synchronously
    awaiting it in the request handler stalls the uploading candidate's own request for
    the full duration and, combined with unindexed queries, degrades every other
    concurrent request too. `ingestion_status` lets the frontend poll for completion.

    `github_access_token` also triggers the Development Stats (contribution calendar)
    GraphQL fetch — best-effort, folded in here since it's part of the same GitHub
    connect flow and is itself a network call worth keeping off the request path.
    """
    async with async_session() as bg_db:
        result = await bg_db.execute(select(CandidateProfile).where(CandidateProfile.id == profile_id))
        profile = result.scalar_one_or_none()
        if profile is None:
            return
        try:
            await _run_ingestion_and_persist(bg_db, profile, state_overrides)
            profile.ingestion_status = "done"
            profile.ingestion_error = None
            # Cleared on every terminal outcome so a finished run never leaves a stale
            # "Analyzing your GitHub repositories" behind for the next poll to show.
            profile.ingestion_stage = None
        except Exception as exc:  # noqa: BLE001 - surfaced via ingestion_error, never crashes the worker
            logger.exception("Background ingestion failed for candidate %s", profile_id)
            profile.ingestion_status = "failed"
            profile.ingestion_error = truncate_error(exc)
            profile.ingestion_stage = None
            await bg_db.commit()
            return

        if github_access_token and profile.github_username:
            try:
                calendar = await fetch_github_calendar(profile.github_username, github_access_token)
                profile.github_stats = {**(profile.github_stats or {}), **asdict(calendar)}
                profile.stats_refreshed_at = datetime.now(timezone.utc)
            except GithubCalendarUnavailable:
                logger.warning(
                    "GitHub calendar fetch failed for %s", profile.github_username, exc_info=True
                )

        await bg_db.commit()


@router.get("/me", response_model=CandidateProfileResponse)
async def get_my_profile(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    return await _get_or_create_profile(db, user)


# Content types each ingestion path can actually parse. Resume text extraction
# (tools/resume.py) handles PDF and Word; certificate OCR (tools/certificate.py) opens
# the bytes with Pillow, so it needs a real image. Anything else raises deep inside the
# parser *after* the file has been read into memory and handed to the background job, surfacing to the
# candidate as a failed background job rather than a rejected upload.
_RESUME_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}
_CERTIFICATE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/tiff"}


async def _read_upload_or_400(
    file: UploadFile, *, allowed_types: set[str], max_mb: int, kind: str
) -> bytes:
    """Read an upload, rejecting the wrong type or an oversized body.

    Mirrors the presentation upload route's guard (`detect_format` + a size ceiling),
    which these two routes were missing entirely. Size is checked after the read because
    Starlette has already spooled the body to disk by the time the handler runs — the
    ceiling bounds what is held in memory and passed to the background job, which is
    what actually costs.
    """
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported_{kind}_type: {file.content_type or 'unknown'}",
        )
    file_bytes = await file.read()
    if len(file_bytes) > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"file_too_large: max {max_mb}MB",
        )
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty_file")
    return file_bytes


@router.post("/me/ingest/resume", response_model=CandidateProfileResponse)
async def ingest_resume(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    profile = await _get_or_create_profile(db, user)
    file_bytes = await _read_upload_or_400(
        file,
        allowed_types=_RESUME_CONTENT_TYPES,
        max_mb=get_settings().resume_max_file_size_mb,
        kind="resume",
    )
    profile.ingestion_status = "processing"
    profile.ingestion_error = None
    await db.commit()
    await db.refresh(profile)
    background_tasks.add_task(
        _run_ingestion_background,
        profile.id,
        {"raw_resume_bytes": file_bytes, "raw_resume_content_type": file.content_type},
        None,
    )
    return profile


@router.post("/me/ingest/certificate", response_model=CandidateProfileResponse)
async def ingest_certificate(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    profile = await _get_or_create_profile(db, user)
    file_bytes = await _read_upload_or_400(
        file,
        allowed_types=_CERTIFICATE_CONTENT_TYPES,
        max_mb=get_settings().certificate_max_file_size_mb,
        kind="certificate",
    )
    profile.ingestion_status = "processing"
    profile.ingestion_error = None
    await db.commit()
    await db.refresh(profile)
    background_tasks.add_task(
        _run_ingestion_background,
        profile.id,
        {"certificate_file_bytes": file_bytes},
        None,
    )
    return profile


@router.get("/me/ingestion-status")
async def get_ingestion_status(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    profile = await _get_or_create_profile(db, user)
    return {
        "status": profile.ingestion_status,
        "error": profile.ingestion_error,
        "stage": profile.ingestion_stage,
    }


# Where the OAuth callback may send the browser back to. GitHub returns the user to a
# fixed registered redirect URI, so the *final* in-app destination has to be carried
# through `state`. An allowlist rather than an arbitrary URL: `state` survives a full
# round trip through github.com, so echoing an attacker-supplied value back into a
# redirect would be an open-redirect primitive.
_OAUTH_RETURN_PATHS = {"profile_edit": "/profile/edit", "onboarding": "/onboarding"}
_DEFAULT_OAUTH_RETURN = "profile_edit"


def _oauth_return_path(key: str | None) -> str:
    return _OAUTH_RETURN_PATHS.get(key or "", _OAUTH_RETURN_PATHS[_DEFAULT_OAUTH_RETURN])


@router.get("/github/oauth-url")
async def github_oauth_url(
    return_to: str = _DEFAULT_OAUTH_RETURN,
    user: User = Depends(require_role("candidate")),
) -> dict:
    settings = get_settings()
    state = secrets.token_urlsafe(24)
    # Normalized at issue time, so the callback only ever reads a key it put there.
    return_key = return_to if return_to in _OAUTH_RETURN_PATHS else _DEFAULT_OAUTH_RETURN
    _oauth_state_cache[state] = (
        str(user.id),
        time.monotonic() + _GITHUB_OAUTH_STATE_TTL_SECONDS,
        return_key,
    )
    authorize_url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_client_id}"
        f"&redirect_uri={settings.github_oauth_redirect_uri}"
        "&scope=read:user%20repo"
        f"&state={state}"
    )
    return {"authorize_url": authorize_url}


@router.get("/github/oauth/callback")
async def github_oauth_callback(
    code: str,
    state: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    cached = _oauth_state_cache.pop(state, None)
    if cached is None or cached[1] < time.monotonic():
        # No usable state means no recorded destination either, so this one falls back
        # to the default rather than reading from the (absent) entry.
        return RedirectResponse(
            f"{settings.frontend_url}{_oauth_return_path(None)}?github=invalid_state"
        )
    user_id = cached[0]
    return_path = _oauth_return_path(cached[2])

    async with httpx.AsyncClient(timeout=get_settings().oauth_exchange_timeout_seconds) as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": settings.github_oauth_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
    token_data = token_response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        return RedirectResponse(
            f"{settings.frontend_url}{return_path}?github=token_exchange_failed"
        )

    # Github(...).get_user() is a blocking PyGithub HTTP call — off-thread so it doesn't
    # stall the event loop for every other in-flight request (same as github_analysis.py).
    github_username = await asyncio.to_thread(
        lambda: Github(login_or_token=access_token).get_user().login
    )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()
    profile = await _get_or_create_profile(db, user)
    profile.github_username = github_username
    profile.ingestion_status = "processing"
    profile.ingestion_error = None
    await db.commit()

    background_tasks.add_task(
        _run_ingestion_background,
        profile.id,
        {"github_username": github_username, "github_access_token": access_token},
        access_token,
    )

    return RedirectResponse(f"{settings.frontend_url}{return_path}?github=connected")


@router.post("/me/github", response_model=CandidateProfileResponse)
async def connect_github_username(
    body: GithubConnectRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    """Connect GitHub by username directly without OAuth.
    Crawls public repositories and runs full candidate intelligence ingestion.
    """
    clean_username = body.github_username.strip().lstrip("@")
    if not clean_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty_username")

    profile = await _get_or_create_profile(db, user)
    profile.github_username = clean_username
    profile.ingestion_status = "processing"
    profile.ingestion_error = None
    profile.ingestion_stage = "Analyzing your GitHub repositories"
    await db.commit()

    background_tasks.add_task(
        _run_ingestion_background,
        profile.id,
        {"github_username": clean_username},
        None,
    )
    await db.refresh(profile)
    return profile


@router.post("/me/leetcode", response_model=CandidateProfileResponse)
async def connect_leetcode(
    body: LeetcodeConnectRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    """Problem Solving Stats — connect by username only (LeetCode has no public OAuth)."""
    profile = await _get_or_create_profile(db, user)
    try:
        stats = await fetch_leetcode_stats(body.leetcode_username)
    except LeetcodeUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="leetcode_username_invalid") from exc

    profile.leetcode_username = body.leetcode_username
    profile.leetcode_stats = asdict(stats)
    profile.stats_refreshed_at = datetime.now(timezone.utc)
    profile.ingestion_status = "processing"
    await db.commit()
    await db.refresh(profile)
    # LeetCode feeds Problem Solving, so the Talent Score is stale until rescored.
    background_tasks.add_task(_run_ingestion_background, profile.id, {}, None)
    return profile


@router.post("/me/stats/refresh", response_model=CandidateProfileResponse)
async def refresh_stats(
    background_tasks: BackgroundTasks,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    """Re-fetches LeetCode's Problem Solving Stats on demand (cooldown-gated — LeetCode's
    API is unofficial/rate-sensitive). GitHub's Development Stats refresh by reconnecting
    GitHub (`/github/oauth-url`) since no GitHub access token is persisted server-side."""
    profile = await _get_or_create_profile(db, user)
    now = datetime.now(timezone.utc)
    if profile.stats_refreshed_at is not None:
        refreshed_at = profile.stats_refreshed_at
        if refreshed_at.tzinfo is None:
            refreshed_at = refreshed_at.replace(tzinfo=timezone.utc)
        retry_at = refreshed_at + _STATS_REFRESH_COOLDOWN
        if now < retry_at:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"error": "refresh_on_cooldown", "retry_at": retry_at.isoformat()},
            )

    leetcode_updated = False
    if profile.leetcode_username:
        try:
            stats = await fetch_leetcode_stats(profile.leetcode_username)
            profile.leetcode_stats = asdict(stats)
            leetcode_updated = True
        except LeetcodeUnavailable:
            logger.warning("LeetCode stats refresh failed for %s", profile.leetcode_username, exc_info=True)

    profile.stats_refreshed_at = now
    if leetcode_updated:
        profile.ingestion_status = "processing"
    await db.commit()
    await db.refresh(profile)
    if leetcode_updated:
        background_tasks.add_task(_run_ingestion_background, profile.id, {}, None)
    return profile


def _to_score_response(score: TalentScore) -> TalentScoreResponse:
    return TalentScoreResponse(
        overall=score.overall,
        # Derived from the canonical name tuple rather than hand-listed. The literal
        # dict here named only seven of the nine axes, silently dropping
        # `open_source_contributions` and `hackathon_performance` - both stored columns,
        # both weighted into `overall`, and both already labelled on the client. The
        # response therefore reported nine expected signals while returning seven
        # dimensions, so a candidate could never see two of the axes their own score
        # was built from.
        sub_scores={
            name: SubScore(value=getattr(score, name)) for name in SUB_SCORE_NAMES
        },
        renormalized_subscores=score.renormalized_subscores or [],
        confidence=EvidenceConfidence(
            # Pre-v2 rows have no confidence columns — treat as fully unknown (0/7)
            # rather than fabricating a number for historical scores.
            available_signals=score.confidence_available_signals or 0,
            expected_signals=score.confidence_expected_signals or len(SUB_SCORE_NAMES),
            confidence=score.confidence if score.confidence is not None else 0.0,
        ),
        score_version=score.score_version,
        computed_at=score.computed_at,
    )


@router.get("/me/score", response_model=TalentScoreResponse | None)
async def get_my_latest_score(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_or_create_profile(db, user)
    result = await db.execute(
        select(TalentScore)
        .where(TalentScore.candidate_id == profile.id)
        .order_by(TalentScore.computed_at.desc())
        .limit(1)
    )
    score = result.scalar_one_or_none()
    return _to_score_response(score) if score else None


@router.get("/me/score/history", response_model=list[TalentScoreResponse])
async def get_my_score_history(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> list[TalentScoreResponse]:
    profile = await _get_or_create_profile(db, user)
    result = await db.execute(
        select(TalentScore).where(TalentScore.candidate_id == profile.id).order_by(TalentScore.computed_at)
    )
    return [_to_score_response(s) for s in result.scalars().all()]


async def _compute_github_summary(db: AsyncSession, profile: CandidateProfile) -> GithubSummary:
    """Shared by `/me/dashboard`, `/me/github-summary`, and the public portfolio route
    (services/api/modules/public/router.py has its own copy scoped to published-only
    projects) — kept as one function here so the two never drift on aggregation logic."""
    # Totals are aggregated in SQL over *all* snapshots, while only the top repos are
    # materialized as rows. Loading every snapshot to sum five columns in Python meant a
    # prolific candidate's dashboard transferred hundreds of rows to produce five
    # integers, and then serialized every one of them into the response as well.
    totals_row = (
        await db.execute(
            select(
                func.coalesce(func.sum(GithubSnapshot.stars), 0),
                func.coalesce(func.sum(GithubSnapshot.commit_count), 0),
                func.coalesce(func.sum(GithubSnapshot.pr_count), 0),
                func.coalesce(func.sum(GithubSnapshot.issue_count), 0),
                func.coalesce(func.sum(GithubSnapshot.forks), 0),
            ).where(GithubSnapshot.candidate_id == profile.id)
        )
    ).one()

    # Bounded: nobody reads past the first few dozen repos on a profile, and the payload
    # is what the dashboard blocks on. Ordered by stars with a NULL-safe fallback so the
    # cut keeps the most substantial work rather than an arbitrary slice.
    project_result = await db.execute(
        select(GithubSnapshot)
        .where(
            GithubSnapshot.candidate_id == profile.id,
            GithubSnapshot.is_fork.is_not(True),
        )
        .order_by(func.coalesce(GithubSnapshot.stars, 0).desc(), GithubSnapshot.pushed_at.desc())
        .limit(_MAX_DASHBOARD_PROJECTS)
    )
    github_stats = profile.github_stats or {}
    return GithubSummary(
        total_stars=totals_row[0],
        total_commits=totals_row[1],
        total_prs=totals_row[2],
        total_issues=totals_row[3],
        total_forks=totals_row[4],
        owned_repo_count=github_stats.get("owned_repo_count", 0),
        external_contributions=github_stats.get("external_contributions", 0),
        pr_review_count=github_stats.get("pr_review_count", 0),
        projects=[
            PublicPortfolioProject(
                repo_full_name=s.repo_full_name,
                stars=s.stars,
                forks=s.forks,
                languages=s.languages,
                topics=s.topics,
                pushed_at=s.pushed_at,
                description=s.description,
                commit_count=s.commit_count,
                pr_count=s.pr_count,
                issue_count=s.issue_count,
            )
            for s in project_result.scalars().all()
        ],
    )


@router.get("/me/badges", response_model=list[BadgeResponse])
async def get_my_badges(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> list[BadgeResponse]:
    profile = await _get_or_create_profile(db, user)
    result = await db.execute(select(Badge).where(Badge.candidate_id == profile.id))
    return [BadgeResponse.model_validate(b) for b in result.scalars().all()]


@router.get("/me/github-summary", response_model=GithubSummary)
async def get_my_github_summary(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> GithubSummary:
    """Split out from `/me/dashboard` (services/api decisions log, 2026-07-30 dashboard-
    resilience pass) so the frontend can fetch Development Stats independently of Talent
    Score — one section failing to load must not blank the whole candidate dashboard."""
    profile = await _get_or_create_profile(db, user)
    return await _compute_github_summary(db, profile)


@router.get("/me/dashboard", response_model=DashboardResponse)
async def get_my_dashboard(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    profile = await _get_or_create_profile(db, user)

    # Newest-first with a LIMIT, then reversed for display. Selecting the whole history
    # ascending just to take `scores[-1]` as the latest meant the payload grew without
    # bound as a candidate was rescored — every ingestion appends a row.
    score_result = await db.execute(
        select(TalentScore)
        .where(TalentScore.candidate_id == profile.id)
        .order_by(TalentScore.computed_at.desc())
        .limit(_MAX_SCORE_HISTORY)
    )
    recent_scores = list(score_result.scalars().all())
    latest_score = _to_score_response(recent_scores[0]) if recent_scores else None
    scores = [_to_score_response(s) for s in reversed(recent_scores)]

    badge_result = await db.execute(select(Badge).where(Badge.candidate_id == profile.id))
    badges = [BadgeResponse.model_validate(b) for b in badge_result.scalars().all()]

    github_summary = await _compute_github_summary(db, profile)

    return DashboardResponse(
        profile=CandidateProfileResponse.model_validate(profile),
        latest_score=latest_score,
        score_history=scores,
        badges=badges,
        github_summary=github_summary,
    )


def _to_document_response(
    doc: GeneratedDocument, file_url: str | None = None
) -> GeneratedDocumentResponse:
    return GeneratedDocumentResponse(
        id=doc.id,
        document_type=doc.document_type,
        target_job_description=doc.target_job_description,
        content=doc.content,
        file_url=file_url,
        fact_check_status=doc.fact_check_status,
        fact_check_findings=doc.fact_check_findings,
        model_used=doc.model_used,
        generated_at=doc.generated_at,
    )


async def _run_document_generation(
    db: AsyncSession,
    profile: CandidateProfile,
    document_type: str,
    target_job_description: str | None,
) -> GeneratedDocument:
    merged_profile_snapshot = {
        "headline": profile.headline,
        "location": profile.location,
        "skills": profile.skills or [],
        "experience": profile.experience or [],
        "education": profile.education or [],
        "github_username": profile.github_username,
    }
    initial_state: DocumentBuilderState = {
        "candidate_id": str(profile.id),
        "document_type": document_type,
        "merged_profile": merged_profile_snapshot,
        "target_job_description": target_job_description,
        "generated_content": None,
        "generation_error": None,
        "fact_check_status": None,
        "fact_check_findings": None,
        "attempts": 0,
    }

    with start_agent_trace(
        "candidate_intelligence.document_generation",
        input_data={"document_type": document_type, "has_target_job": bool(target_job_description)},
        user_id=str(profile.user_id),
        tags=["candidate-intelligence", "document-generation"],
    ) as trace:
        result_state = await get_resume_graph().ainvoke(initial_state)
        trace.update(output={"fact_check_status": result_state.get("fact_check_status")})
    settings = get_settings()

    if result_state.get("generation_error"):
        raise DocumentGenerationUnavailable(result_state["generation_error"])

    doc_row = GeneratedDocument(
        candidate_id=profile.id,
        document_type=document_type,
        target_job_description=target_job_description,
        content=result_state["generated_content"],
        fact_check_status=result_state["fact_check_status"],
        fact_check_findings=result_state["fact_check_findings"],
        attempts=result_state["attempts"],
        model_used=settings.llm_model_judgment,
    )
    db.add(doc_row)

    fact_check_input = {"document_type": document_type, "target_job_description": target_job_description}
    fact_check_output = {
        "fact_check_status": result_state["fact_check_status"],
        "findings": result_state["fact_check_findings"],
    }
    db.add(
        AgentRun(
            agent_name="fact_check_agent",
            subject_type="candidate",
            subject_id=profile.id,
            input_ref=fact_check_input,
            output=fact_check_output,
            model_used=settings.llm_model_fast,
            langfuse_trace_id=trace.trace_id,
        )
    )
    await db.commit()
    await db.refresh(doc_row)

    if doc_row.fact_check_status != "passed":
        raise FactCheckFailed(doc_row)
    return doc_row


@router.post("/me/resume/generate", response_model=GeneratedDocumentResponse)
async def generate_resume(
    body: ResumeGenerateRequest,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> GeneratedDocumentResponse:
    profile = await _get_or_create_profile(db, user)
    try:
        doc_row = await _run_document_generation(db, profile, "resume", body.target_job_description)
    except DocumentGenerationUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except FactCheckFailed as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "fact_check_failed", "findings": exc.document.fact_check_findings},
        ) from exc

    try:
        # WeasyPrint is CPU-heavy native rendering — keep it off the event loop.
        pdf_bytes = await asyncio.to_thread(render_resume_pdf, doc_row.content)
    except PdfGenerationUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    try:
        # cloudinary.uploader.upload is a blocking network call — keep it off the event loop.
        public_url, storage_key = await asyncio.to_thread(
            upload_file,
            pdf_bytes,
            public_id=f"resumes/{profile.id}/{doc_row.id}",
            resource_type="raw",
        )
    except StorageUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    file_row = File(owner_user_id=user.id, storage_key=storage_key, public_url=public_url, file_type="resume")
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)

    doc_row.file_id = file_row.id
    await db.commit()
    await db.refresh(doc_row)

    return _to_document_response(doc_row, file_url=public_url)


@router.post("/me/cover-letter/generate", response_model=GeneratedDocumentResponse)
async def generate_cover_letter(
    body: CoverLetterGenerateRequest,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> GeneratedDocumentResponse:
    profile = await _get_or_create_profile(db, user)
    try:
        doc_row = await _run_document_generation(
            db, profile, "cover_letter", body.target_job_description
        )
    except DocumentGenerationUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except FactCheckFailed as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "fact_check_failed", "findings": exc.document.fact_check_findings},
        ) from exc
    return _to_document_response(doc_row)


@router.get("/me/documents", response_model=list[GeneratedDocumentResponse])
async def list_my_documents(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> list[GeneratedDocumentResponse]:
    profile = await _get_or_create_profile(db, user)
    result = await db.execute(
        select(GeneratedDocument)
        .where(GeneratedDocument.candidate_id == profile.id)
        .order_by(GeneratedDocument.generated_at.desc())
    )
    docs = result.scalars().all()

    file_ids = [d.file_id for d in docs if d.file_id]
    file_urls: dict = {}
    if file_ids:
        file_result = await db.execute(select(File).where(File.id.in_(file_ids)))
        file_urls = {f.id: f.public_url for f in file_result.scalars().all()}

    return [_to_document_response(d, file_url=file_urls.get(d.file_id)) for d in docs]


@router.post("/me/portfolio/publish", response_model=CandidateProfileResponse)
async def publish_portfolio(
    body: PortfolioPublishRequest,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    profile = await _get_or_create_profile(db, user)

    # If a new username was supplied, validate and set it.
    # If not supplied (just toggling publish), the existing profile.username is reused.
    if body.username is not None:
        username = body.username.strip().lower()
        if not _USERNAME_PATTERN.match(username) or username in _RESERVED_USERNAMES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_username")
        existing = await db.execute(
            select(CandidateProfile).where(
                CandidateProfile.username == username, CandidateProfile.id != profile.id
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username_taken")
        profile.username = username
    elif not profile.username:
        # Can't publish without a username — candidate must set one first.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username_required: set a username before publishing your portfolio",
        )

    profile.portfolio_published = True
    await db.commit()
    await db.refresh(profile)
    return profile


@router.post("/me/portfolio/unpublish", response_model=CandidateProfileResponse)
async def unpublish_portfolio(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    profile = await _get_or_create_profile(db, user)
    profile.portfolio_published = False
    await db.commit()
    await db.refresh(profile)
    return profile


def _years_experience_proxy(profile: CandidateProfile) -> float:
    return float(sum((e.get("years") or 0) for e in (profile.experience or [])))


def _to_career_guidance_response(row: CareerRecommendation) -> CareerGuidanceResponse:
    return CareerGuidanceResponse(
        target_role=row.target_role,
        skill_gaps=row.skill_gaps or [],
        recommended_courses=row.recommended_courses or [],
        roadmap=row.roadmap or {"stages": []},
        salary_estimate_low=row.salary_estimate_low,
        salary_estimate_high=row.salary_estimate_high,
        salary_rationale=row.salary_rationale,
        generated_at=row.generated_at,
    )


@router.get("/me/career-guidance", response_model=CareerGuidanceResponse)
async def get_my_career_guidance(
    target_role: str | None = None,
    refresh: bool = False,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> CareerGuidanceResponse:
    if target_role and target_role not in ROLE_SKILL_TAXONOMY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown_target_role. Known roles: {sorted(ROLE_SKILL_TAXONOMY)}",
        )

    profile = await _get_or_create_profile(db, user)

    if not refresh:
        cached_result = await db.execute(
            select(CareerRecommendation)
            .where(
                CareerRecommendation.candidate_id == profile.id,
                CareerRecommendation.target_role == target_role,
            )
            .order_by(CareerRecommendation.generated_at.desc())
            .limit(1)
        )
        cached = cached_result.scalar_one_or_none()
        if cached is not None and (datetime.now(timezone.utc) - cached.generated_at) < _CAREER_RECOMMENDATION_TTL:
            return _to_career_guidance_response(cached)

    score_result = await db.execute(
        select(TalentScore)
        .where(TalentScore.candidate_id == profile.id)
        .order_by(TalentScore.computed_at.desc())
        .limit(1)
    )
    latest_score = score_result.scalar_one_or_none()

    catalog_result = await db.execute(select(CourseCatalogEntry))
    catalog = [
        {
            "id": str(c.id),
            "provider": c.provider,
            "title": c.title,
            "url": c.url,
            "skill_tags": c.skill_tags,
            "level": c.level,
            "estimated_hours": c.estimated_hours,
            "is_free": c.is_free,
        }
        for c in catalog_result.scalars().all()
    ]

    candidate_skills = [s.get("name") for s in (profile.skills or []) if s.get("name")]

    initial_state: CareerGuidanceState = {
        "candidate_id": str(profile.id),
        "candidate_skills": candidate_skills,
        "location": profile.location,
        "years_experience_proxy": _years_experience_proxy(profile),
        "talent_score": latest_score.overall if latest_score else None,
        "target_role": target_role,
        "course_catalog": catalog,
        "resolved_target_role": None,
        "skill_gaps": [],
        "covered_skills": [],
        "recommended_courses": [],
        "roadmap": None,
        "salary_estimate_low": None,
        "salary_estimate_high": None,
        "salary_rationale": None,
    }

    with start_agent_trace(
        "candidate_intelligence.career_guidance",
        input_data={"target_role": target_role, "candidate_skills": candidate_skills},
        user_id=str(profile.user_id),
        tags=["candidate-intelligence", "career-guidance"],
    ) as trace:
        try:
            result_state = await without_db_connection(
                db, lambda: get_career_guidance_graph().ainvoke(initial_state)
            )
        except (CareerGuidanceUnavailable, RoadmapGenerationUnavailable) as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        trace.update(output={"resolved_target_role": result_state.get("resolved_target_role")})

    row = CareerRecommendation(
        candidate_id=profile.id,
        target_role=result_state.get("resolved_target_role") or target_role,
        skill_gaps=result_state.get("skill_gaps", []),
        recommended_courses=result_state.get("recommended_courses", []),
        roadmap=result_state.get("roadmap") or {"stages": []},
        salary_estimate_low=result_state.get("salary_estimate_low"),
        salary_estimate_high=result_state.get("salary_estimate_high"),
        salary_rationale=result_state.get("salary_rationale"),
    )
    db.add(row)

    settings = get_settings()
    career_guidance_input = {"target_role": target_role, "candidate_skills": candidate_skills}
    career_guidance_output = {
        "resolved_target_role": row.target_role,
        "skill_gaps": row.skill_gaps,
        "recommended_courses": row.recommended_courses,
        "roadmap": row.roadmap,
        "salary_estimate_low": row.salary_estimate_low,
        "salary_estimate_high": row.salary_estimate_high,
    }
    db.add(
        AgentRun(
            agent_name="career_guidance_agent",
            subject_type="candidate",
            subject_id=profile.id,
            input_ref=career_guidance_input,
            output=career_guidance_output,
            model_used=settings.llm_model_judgment,
            langfuse_trace_id=trace.trace_id,
        )
    )

    await db.commit()
    await db.refresh(row)
    return _to_career_guidance_response(row)
