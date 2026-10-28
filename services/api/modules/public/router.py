"""
Public Portfolio Controller.
Handles Public Candidate Portfolio SSR Requests.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import Badge, CandidateProfile, GithubSnapshot, TalentScore
from packages.shared_schemas.candidates import (
    BadgeResponse,
    GithubSummary,
    PublicPortfolioProject,
    PublicPortfolioResponse,
)
from services.api.core.db import get_db

router = APIRouter(prefix="/public", tags=["Public Portfolios"])


@router.get("/candidates/{username}", response_model=PublicPortfolioResponse)
async def get_public_portfolio(
    username: str,
    db: AsyncSession = Depends(get_db),
) -> PublicPortfolioResponse:
    result = await db.execute(
        select(CandidateProfile).where(
            CandidateProfile.username == username.strip().lower(),
            CandidateProfile.portfolio_published.is_(True),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="portfolio_not_found")

    snapshot_result = await db.execute(select(GithubSnapshot).where(GithubSnapshot.candidate_id == profile.id))
    snapshots = snapshot_result.scalars().all()
    github_stats = profile.github_stats or {}
    non_fork_projects = [
        PublicPortfolioProject(
            repo_full_name=p.repo_full_name,
            stars=p.stars,
            forks=p.forks,
            languages=p.languages,
            topics=p.topics,
            pushed_at=p.pushed_at,
            description=p.description,
            commit_count=p.commit_count,
            pr_count=p.pr_count,
            issue_count=p.issue_count,
        )
        for p in sorted(snapshots, key=lambda s: s.stars or 0, reverse=True)
        if not p.is_fork
    ]
    github_summary = GithubSummary(
        total_stars=sum(s.stars or 0 for s in snapshots),
        total_commits=sum(s.commit_count or 0 for s in snapshots),
        total_prs=sum(s.pr_count or 0 for s in snapshots),
        total_issues=sum(s.issue_count or 0 for s in snapshots),
        total_forks=sum(s.forks or 0 for s in snapshots),
        owned_repo_count=github_stats.get("owned_repo_count", 0),
        external_contributions=github_stats.get("external_contributions", 0),
        pr_review_count=github_stats.get("pr_review_count", 0),
        projects=non_fork_projects[:12],
    )

    badges_result = await db.execute(select(Badge).where(Badge.candidate_id == profile.id))
    badges = [BadgeResponse.model_validate(b) for b in badges_result.scalars().all()]

    score_result = await db.execute(
        select(TalentScore)
        .where(TalentScore.candidate_id == profile.id)
        .order_by(TalentScore.computed_at.desc())
        .limit(1)
    )
    latest_score = score_result.scalar_one_or_none()

    return PublicPortfolioResponse(
        username=profile.username,
        headline=profile.headline,
        location=profile.location,
        skills=profile.skills,
        experience=profile.experience,
        education=profile.education,
        projects=non_fork_projects[:12],
        badges=badges,
        overall_score=latest_score.overall if latest_score else None,
        github_username=profile.github_username,
        leetcode_username=profile.leetcode_username,
        github_stats=profile.github_stats,
        github_summary=github_summary,
        leetcode_stats=profile.leetcode_stats,
        stats_refreshed_at=profile.stats_refreshed_at,
        updated_at=profile.updated_at,
    )
