# Hackathon-to-Hiring Pipeline

## What it does

Transforms hackathon performance into hiring signals. Ranks teams, surfaces top performers to recruiters, and creates a "top talent watchlist" that recruiters can follow.

## How ranking works

```
Team Submission (repo + pitch deck)
    ↓
    ├─→ Judge Score (human input, 0-100)
    │   - Normalized to 0-100 scale
    │   - Weight: 0.40 (configurable via Hackathon.scoring_config)
    │
    ├─→ Pitch Score (from PPT analyzer)
    │   - 0-100 from rubric analysis
    │   - Weight: 0.30
    │
    ├─→ Repo Quality Score (AST analysis + LLM review)
    │   - Code complexity, test coverage, maintainability
    │   - Weight: 0.20
    │
    └─→ Novelty Score (Qdrant cross-event comparison)
        - "How different is this from last year's top 10?"
        - Penalizes cookie-cutter solutions
        - Weight: 0.10

Final Composite Score = weighted_renormalized_mean(
    [0.40 * judge_score, 0.30 * pitch, 0.20 * repo, 0.10 * novelty]
)
(Missing components dropped, weights renormalized)
```

**Key Fix**: Weights now configurable per hackathon via `Hackathon.scoring_config` (was hardcoded 0.25/0.25/0.25/0.25).

## How recruiters get connected to top performers

```
Event-Driven Architecture (NOT persisted matches)
    ↓
    ├─→ Event: "hackathon.rankings.finalized"
    │   - Triggered when organizer finalizes rankings
    │   - Stores hackathon_id + top_team_ids
    │
    ├─→ Event Consumer Loop (background poll, ~5sec interval)
    │   - Queries events table for new events
    │   - For each event, queries recruiters' watchlists
    │
    ├─→ Live Matching (computed at poll time, NOT pre-computed)
    │   For each (recruiter, watchlist):
    │     - Get watchlist criteria (skills, level, location)
    │     - Get top team members (from rankings)
    │     - Check: do members match criteria?
    │     - If yes → send notification
    │
    └─→ Why live, not persistent?
        - Recruiter creates watchlist AFTER event published
        - If we'd pre-computed matches at event time → miss this recruiter
        - Live re-compute from underlying tables catches latecomers
```

**Key Code**:
- Event consumer: `services/api/core/event_consumer.py::get_matching_top_performers_for_recruiter()`
- Watchlist creation: `POST /recruiters/me/watchlists` (creates WatchlistCriteria)
- Top performers feed: `GET /hackathons/{id}/top-performers` (returns ranked candidates)

## Key design decisions

1. **Composite score formula is rules, not LLM**:
   - Judge score is already LLM-adjacent (human judgment)
   - Code quality is measurable (complexity, tests)
   - Combining with weights is transparent + fast
   - Avoids double-LLMing (judge already judged)

2. **Novelty detection via Qdrant embedding corpus**:
   - Embeds all prior hackathon solution descriptions
   - New solution embed → check cosine distance to corpus
   - Far from corpus = novel; close = cookie-cutter
   - Cold-start: first hackathon has no history (no penalty)

3. **Recruiter matches computed live, not pre-computed**:
   - Pre-computed at event time: misses recruiters who added watchlist later
   - Live re-compute: slightly slower (50ms query per recruiter) but correct
   - Tradeoff: speed vs. correctness; correctness wins

4. **Events table + polling, not real-time WebSocket**:
   - Simpler: don't need WebSocket infrastructure
   - Reliable: if consumer crashes, resumes from last processed event
   - Latency: ~5 sec poll interval (acceptable for recruiting)

## Limitations

- Ranking weights are now configurable but require organizer to set them (defaults used if not)
- Novelty score requires historical hackathon data (cold-start problem: first event has no history)
- Recruiter matching is 1-way (hackathon team doesn't know they matched a watchlist)
- Event polling is ~5sec latency (not real-time)

## Where this lives

| Component | File |
|---|---|
| Ranking formula | `services/agents/hackathon/tools/ranking.py` |
| Ranking aggregation node | `services/agents/hackathon/nodes/ranking_aggregation.py` |
| Novelty scoring | `services/agents/hackathon/nodes/cross_event_novelty.py` |
| Event consumer | `services/api/core/event_consumer.py` |
| Ranking finalize API | `services/api/modules/hackathons/router.py:POST /rankings/finalize` |
| Top performers API | `services/api/modules/hackathons/router.py:GET /top-performers` |
| Watchlist API | `services/api/modules/hackathons/router.py:POST /watchlists` |
| Frontend: Rankings | `apps/web/src/app/(organizer)/hackathons/[id]/rankings/page.tsx` |
| Frontend: Top performers | `apps/web/src/app/(recruiter)/top-performers/page.tsx` |
| DB: HackathonRanking | `packages/db/models/hackathon.py` |
| DB: RecruiterWatchlist | `packages/db/models/hackathon.py` |
