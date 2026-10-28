"""Fraud Risk Report Agent — doc 06 §4, "Sonnet, writes the human-readable report
strictly from `signals`/evidence — never adds unsupported claims". FR-7.

The report text is a NARRATIVE LAYER on top of the already-complete structured evidence
(the `verification_records`/`fraud_flags.evidence` rows always exist and are always
sufficient on their own — this just makes them readable for a human reviewer). If Sonnet
is unavailable (no API key, API error), a flag is still raised with a deterministic
template built directly from the evidence dict — a missing LLM narrative must never
block or weaken the actual evidence-bearing flag (doc 06 §11: "every fraud_flags row
must have non-null evidence" — that requirement doesn't depend on this agent working).
"""

import json
import logging

logger = logging.getLogger(__name__)

from services.api.core.config import get_settings
from services.api.core.llm import LLMUnavailable, generate_structured

_REPORT_PARAMETERS = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "One or two sentences summarizing the concern, citing the specific evidence only.",
        },
        "cited_evidence": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The exact evidence strings this summary is grounded in — must be a subset of the input evidence, never invented.",
        },
    },
    "required": ["summary", "cited_evidence"],
}

_GROUNDING_RULE = (
    "You are writing a fraud risk report for a human reviewer. You must write STRICTLY "
    "from the evidence provided below — never add claims, motives, or conclusions not "
    "directly supported by it. This is the highest ethical-risk part of the platform: a "
    "false accusation can end a candidate's opportunity unfairly. Frame this as "
    "'evidence to review,' never as a guilt verdict. If the evidence is weak or "
    "ambiguous, say so plainly rather than overstating it."
)


def _deterministic_fallback(flag_type: str, evidence_items: list[str]) -> dict:
    """Placeholder used when no provider is reachable, explicitly marked as such.

    `summary_generated=False` is the important part. This template previously landed in
    the same `summary` field as real LLM analysis with nothing distinguishing them, so a
    reviewer reading "Fake Certificate signal raised for review" could not tell whether it
    was a considered judgment or a stub — in the one module where that distinction most
    affects a person. The flag itself must still be raised (a missing narrative is not a
    reason to drop a fraud signal), so this degrades rather than blocking, but it degrades
    visibly.
    """
    return {
        "summary": f"{flag_type.replace('_', ' ').title()} signal raised for review. See cited evidence.",
        "cited_evidence": evidence_items,
        "summary_generated": False,
    }


def _enforce_evidence_subset(result: dict, evidence_items: list[str], flag_type: str) -> dict:
    """Drop any `cited_evidence` string that was not in the supplied evidence.

    The schema description tells the model this must be a subset "never invented", but a
    description is not a constraint and nothing checked it. An invented citation in a
    fraud flag is a fabricated basis for an accusation against a real person, which is
    exactly what this module's prompt spends its length forbidding — so it is enforced
    here rather than trusted.

    Invented citations are removed rather than raising: the real evidence is still worth
    showing a reviewer, and failing the whole report would drop the flag entirely.
    """
    supplied = set(evidence_items)
    cited = result.get("cited_evidence") or []
    kept = [item for item in cited if item in supplied]
    invented = [item for item in cited if item not in supplied]
    if invented:
        logger.warning(
            "fraud.risk_report cited %d evidence string(s) not in the input for flag_type=%s; dropped: %r",
            len(invented), flag_type, invented,
        )
    result["cited_evidence"] = kept
    return result


async def generate_fraud_risk_report(flag_type: str, evidence_items: list[str]) -> dict:
    """Returns {summary, cited_evidence}. Falls back to a deterministic template (never
    raises) if the configured provider is unavailable — matches every other module's
    "typed unavailable, degrade gracefully, never fabricate OR block" pattern."""
    from services.agents.prompts_loader import load_prompt

    prompt = load_prompt(
        "fraud",
        "risk_report",
        flag_type=flag_type,
        evidence_json=json.dumps(evidence_items, indent=2),
    )
    try:
        result = await generate_structured(
            schema_name="fraud_risk_report",
            schema_description="A structured, evidence-linked fraud risk report for one flagged signal.",
            parameters=_REPORT_PARAMETERS,
            prompt=prompt,
            max_tokens=get_settings().llm_max_tokens_default,
            agent_name="fraud.risk_report",
        )
    except LLMUnavailable:
        return _deterministic_fallback(flag_type, evidence_items)

    result = _enforce_evidence_subset(result, evidence_items, flag_type)
    result["summary_generated"] = True
    return result
