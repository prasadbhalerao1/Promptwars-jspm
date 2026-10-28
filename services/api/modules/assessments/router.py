"""
Assessment Controller.
Handles Skill Verification Assessments, Live AI Interviewer Sessions & Reports, and Team Contribution Analytics.
"""
import asyncio
import base64
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from github import Github
from github.GithubException import GithubException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import (
    AgentRun,
    Assessment,
    CandidateProfile,
    ContributionReport,
    InterviewDefinition,
    InterviewReport,
    InterviewSession,
    InterviewTranscriptTurn,
    Job,
    Submission,
    User,
)
from packages.shared_schemas.assessment import (
    AssessmentCreateRequest,
    AssessmentResponse,
    ContributionReportGenerateRequest,
    ContributionReportResponse,
    GenerateDefinitionQuestionsRequest,
    GenerateDefinitionQuestionsResponse,
    InterviewAnswerRequest,
    InterviewAvatarTokenResponse,
    InterviewDefinitionAttemptResponse,
    InterviewDefinitionCreateRequest,
    InterviewDefinitionQuestion,
    InterviewDefinitionResponse,
    InterviewDefinitionUpdateRequest,
    InterviewReportWithTranscriptResponse,
    InterviewSessionResponse,
    InterviewSessionWithTranscriptResponse,
    InterviewStartRequest,
    InterviewTurnResponse,
    SubmissionRequest,
    SubmissionResponse,
)
from services.agents.assessment.contribution_graph import get_contribution_graph
from services.agents.assessment.interview_definition_graph import get_interview_definition_graph
from services.agents.assessment.interview_graph import get_interview_graph
from services.agents.assessment.interview_report_graph import get_interview_report_graph
from services.agents.assessment.state import ContributionState, DefinitionQuestionState, InterviewReportState, InterviewState, VerificationState
from services.agents.assessment.tools.llm_review import AssessmentUnavailable
from services.agents.assessment.tools.interview_llm import generate_definition_questions
from services.agents.assessment.verification_graph import get_verification_graph
from services.agents.prompts_loader import load_prompt
from services.api.core import trugen
from services.api.core.config import get_settings
from services.api.common.constants import truncate_error
from services.api.core.db import async_session, get_db, without_db_connection
from services.api.core.rbac import require_role
from services.api.core.tracing import start_agent_trace
from services.api.modules.candidates.router import _get_or_create_profile
# Single definition of job ownership, shared rather than re-implemented here — the
# submission-access rule below already documents itself as mirroring it. Safe from a
# cycle: recruitment/router.py imports nothing from this module.
from services.api.modules.recruitment.router import _job_owned_by

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Assessments & Verification"])


def _candidate_profile_summary(profile: CandidateProfile) -> str:
    skills = ", ".join(s.get("name", "") for s in (profile.skills or []) if s.get("name"))
    parts = []
    if profile.headline:
        parts.append(profile.headline)
    if skills:
        parts.append(f"Skills: {skills}")
    if profile.location:
        parts.append(f"Location: {profile.location}")
    return " | ".join(parts) or "No profile details available."


def _fetch_repo_sample_source(repo_full_name: str, max_size: int = 20_000) -> str:
    client = Github(retry=None)
    try:
        repo = client.get_repo(repo_full_name)
        contents = repo.get_contents("")
        for item in contents:
            if item.path.endswith(".py") and item.size < max_size:
                return base64.b64decode(item.content).decode("utf-8", errors="ignore")
    except (GithubException, UnicodeDecodeError):
        pass
    return ""


@router.post("/assessments", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    body: AssessmentCreateRequest,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> Assessment:
    """Create an assessment, optionally bound to a job and/or a specific candidate.

    `job_id` is ownership-checked. It was taken straight from the body, so a recruiter
    could attach an assessment to *another* recruiter's posting — which is not just an
    unwanted row: `_require_submission_access` derives who may read a submission from
    the assessment's job, so the resulting submissions became readable by the other
    org's recruiters, and the candidate saw an assessment attributed to a job its real
    owner never created.

    `job_id=None` (a reusable template not yet tied to a posting) stays allowed, matching
    the nullable-by-design contract on `AssessmentCreateRequest`.
    """
    if body.job_id is not None:
        await _job_owned_by(db, body.job_id, user)

    assessment = Assessment(
        job_id=body.job_id, candidate_id=body.candidate_id, type=body.type, spec=body.spec
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)
    return assessment


@router.get("/assessments/mine", response_model=list[AssessmentResponse])
async def list_my_assessments(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> list[Assessment]:
    profile = await _get_or_create_profile(db, user)
    result = await db.execute(
        select(Assessment)
        .where(Assessment.candidate_id == profile.id)
        .order_by(Assessment.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: uuid.UUID,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> Assessment:
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assessment_not_found")

    # `spec` carries hidden test cases in full — without this check any candidate could
    # read another candidate's assessment (and its answers) by guessing a UUID.
    # `candidate_id` is nullable for not-yet-assigned reusable templates, which stay
    # readable; a 404 (not 403) avoids confirming that someone else's ID exists.
    if assessment.candidate_id is not None:
        profile = await _get_or_create_profile(db, user)
        if assessment.candidate_id != profile.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assessment_not_found")

    return assessment


@router.post("/assessments/{assessment_id}/submit", response_model=SubmissionResponse)
async def submit_assessment(
    assessment_id: uuid.UUID,
    body: SubmissionRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> Submission:
    """Records the submission and returns immediately with `grading_status="processing"`.

    The verification graph (repo fetch for project_analysis, static analysis, LLM code
    review) previously ran inline here, so the candidate's "Submit" request stayed open
    for the entire pipeline with no feedback. Clients poll `GET /submissions/{id}` and
    re-render once `grading_status` is no longer "processing" — same pattern as
    presentation upload and job matching.
    """
    profile = await _get_or_create_profile(db, user)

    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assessment_not_found")

    # Same assignment rule `get_assessment` applies to reads. Without it a candidate
    # could submit against any assessment id, including one assigned to someone else —
    # and against an unassigned template (`candidate_id is None`), whose submissions
    # `_require_submission_access` treats as having no owning recruiter and therefore
    # leaves readable by every recruiter on the platform. 404 rather than 403, so the
    # response does not confirm that someone else's assessment exists.
    if assessment.candidate_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assessment_not_found")

    submission = Submission(
        assessment_id=assessment.id,
        candidate_id=profile.id,
        code_or_answers=body.code_or_answers,
        test_results={"results": [r.model_dump() for r in body.test_results], "rationale": None},
        grading_status="processing",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    background_tasks.add_task(
        _grade_submission_background,
        submission.id,
        assessment.id,
        user.id,
        [r.model_dump() for r in body.test_results],
    )
    return submission


async def _grade_submission_background(
    submission_id: uuid.UUID,
    assessment_id: uuid.UUID,
    user_id: uuid.UUID,
    test_results: list[dict],
) -> None:
    """Runs the verification graph outside the request/response cycle in its own session.

    Never raises: any failure is recorded as `grading_status="failed"` with the reason on
    the row, so a submission can't be left stuck in "processing" forever (the same
    guarantee `_analyze_presentation` makes for pitch decks).
    """
    async with async_session() as db:
        submission = (
            await db.execute(select(Submission).where(Submission.id == submission_id))
        ).scalar_one_or_none()
        if submission is None:
            logger.error("submission %s vanished before grading could run", submission_id)
            return

        assessment = (
            await db.execute(select(Assessment).where(Assessment.id == assessment_id))
        ).scalar_one_or_none()
        if assessment is None:
            submission.grading_status = "failed"
            submission.grading_error = "assessment_not_found"
            await db.commit()
            return

        try:
            code_or_answers = dict(submission.code_or_answers or {})
            if assessment.type == "project_analysis":
                repo_full_name = code_or_answers.get("repo_full_name", "")
                # Synchronous PyGithub network call — keep it off the event loop.
                code_or_answers["code"] = (
                    await asyncio.to_thread(_fetch_repo_sample_source, repo_full_name)
                    if repo_full_name
                    else ""
                )

            initial_state: VerificationState = {
                "assessment_type": assessment.type,
                "spec": assessment.spec or {},
                "code_or_answers": code_or_answers,
                "test_results": test_results,
                "static_analysis": {},
                "tests_passed": 0,
                "tests_total": 0,
                "grading_rationale": None,
                "llm_review": None,
                "score": None,
            }

            with start_agent_trace(
                "assessment.verification",
                input_data={"assessment_type": assessment.type},
                user_id=str(user_id),
                tags=["assessment", "verification"],
            ) as trace:
                result_state = await get_verification_graph().ainvoke(initial_state)
                trace.update(
                    output={"score": result_state["score"], "tests_passed": result_state["tests_passed"]}
                )

            submission.test_results = {
                "results": test_results,
                "rationale": result_state["grading_rationale"],
            }
            submission.static_analysis = result_state["static_analysis"]
            submission.llm_review = result_state["llm_review"]
            submission.score = result_state["score"]
            submission.grading_status = "done"
            submission.grading_error = None

            settings = get_settings()
            db.add(
                AgentRun(
                    agent_name="verification_report_agent",
                    subject_type="submission",
                    subject_id=submission.id,
                    input_ref={
                        "assessment_type": assessment.type,
                        "tests_total": result_state["tests_total"],
                    },
                    output={
                        "score": result_state["score"],
                        "tests_passed": result_state["tests_passed"],
                    },
                    model_used=settings.llm_model_judgment,
                    langfuse_trace_id=trace.trace_id,
                )
            )
        except AssessmentUnavailable as exc:
            submission.grading_status = "failed"
            submission.grading_error = truncate_error(exc)
        except Exception as exc:  # noqa: BLE001 - surfaced via grading_error, never crashes the worker
            logger.exception("grading failed for submission %s", submission_id)
            submission.grading_status = "failed"
            submission.grading_error = truncate_error(exc)

        await db.commit()


async def _require_submission_access(db: AsyncSession, submission: Submission, user: User) -> None:
    """Recruiter may read a submission only if they own the job it was assessed for.

    Ownership mirrors `recruitment/router.py:_job_owned_by` — same organization, or the
    recruiter who posted the job.

    Every branch refuses rather than returns. The three "no owner to check against"
    cases (missing assessment, assessment with no `job_id`, dangling `job_id`) used to
    fall through to an early `return`, which meant *any* recruiter could read the
    submission — its full code and answers — whenever the owning job could not be
    resolved. A candidate submitting against an unassigned template hit exactly that
    branch, so their code was platform-readable by construction. `submit_assessment` now
    also refuses submissions against assessments the candidate wasn't assigned, which
    closes the other half.
    """
    assessment = (
        await db.execute(select(Assessment).where(Assessment.id == submission.assessment_id))
    ).scalar_one_or_none()
    if assessment is None or assessment.job_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_job_posting")

    job = (await db.execute(select(Job).where(Job.id == assessment.job_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_job_posting")
    if user.organization_id and job.organization_id == user.organization_id:
        return
    if job.posted_by_user_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_job_posting")


@router.get("/submissions/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: uuid.UUID,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> Submission:
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    submission = result.scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission_not_found")

    # Submissions contain a candidate's full code/answers — scope them to the recruiter
    # who owns the underlying job posting (org membership or direct ownership), the same
    # rule `recruitment/router.py:_job_owned_by` applies everywhere else.
    await _require_submission_access(db, submission, user)
    return submission


def _default_topic_plan(profile: CandidateProfile) -> list[str]:
    """Generate a rich set of interview topics from the candidate's profile.
    If skills are available, use them; otherwise, generate breadth-based topics
    that cover fundamental to advanced areas based on profile signals."""
    skills = [s.get("name") for s in (profile.skills or []) if s.get("name")]
    if skills:
        return skills[:5]

    # Fallback: generate rich, progressive topics covering breadth
    # of technical competencies (foundational → advanced)
    return [
        "Core programming fundamentals and language proficiency",
        "Problem-solving approach and algorithm design",
        "System design and architectural thinking",
        "Real-world project experience and technical depth",
        "Collaboration, communication, and adaptability",
    ]


async def _definition_owned_by(db: AsyncSession, definition_id: uuid.UUID, user: User) -> InterviewDefinition:
    result = await db.execute(select(InterviewDefinition).where(InterviewDefinition.id == definition_id))
    definition = result.scalar_one_or_none()
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interview_definition_not_found")
    if definition.created_by_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_interview_definition")
    return definition


@router.post("/interview-definitions/generate-questions", response_model=GenerateDefinitionQuestionsResponse)
async def generate_definition_questions_endpoint(
    body: GenerateDefinitionQuestionsRequest,
    user: User = Depends(require_role("recruiter", "candidate")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate interview topics from role/JD context without persisting. Recruiters use this to create definitions; candidates use it for practice interviews."""
    initial_state: DefinitionQuestionState = {
        "role_title": body.role_title,
        "job_description": body.job_description,
        "years_experience": body.years_experience,
        "question_count": body.question_count,
        "topics": [],
    }

    with start_agent_trace(
        "assessment.interview.definition_questions",
        input_data={"role_title": body.role_title, "question_count": body.question_count},
        user_id=str(user.id),
        tags=["assessment", "interview", "definition"],
    ) as trace:
        try:
            result_state = await without_db_connection(
                db, lambda: get_interview_definition_graph().ainvoke(initial_state)
            )
        except AssessmentUnavailable as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        trace.update(output={"topics": result_state["topics"]})

    questions = [
        InterviewDefinitionQuestion(id=str(i), topic=topic)
        for i, topic in enumerate(result_state["topics"])
    ]
    return {"questions": questions}


@router.post("/interview-definitions", response_model=InterviewDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_interview_definition(
    body: InterviewDefinitionCreateRequest,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> InterviewDefinition:
    """Persist a new interview definition."""
    definition = InterviewDefinition(
        created_by_user_id=user.id,
        title=body.title,
        role_title=body.role_title,
        job_description=body.job_description,
        years_experience=body.years_experience,
        questions=[q.model_dump() for q in body.questions],
        question_count=len(body.questions),
        duration_minutes=body.duration_minutes,
        is_active=True,
    )
    db.add(definition)
    await db.commit()
    await db.refresh(definition)
    return definition


@router.get("/interview-definitions/mine", response_model=list[InterviewDefinitionResponse])
async def list_my_interview_definitions(
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> list[InterviewDefinition]:
    """List interview definitions created by the recruiter."""
    result = await db.execute(
        select(InterviewDefinition)
        .where(InterviewDefinition.created_by_user_id == user.id)
        .order_by(InterviewDefinition.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/interview-definitions/open", response_model=list[InterviewDefinitionResponse])
async def list_open_interview_definitions(
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> list[InterviewDefinition]:
    """Browse open interview definitions (candidates)."""
    result = await db.execute(
        select(InterviewDefinition)
        .where(InterviewDefinition.is_active == True)
        .order_by(InterviewDefinition.created_at.desc())
    )
    return list(result.scalars().all())


@router.patch("/interview-definitions/{definition_id}", response_model=InterviewDefinitionResponse)
async def update_interview_definition(
    definition_id: uuid.UUID,
    body: InterviewDefinitionUpdateRequest,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> InterviewDefinition:
    """Update an interview definition (ownership-checked)."""
    definition = await _definition_owned_by(db, definition_id, user)

    if body.title is not None:
        definition.title = body.title
    if body.questions is not None:
        definition.questions = [q.model_dump() for q in body.questions]
        definition.question_count = len(body.questions)
    if body.duration_minutes is not None:
        definition.duration_minutes = body.duration_minutes
    if body.is_active is not None:
        definition.is_active = body.is_active

    await db.commit()
    await db.refresh(definition)
    return definition


@router.get("/interview-definitions/{definition_id}/attempts", response_model=list[InterviewDefinitionAttemptResponse])
async def list_interview_definition_attempts(
    definition_id: uuid.UUID,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all interview attempts for a definition (ownership-checked)."""
    definition = await _definition_owned_by(db, definition_id, user)

    # `has_report` comes from an EXISTS correlated subquery rather than a per-attempt
    # SELECT: this used to issue one extra round trip for every attempt in the list, so a
    # definition with 50 attempts cost 51 queries. One query now, and EXISTS lets
    # Postgres stop at the first matching report instead of materializing the row.
    has_report = (
        select(InterviewReport.id)
        .where(InterviewReport.session_id == InterviewSession.id)
        .exists()
    )
    result = await db.execute(
        select(InterviewSession, CandidateProfile, has_report)
        .join(CandidateProfile, InterviewSession.candidate_id == CandidateProfile.id)
        .where(InterviewSession.interview_definition_id == definition_id)
        .order_by(InterviewSession.started_at.desc())
    )

    return [
        {
            "session_id": session.id,
            "candidate_id": profile.id,
            "candidate_name": profile.full_name,
            "status": session.status,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "has_report": report_exists,
        }
        for session, profile, report_exists in result.all()
    ]


@router.post("/interview-sessions", response_model=InterviewTurnResponse, status_code=status.HTTP_201_CREATED)
async def start_interview(
    body: InterviewStartRequest,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    profile = await _get_or_create_profile(db, user)

    # Derive topic_plan and job_context from definition if provided
    job_context = None
    if body.interview_definition_id:
        def_result = await db.execute(select(InterviewDefinition).where(InterviewDefinition.id == body.interview_definition_id))
        definition = def_result.scalar_one_or_none()
        if definition is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interview_definition_not_found")
        topic_plan = [q["topic"] for q in definition.questions]
        job_context = {
            "role_title": definition.role_title,
            "job_description": definition.job_description,
            "years_experience": definition.years_experience,
        }
    else:
        topic_plan = body.topic_plan or _default_topic_plan(profile)
        # A practice interview's topics were generated from a role the candidate typed in;
        # without this the interviewer only saw bare topic names and lost the JD entirely.
        if body.role_title and body.job_description:
            job_context = {
                "role_title": body.role_title,
                "job_description": body.job_description,
                "years_experience": body.years_experience,
            }

    if body.mode == "avatar" and not trugen.trugen_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="avatar_interviews_unavailable")

    # Worst-case interview length is 2 x len(topic_plan) turns (one answer plus at most one
    # follow-up per topic), and every turn costs two serial judgment-tier LLM calls. The
    # plan is caller-supplied and was accepted at any length, so a 10,000-element list
    # bought a 20,000-turn interview against the provider account. Truncating rather than
    # rejecting keeps a legitimate over-long plan usable.
    max_topics = get_settings().interview_max_topics
    if len(topic_plan) > max_topics:
        logger.warning(
            "Interview topic plan of %d truncated to %d for candidate %s",
            len(topic_plan), max_topics, profile.id,
        )
        topic_plan = topic_plan[:max_topics]
    if not topic_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="empty_topic_plan"
        )

    session = InterviewSession(
        candidate_id=profile.id,
        job_id=body.job_id,
        interview_definition_id=body.interview_definition_id,
        state={
            "topic_plan": topic_plan,
            "current_topic_idx": 0,
            "transcript": [],
            "per_topic_scores": {},
            "follow_up_count_this_topic": 0,
            "job_context": job_context,
            "mode": body.mode,
        },
    )
    db.add(session)

    if body.mode == "avatar":
        # The avatar asks the questions, so there is no first question to generate here.
        # The TruGen agent is created when the page asks for a token, which keeps a
        # started-but-abandoned session from leaving an agent behind.
        await db.commit()
        return {
            "session_id": session.id,
            "question": None,
            "topics_remaining": len(topic_plan),
            "status": "in_progress",
            "mode": "avatar",
        }

    # Commit, not just flush: the graph call below releases this session's connection,
    # which discards any open transaction. A flushed-but-uncommitted InterviewSession
    # would be rolled back and the row lost. Committing here also means the session row
    # exists for the whole (slow) first-question generation, so a client that reconnects
    # mid-call finds a real session rather than a phantom id.
    await db.commit()

    initial_state: InterviewState = {
        "session_id": str(session.id),
        "candidate_id": str(profile.id),
        "mode": "start",
        "candidate_profile_summary": _candidate_profile_summary(profile),
        "job_context": job_context,
        "topic_plan": topic_plan,
        "current_topic_idx": 0,
        "transcript": [],
        "per_topic_scores": {},
        "follow_up_count_this_topic": 0,
        "next_question": None,
        "interview_status": "in_progress",
        "last_answer_verdict": None,
    }
    with start_agent_trace(
        "assessment.interview.start",
        input_data={"topic_plan": topic_plan},
        user_id=str(user.id),
        session_id=str(session.id),
        tags=["assessment", "interview"],
    ) as trace:
        try:
            result_state = await without_db_connection(
                db, lambda: get_interview_graph().ainvoke(initial_state)
            )
        except AssessmentUnavailable as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        trace.update(output={"question": result_state["next_question"]})

    session = await db.merge(session)
    session.state = {
        "topic_plan": result_state["topic_plan"],
        "current_topic_idx": result_state["current_topic_idx"],
        "transcript": result_state["transcript"],
        "per_topic_scores": result_state["per_topic_scores"],
        "follow_up_count_this_topic": result_state["follow_up_count_this_topic"],
        # Must be persisted here, not just on /turn: interview_turn rebuilds its state
        # from saved.get("job_context"), so omitting it meant every definition-backed
        # interview silently lost its role/JD context from the second question onward.
        "job_context": job_context,
    }
    db.add(
        InterviewTranscriptTurn(session_id=session.id, turn_index=0, role="agent", text=result_state["next_question"])
    )
    await db.commit()

    return {
        "session_id": session.id,
        "question": result_state["next_question"],
        "topics_remaining": len(topic_plan) - result_state["current_topic_idx"],
        "status": result_state["interview_status"],
    }


async def _session_owned_by(
    db: AsyncSession, session_id: uuid.UUID, user: User
) -> tuple[InterviewSession, CandidateProfile]:
    """Load an interview session, enforcing that `user` is the candidate being interviewed.

    Every candidate-facing session route goes through this. The read route checked
    ownership; `/turn` and `/end` looked the session up by id and never compared it to
    the caller, so any candidate holding a session UUID could answer questions into
    someone else's interview and then force-finalize it. `/end` was the worse half: it
    writes an `InterviewReport` — the technical/communication ratings and hiring
    recommendation a recruiter later reads as an assessment of the victim — so a third
    party could author another candidate's evaluation.

    Returns the profile alongside the session because callers need it anyway (to build
    the candidate summary the graph is prompted with), which keeps this from costing an
    extra query over the lookup it replaces.
    """
    result = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interview_session_not_found")

    profile = await _get_or_create_profile(db, user)
    if session.candidate_id != profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_interview_session")
    return session, profile


@router.get("/interview-sessions/{session_id}", response_model=InterviewSessionWithTranscriptResponse)
async def get_interview_session(
    session_id: uuid.UUID,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lets the frontend hydrate an in-progress (or completed) session's transcript on
    page load/reload — e.g. a direct link to /interview/{session_id} — since the initial
    question is otherwise only ever returned once, from the POST /interview-sessions
    response that started it."""
    session, _ = await _session_owned_by(db, session_id, user)

    turns_result = await db.execute(
        select(InterviewTranscriptTurn)
        .where(InterviewTranscriptTurn.session_id == session_id)
        .order_by(InterviewTranscriptTurn.turn_index)
    )
    turns = turns_result.scalars().all()
    saved = session.state or {}

    return {
        "session_id": session.id,
        "status": session.status,
        "transcript": turns,
        "mode": saved.get("mode", "classic"),
        "role_title": (saved.get("job_context") or {}).get("role_title"),
        "topics": saved.get("topic_plan", []),
    }


# Sent automatically by the browser (KICKOFF_MESSAGE in components/interview/
# AvatarInterview.tsx) because TruGen agents wait for the candidate to speak first. It is
# not an answer, so it never counts toward "the candidate said something scoreable".
_AVATAR_KICKOFF = "Hi, I'm ready to start the interview."


def _avatar_system_prompt(saved: dict, profile: CandidateProfile, max_minutes: int) -> str:
    job = saved.get("job_context") or {}
    years = job.get("years_experience")
    return load_prompt(
        "assessment",
        "avatar_interviewer",
        max_minutes=max_minutes,
        role_title=job.get("role_title") or "General software engineering",
        experience_level=f"{years} years" if years is not None else "Not specified; pitch questions at a mid level.",
        job_description=job.get("job_description") or "No job description provided; stay with the topics.",
        topic_list="\n".join(f"{i}. {t}" for i, t in enumerate(saved.get("topic_plan", []), start=1)),
        candidate_background=_candidate_profile_summary(profile),
    )


@router.post("/interview-sessions/{session_id}/avatar-token", response_model=InterviewAvatarTokenResponse)
async def avatar_session_token(
    session_id: uuid.UUID,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mint a browser token for the session's TruGen avatar, creating the agent on first use.

    Called again on reconnect: each call opens a new TruGen conversation, and every
    conversation id is kept so `/end` can stitch the transcript back together.
    """
    session, profile = await _session_owned_by(db, session_id, user)
    saved = dict(session.state or {})
    if saved.get("mode") != "avatar":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_an_avatar_session")
    if session.status != "in_progress":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="interview_session_not_in_progress")

    topics = saved.get("topic_plan", [])
    # About three minutes per topic, bounded by what the TruGen plan allows per call.
    max_seconds = min(get_settings().trugen_max_call_seconds, max(180, 180 * len(topics)))
    max_minutes = max(1, max_seconds // 60)
    role_title = (saved.get("job_context") or {}).get("role_title") or "Practice interview"

    try:
        agent_id = saved.get("trugen_agent_id")
        if not agent_id:
            agent_id = await trugen.create_interview_agent(
                name=f"TRACE interview {session.id}",
                system_prompt=_avatar_system_prompt(saved, profile, max_minutes),
                greeting=f"Hi {(profile.full_name or '').split(' ')[0] or 'there'}, thanks for joining. "
                f"This is your interview for {role_title}.",
                max_duration_seconds=max_seconds,
                conversational_context=(
                    f"Interview for {role_title}. Topics in order: "
                    + "; ".join(topics)
                    + ". Ask one question at a time, spoken plainly, no markdown or lists."
                ),
            )
            saved["trugen_agent_id"] = agent_id
        minted = await trugen.create_conversation_token(
            agent_id=agent_id,
            user_id=str(session.id),
            user_name=profile.full_name or "Candidate",
            context={"interview_session_id": str(session.id), "role_title": role_title},
        )
    except trugen.TrugenBusy as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="avatar_busy") from exc
    except trugen.TrugenUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="avatar_interviews_unavailable") from exc
    finally:
        # Persist the agent id even when minting failed, so a retry reuses it instead of
        # creating a second agent.
        if saved.get("trugen_agent_id") and saved.get("trugen_agent_id") != (session.state or {}).get("trugen_agent_id"):
            session.state = saved
            await db.commit()

    # A new dict, not `saved` mutated in place: `saved` may already be the object assigned
    # to `session.state` in the `finally` above, and reassigning the same object is not a
    # change SQLAlchemy can see, so the conversation id was silently never persisted.
    session.state = {
        **saved,
        "trugen_conversation_ids": [*saved.get("trugen_conversation_ids", []), minted["conversation_id"]],
    }
    await db.commit()
    return minted


async def _collect_avatar_transcript(saved: dict) -> list[dict[str, str]]:
    """Pull every TruGen conversation for the session, in order, into one transcript.

    TruGen finalizes a conversation's transcript a moment after the call closes, so a
    conversation still reported as live is re-read a few times before being taken as is.
    """
    turns: list[dict[str, str]] = []
    conversation_ids = list(saved.get("trugen_conversation_ids") or [])
    if not conversation_ids and saved.get("trugen_agent_id"):
        # Each session has its own agent, so its conversations can be recovered from
        # TruGen even if the ids were never recorded here.
        conversation_ids = await trugen.conversation_ids_for_agent(saved["trugen_agent_id"])
    for conversation_id in conversation_ids:
        status_, part = "", []
        for attempt in range(4):
            status_, part = await trugen.fetch_transcript(conversation_id)
            if status_.lower() == "ended" or attempt == 3:
                break
            await asyncio.sleep(1.5)
        turns.extend(part)
    return turns


@router.post("/interview-sessions/{session_id}/turn", response_model=InterviewTurnResponse)
async def interview_turn(
    session_id: uuid.UUID,
    body: InterviewAnswerRequest,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    session, profile = await _session_owned_by(db, session_id, user)
    if session.status != "in_progress":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="interview_session_not_in_progress")

    saved = session.state or {}
    transcript = [*saved.get("transcript", []), {"role": "candidate", "text": body.answer_text}]

    initial_state: InterviewState = {
        "session_id": str(session.id),
        "candidate_id": str(session.candidate_id),
        "mode": "turn",
        "candidate_profile_summary": _candidate_profile_summary(profile),
        "job_context": saved.get("job_context"),
        "topic_plan": saved.get("topic_plan", []),
        "current_topic_idx": saved.get("current_topic_idx", 0),
        "transcript": transcript,
        "per_topic_scores": saved.get("per_topic_scores", {}),
        "follow_up_count_this_topic": saved.get("follow_up_count_this_topic", 0),
        "next_question": None,
        "interview_status": "in_progress",
        "last_answer_verdict": None,
    }
    with start_agent_trace(
        "assessment.interview.turn",
        input_data={"answer_text": body.answer_text},
        user_id=str(user.id),
        session_id=str(session.id),
        tags=["assessment", "interview"],
    ) as trace:
        try:
            # Two serial judgment-tier LLM calls (turn_evaluation then question/followup)
            # run inside this graph. Releasing the pooled connection first means twenty
            # concurrent interviews no longer exhaust the pool and stall every other
            # endpoint — everything this handler needs from `session`/`profile` has
            # already been read into `initial_state` above.
            result_state = await without_db_connection(
                db, lambda: get_interview_graph().ainvoke(initial_state)
            )
        except AssessmentUnavailable as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        trace.update(output={"question": result_state["next_question"], "status": result_state["interview_status"]})

    # `session` was loaded before the connection was released; re-attach it so the
    # mutations below are tracked and flushed on commit.
    session = await db.merge(session)

    session.state = {
        "topic_plan": result_state["topic_plan"],
        "current_topic_idx": result_state["current_topic_idx"],
        "transcript": result_state["transcript"],
        "per_topic_scores": result_state["per_topic_scores"],
        "follow_up_count_this_topic": result_state["follow_up_count_this_topic"],
        "job_context": result_state.get("job_context"),
    }

    last_turn = await db.execute(
        select(InterviewTranscriptTurn.turn_index)
        .where(InterviewTranscriptTurn.session_id == session.id)
        .order_by(InterviewTranscriptTurn.turn_index.desc())
        .limit(1)
    )
    last_index = last_turn.scalar_one_or_none()
    next_index = 0 if last_index is None else last_index + 1
    db.add(InterviewTranscriptTurn(session_id=session.id, turn_index=next_index, role="candidate", text=body.answer_text))
    if result_state["next_question"]:
        db.add(
            InterviewTranscriptTurn(
                session_id=session.id, turn_index=next_index + 1, role="agent", text=result_state["next_question"]
            )
        )

    if result_state["interview_status"] == "completed":
        session.status = "completed"
        session.ended_at = datetime.now(timezone.utc)

    await db.commit()

    return {
        "session_id": session.id,
        "question": result_state["next_question"],
        "topics_remaining": len(result_state["topic_plan"]) - result_state["current_topic_idx"],
        "status": result_state["interview_status"],
    }


@router.post("/interview-sessions/{session_id}/end", response_model=InterviewReportWithTranscriptResponse)
async def end_interview(
    session_id: uuid.UUID,
    user: User = Depends(require_role("candidate")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    session, _ = await _session_owned_by(db, session_id, user)

    saved = session.state or {}
    if saved.get("mode") == "avatar" and session.status == "in_progress":
        try:
            avatar_turns = await without_db_connection(db, lambda: _collect_avatar_transcript(saved))
        except trugen.TrugenUnavailable as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="avatar_transcript_unavailable") from exc
        session = await db.merge(session)
        if not any(t["role"] == "candidate" and t["text"] != _AVATAR_KICKOFF for t in avatar_turns):
            # Nothing the candidate said reached the transcript (they ended before
            # answering, or the call never connected). Scoring that would put a fabricated
            # report in front of a recruiter, so the session stays open to resume instead.
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="interview_transcript_empty")

        await db.execute(
            InterviewTranscriptTurn.__table__.delete().where(InterviewTranscriptTurn.session_id == session.id)
        )
        for index, turn in enumerate(avatar_turns):
            db.add(InterviewTranscriptTurn(session_id=session.id, turn_index=index, role=turn["role"], text=turn["text"]))
        saved = {**saved, "transcript": avatar_turns}
        session.state = saved
        await db.commit()
        if saved.get("trugen_agent_id"):
            await trugen.delete_agent(saved["trugen_agent_id"])

    report_state: InterviewReportState = {
        "transcript": saved.get("transcript", []),
        "per_topic_scores": saved.get("per_topic_scores", {}),
        "topic_plan": saved.get("topic_plan", []),
        "response_confidence_signal": None,
        "technical_rating": None,
        "communication_rating": None,
        "hiring_recommendation": None,
    }
    with start_agent_trace(
        "assessment.interview.report",
        input_data={"topic_count": len(saved.get("topic_plan", []))},
        user_id=str(user.id),
        session_id=str(session.id),
        tags=["assessment", "interview"],
    ) as trace:
        try:
            result_state = await without_db_connection(
                db, lambda: get_interview_report_graph().ainvoke(report_state)
            )
        except AssessmentUnavailable as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        trace.update(output=dict(result_state))

    session = await db.merge(session)
    if session.status != "completed":
        session.status = "completed"
        session.ended_at = datetime.now(timezone.utc)

    report = InterviewReport(
        session_id=session.id,
        response_confidence_signal=result_state["response_confidence_signal"],
        technical_rating=result_state["technical_rating"],
        communication_rating=result_state["communication_rating"],
        hiring_recommendation=result_state["hiring_recommendation"],
    )
    db.add(report)

    settings = get_settings()
    interview_input = {"topic_count": len(saved.get("topic_plan", []))}
    interview_output = dict(result_state)
    db.add(
        AgentRun(
            agent_name="interview_report_agent",
            subject_type="interview_session",
            subject_id=session.id,
            input_ref=interview_input,
            output=interview_output,
            model_used=settings.llm_model_judgment,
            langfuse_trace_id=trace.trace_id,
        )
    )
    await db.commit()
    await db.refresh(report)

    transcript_result = await db.execute(
        select(InterviewTranscriptTurn)
        .where(InterviewTranscriptTurn.session_id == session.id)
        .order_by(InterviewTranscriptTurn.turn_index)
    )
    transcript_rows = transcript_result.scalars().all()

    return {
        "id": report.id,
        "session_id": report.session_id,
        "response_confidence_signal": report.response_confidence_signal,
        "technical_rating": report.technical_rating,
        "communication_rating": report.communication_rating,
        "hiring_recommendation": report.hiring_recommendation,
        "generated_at": report.generated_at,
        "transcript": transcript_rows,
    }


@router.get("/interview-sessions/{session_id}/report", response_model=InterviewReportWithTranscriptResponse)
async def get_interview_report(
    session_id: uuid.UUID,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Read a finished interview's report and full transcript.

    Scoped to the recruiter who owns the interview definition the session ran against —
    the same rule `_definition_owned_by` applies to `/interview-definitions/{id}/attempts`,
    which is the list this report is opened from. Without it the role check was the only
    gate, so any recruiter could read any candidate's transcript and hiring
    recommendation on the platform by session UUID.

    Sessions with no `interview_definition_id` (candidate self-practice runs, started
    from a bare topic plan) have no owning recruiter to check against. Those are not a
    recruiter's to read at all, so they are refused rather than left open.
    """
    session = (
        await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interview_session_not_found")
    if session.interview_definition_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_interview_session")
    await _definition_owned_by(db, session.interview_definition_id, user)

    result = await db.execute(
        select(InterviewReport).where(InterviewReport.session_id == session_id).order_by(InterviewReport.generated_at.desc())
    )
    report = result.scalars().first()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interview_report_not_found")

    transcript_result = await db.execute(
        select(InterviewTranscriptTurn)
        .where(InterviewTranscriptTurn.session_id == session_id)
        .order_by(InterviewTranscriptTurn.turn_index)
    )
    return {
        "id": report.id,
        "session_id": report.session_id,
        "response_confidence_signal": report.response_confidence_signal,
        "technical_rating": report.technical_rating,
        "communication_rating": report.communication_rating,
        "hiring_recommendation": report.hiring_recommendation,
        "generated_at": report.generated_at,
        "transcript": transcript_result.scalars().all(),
    }


@router.post("/contribution-reports/generate", response_model=list[ContributionReportResponse])
async def generate_contribution_report(
    body: ContributionReportGenerateRequest,
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> list[ContributionReport]:
    initial_state: ContributionState = {
        "repo_full_name": body.repo_full_name,
        "github_usernames": body.github_usernames,
        "access_token": None,
        "raw_stats": {},
        "shares": {},
        "narratives": {},
        "results": [],
    }
    with start_agent_trace(
        "assessment.contribution_report",
        input_data={"repo_full_name": body.repo_full_name, "member_count": len(body.github_usernames)},
        user_id=str(user.id),
        tags=["assessment", "contribution"],
    ) as trace:
        try:
            # GitHub crawl + per-member LLM narratives — the longest-held connection in
            # this router before this change.
            result_state = await without_db_connection(
                db, lambda: get_contribution_graph().ainvoke(initial_state)
            )
        except AssessmentUnavailable as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        trace.update(output={"results": result_state["results"]})

    profiles_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.github_username.in_(body.github_usernames))
    )
    profile_by_username = {p.github_username: p for p in profiles_result.scalars().all()}

    rows: list[ContributionReport] = []
    for r in result_state["results"]:
        matched_profile = profile_by_username.get(r["github_username"])
        row = ContributionReport(
            repo_full_name=body.repo_full_name,
            candidate_id=matched_profile.id if matched_profile else None,
            github_username=r["github_username"],
            contribution_share=r["contribution_share"],
            commits=r["commits"],
            lines_survived=r["lines_survived"],
            prs_opened=r["prs_opened"],
            prs_reviewed=r["prs_reviewed"],
            anomaly_note=r["anomaly_note"],
        )
        db.add(row)
        rows.append(row)

    settings = get_settings()
    contribution_input = {"repo_full_name": body.repo_full_name, "member_count": len(body.github_usernames)}
    contribution_output = {"results": result_state["results"]}
    db.add(
        AgentRun(
            agent_name="contribution_weighting_agent",
            subject_type="repo",
            subject_id=uuid.uuid5(uuid.NAMESPACE_URL, body.repo_full_name),
            input_ref=contribution_input,
            output=contribution_output,
            model_used=settings.embedding_model,
            langfuse_trace_id=trace.trace_id,
        )
    )
    # `generated_at` is a server-side default, so the rows do need to be re-read after
    # commit — but as one query, not `db.refresh()` per row (which was a round trip each).
    await db.commit()
    if rows:
        await db.execute(
            select(ContributionReport).where(ContributionReport.id.in_([r.id for r in rows]))
        )
    return rows


@router.get("/contribution-reports", response_model=list[ContributionReportResponse])
async def list_contribution_reports(
    repo_full_name: str = Query(...),
    user: User = Depends(require_role("recruiter")),
    db: AsyncSession = Depends(get_db),
) -> list[ContributionReport]:
    result = await db.execute(
        select(ContributionReport)
        .where(ContributionReport.repo_full_name == repo_full_name)
        .order_by(ContributionReport.contribution_share.desc())
    )
    return list(result.scalars().all())
