"""AI Interview Agent's four LLM steps (FR-2.1/2.2/2.3/2.4, judgment-tier per doc 03 §5 —
adapting difficulty and judging answer quality both need real reasoning, not
extraction-tier speed). Routed through `services.api.core.llm.generate_structured` —
see `assessment/tools/llm_review.py` for the same pattern.
"""

import json

from services.agents.assessment.tools.llm_review import AssessmentUnavailable
from services.api.core.llm import generate_structured
from services.api.core.config import get_settings

__all__ = ["AssessmentUnavailable", "generate_question", "evaluate_turn", "generate_followup", "generate_interview_report", "generate_definition_questions"]

_DEFINITION_QUESTIONS_PARAMETERS = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of interview topic phrases, ordered by difficulty.",
        }
    },
    "required": ["topics"],
}

_QUESTION_PARAMETERS = {
    "type": "object",
    "properties": {"question": {"type": "string"}},
    "required": ["question"],
}

_TURN_EVAL_PARAMETERS = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "description": "0-100, this answer's quality on this topic"},
        "verdict": {
            "type": "string",
            "enum": ["weak", "sufficient"],
            "description": "'weak' if the answer was vague, evasive, or missed the core of the question and deserves a follow-up; 'sufficient' if it substantively addressed the question, even if imperfect.",
        },
        "hedging_detected": {
            "type": "boolean",
            "description": "true if the answer relied on hedging language ('I think', 'maybe', 'not totally sure') rather than concrete specifics.",
        },
        "specificity": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "How concrete/specific the answer was (named tools, real numbers, actual tradeoffs) vs. generic.",
        },
    },
    "required": ["score", "verdict", "hedging_detected", "specificity"],
}

_FOLLOWUP_PARAMETERS = {
    "type": "object",
    "properties": {"question": {"type": "string"}},
    "required": ["question"],
}

_REPORT_PARAMETERS = {
    "type": "object",
    "properties": {
        "technical_rating": {"type": "number", "description": "0-100"},
        "communication_rating": {
            "type": "number",
            "description": "0-100, based ONLY on transcript signals: clarity, structure, filler-word/hedging rate. Never infer from tone or vocal delivery — there is none, this is text.",
        },
        "response_confidence_signal": {
            "type": "number",
            "description": "0-100, derived from hedging-language frequency and answer specificity/structure across the transcript — NOT a guess at the candidate's emotional confidence.",
        },
        "hiring_recommendation": {
            "type": "string",
            "description": "2-4 sentences of advisory rationale a recruiter can inspect and disagree with — never a bare pass/fail verdict, never a single word.",
        },
    },
    "required": [
        "technical_rating",
        "communication_rating",
        "response_confidence_signal",
        "hiring_recommendation",
    ],
}


# How many of the most recent transcript turns to send verbatim when asking the next
# question. The prompt only needs history for two things — "show awareness of what's been
# discussed" and "avoid repetition" — and both are served by the recent turns plus a list
# of the earlier topics.
#
# Sending the whole transcript made cost quadratic in interview length: turn N re-sent
# every prior turn, so a 20-turn interview paid for ~210 turn-renderings instead of 20.
# Long answers made it worse, since each one was resent on every subsequent question.
_MAX_VERBATIM_TURNS = get_settings().interview_max_verbatim_turns
# Truncation ceiling for a single answer. A candidate pasting a large block (a stack
# trace, a whole file) would otherwise blow up every later prompt that includes it.
_MAX_TURN_CHARS = get_settings().interview_max_turn_chars


def _render_history(transcript: list[dict]) -> str:
    """Bounded rendering of the interview so far.

    Recent turns go in verbatim; everything older collapses to a one-line summary of the
    questions already asked, which is what the "avoid repetition" instruction actually
    needs. Returns the same "(interview just starting)" sentinel as before for an empty
    transcript, so the prompt reads identically on the first question.
    """
    if not transcript:
        return "(interview just starting)"

    def render(turn: dict) -> str:
        text = (turn.get("text") or "").strip()
        if len(text) > _MAX_TURN_CHARS:
            text = text[:_MAX_TURN_CHARS] + " … [truncated]"
        return f"{turn.get('role')}: {text}"

    if len(transcript) <= _MAX_VERBATIM_TURNS:
        return "\n".join(render(t) for t in transcript)

    older, recent = transcript[:-_MAX_VERBATIM_TURNS], transcript[-_MAX_VERBATIM_TURNS:]
    asked = [
        (t.get("text") or "").strip()
        for t in older
        if t.get("role") == "agent" and (t.get("text") or "").strip()
    ]
    lines = []
    if asked:
        summarized = "; ".join(q[:120] for q in asked)
        lines.append(f"(earlier in this interview, already asked: {summarized})")
    else:
        lines.append(f"({len(older)} earlier turn(s) omitted)")
    lines.extend(render(t) for t in recent)
    return "\n".join(lines)


async def generate_question(topic: str, candidate_profile_summary: str, transcript: list[dict], job_context: dict | None = None) -> str:
    import logging
    from services.agents.prompts_loader import load_prompt

    logger = logging.getLogger(__name__)

    history = _render_history(transcript)

    role_context_section = ""
    if job_context:
        role_context_section = f"""## Role Context

**Role Title:** {job_context.get('role_title', 'Not specified')}

**Job Description:** {job_context.get('job_description', 'Not specified')}

**Expected Experience:** {job_context.get('years_experience', 'Not specified')} years
"""

    prompt = load_prompt(
        "assessment",
        "generate_question",
        topic=topic,
        candidate_profile_summary=candidate_profile_summary,
        conversation_history=history,
        role_context_section=role_context_section,
    )

    logger.info(f"Generating question for topic: {topic}")
    logger.debug(f"Prompt:\n{prompt}")

    try:
        result = await generate_structured(
            schema_name="interview_question",
            schema_description="The next interview question to ask the candidate.",
            parameters=_QUESTION_PARAMETERS,
            prompt=prompt,
            max_tokens=256,
            agent_name="assessment.interview.question",
        )
        logger.info(f"Question generated: {result.get('question', '?')}")
        return result["question"]
    except Exception as e:
        logger.error(f"Failed to generate question: {e}", exc_info=True)
        raise


async def evaluate_turn(topic: str, question: str, answer: str) -> dict:
    from services.agents.prompts_loader import load_prompt

    prompt = load_prompt(
        "assessment",
        "evaluate_turn",
        topic=topic,
        question=question,
        answer=answer,
    )
    return await generate_structured(
        schema_name="turn_evaluation",
        schema_description="Evaluation of the candidate's most recent answer against the current topic.",
        parameters=_TURN_EVAL_PARAMETERS,
        prompt=prompt,
        max_tokens=512,
        agent_name="assessment.interview.evaluate_turn",
    )


async def generate_followup(topic: str, question: str, answer: str) -> str:
    from services.agents.prompts_loader import load_prompt

    prompt = load_prompt(
        "assessment",
        "generate_followup",
        topic=topic,
        question=question,
        answer=answer,
    )
    result = await generate_structured(
        schema_name="followup_question",
        schema_description="A targeted follow-up question probing the weak spot in the candidate's last answer.",
        parameters=_FOLLOWUP_PARAMETERS,
        prompt=prompt,
        max_tokens=256,
        agent_name="assessment.interview.followup",
    )
    return result["question"]


async def generate_definition_questions(
    role_title: str, job_description: str, years_experience: int | None, question_count: int
) -> list[str]:
    from services.agents.prompts_loader import load_prompt

    prompt = load_prompt(
        "assessment",
        "generate_definition_questions",
        role_title=role_title,
        job_description=job_description,
        years_experience=str(years_experience) if years_experience else "not specified",
        question_count=str(question_count),
    )
    result = await generate_structured(
        schema_name="definition_questions",
        schema_description="Drafted interview topics for a recruiter-authored interview definition.",
        parameters=_DEFINITION_QUESTIONS_PARAMETERS,
        prompt=prompt,
        max_tokens=512,
        agent_name="assessment.interview.definition_questions",
    )

    # The JSON schema guarantees a list of strings; it cannot guarantee the list is
    # non-empty or that entries are meaningful. An empty topic plan is not a degraded
    # interview, it is an unrunnable one — every downstream node indexes into it — so
    # fail here with a typed error rather than persisting a definition that breaks the
    # moment a candidate opens it.
    topics = [t.strip() for t in result.get("topics", []) if isinstance(t, str) and t.strip()]
    if not topics:
        raise AssessmentUnavailable(
            "The model returned no usable interview topics. Try again, or give a more "
            "detailed job description."
        )
    # The prompt asks for exactly `question_count`; models occasionally overshoot. Trim
    # rather than reject — extra topics are still valid, just more than was asked for.
    return topics[:question_count]


def _render_report_history(transcript: list[dict]) -> str:
    """Render the full transcript for the report, with each turn length-capped.

    Unlike `_render_history`, which drops older turns because the next *question* only
    needs recent context, the report summarizes the whole interview — so every turn is
    kept. What is bounded is per-turn length: one pasted file must not crowd out the
    other nineteen answers."""
    if not transcript:
        return "(no transcript recorded)"

    lines = []
    for turn in transcript:
        text = (turn.get("text") or "").strip()
        if len(text) > _MAX_TURN_CHARS:
            text = text[:_MAX_TURN_CHARS] + f"... [truncated, {len(text)} chars total]"
        lines.append(f"{turn.get('role', 'unknown')}: {text}")
    return chr(10).join(lines)


async def generate_interview_report(transcript: list[dict], per_topic_scores: dict[str, float]) -> dict:
    from services.agents.prompts_loader import load_prompt

    # Bounded via `_render_report_history` rather than joining the raw transcript. The
    # per-turn path has always truncated (see `_render_history` above), but this call
    # concatenated every turn verbatim — so a long interview, or one where a candidate
    # pasted a stack trace, sent an unbounded prompt into a fixed `max_tokens` call and
    # could exceed the context window outright. The report needs the whole interview, so
    # this bounds per-turn length rather than dropping turns.
    history = _render_report_history(transcript)
    prompt = load_prompt(
        "assessment",
        "interview_report",
        per_topic_scores_json=json.dumps(per_topic_scores),
        transcript_history=history,
    )
    return await generate_structured(
        schema_name="interview_report",
        schema_description="Final interview report synthesized from the full transcript.",
        parameters=_REPORT_PARAMETERS,
        prompt=prompt,
        max_tokens=get_settings().llm_max_tokens_default,
        agent_name="assessment.interview.report",
    )
