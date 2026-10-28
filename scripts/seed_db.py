"""Database & Vector DB Seeding Script.

Seeds the PostgreSQL relational database and Qdrant vector database with rich demo data
for candidates, job postings, assessments, hackathons, and course catalogs.

Usage:
    python scripts/seed_db.py
"""

import asyncio
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Repo root on sys.path so `packages`/`services` import when this is run directly as
# `python scripts/seed_db.py`, without needing PYTHONPATH to be set by the caller.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import (
    CandidateProfile,
    CourseCatalogEntry,
    Hackathon,
    HackathonTeam,
    Job,
    Organization,
    RoleSkillRequirement,
    SkillDescription,
    TalentScore,
    User,
)
from services.api.core.db import async_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("trace.seed")


async def seed_relational_database(session: AsyncSession):
    logger.info("Seeding relational database tables...")

    # 1. Organization
    org_stmt = select(Organization).where(Organization.name == "Demo Tech Corp")
    org_res = await session.execute(org_stmt)
    org = org_res.scalar_one_or_none()
    if not org:
        org = Organization(
            id=uuid.uuid4(),
            name="Demo Tech Corp",
            domain="trace.dev",
            org_type="company",
            created_at=datetime.now(timezone.utc),
        )
        session.add(org)
        await session.flush()
        logger.info("Created Organization: Demo Tech Corp")

    # 2. Demo Users
    user_data = [
        ("user_candidate_demo", "demo_candidate@trace.dev", "candidate", "Prasad Bhalerao"),
        ("user_recruiter_demo", "demo_recruiter@trace.dev", "recruiter", "Sarah Chen"),
        ("user_organizer_demo", "demo_organizer@trace.dev", "organizer", "Marcus Vance"),
        ("user_judge_demo", "demo_judge@trace.dev", "judge", "Dr. Elena Rostova"),
        ("user_admin_demo", "demo_admin@trace.dev", "admin", "System Administrator"),
    ]

    users_map = {}
    from services.api.core.security import hash_password

    for _legacy_id, email, role, full_name in user_data:
        user_stmt = select(User).where(User.email == email)
        u_res = await session.execute(user_stmt)
        user = u_res.scalar_one_or_none()
        if not user:
            user = User(
                id=uuid.uuid4(),
                password_hash=hash_password("password123"),
                email=email,
                role=role,
                full_name=full_name,
                organization_id=org.id,
                created_at=datetime.now(timezone.utc),
            )
            session.add(user)
            await session.flush()
            logger.info("Created User: %s (%s)", full_name, role)
        users_map[role] = user

    candidate_user = users_map["candidate"]
    recruiter_user = users_map["recruiter"]

    # 3. Candidate Profile
    prof_stmt = select(CandidateProfile).where(CandidateProfile.user_id == candidate_user.id)
    p_res = await session.execute(prof_stmt)
    profile = p_res.scalar_one_or_none()

    prasad_education = [
        {
            "institution": "JSPM's Rajarshi Shahu College of Engineering (RSCOE)",
            "degree": "B.Tech in Computer Science and Business Systems (CSBS)",
            "dates": "2024 - 2028",
            "gpa": "9.30 CGPA",
        },
        {
            "institution": "Fattechand Junior College, Chinchwad",
            "degree": "Higher Secondary Certificate (HSC) - 12th",
            "dates": "2022 - 2024",
            "gpa": "84.50%",
        },
        {
            "institution": "MSS High School, Chinchwad",
            "degree": "Secondary School Certificate (SSC) - 10th",
            "dates": "2020 - 2022",
            "gpa": "94.80%",
        },
    ]

    prasad_experience = [
        {
            "company": "Gotham-AI & TechHawks Club (JSPM's RSCOE)",
            "role": "Vice President & Lead Developer",
            "location": "Pune, India",
            "dates": "Aug 2024 - Present",
            "bullets": [
                "Elected Vice President to direct technical operations and student AI initiatives, conducting workshops on modern web stacks and agentic AI for 200+ engineering students.",
                "Architected and launched collaborative community web applications and portal dashboards using React.js, Tailwind CSS, and Node.js.",
                "Organized internal hackathons and hands-on coding bootcamps, improving community contest participation and problem-solving benchmarks.",
            ],
        },
        {
            "company": "Competitive Coding Club",
            "role": "Technical Contributor & Problem Solver",
            "location": "Pune, India",
            "dates": "Jan 2024 - Present",
            "bullets": [
                "Solved 30+ algorithmic problems across LeetCode and competitive coding platforms with active contest participation (Biweekly Contest 164).",
                "Collaborated with peer developers on technical hackathons, building prototype solutions under tight deadlines.",
            ],
        },
    ]

    prasad_skills = [
        {"name": "C/C++", "source": "github_analysis", "confidence": 0.95},
        {"name": "Python", "source": "github_analysis", "confidence": 0.95},
        {"name": "JavaScript", "source": "github_analysis", "confidence": 0.94},
        {"name": "TypeScript", "source": "github_analysis", "confidence": 0.92},
        {"name": "React", "source": "github_analysis", "confidence": 0.90},
        {"name": "Next.js", "source": "github_analysis", "confidence": 0.88},
        {"name": "Node.js", "source": "github_analysis", "confidence": 0.90},
        {"name": "Express.js", "source": "github_analysis", "confidence": 0.89},
        {"name": "FastAPI", "source": "github_analysis", "confidence": 0.88},
        {"name": "LangGraph", "source": "verified", "confidence": 0.92},
        {"name": "MongoDB", "source": "verified", "confidence": 0.90},
        {"name": "PostgreSQL", "source": "verified", "confidence": 0.87},
        {"name": "Tailwind CSS", "source": "github_analysis", "confidence": 0.92},
        {"name": "Docker", "source": "verified", "confidence": 0.85},
        {"name": "Redis", "source": "verified", "confidence": 0.82},
    ]

    if not profile:
        profile = CandidateProfile(
            id=uuid.uuid4(),
            user_id=candidate_user.id,
            github_username="prasadbhalerao1",
            leetcode_username="prasad8671",
            username="prasadbhalerao",
            headline="Full Stack Web Developer & AI Engineer | CSBS Undergraduate at JSPM's RSCOE",
            location="Pune, Maharashtra, India",
            education=prasad_education,
            experience=prasad_experience,
            skills=prasad_skills,
            portfolio_published=True,
            updated_at=datetime.now(timezone.utc),
        )
        session.add(profile)
        await session.flush()

        score = TalentScore(
            id=uuid.uuid4(),
            candidate_id=profile.id,
            overall=88.5,
            score_version="v1",
            coding_ability=92.0,
            technical_consistency=88.0,
            community_participation=85.0,
            leadership=80.0,
            project_quality=90.0,
            innovation=86.0,
            renormalized_subscores=["problem_solving"],
            computed_at=datetime.now(timezone.utc),
        )
        session.add(score)
        logger.info("Created Candidate Profile & Talent Score for Prasad Bhalerao")
    else:
        profile.github_username = "prasadbhalerao1"
        profile.leetcode_username = "prasad8671"
        profile.username = "prasadbhalerao"
        profile.headline = "Full Stack Web Developer & AI Engineer | CSBS Undergraduate at JSPM's RSCOE"
        profile.location = "Pune, Maharashtra, India"
        profile.education = prasad_education
        profile.experience = prasad_experience
        profile.skills = prasad_skills
        profile.portfolio_published = True
        profile.updated_at = datetime.now(timezone.utc)
        session.add(profile)
        await session.flush()
        logger.info("Updated Candidate Profile for Prasad Bhalerao")

    # 4. Job Postings
    jobs_data = [
        ("Senior Fullstack AI Engineer", "Build agentic workflows and React control-planes.", ["Python", "FastAPI", "TypeScript", "React"], 4, True, "Remote"),
        ("Backend Systems Architect", "High-throughput PostgreSQL and distributed microservices.", ["Python", "PostgreSQL", "Docker", "Redis"], 6, True, "New York, NY"),
    ]

    for title, desc, req_skills, min_exp, is_remote, loc in jobs_data:
        j_stmt = select(Job).where(Job.title == title)
        j_res = await session.execute(j_stmt)
        if not j_res.scalar_one_or_none():
            job = Job(
                id=uuid.uuid4(),
                posted_by_user_id=recruiter_user.id,
                organization_id=org.id,
                title=title,
                description=desc,
                required_skills=req_skills,
                min_experience_years=min_exp,
                is_remote=is_remote,
                location=loc,
                created_at=datetime.now(timezone.utc),
            )
            session.add(job)
            logger.info("Created Job Posting: %s", title)

    # 5. Course Catalog Entries
    course_data = [
        ("coursera", "Advanced LangGraph & Multi-Agent Architecture", "https://coursera.org/langgraph", ["Python", "LangGraph"], "intermediate"),
        ("vendor", "Production FastAPI & Async Architectures", "https://udemy.com/fastapi", ["Python", "FastAPI"], "advanced"),
    ]

    for provider, title, url, skill_tags, level in course_data:
        c_stmt = select(CourseCatalogEntry).where(CourseCatalogEntry.title == title)
        c_res = await session.execute(c_stmt)
        if not c_res.scalar_one_or_none():
            course = CourseCatalogEntry(
                id=uuid.uuid4(),
                provider=provider,
                title=title,
                url=url,
                skill_tags=skill_tags,
                level=level,
                is_free=False,
                created_at=datetime.now(timezone.utc),
            )
            session.add(course)
            logger.info("Created Course Catalog Entry: %s", title)

    # 5b. Curated catalogs — role requirement sets and skill glosses.
    #
    # These were Python dict literals until the catalog migration; the code still carries
    # them as SEED constants, which are both the fallback when the database is
    # unreachable and the source for this seeding step. Seeding from the same constants
    # the fallback uses guarantees a freshly-seeded database behaves identically to a
    # database-less one.
    #
    # Upserted rather than insert-if-absent: unlike a course row (which an admin may
    # legitimately edit), a seed weight changing in code should propagate on re-seed.
    # An admin-added role that does not exist in the seed is left untouched.
    from services.agents.candidate_intelligence.tools.role_taxonomy import ROLE_SKILL_TAXONOMY_SEED
    from services.agents.recruitment.tools.skill_descriptions import SKILL_DESCRIPTIONS_SEED

    existing_reqs = {
        (row.role, row.skill_name): row
        for row in (await session.execute(select(RoleSkillRequirement))).scalars().all()
    }
    created_reqs = 0
    for role, skills in ROLE_SKILL_TAXONOMY_SEED.items():
        for skill_name, weight in skills:
            row = existing_reqs.get((role, skill_name))
            if row is None:
                session.add(RoleSkillRequirement(role=role, skill_name=skill_name, weight=weight))
                created_reqs += 1
            else:
                row.weight = weight
    logger.info(
        "Role skill requirements: %d created, %d refreshed",
        created_reqs, len(existing_reqs),
    )

    existing_descriptions = {
        row.skill_name: row
        for row in (await session.execute(select(SkillDescription))).scalars().all()
    }
    created_descriptions = 0
    for skill_name, description in SKILL_DESCRIPTIONS_SEED.items():
        row = existing_descriptions.get(skill_name)
        if row is None:
            session.add(SkillDescription(skill_name=skill_name, description=description))
            created_descriptions += 1
        else:
            row.description = description
    logger.info(
        "Skill descriptions: %d created, %d refreshed",
        created_descriptions, len(existing_descriptions),
    )

    # 6. Hackathon Event
    h_stmt = select(Hackathon).where(Hackathon.name == "Global AI Hackathon 2026")
    h_res = await session.execute(h_stmt)
    hackathon = h_res.scalar_one_or_none()
    if not hackathon:
        hackathon = Hackathon(
            id=uuid.uuid4(),
            organizer_user_id=users_map["organizer"].id,
            organizer_org_id=org.id,
            name="Global AI Hackathon 2026",
            tracks=["Full-Stack AI", "Agentic Systems"],
            ingestion_mode="direct",
            status="active",
            created_at=datetime.now(timezone.utc),
        )
        session.add(hackathon)
        await session.flush()

        # Add Hackathon Team
        team = HackathonTeam(
            id=uuid.uuid4(),
            hackathon_id=hackathon.id,
            team_name="CyberAgents",
            created_at=datetime.now(timezone.utc),
        )
        session.add(team)
        logger.info("Created Hackathon Event & Team: CyberAgents")

    await session.commit()
    logger.info("Relational database seeding completed successfully!")


async def seed_vector_database():
    logger.info("Seeding Qdrant vector database...")
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models

        from services.api.core.config import get_settings

        from scripts.ensure_qdrant_indexes import COLLECTION_PAYLOAD_INDEXES
        from services.api.core.qdrant import ensure_payload_indexes

        settings = get_settings()
        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)

        # Names taken from `COLLECTION_PAYLOAD_INDEXES`, which mirrors what the app
        # actually reads and writes. This list previously named `slide_embeddings` and
        # `candidate_skill_vectors` — neither of which any code path uses. The real
        # collections (`presentation_slide_embeddings`, `candidate_project_embeddings`,
        # `job_description_embeddings`) were absent, so seeding created two empty
        # collections nothing queried and pre-created none of the ones that matter.
        for col, payload_fields in COLLECTION_PAYLOAD_INDEXES.items():
            if not client.collection_exists(col):
                client.create_collection(
                    collection_name=col,
                    vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
                )
                logger.info("Created Qdrant vector collection: %s", col)
            # Indexes the filtered fields up front so the first real search is already
            # fast, and repairs collections created before payload indexing existed.
            ensure_payload_indexes(client, col, payload_fields)

        logger.info("Qdrant vector database seeding completed successfully!")
    except Exception as e:
        logger.warning("Vector DB seeding skipped or degraded: %s", e)


async def main():
    async with async_session() as session:
        await seed_relational_database(session)
    await seed_vector_database()


if __name__ == "__main__":
    asyncio.run(main())
