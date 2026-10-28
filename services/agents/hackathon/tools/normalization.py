"""Normalization Agent — doc 05 §4, "Haiku (schema mapping) + rules". Only used for
webhook ingestion (FR-7b): a platform push has no human in the loop to confirm field
mapping, unlike CSV import where the organizer already resolves ambiguous columns in the
client-side SheetJS preview grid before submitting the already-structured
`CSVImportRequest` (doc 05 §8's `CSVImportPreview.tsx`) — so CSV rows need no server-side
normalization pass, only validation.

Rules-first: a small synonym table covers the field-name variance actually documented
across Devpost/Devfolio-style payloads (doc 05 §2). Haiku is only invoked as a fallback
when the raw payload's keys don't match any known synonym for a required field — schema
mapping is a low-stakes extraction task, squarely Haiku-tier per constraints.md §5's
model-routing policy, never Sonnet.
"""

import json
from typing import Any

from packages.shared_schemas.hackathon import TeamMemberInput, TeamSubmissionInput
from services.agents.prompts_loader import load_prompt
from services.api.core.llm import LLMUnavailable, generate_structured

_TEAM_NAME_KEYS = {"team_name", "team", "teamname", "project_team", "squad"}
_TRACK_KEYS = {"track", "category", "tracks"}
_REPO_KEYS = {"repo_url", "repo", "repository", "github_url", "github", "github_link"}
_MEMBERS_KEYS = {"members", "team_members", "participants", "roster"}
_MEMBER_GITHUB_KEYS = {"github_username", "github", "github_handle", "username"}
_MEMBER_NAME_KEYS = {"display_name", "name", "full_name", "participant_name"}
_MEMBER_ROLE_KEYS = {"role", "team_role"}

_SCHEMA_MAPPING_PARAMETERS = {
    "type": "object",
    "properties": {
        "team_name": {"type": "string"},
        "track": {"type": ["string", "null"]},
        "repo_url": {"type": ["string", "null"]},
        "members": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "github_username": {"type": ["string", "null"]},
                    "display_name": {"type": ["string", "null"]},
                },
            },
        },
    },
    "required": ["team_name"],
}

# Raised when rules can't confidently map the payload and the LLM fallback also can't
# run (missing/misconfigured provider key) or fails — never guess a team name out of
# thin air.
NormalizationUnavailable = LLMUnavailable


def _find(raw: dict[str, Any], keys: set[str]) -> Any:
    lowered = {str(k).strip().lower().replace(" ", "_"): v for k, v in raw.items()}
    for key in keys:
        if key in lowered and lowered[key] not in (None, ""):
            return lowered[key]
    return None


def _rule_based_normalize(raw: dict[str, Any]) -> TeamSubmissionInput | None:
    team_name = _find(raw, _TEAM_NAME_KEYS)
    if not team_name:
        return None

    members_raw = _find(raw, _MEMBERS_KEYS) or []
    members = [
        TeamMemberInput(
            github_username=_find(m, _MEMBER_GITHUB_KEYS) if isinstance(m, dict) else None,
            display_name=_find(m, _MEMBER_NAME_KEYS) if isinstance(m, dict) else str(m),
            role=(_find(m, _MEMBER_ROLE_KEYS) if isinstance(m, dict) else None) or "member",
        )
        for m in members_raw
        if m
    ]

    return TeamSubmissionInput(
        team_name=str(team_name),
        track=_find(raw, _TRACK_KEYS),
        members=members,
        repo_url=_find(raw, _REPO_KEYS),
    )


async def _haiku_fallback_normalize(raw: dict[str, Any]) -> TeamSubmissionInput:
    prompt = load_prompt(
        "hackathon", "normalize_submission", raw_payload=json.dumps(raw, default=str)
    )
    data = await generate_structured(
        schema_name="normalized_submission",
        schema_description=(
            "Map an arbitrary hackathon-platform submission payload onto this platform's "
            "fixed team-submission schema. Only extract values that are actually present in "
            "the payload — never invent a team name, repo URL, or member that isn't there."
        ),
        parameters=_SCHEMA_MAPPING_PARAMETERS,
        prompt=prompt,
        is_fast=True,
        agent_name="hackathon.normalization",
    )
    return TeamSubmissionInput(
        team_name=data["team_name"],
        track=data.get("track"),
        members=[
            TeamMemberInput(github_username=m.get("github_username"), display_name=m.get("display_name"))
            for m in data.get("members", [])
        ],
        repo_url=data.get("repo_url"),
    )


async def normalize_webhook_payload(raw: dict[str, Any]) -> TeamSubmissionInput:
    result = _rule_based_normalize(raw)
    if result is not None:
        return result
    return await _haiku_fallback_normalize(raw)
