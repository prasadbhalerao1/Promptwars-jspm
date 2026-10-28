"""Interview Report Agent — FR-2.4. Node contract: constraints.md §2.3. Separate
on-demand subgraph (see `interview_report_graph.py`), invoked once when the candidate
calls `POST /interview-sessions/{id}/end` — same pattern as Module 01's
career_guidance_graph being separate from the main ingestion fan-out."""

from services.agents.assessment.state import InterviewReportState
from services.agents.assessment.tools.interview_llm import generate_interview_report
from services.api.core.llm import validated_score


async def run(state: InterviewReportState) -> dict:
    report = await generate_interview_report(state["transcript"], state["per_topic_scores"])
    # All three numeric fields are clamped to their documented 0-100 range before they
    # reach the `InterviewReport` row a recruiter reads as an assessment of a candidate.
    # The JSON schema calls them "0-100", but that is prose the provider is free to
    # ignore, and nothing here previously rejected a 0-10 or 0-1 answer.
    return {
        "response_confidence_signal": validated_score(report.get("response_confidence_signal")),
        "technical_rating": validated_score(report.get("technical_rating")),
        "communication_rating": validated_score(report.get("communication_rating")),
        "hiring_recommendation": report.get("hiring_recommendation"),
    }
