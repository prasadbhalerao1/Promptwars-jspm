"""
Recruitment Controller.
Handles Job Creation, Flow B Match Reranking, Recruiter Copilot, Applicant Tracking Kanban, and Hiring Analytics.
"""
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import (
    AgentRun,
    Application,
    Badge,
    CandidateProfile,
    ContributionReport,
    CopilotConversation,
    FraudFlag,
    GithubSnapshot,
    InterviewReport,
    InterviewSession,
    Job,
    LocationAlias,
    MatchScore,
    SkillTaxonomyEntry,
    Submission,
    TalentScore,
    User,
)
from packages.shared_schemas.recruitment import (
    APPLICATION_STAGES,
    ApplicationResponse,
    ApplicationStageUpdateRequest,
    ApplicationWithCandidateResponse,
    ApplicationWithJobResponse,
    CopilotQueryRequest,
    CopilotQueryResponse,
    CopilotResult,
    FunnelStage,
    HiringFunnelResponse,
    JobCreateRequest,
    JobResponse,
    MatchScoreWithCandidateResponse,
    SourceBreakdownResponse,
    TimeToHireResponse,
)
from services.agents.recruitment.copilot_graph import get_copilot_graph
from services.agents.recruitment.matching_graph import get_matching_graph
from services.agents.recruitment.state import CopilotState, MatchingState
from services.agents.recruitment.tools.embeddings import RecruitmentUnavailable
from services.api.core.config import get_settings
from services.api.common.constants import clamp_page_size, truncate_error
from services.api.core.db import async_session, get_db, without_db_connection
from services.api.core.rbac import require_role
from services.api.core.tracing import start_agent_trace

router = APIRouter(tags=["Recruitment & Copilot"])


def _estimate_experience_years(experience: list[dict] | None) -> float:
    return sum(e.get("years") or 0 for e in (experience or []))


# _build_candidate_pool does 4 unfiltered full-table scans (every TalentScore, Badge,
# GithubSnapshot, and CandidateProfile row) — expensive and was being re-run from scratch
# on every job create, every recompute, and every Copilot query in the same session. A
# short in-process TTL cache (same pattern as _oauth_state_cache in candidates/router.py)
# avoids repeating that work for back-to-back calls without adding an infra dependency;
# each entry is small (list of dicts) and self-expires, so no eviction logic is needed.
_CANDIDATE_POOL_CACHE_TTL_SECONDS = get_settings().candidate_pool_cache_ttl_seconds
_candidate_pool_cache: tuple[float, list[dict]] | None = None

# Ceiling on how many candidates one matching/Copilot run considers. The scans below are
# unfiltered by design — matching has to look at everyone, and there is no
# recruiter-visibility column to narrow by — so without a bound the pool, and the four
# result sets feeding it, grow linearly with total platform signups. Every entry is then
# held in memory (once per uvicorn worker, since the cache is process-local) and passed
# whole into the matching/Copilot graph as `candidate_pool`.
#
# Ordered by most-recently-updated profile so the cut keeps active candidates rather than
# an arbitrary slice. Well above any realistic pool for this deployment; raise it only
# alongside a real retrieval step (Qdrant already backs the semantic half of matching),
# not as a way to postpone one.
_MAX_CANDIDATE_POOL = get_settings().max_candidate_pool


async def _build_candidate_pool(db: AsyncSession, *, use_cache: bool = True) -> list[dict]:
    global _candidate_pool_cache
    if use_cache and _candidate_pool_cache is not None:
        cached_at, pool = _candidate_pool_cache
        if time.monotonic() - cached_at < _CANDIDATE_POOL_CACHE_TTL_SECONDS:
            return pool
    # Candidates with no skills recorded yet contribute no skill_similarity signal and
    # can't be meaningfully matched — excluding them narrows every scan below without
    # changing who's actually eligible for matching (no recruiter-visibility opt-in
    # field exists on this model to filter by instead).
    profiles_result = await db.execute(
        select(CandidateProfile)
        .where(CandidateProfile.skills.is_not(None))
        .order_by(CandidateProfile.updated_at.desc())
        .limit(_MAX_CANDIDATE_POOL)
    )
    profiles = profiles_result.scalars().all()
    candidate_ids = [p.id for p in profiles]

    if not candidate_ids:
        _candidate_pool_cache = (time.monotonic(), [])
        return []

    scores_result = await db.execute(
        select(TalentScore)
        .where(TalentScore.candidate_id.in_(candidate_ids))
        .order_by(TalentScore.candidate_id, TalentScore.computed_at.desc())
    )
    latest_score_by_candidate: dict[uuid.UUID, float | None] = {}
    latest_sub_scores_by_candidate: dict[uuid.UUID, dict[str, float | None]] = {}
    for s in scores_result.scalars().all():
        if s.candidate_id not in latest_score_by_candidate:
            latest_score_by_candidate[s.candidate_id] = s.overall
            latest_sub_scores_by_candidate[s.candidate_id] = {
                "coding_ability": s.coding_ability,
                "problem_solving": s.problem_solving,
                "project_quality": s.project_quality,
                "innovation": s.innovation,
                "technical_consistency": s.technical_consistency,
                "community_participation": s.community_participation,
                "leadership": s.leadership,
                "open_source_contributions": s.open_source_contributions,
                "hackathon_performance": s.hackathon_performance,
            }

    badges_result = await db.execute(select(Badge).where(Badge.candidate_id.in_(candidate_ids)))
    verified_skills_by_candidate: dict[uuid.UUID, set[str]] = defaultdict(set)
    for b in badges_result.scalars().all():
        verified_skills_by_candidate[b.candidate_id].add(b.skill_name.lower())

    snapshots_result = await db.execute(
        select(GithubSnapshot).where(GithubSnapshot.candidate_id.in_(candidate_ids))
    )
    snapshots_by_candidate: dict[uuid.UUID, list[GithubSnapshot]] = defaultdict(list)
    for gs in snapshots_result.scalars().all():
        snapshots_by_candidate[gs.candidate_id].append(gs)

    pool: list[dict] = []
    for p in profiles:
        verified = verified_skills_by_candidate.get(p.id, set())
        skills = [
            {"name": s["name"], "verified": s["name"].strip().lower() in verified}
            for s in (p.skills or [])
            if s.get("name")
        ]
        snaps = sorted(snapshots_by_candidate.get(p.id, []), key=lambda s: s.stars or 0, reverse=True)
        repo_summaries = [
            f"{s.repo_full_name}: {s.stars or 0} stars, {s.commit_count or 0} commits" for s in snaps[:5]
        ]
        pool.append(
            {
                "candidate_id": str(p.id),
                "skills": skills,
                "location": p.location,
                "experience_years": _estimate_experience_years(p.experience),
                "overall_talent_score": latest_score_by_candidate.get(p.id),
                "sub_scores": latest_sub_scores_by_candidate.get(p.id, {}),
                "github_username": p.github_username,
                "headline": p.headline,
                "hackathon_experience": False,
                "repo_summaries": repo_summaries,
            }
        )
    _candidate_pool_cache = (time.monotonic(), pool)
    return pool


def _visible_jobs_clause(user: User):
    """SQL predicate for "jobs this recruiter may see" — the list form of `_job_owned_by`.

    `_job_owned_by` grants access on org membership *or* direct authorship, but the three
    list/aggregate call sites each rebuilt the rule inline and two of them filtered on
    `posted_by_user_id` alone. A recruiter in an organization therefore saw an org-mate's
    job in `GET /jobs` (which did branch on org) while `GET /applications` returned no
    applicants for it and the analytics endpoints silently excluded it from the funnel,
    time-to-hire and source breakdown — the same job visible or invisible depending on
    which endpoint asked. Fetching it by id worked, because that path went through
    `_job_owned_by`.

    One definition, used everywhere, so the single-row check and the list query cannot
    drift apart again.
    """
    if user.organization_id:
        return Job.organization_id == user.organization_id
    return Job.posted_by_user_id == user.id


async def _job_owned_by(db: AsyncSession, job_id: uuid.UUID, user: User) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    if user.organization_id and job.organization_id == user.organization_id:
        return job
    if job.posted_by_user_id == user.id:
        return job
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_job_posting")


async def _run_matching_and_persist(
    db: AsyncSession, job: Job, *, use_pool_cache: bool = True
) -> list[MatchScore]:
    candidate_pool = await _build_candidate_pool(db, use_cache=use_pool_cache)

    # An empty pool means "nobody to match against", and that is the honest answer. This
    # used to substitute `_get_demo_candidate_pool()` — 171 lines of invented candidates
    # ("demo-alice-chen", fabricated Talent Scores and GitHub stars) that a recruiter
    # would have seen as real ranked matches. It could not even work: persistence below
    # does `uuid.UUID(r["candidate_id"])`, and `uuid.UUID("demo-alice-chen")` raises
    # ValueError, so an empty database turned every match run into an opaque 500 rather
    # than an empty list.
    if not candidate_pool:
        return []

    initial_state: MatchingState = {
        "job_id": str(job.id),
        "job_description": job.description,
        "job_required_skills": job.required_skills or [],
        "job_min_experience_years": job.min_experience_years,
        "job_location": job.location,
        "job_is_remote": job.is_remote,
        "candidate_pool": candidate_pool,
        "job_embedding": None,
        "core_match_scores": {},
        "project_relevance_scores": {},
        "match_results": [],
    }
    with start_agent_trace(
        "recruitment.matching",
        input_data={"job_id": str(job.id), "candidate_pool_size": len(candidate_pool)},
        user_id=str(job.posted_by_user_id) if job.posted_by_user_id else None,
        tags=["recruitment", "matching"],
    ) as trace:
        result_state = await get_matching_graph().ainvoke(initial_state)
        trace.update(output={"match_count": len(result_state["match_results"])})

    settings = get_settings()

    # Load every pre-existing MatchScore for this job in one query instead of a SELECT
    # per matched candidate — with a large pool that was hundreds of sequential
    # round-trips tacked on after the graph had already finished computing.
    result_candidate_ids = [uuid.UUID(r["candidate_id"]) for r in result_state["match_results"]]
    existing_rows = await db.execute(
        select(MatchScore).where(
            MatchScore.job_id == job.id, MatchScore.candidate_id.in_(result_candidate_ids)
        )
    ) if result_candidate_ids else None
    row_by_candidate: dict[uuid.UUID, MatchScore] = (
        {row.candidate_id: row for row in existing_rows.scalars().all()} if existing_rows else {}
    )

    rows: list[MatchScore] = []
    for r in result_state["match_results"]:
        candidate_id = uuid.UUID(r["candidate_id"])
        row = row_by_candidate.get(candidate_id)
        if row is None:
            row = MatchScore(job_id=job.id, candidate_id=candidate_id)
            db.add(row)
        row.match_percentage = r["match_percentage"]
        row.skill_similarity = r["skill_similarity"]
        row.semantic_similarity = r["semantic_similarity"]
        row.experience_match = r["experience_match"]
        row.talent_score_alignment = r["talent_score_alignment"]
        row.project_relevance = r["project_relevance"]
        row.explanation = r["explanation"]
        row.computed_at = datetime.now(timezone.utc)
        rows.append(row)

    score_aggregation_input = {"candidate_count": len(candidate_pool), "required_skills": job.required_skills}
    score_aggregation_output = {"match_count": len(result_state["match_results"])}
    db.add(
        AgentRun(
            agent_name="score_aggregation_agent",
            subject_type="job",
            subject_id=job.id,
            input_ref=score_aggregation_input,
            output=score_aggregation_output,
            model_used=settings.embedding_model,
            langfuse_trace_id=trace.trace_id,
        )
    )
    await db.commit()
    # No per-row refresh(): the sessionmaker sets expire_on_commit=False, so these
    # instances keep their attribute values after commit. Refreshing was one extra
    # round-trip per matched candidate for data no caller reads back.
    return rows


async def _run_matching_background(job_id: uuid.UUID, use_pool_cache: bool = True) -> None:
    """Runs `_run_matching_and_persist` outside the request/response cycle, in its own DB
    session. Matching does a full candidate-pool build plus per-candidate embedding/Qdrant
    work — synchronously awaiting it in `POST /jobs` and `?recompute=true` blocked the
    recruiter's request for however long that took and scaled linearly with candidate
    count. `matching_status` lets the frontend poll for completion; `GET /jobs/{id}/matches`
    remains the read path once it's done.

    `use_pool_cache` is positional (not keyword-only) so this same function works both as
    an arq task target and as the in-process `BackgroundTasks` fallback, which forward
    arguments positionally — see `services/api/core/queue.py::enqueue`."""
    async with async_session() as bg_db:
        result = await bg_db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            return
        try:
            await _run_matching_and_persist(bg_db, job, use_pool_cache=use_pool_cache)
            job.matching_status = "done"
            job.matching_error = None
        except RecruitmentUnavailable as exc:
            job.matching_status = "failed"
            job.matching_error = truncate_error(exc)
        except Exception as exc:  # noqa: BLE001 - surfaced via matching_error, never crashes the worker
            job.matching_status = "failed"
            job.matching_error = truncate_error(exc)
        await bg_db.commit()


router_stage_values = set(APPLICATION_STAGES)
_FRAUD_STATUS_SEVERITY = {"upheld": 3, "under_review": 2, "raised": 1}


async def _fraud_flag_status_by_candidate(
    db: AsyncSession, candidate_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not candidate_ids:
        return {}
    result = await db.execute(
        select(FraudFlag.candidate_id, FraudFlag.status).where(
            FraudFlag.candidate_id.in_(candidate_ids),
            FraudFlag.status.in_(("raised", "under_review", "upheld")),
        )
    )
    status_by_candidate: dict[uuid.UUID, str] = {}
    for cid, flag_status in result.all():
        current = status_by_candidate.get(cid)
        if current is None or _FRAUD_STATUS_SEVERITY[flag_status] > _FRAUD_STATUS_SEVERITY[current]:
            status_by_candidate[cid] = flag_status
    return status_by_candidate


async def _latest_report_refs_by_candidate(
    db: AsyncSession, candidate_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict]:
    if not candidate_ids:
        return {}
    refs: dict[uuid.UUID, dict] = {cid: {} for cid in candidate_ids}

    submissions_result = await db.execute(
        select(Submission.candidate_id, Submission.id, Submission.submitted_at)
        .where(Submission.candidate_id.in_(candidate_ids))
        .order_by(Submission.candidate_id, Submission.submitted_at.desc())
    )
    for cid, submission_id, _ in submissions_result.all():
        refs.setdefault(cid, {}).setdefault("latest_submission_id", submission_id)

    interview_result = await db.execute(
        select(InterviewSession.candidate_id, InterviewReport.session_id, InterviewReport.generated_at)
        .join(InterviewReport, InterviewReport.session_id == InterviewSession.id)
        .where(InterviewSession.candidate_id.in_(candidate_ids))
        .order_by(InterviewSession.candidate_id, InterviewReport.generated_at.desc())
    )
    for cid, session_id, _ in interview_result.all():
        refs.setdefault(cid, {}).setdefault("latest_interview_session_id", session_id)

    contribution_result = await db.execute(
        select(ContributionReport.candidate_id, ContributionReport.repo_full_name, ContributionReport.generated_at)
        .where(ContributionReport.candidate_id.in_(candidate_ids))
        .order_by(ContributionReport.candidate_id, ContributionReport.generated_at.desc())
    )
    for cid, repo_full_name, _ in contribution_result.all():
        refs.setdefault(cid, {}).setdefault("latest_contribution_repo_full_name", repo_full_name)

    return refs


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: JobCreateRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> Job:
    job = Job(
        organization_id=user.organization_id,
        posted_by_user_id=user.id,
        title=body.title,
        description=body.description,
        required_skills=body.required_skills,
        min_experience_years=body.min_experience_years,
        location=body.location,
        is_remote=body.is_remote,
        matching_status="processing",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(
        _run_matching_background,
        job.id,
        True,
    )
    return job


@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> list[Job]:
    result = await db.execute(
        select(Job).where(_visible_jobs_clause(user)).order_by(Job.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/jobs/open", response_model=list[JobResponse])
async def list_open_jobs(
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> list[Job]:
    """Open jobs, newest first.

    Paginated: this returned every Job row across every organization on a page any
    candidate can open, so the payload grew with total platform history. Same
    shared `clamp_page_size` helper as `get_audit_log`, so a client cannot ask
    for an unbounded page by passing a huge limit.
    """
    capped_limit = clamp_page_size(limit)
    result = await db.execute(
        select(Job).order_by(Job.created_at.desc()).limit(capped_limit).offset(max(0, offset))
    )
    return list(result.scalars().all())


@router.get("/jobs/{job_id}/matching-status")
async def get_matching_status(
    job_id: uuid.UUID,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    job = await _job_owned_by(db, job_id, user)
    return {"status": job.matching_status, "error": job.matching_error}


@router.get("/jobs/{job_id}/matches", response_model=list[MatchScoreWithCandidateResponse])
async def get_job_matches(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    recompute: bool = Query(
        False,
        description="Kick off Flow B in the background instead of reading persisted rows only. "
        "Returns the currently-persisted rows immediately; poll GET /jobs/{id}/matching-status "
        "and re-fetch once it's no longer 'processing'.",
    ),
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    job = await _job_owned_by(db, job_id, user)

    if recompute:
        job.matching_status = "processing"
        job.matching_error = None
        await db.commit()
        background_tasks.add_task(
            _run_matching_background,
            job.id,
            False,
        )

    result = await db.execute(
        select(MatchScore).where(MatchScore.job_id == job.id).order_by(MatchScore.match_percentage.desc())
    )
    scores = result.scalars().all()
    if not scores:
        return []

    profiles_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.id.in_([s.candidate_id for s in scores]))
    )
    profiles_by_id = {p.id: p for p in profiles_result.scalars().all()}

    talent_scores_result = await db.execute(
        select(TalentScore)
        .where(TalentScore.candidate_id.in_([s.candidate_id for s in scores]))
        .order_by(TalentScore.candidate_id, TalentScore.computed_at.desc())
    )
    latest_talent_score: dict[uuid.UUID, float | None] = {}
    for row in talent_scores_result.scalars().all():
        latest_talent_score.setdefault(row.candidate_id, row.overall)

    fraud_status_by_candidate = await _fraud_flag_status_by_candidate(db, [s.candidate_id for s in scores])

    return [
        {
            "id": s.id,
            "job_id": s.job_id,
            "candidate_id": s.candidate_id,
            "match_percentage": s.match_percentage,
            "skill_similarity": s.skill_similarity,
            "semantic_similarity": s.semantic_similarity,
            "experience_match": s.experience_match,
            "talent_score_alignment": s.talent_score_alignment,
            "project_relevance": s.project_relevance,
            "explanation": s.explanation,
            "computed_at": s.computed_at,
            "candidate_headline": profiles_by_id[s.candidate_id].headline if s.candidate_id in profiles_by_id else None,
            "candidate_location": profiles_by_id[s.candidate_id].location if s.candidate_id in profiles_by_id else None,
            "candidate_github_username": profiles_by_id[s.candidate_id].github_username
            if s.candidate_id in profiles_by_id
            else None,
            "candidate_overall_talent_score": latest_talent_score.get(s.candidate_id),
            "fraud_flag_status": fraud_status_by_candidate.get(s.candidate_id),
        }
        for s in scores
    ]


@router.post("/jobs/{job_id}/apply", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def apply_to_job(
    job_id: uuid.UUID,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> Application:
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    if job_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")

    profile_result = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        await db.flush()

    application = Application(job_id=job_id, candidate_id=profile.id, stage="sourced", source="direct")
    db.add(application)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_applied") from exc
    await db.refresh(application)
    return application


@router.get("/candidates/me/applications", response_model=list[ApplicationWithJobResponse])
async def get_my_applications(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    profile_result = await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        return []

    result = await db.execute(
        select(Application, Job)
        .join(Job, Application.job_id == Job.id)
        .where(Application.candidate_id == profile.id)
        .order_by(Application.applied_at.desc())
    )
    return [
        {
            "id": app.id,
            "job_id": app.job_id,
            "candidate_id": app.candidate_id,
            "stage": app.stage,
            "source": app.source,
            "applied_at": app.applied_at,
            "stage_updated_at": app.stage_updated_at,
            "job_title": job.title,
            "job_location": job.location,
        }
        for app, job in result.all()
    ]


@router.get("/applications", response_model=list[ApplicationWithCandidateResponse])
async def list_applications(
    job_id: uuid.UUID | None = None,
    stage: str | None = None,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    query = select(Application, CandidateProfile).join(
        CandidateProfile, Application.candidate_id == CandidateProfile.id
    )
    if job_id is not None:
        await _job_owned_by(db, job_id, user)
        query = query.where(Application.job_id == job_id)
    else:
        my_jobs = await db.execute(select(Job.id).where(_visible_jobs_clause(user)))
        query = query.where(Application.job_id.in_([row[0] for row in my_jobs.all()]))
    if stage is not None:
        if stage not in router_stage_values:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_stage")
        query = query.where(Application.stage == stage)

    result = await db.execute(query.order_by(Application.stage_updated_at.desc()))
    rows = result.all()
    candidate_ids = [profile.id for _, profile in rows]

    latest_score_by_candidate: dict[uuid.UUID, float | None] = {}
    if candidate_ids:
        scores_result = await db.execute(
            select(TalentScore)
            .where(TalentScore.candidate_id.in_(candidate_ids))
            .order_by(TalentScore.candidate_id, TalentScore.computed_at.desc())
        )
        for s in scores_result.scalars().all():
            latest_score_by_candidate.setdefault(s.candidate_id, s.overall)

    fraud_status_by_candidate = await _fraud_flag_status_by_candidate(db, candidate_ids)
    report_refs_by_candidate = await _latest_report_refs_by_candidate(db, candidate_ids)

    return [
        {
            "id": app.id,
            "job_id": app.job_id,
            "candidate_id": app.candidate_id,
            "stage": app.stage,
            "source": app.source,
            "applied_at": app.applied_at,
            "stage_updated_at": app.stage_updated_at,
            "candidate_headline": profile.headline,
            "candidate_github_username": profile.github_username,
            "candidate_overall_talent_score": latest_score_by_candidate.get(profile.id),
            "fraud_flag_status": fraud_status_by_candidate.get(profile.id),
            **report_refs_by_candidate.get(profile.id, {}),
        }
        for app, profile in rows
    ]


@router.patch("/applications/{application_id}/stage", response_model=ApplicationResponse)
async def update_application_stage(
    application_id: uuid.UUID,
    body: ApplicationStageUpdateRequest,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> Application:
    if body.stage not in router_stage_values:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_stage")

    result = await db.execute(select(Application).where(Application.id == application_id))
    application = result.scalar_one_or_none()
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application_not_found")
    await _job_owned_by(db, application.job_id, user)

    application.stage = body.stage
    application.stage_updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(application)
    return application


@router.post("/copilot/query", response_model=CopilotQueryResponse)
async def copilot_query(
    body: CopilotQueryRequest,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> CopilotQueryResponse:
    if body.conversation_id is not None:
        result = await db.execute(
            select(CopilotConversation).where(
                CopilotConversation.id == body.conversation_id, CopilotConversation.recruiter_id == user.id
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation_not_found")
    else:
        conversation = CopilotConversation(recruiter_id=user.id, messages=[], structured_filters=None)
        db.add(conversation)
        # Commit rather than flush: the copilot graph below runs with this session's
        # connection released, which would roll back a merely-flushed row and lose the
        # conversation the response then refers to by id.
        await db.commit()

    taxonomy_result = await db.execute(select(SkillTaxonomyEntry))
    skill_synonyms = {row.canonical_name: row.synonyms or [] for row in taxonomy_result.scalars().all()}
    alias_result = await db.execute(select(LocationAlias))
    location_aliases = {row.canonical_name: row.aliases or [] for row in alias_result.scalars().all()}

    # No demo substitution here either: with an empty pool the graph simply produces an
    # empty shortlist, and "no candidates match" is the truthful answer to give a
    # recruiter. Inventing plausible-looking people is worse than returning nothing.
    candidate_pool = await _build_candidate_pool(db)

    initial_state: CopilotState = {
        "recruiter_id": str(user.id),
        "conversation_id": str(conversation.id),
        "raw_query": body.message,
        "prior_filters": conversation.structured_filters,
        "candidate_pool": candidate_pool,
        "skill_synonyms": skill_synonyms,
        "location_aliases": location_aliases,
        "structured_filters": {},
        "shortlist": [],
        "ranked_candidate_ids": [],
        "explanations": {},
    }
    with start_agent_trace(
        "recruitment.copilot_query",
        input_data={"message": body.message},
        user_id=str(user.id),
        session_id=str(conversation.id),
        tags=["recruitment", "copilot"],
    ) as trace:
        try:
            # The candidate pool is already materialized in `initial_state`, so the graph
            # (query understanding, embeddings, Qdrant, reranking, explanations) needs no
            # database at all while it runs.
            result_state = await without_db_connection(
                db, lambda: get_copilot_graph().ainvoke(initial_state)
            )
        except RecruitmentUnavailable as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        trace.update(output={"ranked_candidate_ids": result_state["ranked_candidate_ids"]})

    shortlist_by_id = {c["candidate_id"]: c for c in result_state["shortlist"]}
    results = [
        CopilotResult(
            candidate_id=cid,
            match_percentage=shortlist_by_id.get(cid, {}).get("_retrieval_score"),
            explanation=result_state["explanations"].get(cid, "Matched the recruiter's structured filters."),
        )
        for cid in result_state["ranked_candidate_ids"]
    ]

    settings = get_settings()
    # Re-attach: `conversation` was loaded before the graph call released the connection.
    conversation = await db.merge(conversation)
    conversation.messages = [
        *(conversation.messages or []),
        {"role": "recruiter", "content": body.message},
        {
            "role": "copilot",
            "content": f"{len(results)} candidate(s) found.",
            "candidate_ids": [r.candidate_id for r in results],
        },
    ]
    conversation.structured_filters = result_state["structured_filters"]
    copilot_input = {"raw_query": body.message, "structured_filters": result_state["structured_filters"]}
    copilot_output = {"result_count": len(results), "ranked_candidate_ids": result_state["ranked_candidate_ids"]}
    db.add(
        AgentRun(
            agent_name="recruiter_copilot",
            subject_type="copilot_conversation",
            subject_id=conversation.id,
            input_ref=copilot_input,
            output=copilot_output,
            model_used=settings.llm_model_judgment,
            langfuse_trace_id=trace.trace_id,
        )
    )
    await db.commit()

    return CopilotQueryResponse(
        conversation_id=conversation.id,
        results=results,
        structured_filters_used=result_state["structured_filters"],
    )


async def _recruiter_job_ids(db: AsyncSession, user: User, job_id: uuid.UUID | None) -> list[uuid.UUID]:
    if job_id is not None:
        await _job_owned_by(db, job_id, user)
        return [job_id]
    result = await db.execute(select(Job.id).where(_visible_jobs_clause(user)))
    return [row[0] for row in result.all()]


@router.get("/analytics/hiring-funnel", response_model=HiringFunnelResponse)
async def hiring_funnel(
    job_id: uuid.UUID | None = None,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> HiringFunnelResponse:
    job_ids = await _recruiter_job_ids(db, user, job_id)
    # Counted in SQL, not in Python. This used to pull every application row for the
    # recruiter's jobs across the wire purely to increment a defaultdict — so the payload
    # grew with pipeline size while the answer stayed a handful of integers.
    # `idx_applications_job_stage` covers (job_id, stage), so this is served index-only.
    result = await db.execute(
        select(Application.stage, func.count())
        .where(Application.job_id.in_(job_ids))
        .group_by(Application.stage)
    )
    counts: dict[str, int] = {stage: count for stage, count in result.all()}

    stages = []
    previous_count: int | None = None
    for stage_name in APPLICATION_STAGES:
        count = counts.get(stage_name, 0)
        conversion = (count / previous_count) if previous_count else None
        stages.append(FunnelStage(stage=stage_name, count=count, conversion_rate_from_previous=conversion))
        previous_count = count if count else previous_count
    return HiringFunnelResponse(job_id=job_id, stages=stages)


@router.get("/analytics/time-to-hire", response_model=TimeToHireResponse)
async def time_to_hire(
    job_id: uuid.UUID | None = None,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> TimeToHireResponse:
    job_ids = await _recruiter_job_ids(db, user, job_id)
    result = await db.execute(
        select(Application.applied_at, Application.stage_updated_at)
        .where(Application.job_id.in_(job_ids))
        .where(Application.stage == "hired")
    )
    days: list[float] = []
    for applied_at, stage_updated_at in result.all():
        days.append((stage_updated_at - applied_at).total_seconds() / 86400)

    buckets = {"0-7d": 0, "8-14d": 0, "15-30d": 0, "31d+": 0}
    for d in days:
        if d <= 7:
            buckets["0-7d"] += 1
        elif d <= 14:
            buckets["8-14d"] += 1
        elif d <= 30:
            buckets["15-30d"] += 1
        else:
            buckets["31d+"] += 1

    median = None
    if days:
        sorted_days = sorted(days)
        mid = len(sorted_days) // 2
        median = sorted_days[mid] if len(sorted_days) % 2 else (sorted_days[mid - 1] + sorted_days[mid]) / 2

    return TimeToHireResponse(job_id=job_id, distribution=buckets, median_days=median)


@router.get("/analytics/source-breakdown", response_model=SourceBreakdownResponse)
async def source_breakdown(
    job_id: uuid.UUID | None = None,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> SourceBreakdownResponse:
    job_ids = await _recruiter_job_ids(db, user, job_id)
    # Aggregated in SQL for the same reason as the funnel above. NULL source means
    # "direct", so it is coalesced server-side rather than after transferring every row.
    result = await db.execute(
        select(func.coalesce(Application.source, "direct"), func.count())
        .where(Application.job_id.in_(job_ids))
        .group_by(func.coalesce(Application.source, "direct"))
    )
    counts: dict[str, int] = {source: count for source, count in result.all()}

    return SourceBreakdownResponse(
        job_id=job_id,
        direct=counts.get("direct", 0),
        copilot_search=counts.get("copilot_search", 0),
        hackathon=counts.get("hackathon", 0),
    )
