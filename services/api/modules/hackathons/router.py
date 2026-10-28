"""
Hackathon Controller.
Handles Hackathon Creation, Team Ingestion (CSV, Webhook, Direct), Submissions, Judging Queue, Finalize Rankings, and Top Performers Feed.
"""
import logging
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import (
    AgentRun,
    Assessment,
    CandidateProfile,
    Event,
    Hackathon,
    HackathonRanking,
    HackathonSubmission,
    HackathonTeam,
    HackathonTeamMember,
    PlagiarismMatch,
    PresentationScore,
    RecruiterWatchlist,
    Submission,
    User,
)
from packages.shared_schemas.hackathon import (
    CSVImportRequest,
    CSVImportResponse,
    CSVImportRowError,
    FinalizeRankingsRequest,
    FinalizeRankingsResponse,
    HackathonCreateRequest,
    HackathonResponse,
    JudgeQueueEntry,
    JudgeScoreRequest,
    RankingResponse,
    SubmissionResponse,
    TeamDetailResponse,
    TeamMemberResponse,
    TeamResponse,
    TeamSubmissionInput,
    TopPerformerEntry,
    TopPerformersFeedResponse,
    WatchlistCreateRequest,
    WatchlistResponse,
)
from services.agents.hackathon.graph import get_hackathon_ranking_graph
from services.agents.hackathon.state import HackathonRankingState
from services.agents.hackathon.tools.normalization import NormalizationUnavailable, normalize_webhook_payload
from services.api.core.config import get_settings
from services.api.common.constants import truncate_error
from services.api.core.db import async_session, get_db
from services.api.core.event_consumer import get_matching_top_performers_for_recruiter
from services.api.core.rbac import require_role
from services.api.core.tracing import start_agent_trace

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Hackathons & Top Performers"])


async def _get_hackathon_or_404(db: AsyncSession, hackathon_id: uuid.UUID) -> Hackathon:
    result = await db.execute(select(Hackathon).where(Hackathon.id == hackathon_id))
    hackathon = result.scalar_one_or_none()
    if hackathon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="hackathon_not_found")
    return hackathon


async def _upsert_team(db: AsyncSession, hackathon_id: uuid.UUID, team_input: TeamSubmissionInput) -> tuple[HackathonTeam, int]:
    existing = await db.execute(
        select(HackathonTeam).where(
            HackathonTeam.hackathon_id == hackathon_id,
            HackathonTeam.team_name == team_input.team_name,
        )
    )
    team = existing.scalar_one_or_none()
    if team is None:
        team = HackathonTeam(hackathon_id=hackathon_id, team_name=team_input.team_name, track=team_input.track)
        db.add(team)
        await db.flush()
    else:
        team.track = team_input.track or team.track

    existing_members = await db.execute(
        select(HackathonTeamMember).where(HackathonTeamMember.team_id == team.id)
    )
    for m in existing_members.scalars().all():
        await db.delete(m)
    await db.flush()

    # Resolve every member's GitHub username to a candidate id in one IN-query instead of
    # one SELECT per member. This helper runs once per team during a roster import, so the
    # per-member query made import cost O(teams x members) round trips.
    usernames = [m.github_username for m in team_input.members if m.github_username]
    profile_ids_by_username: dict[str, uuid.UUID] = {}
    if usernames:
        profile_rows = await db.execute(
            select(CandidateProfile.github_username, CandidateProfile.id).where(
                CandidateProfile.github_username.in_(usernames)
            )
        )
        profile_ids_by_username = {username: pid for username, pid in profile_rows.all()}

    members_created = 0
    for member_input in team_input.members:
        candidate_id = (
            profile_ids_by_username.get(member_input.github_username)
            if member_input.github_username
            else None
        )
        db.add(
            HackathonTeamMember(
                team_id=team.id,
                candidate_id=candidate_id,
                github_username=member_input.github_username,
                display_name=member_input.display_name,
                role=member_input.role or "member",
            )
        )
        members_created += 1

    if team_input.repo_url or team_input.presentation_id or team_input.judge_score is not None:
        submission_result = await db.execute(
            select(HackathonSubmission).where(HackathonSubmission.team_id == team.id)
        )
        submission = submission_result.scalar_one_or_none()
        if submission is None:
            submission = HackathonSubmission(team_id=team.id)
            db.add(submission)
        submission.repo_url = team_input.repo_url or submission.repo_url
        submission.presentation_id = team_input.presentation_id or submission.presentation_id
        if team_input.judge_score is not None:
            submission.judge_score = team_input.judge_score

    await db.flush()
    return team, members_created


@router.post("/hackathons", response_model=HackathonResponse, status_code=status.HTTP_201_CREATED)
async def create_hackathon(
    body: HackathonCreateRequest,
    user: User = Depends(require_role("organizer")),
    db: AsyncSession = Depends(get_db),
) -> Hackathon:
    hackathon = Hackathon(
        organizer_org_id=user.organization_id,
        organizer_user_id=user.id,
        name=body.name,
        start_date=body.start_date,
        end_date=body.end_date,
        tracks=body.tracks,
        ingestion_mode=body.ingestion_mode,
    )
    db.add(hackathon)
    await db.commit()
    await db.refresh(hackathon)
    return hackathon


@router.get("/hackathons", response_model=list[HackathonResponse])
async def list_my_hackathons(
    user: User = Depends(require_role("organizer")),
    db: AsyncSession = Depends(get_db),
) -> list[Hackathon]:
    result = await db.execute(
        select(Hackathon).where(Hackathon.organizer_user_id == user.id).order_by(Hackathon.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/hackathons/open", response_model=list[HackathonResponse])
async def list_open_hackathons(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> list[Hackathon]:
    result = await db.execute(
        select(Hackathon).where(Hackathon.status.in_(["draft", "active"])).order_by(Hackathon.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/hackathons/{hackathon_id}", response_model=HackathonResponse)
async def get_hackathon(hackathon_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Hackathon:
    return await _get_hackathon_or_404(db, hackathon_id)


@router.post("/hackathons/{hackathon_id}/import/csv", response_model=CSVImportResponse, status_code=status.HTTP_201_CREATED)
async def import_csv(
    hackathon_id: uuid.UUID,
    body: CSVImportRequest,
    user: User = Depends(require_role("organizer")),
    db: AsyncSession = Depends(get_db),
) -> CSVImportResponse:
    await _get_hackathon_or_404(db, hackathon_id)

    teams_created = 0
    members_created = 0
    row_errors: list[CSVImportRowError] = []
    seen_names: set[str] = set()

    for idx, team_input in enumerate(body.teams):
        if not team_input.team_name.strip():
            row_errors.append(CSVImportRowError(row_index=idx, team_name=None, error="missing_team_name"))
            continue
        if team_input.team_name in seen_names:
            row_errors.append(
                CSVImportRowError(row_index=idx, team_name=team_input.team_name, error="duplicate_team_name_in_import")
            )
            continue
        seen_names.add(team_input.team_name)
        try:
            _, member_count = await _upsert_team(db, hackathon_id, team_input)
            teams_created += 1
            members_created += member_count
        except Exception as exc:
            row_errors.append(CSVImportRowError(row_index=idx, team_name=team_input.team_name, error=str(exc)))

    await db.commit()
    return CSVImportResponse(teams_created=teams_created, members_created=members_created, row_errors=row_errors)


@router.post("/hackathons/{hackathon_id}/webhook", status_code=status.HTTP_201_CREATED)
async def receive_webhook(
    hackathon_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    x_webhook_secret: str | None = Header(default=None),
) -> TeamResponse:
    """Registers a team from an external hackathon platform.

    Authenticated by a shared secret rather than `require_role`: the caller is another
    service, not a signed-in user. This endpoint previously had no verification at all,
    so anyone who knew (or guessed) a hackathon ID could create and overwrite teams in
    it — `_upsert_team` matches on team name, so a request could also mutate an existing
    team's members.

    A deployment that has not set the secret gets a disabled endpoint, not an open one.
    """
    settings = get_settings()
    if not settings.hackathon_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="webhook_not_configured",
        )
    # compare_digest, not `!=`: the comparison is against attacker-supplied input, and a
    # short-circuiting compare leaks the secret one byte at a time.
    if not x_webhook_secret or not secrets.compare_digest(
        x_webhook_secret, settings.hackathon_webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_webhook_secret"
        )

    await _get_hackathon_or_404(db, hackathon_id)
    try:
        team_input = await normalize_webhook_payload(body)
    except NormalizationUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    team, _ = await _upsert_team(db, hackathon_id, team_input)
    await db.commit()
    await db.refresh(team)
    return team


@router.post("/hackathons/{hackathon_id}/submissions", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def submit_direct(
    hackathon_id: uuid.UUID,
    body: TeamSubmissionInput,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> HackathonTeam:
    """Candidate-facing in-platform team submission (FR-7c).

    `_upsert_team` matches on team *name* and rebuilds the roster from the payload, so
    posting an existing team's name overwrites that team: its members are deleted and
    replaced, and its repo/deck are repointed. Unauthenticated callers already have to
    clear a shared secret for the same primitive on the webhook route; this path is
    authenticated but was not checked at all, so any candidate could take over any team
    in any hackathon by guessing its name.

    Two rules make the takeover impossible while leaving normal use unchanged:

    - A candidate may only create a team, or update one they are already a member of.
      First submission wins the name; everyone else is refused rather than silently
      overwriting.
    - `judge_score` is stripped. It exists on the shared input shape because the
      organizer CSV and platform webhook may carry a score already, but a candidate
      scoring their own submission is self-evidently not allowed. The join form omits
      the field by convention — this is what enforces it.
    """
    await _get_hackathon_or_404(db, hackathon_id)

    profile = (
        await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="candidate_profile_required"
        )

    existing = (
        await db.execute(
            select(HackathonTeam).where(
                HackathonTeam.hackathon_id == hackathon_id,
                HackathonTeam.team_name == body.team_name,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        is_member = (
            await db.execute(
                select(HackathonTeamMember.id).where(
                    HackathonTeamMember.team_id == existing.id,
                    HackathonTeamMember.candidate_id == profile.id,
                )
            )
        ).first() is not None
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="team_name_taken"
            )

    team, _ = await _upsert_team(
        db, hackathon_id, body.model_copy(update={"judge_score": None})
    )

    # The submitter is always on the roster they just posted. `_upsert_team` resolves
    # members by GitHub username, so a candidate who has not connected GitHub (or who
    # left themselves out of the member list) would otherwise create a team they are not
    # a member of — and would then be locked out of their own next submission by the
    # membership check above.
    already_listed = (
        await db.execute(
            select(HackathonTeamMember.id).where(
                HackathonTeamMember.team_id == team.id,
                HackathonTeamMember.candidate_id == profile.id,
            )
        )
    ).first() is not None
    if not already_listed:
        db.add(
            HackathonTeamMember(
                team_id=team.id,
                candidate_id=profile.id,
                github_username=profile.github_username,
                display_name=user.full_name,
                role="member",
            )
        )

    await db.commit()
    await db.refresh(team)
    return team


@router.get("/hackathons/{hackathon_id}/teams", response_model=list[TeamResponse])
async def list_teams(hackathon_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[HackathonTeam]:
    await _get_hackathon_or_404(db, hackathon_id)
    result = await db.execute(
        select(HackathonTeam).where(HackathonTeam.hackathon_id == hackathon_id).order_by(HackathonTeam.created_at)
    )
    return list(result.scalars().all())


async def _team_or_404(db: AsyncSession, hackathon_id: uuid.UUID, team_id: uuid.UUID) -> HackathonTeam:
    result = await db.execute(
        select(HackathonTeam).where(HackathonTeam.id == team_id, HackathonTeam.hackathon_id == hackathon_id)
    )
    team = result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team_not_found")
    return team


@router.get("/hackathons/{hackathon_id}/teams/{team_id}", response_model=TeamDetailResponse)
async def get_team_detail(
    hackathon_id: uuid.UUID, team_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> TeamDetailResponse:
    team = await _team_or_404(db, hackathon_id, team_id)

    members_result = await db.execute(select(HackathonTeamMember).where(HackathonTeamMember.team_id == team.id))
    members = list(members_result.scalars().all())

    submission_result = await db.execute(select(HackathonSubmission).where(HackathonSubmission.team_id == team.id))
    submission = submission_result.scalar_one_or_none()

    ranking_result = await db.execute(
        select(HackathonRanking).where(
            HackathonRanking.hackathon_id == hackathon_id, HackathonRanking.team_id == team.id
        )
    )
    ranking = ranking_result.scalar_one_or_none()

    return TeamDetailResponse(
        team=TeamResponse.model_validate(team),
        members=[TeamMemberResponse.model_validate(m) for m in members],
        submission=SubmissionResponse.model_validate(submission) if submission else None,
        ranking=RankingResponse.model_validate(ranking) if ranking else None,
    )


@router.get("/judging/queue", response_model=list[JudgeQueueEntry])
async def judging_queue(
    user: User = Depends(require_role("judge")),
    db: AsyncSession = Depends(get_db),
) -> list[JudgeQueueEntry]:
    result = await db.execute(
        select(HackathonSubmission, HackathonTeam, Hackathon)
        .join(HackathonTeam, HackathonSubmission.team_id == HackathonTeam.id)
        .join(Hackathon, HackathonTeam.hackathon_id == Hackathon.id)
        .order_by(HackathonSubmission.submitted_at.desc())
    )
    return [
        JudgeQueueEntry(
            submission_id=submission.id,
            hackathon_id=hackathon.id,
            hackathon_name=hackathon.name,
            team_id=team.id,
            team_name=team.team_name,
            repo_url=submission.repo_url,
            presentation_id=submission.presentation_id,
            judge_score=submission.judge_score,
            judge_rationale=submission.judge_rationale,
        )
        for submission, team, hackathon in result.all()
    ]


@router.post("/hackathons/{hackathon_id}/submissions/{submission_id}/judge-score", response_model=SubmissionResponse)
async def submit_judge_score(
    hackathon_id: uuid.UUID,
    submission_id: uuid.UUID,
    body: JudgeScoreRequest,
    user: User = Depends(require_role("judge")),
    db: AsyncSession = Depends(get_db),
) -> HackathonSubmission:
    result = await db.execute(
        select(HackathonSubmission)
        .join(HackathonTeam, HackathonSubmission.team_id == HackathonTeam.id)
        .where(HackathonSubmission.id == submission_id, HackathonTeam.hackathon_id == hackathon_id)
    )
    submission = result.scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission_not_found")

    submission.judge_score = body.score
    submission.judge_rationale = body.rationale
    submission.judge_user_id = user.id
    await db.commit()
    await db.refresh(submission)
    return submission


async def _resolve_repo_candidate(db: AsyncSession, member_candidate_ids: list[uuid.UUID]) -> uuid.UUID | None:
    return member_candidate_ids[0] if member_candidate_ids else None


@router.post("/hackathons/{hackathon_id}/rankings/finalize", response_model=FinalizeRankingsResponse)
async def finalize_rankings(
    hackathon_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    body: FinalizeRankingsRequest | None = None,
    user: User = Depends(require_role("organizer")),
    db: AsyncSession = Depends(get_db),
) -> FinalizeRankingsResponse:
    """Kicks off finalization in the background and returns the currently-persisted
    rankings immediately.

    The pipeline (per-team repo verification against GitHub, cross-event novelty search,
    composite scoring) previously ran inline here, holding the organizer's request open
    for the entire run and scaling linearly with team count — the "Finalizing…" button
    just sat there. Clients poll `GET /hackathons/{id}/rankings/status` and re-fetch
    `GET /hackathons/{id}/rankings` once it leaves "processing". Same pattern as job
    matching (`Job.matching_status`) and presentation upload.
    """
    hackathon = await _get_hackathon_or_404(db, hackathon_id)
    if hackathon.organizer_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_hackathon")

    teams_result = await db.execute(select(HackathonTeam).where(HackathonTeam.hackathon_id == hackathon_id))
    teams = list(teams_result.scalars().all())
    if not teams:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no_teams_to_rank")

    if hackathon.ranking_status == "processing":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ranking_already_in_progress")

    hackathon.ranking_status = "processing"
    hackathon.ranking_error = None
    await db.commit()

    background_tasks.add_task(
        _run_finalization_background,
        hackathon_id,
        user.id,
    )

    existing = await db.execute(
        select(HackathonRanking).where(HackathonRanking.hackathon_id == hackathon_id)
    )
    team_names = {str(t.id): t.team_name for t in teams}
    return FinalizeRankingsResponse(
        hackathon_id=hackathon_id,
        ranking_status="processing",
        rankings=[
            RankingResponse(
                id=r.id,
                hackathon_id=r.hackathon_id,
                team_id=r.team_id,
                team_name=team_names.get(str(r.team_id)),
                rank=r.rank,
                composite_score=r.composite_score,
                score_breakdown=r.score_breakdown,
                finalized_at=r.finalized_at,
            )
            for r in sorted(existing.scalars().all(), key=lambda r: r.rank)
        ],
    )


@router.get("/hackathons/{hackathon_id}/rankings/status")
async def get_ranking_status(
    hackathon_id: uuid.UUID,
    user: User = Depends(require_role("organizer")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    hackathon = await _get_hackathon_or_404(db, hackathon_id)
    if hackathon.organizer_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_hackathon")
    return {"status": hackathon.ranking_status, "error": hackathon.ranking_error}


async def _build_team_states(db: AsyncSession, teams: list[HackathonTeam]) -> list[dict]:
    """Gathers the per-team ranking inputs in a fixed number of queries.

    Previously issued up to four queries *per team* (submission, members, repo-analysis
    submission, pitch score + plagiarism matches), so a 60-team event cost ~240 sequential
    round-trips before the graph even started.
    """
    team_ids = [t.id for t in teams]

    submissions_result = await db.execute(
        select(HackathonSubmission).where(HackathonSubmission.team_id.in_(team_ids))
    )
    submission_by_team = {s.team_id: s for s in submissions_result.scalars().all()}

    members_result = await db.execute(
        select(HackathonTeamMember).where(HackathonTeamMember.team_id.in_(team_ids))
    )
    members_by_team: dict[uuid.UUID, list[HackathonTeamMember]] = defaultdict(list)
    for m in members_result.scalars().all():
        members_by_team[m.team_id].append(m)

    analysis_ids = [
        s.repo_analysis_submission_id
        for s in submission_by_team.values()
        if s.repo_analysis_submission_id is not None
    ]
    repo_score_by_submission_id: dict[uuid.UUID, float | None] = {}
    if analysis_ids:
        analysis_result = await db.execute(select(Submission).where(Submission.id.in_(analysis_ids)))
        repo_score_by_submission_id = {row.id: row.score for row in analysis_result.scalars().all()}

    presentation_ids = [
        s.presentation_id for s in submission_by_team.values() if s.presentation_id is not None
    ]
    pitch_score_by_presentation: dict[uuid.UUID, float | None] = {}
    plagiarism_by_presentation: dict[uuid.UUID, list[float]] = defaultdict(list)
    if presentation_ids:
        # Ordered newest-first so the first row seen per presentation is the latest score
        # — same "setdefault wins" idiom as recruitment/router.py's latest-talent-score.
        scores_result = await db.execute(
            select(PresentationScore)
            .where(PresentationScore.presentation_id.in_(presentation_ids))
            .order_by(PresentationScore.presentation_id, PresentationScore.computed_at.desc())
        )
        for row in scores_result.scalars().all():
            pitch_score_by_presentation.setdefault(row.presentation_id, row.overall_pitch_score)

        matches_result = await db.execute(
            select(PlagiarismMatch.presentation_id, PlagiarismMatch.similarity).where(
                PlagiarismMatch.presentation_id.in_(presentation_ids)
            )
        )
        for presentation_id, similarity in matches_result.all():
            plagiarism_by_presentation[presentation_id].append(similarity)

    team_states: list[dict] = []
    for team in teams:
        submission = submission_by_team.get(team.id)
        member_candidate_ids = [
            str(m.candidate_id) for m in members_by_team.get(team.id, []) if m.candidate_id is not None
        ]

        repo_score = None
        if submission and submission.repo_analysis_submission_id:
            repo_score = repo_score_by_submission_id.get(submission.repo_analysis_submission_id)

        pitch_score = None
        plagiarism_similarities: list[float] = []
        if submission and submission.presentation_id:
            pitch_score = pitch_score_by_presentation.get(submission.presentation_id)
            plagiarism_similarities = plagiarism_by_presentation.get(submission.presentation_id, [])

        team_states.append(
            {
                "team_id": str(team.id),
                "repo_url": submission.repo_url if submission else None,
                "presentation_id": str(submission.presentation_id) if submission and submission.presentation_id else None,
                "judge_score": submission.judge_score if submission else None,
                "repo_score": repo_score,
                "pitch_score": pitch_score,
                "plagiarism_similarities": plagiarism_similarities,
                "member_candidate_ids": member_candidate_ids,
            }
        )
    return team_states


async def _run_finalization_background(hackathon_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Runs the ranking pipeline outside the request/response cycle in its own session.

    Never raises: any failure is recorded as `ranking_status="failed"` with the reason, so
    the organizer sees a real error instead of an event stuck on "processing" forever.
    """
    async with async_session() as db:
        hackathon = (
            await db.execute(select(Hackathon).where(Hackathon.id == hackathon_id))
        ).scalar_one_or_none()
        if hackathon is None:
            logger.error("hackathon %s vanished before finalization could run", hackathon_id)
            return
        try:
            await _finalize_and_persist(db, hackathon, user_id)
            hackathon.ranking_status = "done"
            hackathon.ranking_error = None
        except Exception as exc:  # noqa: BLE001 - surfaced via ranking_error
            logger.exception("ranking finalization failed for hackathon %s", hackathon_id)
            await db.rollback()
            # Re-fetch after rollback: the instance above is detached from the rolled-back
            # transaction, so mutate a live row rather than a stale one.
            hackathon = (
                await db.execute(select(Hackathon).where(Hackathon.id == hackathon_id))
            ).scalar_one_or_none()
            if hackathon is None:
                return
            hackathon.ranking_status = "failed"
            hackathon.ranking_error = truncate_error(exc)
        await db.commit()


async def _finalize_and_persist(
    db: AsyncSession, hackathon: Hackathon, user_id: uuid.UUID
) -> list[HackathonRanking]:
    hackathon_id = hackathon.id
    teams_result = await db.execute(select(HackathonTeam).where(HackathonTeam.hackathon_id == hackathon_id))
    teams = list(teams_result.scalars().all())
    if not teams:
        return []

    team_states = await _build_team_states(db, teams)

    initial_state: HackathonRankingState = {
        "hackathon_id": str(hackathon_id),
        "scoring_config": hackathon.scoring_config,  # Now configurable per hackathon, defaults to None (uses hardcoded defaults)
        "teams": team_states,
        "repo_scores": {},
        "repo_verification_results": {},
        "novelty_scores": {},
        "final_rankings": [],
        "notification_event_payload": None,
    }
    with start_agent_trace(
        "hackathon.ranking_finalize",
        input_data={"hackathon_id": str(hackathon_id), "team_count": len(teams)},
        user_id=str(user_id),
        tags=["hackathon", "ranking"],
    ) as trace:
        result_state = await get_hackathon_ranking_graph().ainvoke(initial_state)
        trace.update(output={"final_rankings": result_state["final_rankings"]})

    teams_by_id = {str(t.id): t for t in teams}
    team_state_by_id = {t["team_id"]: t for t in team_states}
    verification_results = result_state["repo_verification_results"]

    # One query for every team's submission row instead of one per verified repo.
    verified_team_ids = [teams_by_id[tid].id for tid in verification_results if tid in teams_by_id]
    submission_by_team: dict[uuid.UUID, HackathonSubmission] = {}
    if verified_team_ids:
        submission_rows = await db.execute(
            select(HackathonSubmission).where(HackathonSubmission.team_id.in_(verified_team_ids))
        )
        submission_by_team = {s.team_id: s for s in submission_rows.scalars().all()}

    for team_id_str, verification in verification_results.items():
        team = teams_by_id.get(team_id_str)
        team_state = team_state_by_id.get(team_id_str)
        if team is None or team_state is None:
            continue
        candidate_id = await _resolve_repo_candidate(db, [uuid.UUID(c) for c in team_state["member_candidate_ids"]])
        if candidate_id is None:
            continue

        assessment = Assessment(type="project_analysis", spec={})
        db.add(assessment)
        await db.flush()
        analysis_submission = Submission(
            assessment_id=assessment.id,
            candidate_id=candidate_id,
            code_or_answers={"repo_full_name": verification["repo_full_name"]},
            static_analysis=verification["static_analysis"],
            llm_review=verification["llm_review"],
            score=verification["score"],
            # Scored by the ranking pipeline itself, not the async grading path.
            grading_status="done",
        )
        db.add(analysis_submission)
        await db.flush()

        submission_row = submission_by_team.get(team.id)
        if submission_row:
            submission_row.repo_analysis_submission_id = analysis_submission.id

    # Load all pre-existing ranking rows at once — re-finalizing a 60-team event used to
    # issue one SELECT per team here.
    final_team_ids = [uuid.UUID(entry["team_id"]) for entry in result_state["final_rankings"]]
    existing_rankings: dict[uuid.UUID, HackathonRanking] = {}
    if final_team_ids:
        existing_result = await db.execute(
            select(HackathonRanking).where(
                HackathonRanking.hackathon_id == hackathon_id,
                HackathonRanking.team_id.in_(final_team_ids),
            )
        )
        existing_rankings = {r.team_id: r for r in existing_result.scalars().all()}

    rankings: list[HackathonRanking] = []
    for entry in result_state["final_rankings"]:
        team_id = uuid.UUID(entry["team_id"])
        ranking_row = existing_rankings.get(team_id)
        if ranking_row is None:
            ranking_row = HackathonRanking(hackathon_id=hackathon_id, team_id=team_id)
            db.add(ranking_row)
        ranking_row.rank = entry["rank"]
        ranking_row.composite_score = entry["composite_score"] if entry["composite_score"] is not None else 0.0
        ranking_row.score_breakdown = entry["score_breakdown"]
        ranking_row.finalized_at = datetime.now(timezone.utc)
        rankings.append(ranking_row)

    hackathon.status = "finalized"

    settings = get_settings()
    hackathon_ranking_input = {"team_count": len(teams)}
    hackathon_ranking_output = {"final_rankings": result_state["final_rankings"]}
    db.add(
        AgentRun(
            agent_name="hackathon_ranking_agent",
            subject_type="hackathon",
            subject_id=hackathon_id,
            input_ref=hackathon_ranking_input,
            output=hackathon_ranking_output,
            model_used=settings.llm_model_judgment,
            langfuse_trace_id=trace.trace_id,
        )
    )
    db.add(Event(event_type="hackathon.rankings.finalized", payload=result_state["notification_event_payload"]))

    # Committed by the caller (`_run_finalization_background`) together with the
    # ranking_status flip, so a crash between the two can't leave rankings written but
    # the event still showing "processing". No per-row refresh: expire_on_commit=False.
    await db.flush()
    return rankings


@router.get("/hackathons/{hackathon_id}/rankings", response_model=list[RankingResponse])
async def get_rankings(hackathon_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[RankingResponse]:
    await _get_hackathon_or_404(db, hackathon_id)
    result = await db.execute(
        select(HackathonRanking, HackathonTeam)
        .join(HackathonTeam, HackathonRanking.team_id == HackathonTeam.id)
        .where(HackathonRanking.hackathon_id == hackathon_id)
        .order_by(HackathonRanking.rank)
    )
    return [
        RankingResponse(
            id=ranking.id,
            hackathon_id=ranking.hackathon_id,
            team_id=ranking.team_id,
            team_name=team.team_name,
            rank=ranking.rank,
            composite_score=ranking.composite_score,
            score_breakdown=ranking.score_breakdown,
            finalized_at=ranking.finalized_at,
        )
        for ranking, team in result.all()
    ]


@router.post("/recruiters/me/watchlists", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    body: WatchlistCreateRequest,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> RecruiterWatchlist:
    watchlist = RecruiterWatchlist(
        recruiter_id=user.id,
        criteria={"track": body.track, "min_rank": body.min_rank, "skills": body.skills},
    )
    db.add(watchlist)
    await db.commit()
    await db.refresh(watchlist)
    return watchlist


@router.get("/recruiters/me/top-performers-feed", response_model=TopPerformersFeedResponse)
async def top_performers_feed(
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> TopPerformersFeedResponse:
    entries = await get_matching_top_performers_for_recruiter(db, user.id)
    return TopPerformersFeedResponse(entries=[TopPerformerEntry(**e) for e in entries])
