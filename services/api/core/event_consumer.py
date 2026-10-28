"""Cross-module event consumer — the `events` table's only consumer-side implementation
so far (`packages/db/models/event.py`; Module 05's `finalize_rankings` endpoint in
`services/api/routers/hackathons.py` is the only publisher, per
`.agents/decisions.md`'s 2026-07-30 Phase 2 entry).

Two responsibilities, deliberately separated:

1. `process_pending_events` — bookkeeping. Marks unprocessed `hackathon.rankings.finalized`
   rows as handled (`processed_at`). This is idempotent-safe housekeeping, not the source
   of truth for what a recruiter's feed shows.
2. `get_matching_top_performers_for_recruiter` — the actual matching logic, computed LIVE
   from `hackathon_rankings` + `hackathon_team_members` + `candidate_profiles` +
   `recruiter_watchlists` at read time, not from a persisted match table. Chosen over
   persisting matches for the same reason Module 05's own `top-performers-feed` endpoint
   already reads rankings live: a recruiter's watchlist can be created *after* an event
   was published (or edited afterward), so a match computed only at event-processing time
   would go stale or miss it. Computing live off tables that already exist means a
   recruiter always sees a feed consistent with their *current* watchlist criteria and
   *all* finalized rankings, not just ones processed after their watchlist existed. This
   also avoids a new table per the assignment's explicit preference ("prefer computing
   live... unless there's a clear reason not to" — there isn't one here).

No task queue (Celery/Arq) — this repo doesn't use one for anything yet. A simple polling
loop is enough for a hackathon-scoped demo; see `run_polling_loop` and its
`.agents/decisions.md` entry for why a fixed-interval `asyncio` loop was chosen over
Celery/Arq/webhooks.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import (
    CandidateProfile,
    Event,
    Hackathon,
    HackathonRanking,
    HackathonTeam,
    HackathonTeamMember,
    RecruiterWatchlist,
)
from services.api.core.db import async_session
from services.api.core.config import get_settings

logger = logging.getLogger("event_consumer")

_HACKATHON_RANKINGS_FINALIZED = "hackathon.rankings.finalized"

DEFAULT_POLL_INTERVAL_SECONDS = get_settings().event_poll_interval_seconds


async def process_pending_events(db: AsyncSession) -> dict:
    """Marks all unprocessed `hackathon.rankings.finalized` events as handled. Does not
    itself compute or persist any matches (see module docstring) — the actual matching a
    recruiter sees is always computed live by `get_matching_top_performers_for_recruiter`
    off the underlying tables, which are unaffected by whether an event row has been
    "processed" or not. Processing an event here is purely a durability/observability
    record ("this event has been seen by the consumer at least once"), matching the
    `events` table's own `processed_at` column contract.
    """
    # Served by the partial index `idx_events_unprocessed_type` (migration
    # w8x9y0z1a2b3): without it this ran a sequential scan of the whole `events` table
    # every 30 seconds, forever, and the cost grew with total event history even though
    # the result set is almost always empty. `FOR UPDATE SKIP LOCKED` makes the claim
    # safe if a second consumer is ever added — each row is handed to exactly one worker
    # instead of both processing it.
    result = await db.execute(
        select(Event)
        .where(Event.event_type == _HACKATHON_RANKINGS_FINALIZED, Event.processed_at.is_(None))
        .with_for_update(skip_locked=True)
    )
    pending = list(result.scalars().all())

    processed_ids: list[str] = []
    for event in pending:
        payload = event.payload or {}
        candidate_ids = payload.get("candidate_ids") or []
        top_teams = payload.get("top_teams") or []
        logger.info(
            "event_consumer: processing %s event_id=%s hackathon_id=%s top_teams=%d candidate_ids=%d",
            _HACKATHON_RANKINGS_FINALIZED,
            event.id,
            payload.get("hackathon_id"),
            len(top_teams),
            len(candidate_ids),
        )
        event.processed_at = datetime.now(timezone.utc)
        processed_ids.append(str(event.id))

    if pending:
        await db.commit()

    return {"processed_count": len(pending), "event_ids": processed_ids}


def _watchlist_matches(
    criteria: dict,
    *,
    team_track: str | None,
    rank: int,
    candidate_skill_names: set[str],
) -> tuple[bool, list[str]]:
    """A watchlist matches a (team, candidate) pair if every criterion it actually
    specifies is satisfied — unspecified criteria (None/empty) are treated as "no
    constraint", not "must be empty". Returns (matched, reasons) so the feed can show why."""
    reasons: list[str] = []

    track = criteria.get("track")
    if track:
        if not team_track or team_track.lower() != track.lower():
            return False, []
        reasons.append(f"track '{track}'")

    min_rank = criteria.get("min_rank")
    if min_rank is not None:
        if rank > min_rank:
            return False, []
        reasons.append(f"rank <= {min_rank}")

    skills = criteria.get("skills") or []
    if skills:
        wanted = {s.strip().lower() for s in skills if s and s.strip()}
        matched_skills = wanted & candidate_skill_names
        if not matched_skills:
            return False, []
        reasons.append(f"skills {sorted(matched_skills)}")

    # A watchlist with zero criteria (track/min_rank/skills all empty) matches everything
    # — an intentionally permissive "notify me about all top performers" watchlist.
    return True, reasons


async def get_matching_top_performers_for_recruiter(db: AsyncSession, recruiter_id: uuid.UUID) -> list[dict]:
    """Live-computed feed: every finalized ranking, tagged with whether it matches ANY of
    this recruiter's `recruiter_watchlists`, and why. Recruiters with zero watchlists see
    every top-3 finisher unfiltered (`matched_watchlist=False`, `match_reasons=[]` for all
    — same "not empty before Phase 2" behavior Module 05's own endpoint already had),
    since there is nothing yet to filter against.
    """
    watchlists_result = await db.execute(select(RecruiterWatchlist).where(RecruiterWatchlist.recruiter_id == recruiter_id))
    watchlists = list(watchlists_result.scalars().all())

    rankings_result = await db.execute(
        select(HackathonRanking, HackathonTeam, Hackathon)
        .join(HackathonTeam, HackathonRanking.team_id == HackathonTeam.id)
        .join(Hackathon, HackathonRanking.hackathon_id == Hackathon.id)
        .where(HackathonRanking.rank <= 3)
        .order_by(HackathonRanking.finalized_at.desc())
    )
    rows = rankings_result.all()

    team_ids = [team.id for _, team, _ in rows]
    members_result = await db.execute(select(HackathonTeamMember).where(HackathonTeamMember.team_id.in_(team_ids)))
    members_by_team: dict[uuid.UUID, list[HackathonTeamMember]] = {}
    for m in members_result.scalars().all():
        members_by_team.setdefault(m.team_id, []).append(m)

    candidate_ids = [m.candidate_id for members in members_by_team.values() for m in members if m.candidate_id]
    profiles_result = await db.execute(select(CandidateProfile).where(CandidateProfile.id.in_(candidate_ids)))
    profiles_by_id = {p.id: p for p in profiles_result.scalars().all()}

    entries: list[dict] = []
    for ranking, team, hackathon in rows:
        team_members = members_by_team.get(team.id, [])
        registered = [m for m in team_members if m.candidate_id is not None] or [None]
        for member in registered:
            profile = profiles_by_id.get(member.candidate_id) if member else None
            candidate_skill_names = (
                {s.get("name", "").strip().lower() for s in (profile.skills or []) if s.get("name")}
                if profile
                else set()
            )

            matched = False
            reasons: list[str] = []
            for wl in watchlists:
                is_match, wl_reasons = _watchlist_matches(
                    wl.criteria or {},
                    team_track=team.track,
                    rank=ranking.rank,
                    candidate_skill_names=candidate_skill_names,
                )
                if is_match:
                    matched = True
                    reasons.extend(r for r in wl_reasons if r not in reasons)

            entries.append(
                {
                    "hackathon_id": hackathon.id,
                    "hackathon_name": hackathon.name,
                    "team_id": team.id,
                    "team_name": team.team_name,
                    "rank": ranking.rank,
                    "composite_score": ranking.composite_score,
                    "candidate_id": profile.id if profile else None,
                    "candidate_headline": profile.headline if profile else None,
                    "candidate_github_username": profile.github_username if profile else None,
                    "matched_watchlist": matched,
                    "match_reasons": reasons,
                }
            )

    # Recruiters with active watchlists see matches surfaced first (still showing the rest
    # of the unfiltered feed below, same "never empty" behavior as before).
    if watchlists:
        entries.sort(key=lambda e: (not e["matched_watchlist"], e["rank"]))

    return entries


async def run_polling_loop(interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS) -> None:
    """Fixed-interval `asyncio` polling loop — started as a background task from
    `services/api/main.py`'s startup hook. Not Celery/Arq: this repo has no task-queue
    dependency anywhere yet, and a hackathon-scoped demo doesn't need one for a single
    lightweight polling job (see `.agents/decisions.md`'s 2026-07-30 entry). Each cycle
    opens its own short-lived `AsyncSession` (never holds one across `sleep`), and a
    failure in one cycle is logged and swallowed rather than killing the loop — the same
    "never let one bad row take down the whole process" spirit as
    `hackathons.py`'s CSV row-error handling.
    """
    while True:
        try:
            async with async_session() as db:
                summary = await process_pending_events(db)
                if summary["processed_count"]:
                    logger.info("event_consumer: processed %d event(s)", summary["processed_count"])
        except Exception:
            logger.exception("event_consumer: polling cycle failed")
        await asyncio.sleep(interval_seconds)
