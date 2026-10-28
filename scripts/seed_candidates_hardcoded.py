#!/usr/bin/env python3
"""
Seed database with rich, realistic candidate data.
Run this to populate the database with actual candidates.

Usage:
    python scripts/seed_candidates_hardcoded.py
"""

import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

import sys
from pathlib import Path

# Repo root on sys.path so `packages`/`services` import when this is run directly as
# `python scripts/seed_candidates_hardcoded.py` from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# This script prints check marks/bullets; the Windows console defaults to cp1252, which
# can't encode them and would crash the run *after* the rows were already committed.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from packages.db.models.base import Base
from packages.db.models.user import User
from packages.db.models.candidate import CandidateProfile, TalentScore
from services.api.core.security import hash_password
from services.api.core.config import get_settings
from services.agents.candidate_intelligence.tools.aggregate import SUB_SCORE_WEIGHTS


CANDIDATES = [
    {
        "name": "Alice Chen",
        "email": "alice@example.com",
        "username": "alice_chen",
        "github": "alice-chen-dev",
        "headline": "Senior Full-Stack Engineer with AI expertise",
        "location": "San Francisco, CA",
        "skills": [
            {"name": "Python", "source": "github", "confidence": 0.95},
            {"name": "TypeScript", "source": "github", "confidence": 0.92},
            {"name": "React", "source": "github", "confidence": 0.90},
            {"name": "FastAPI", "source": "github", "confidence": 0.88},
            {"name": "PostgreSQL", "source": "github", "confidence": 0.87},
            {"name": "Docker", "source": "verified", "confidence": 0.85},
            {"name": "Redis", "source": "github", "confidence": 0.80},
        ],
        "experience_years": 6.5,
        "overall_score": 82.0,
        "sub_scores": {
            "coding_ability": 88,
            "problem_solving": 85,
            "project_quality": 87,
            "innovation": 84,
            "technical_consistency": 89,
            "community_participation": 78,
            "leadership": 76,
            "open_source_contributions": 72,
            "hackathon_performance": 81,
        },
    },
    {
        "name": "Bob Wilson",
        "email": "bob@example.com",
        "username": "bob_wilson",
        "github": "bob-wilson-dev",
        "headline": "Backend Systems Engineer focused on scalability",
        "location": "New York, NY",
        "skills": [
            {"name": "Python", "source": "github", "confidence": 0.96},
            {"name": "Go", "source": "github", "confidence": 0.91},
            {"name": "PostgreSQL", "source": "verified", "confidence": 0.94},
            {"name": "Redis", "source": "github", "confidence": 0.89},
            {"name": "Kubernetes", "source": "github", "confidence": 0.87},
            {"name": "gRPC", "source": "github", "confidence": 0.84},
            {"name": "Microservices", "source": "github", "confidence": 0.86},
        ],
        "experience_years": 7.2,
        "overall_score": 85.0,
        "sub_scores": {
            "coding_ability": 90,
            "problem_solving": 88,
            "project_quality": 84,
            "innovation": 79,
            "technical_consistency": 92,
            "community_participation": 81,
            "leadership": 82,
            "open_source_contributions": 75,
            "hackathon_performance": 77,
        },
    },
    {
        "name": "Charlie Davis",
        "email": "charlie@example.com",
        "username": "charlie_davis",
        "github": "charlie-davis-dev",
        "headline": "Frontend Specialist with design sensibility",
        "location": "Austin, TX",
        "skills": [
            {"name": "TypeScript", "source": "github", "confidence": 0.94},
            {"name": "React", "source": "verified", "confidence": 0.96},
            {"name": "Vue.js", "source": "github", "confidence": 0.89},
            {"name": "CSS", "source": "github", "confidence": 0.92},
            {"name": "Next.js", "source": "github", "confidence": 0.90},
            {"name": "Tailwind", "source": "github", "confidence": 0.93},
            {"name": "GraphQL", "source": "github", "confidence": 0.86},
        ],
        "experience_years": 5.1,
        "overall_score": 79.0,
        "sub_scores": {
            "coding_ability": 82,
            "problem_solving": 78,
            "project_quality": 85,
            "innovation": 88,
            "technical_consistency": 80,
            "community_participation": 74,
            "leadership": 68,
            "open_source_contributions": 70,
            "hackathon_performance": 83,
        },
    },
    {
        "name": "Diana Patel",
        "email": "diana@example.com",
        "username": "diana_patel",
        "github": "diana-patel-dev",
        "headline": "ML Engineer and data specialist",
        "location": "San Francisco, CA",
        "skills": [
            {"name": "Python", "source": "verified", "confidence": 0.98},
            {"name": "PyTorch", "source": "github", "confidence": 0.92},
            {"name": "TensorFlow", "source": "github", "confidence": 0.90},
            {"name": "SQL", "source": "verified", "confidence": 0.93},
            {"name": "Pandas", "source": "github", "confidence": 0.91},
            {"name": "Scikit-learn", "source": "github", "confidence": 0.89},
            {"name": "FastAPI", "source": "github", "confidence": 0.85},
        ],
        "experience_years": 4.8,
        "overall_score": 84.0,
        "sub_scores": {
            "coding_ability": 89,
            "problem_solving": 91,
            "project_quality": 86,
            "innovation": 89,
            "technical_consistency": 87,
            "community_participation": 79,
            "leadership": 72,
            "open_source_contributions": 80,
            "hackathon_performance": 85,
        },
    },
    {
        "name": "Evan Martinez",
        "email": "evan@example.com",
        "username": "evan_martinez",
        "github": "evan-martinez-dev",
        "headline": "DevOps and Infrastructure Engineer",
        "location": "Remote",
        "skills": [
            {"name": "Kubernetes", "source": "verified", "confidence": 0.95},
            {"name": "Docker", "source": "verified", "confidence": 0.96},
            {"name": "Terraform", "source": "github", "confidence": 0.92},
            {"name": "AWS", "source": "verified", "confidence": 0.91},
            {"name": "Python", "source": "github", "confidence": 0.88},
            {"name": "Go", "source": "github", "confidence": 0.87},
            {"name": "CI/CD", "source": "github", "confidence": 0.93},
        ],
        "experience_years": 5.5,
        "overall_score": 81.0,
        "sub_scores": {
            "coding_ability": 85,
            "problem_solving": 83,
            "project_quality": 82,
            "innovation": 80,
            "technical_consistency": 88,
            "community_participation": 76,
            "leadership": 79,
            "open_source_contributions": 74,
            "hackathon_performance": 75,
        },
    },
]


async def seed_candidates():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("\n" + "="*70)
        print("SEEDING CANDIDATES")
        print("="*70 + "\n")

        for candidate_data in CANDIDATES:
            email = candidate_data["email"]

            # Check if user exists
            user_result = await session.execute(select(User).where(User.email == email))
            user = user_result.scalar_one_or_none()

            if user:
                print(f"✓ User exists: {candidate_data['name']} ({email})")
            else:
                # Create user
                user = User(
                    id=uuid.uuid4(),
                    email=email,
                    password_hash=hash_password("password123"),
                    full_name=candidate_data["name"],
                    role="candidate",
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(user)
                await session.flush()
                print(f"✓ Created user: {candidate_data['name']} ({email})")

            # Check if profile exists
            profile_result = await session.execute(
                select(CandidateProfile).where(CandidateProfile.user_id == user.id)
            )
            profile = profile_result.scalar_one_or_none()

            if profile:
                print(f"  → Profile already exists")
            else:
                # Create candidate profile
                profile = CandidateProfile(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    username=candidate_data["username"],
                    github_username=candidate_data["github"],
                    headline=candidate_data["headline"],
                    location=candidate_data["location"],
                    skills=candidate_data["skills"],
                    experience=[
                        {
                            "company": "Tech Corp",
                            "title": "Senior Engineer",
                            "years": candidate_data["experience_years"],
                        }
                    ],
                    portfolio_published=True,
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(profile)
                await session.flush()
                print(f"  → Created profile: {candidate_data['username']}")

                # Create talent score
                score = TalentScore(
                    id=uuid.uuid4(),
                    candidate_id=profile.id,
                    overall=candidate_data["overall_score"],
                    coding_ability=candidate_data["sub_scores"]["coding_ability"],
                    problem_solving=candidate_data["sub_scores"]["problem_solving"],
                    project_quality=candidate_data["sub_scores"]["project_quality"],
                    innovation=candidate_data["sub_scores"]["innovation"],
                    technical_consistency=candidate_data["sub_scores"]["technical_consistency"],
                    community_participation=candidate_data["sub_scores"]["community_participation"],
                    leadership=candidate_data["sub_scores"]["leadership"],
                    open_source_contributions=candidate_data["sub_scores"]["open_source_contributions"],
                    hackathon_performance=candidate_data["sub_scores"]["hackathon_performance"],
                    # Derived the same way `compute_confidence` does, rather than left
                    # NULL. A seeded score that omits these reads back as
                    # "0/9 signals - sparse profile" on the dashboard while nine
                    # populated sub-scores sit directly beside it, which makes the
                    # product contradict itself on its most important screen.
                    confidence_available_signals=len(candidate_data["sub_scores"]),
                    confidence_expected_signals=len(SUB_SCORE_WEIGHTS),
                    confidence=round(
                        len(candidate_data["sub_scores"]) / len(SUB_SCORE_WEIGHTS), 2
                    ),
                    computed_at=datetime.now(timezone.utc),
                )
                session.add(score)
                print(f"  → Created talent score: {candidate_data['overall_score']}/100")

        await session.commit()

        print("\n" + "="*70)
        print("DATABASE SEEDED SUCCESSFULLY!")
        print("="*70)
        print("\nCandidates seeded:")
        for c in CANDIDATES:
            print(f"  • {c['name']:20} | {c['email']:30} | Score: {c['overall_score']}/100")
        print("\n" + "="*70)
        print("Login credentials for testing:")
        print("  Email: alice@example.com | Password: password123")
        print("  Email: bob@example.com   | Password: password123")
        print("  Email: charlie@example.com | Password: password123")
        print("="*70 + "\n")

        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_candidates())
