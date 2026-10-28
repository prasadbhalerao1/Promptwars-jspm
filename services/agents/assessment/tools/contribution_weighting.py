"""Contribution Weighting Agent — FR-3.2, doc 03 §7's exact formula:

    contribution_share(member) = normalize(
        0.35 * lines_changed_that_survive_to_HEAD
      + 0.25 * commits_count
      + 0.20 * PRs_opened_and_merged
      + 0.20 * PR_reviews_given
    )

Rules only (the share itself) plus an optional Haiku narrative summary. Implementation
detail not specified by the doc: each raw component is first min-max scaled against the
team's own max for that component (0-1) before the weights are applied — otherwise
`lines_survived` (often hundreds) would numerically dominate `commits_count` (often
single digits) regardless of the stated weights, making them meaningless. Final shares
are then normalized to sum to 1 across the team, per the formula's own "normalize(...)".
The report always includes the raw components alongside the share (doc 03 §7), so a
recruiter can see exactly why.
"""

from services.agents.assessment.tools.github_contribution import MemberCommitStats

W_LINES = 0.35
W_COMMITS = 0.25
W_PRS_OPENED = 0.20
W_PRS_REVIEWED = 0.20

# doc 03 §3.3: a member with genuinely zero attributable signal is flagged as a report
# note for human review, never an automatic penalty beyond their (correctly) near-zero share.
_ZERO_CONTRIBUTION_NOTE = (
    "No attributable commits, PRs, or reviews found for this member on this repo — "
    "flagged for human review, not an automatic penalty."
)

# A zero caused by a failed GitHub lookup must never be reported with the note above.
# That note is a finding about a person; a rate-limit blip is a fact about our data
# collection, and conflating the two turned a transient API error into a human-facing
# claim that a real team member contributed nothing.
_INCOMPLETE_DATA_NOTE = (
    "GitHub data for this member could not be fully retrieved (API error or rate limit), "
    "so their contribution could not be measured. This is not a finding about their work."
)


def _scale(value: int, team_max: int) -> float:
    if team_max <= 0:
        return 0.0
    return value / team_max


def compute_shares(stats_by_username: dict[str, MemberCommitStats]) -> dict[str, dict]:
    """Returns username -> {share, raw: {...}, anomaly_note}."""
    if not stats_by_username:
        return {}

    max_lines = max((s.lines_survived for s in stats_by_username.values()), default=0)
    max_commits = max((s.commits for s in stats_by_username.values()), default=0)
    max_prs_opened = max((s.prs_opened for s in stats_by_username.values()), default=0)
    max_prs_reviewed = max((s.prs_reviewed for s in stats_by_username.values()), default=0)

    weighted: dict[str, float] = {}
    for username, s in stats_by_username.items():
        weighted[username] = (
            W_LINES * _scale(s.lines_survived, max_lines)
            + W_COMMITS * _scale(s.commits, max_commits)
            + W_PRS_OPENED * _scale(s.prs_opened, max_prs_opened)
            + W_PRS_REVIEWED * _scale(s.prs_reviewed, max_prs_reviewed)
        )

    total = sum(weighted.values())
    results: dict[str, dict] = {}
    for username, s in stats_by_username.items():
        share = (weighted[username] / total) if total > 0 else 0.0
        is_zero = s.commits == 0 and s.prs_opened == 0 and s.prs_reviewed == 0
        incomplete = getattr(s, "data_incomplete", False)
        if incomplete:
            anomaly_note = _INCOMPLETE_DATA_NOTE
        elif is_zero:
            anomaly_note = _ZERO_CONTRIBUTION_NOTE
        else:
            anomaly_note = None

        results[username] = {
            "share": round(share, 4),
            "raw": {
                "commits": s.commits,
                "lines_survived": s.lines_survived,
                "prs_opened": s.prs_opened,
                "prs_reviewed": s.prs_reviewed,
            },
            "data_incomplete": incomplete,
            "anomaly_note": anomaly_note,
        }
    return results
