"""Hackathon performance scoring — combines platform-run results + self-reported experience."""

from packages.shared_schemas.candidates import SubScore


# Base scores per result tier (never negative, no penalties)
RESULT_TIER_SCORES = {
    "winner": 100.0,
    "top5": 75.0,
    "finalist": 50.0,
    "participant": 25.0,
}

# Default weight for platform-run hackathons (already verified by platform)
PLATFORM_WEIGHT = 1.0

# Clamp user-input weight to reasonable range so one entry can't dominate
MIN_WEIGHT = 0.2
MAX_WEIGHT = 1.0


def normalize_weight(weight: float) -> float:
    """Clamp user-input weight to [MIN_WEIGHT, MAX_WEIGHT] range.

    Converts 1-5 scale or any numeric input to a normalized 0.2-1.0 range.
    This prevents a single high-importance entry from overwhelming the score.
    """
    if weight is None:
        return PLATFORM_WEIGHT

    # If weight is 1-5 scale, normalize to 0.2-1.0
    if 1 <= weight <= 5:
        return MIN_WEIGHT + (weight - 1) * (MAX_WEIGHT - MIN_WEIGHT) / 4

    # If already 0-1 scale, clamp it
    return max(MIN_WEIGHT, min(MAX_WEIGHT, float(weight)))


def hackathon_performance(
    platform_results: list[dict] | None = None,
    self_reported: list[dict] | None = None,
) -> SubScore:
    """Score hackathon performance from both platform-run events and self-reported entries.

    Platform results come from HackathonRanking/HackathonTeamMember (rank → tier).
    Self-reported entries are from CandidateProfile.hackathon_experience (user-input).

    Scoring logic:
    - Each entry: base_score(tier) * normalized_weight, capped at 100 per entry
    - Combine across all entries: best 5 + average of rest, saturated at 100
    - Never negative (cold-start when both lists empty → None)
    """
    if not platform_results and not self_reported:
        return SubScore(
            value=None,
            rationale="No hackathon participation found — cold start.",
        )

    entries = []

    # Platform-run hackathons: derive tier from rank
    if platform_results:
        for result in platform_results:
            rank = result.get("rank")
            if rank is None:
                continue

            # Tier mapping: rank 1 = winner, 2-5 = top5, 6-10 = finalist, 11+ = participant
            if rank == 1:
                tier = "winner"
            elif 2 <= rank <= 5:
                tier = "top5"
            elif 6 <= rank <= 10:
                tier = "finalist"
            else:
                tier = "participant"

            base_score = RESULT_TIER_SCORES.get(tier, 0.0)
            weighted_score = base_score * PLATFORM_WEIGHT
            entries.append({
                "score": min(100.0, weighted_score),
                "source": "platform",
                "tier": tier,
                "rank": rank,
            })

    # Self-reported hackathons
    if self_reported:
        for entry in self_reported:
            result = entry.get("result", "participant")
            weight = entry.get("weight", 1.0)

            base_score = RESULT_TIER_SCORES.get(result, 0.0)
            normalized_w = normalize_weight(weight)
            weighted_score = base_score * normalized_w

            entries.append({
                "score": min(100.0, weighted_score),
                "source": "self-reported",
                "tier": result,
                "name": entry.get("name", "Unknown"),
            })

    if not entries:
        return SubScore(
            value=None,
            rationale="No valid hackathon entries found — cold start.",
        )

    # Combine scores: sort descending, take best 5, average the rest
    # This prevents one high-tier entry from saturating, while rewarding breadth
    scores = sorted([e["score"] for e in entries], reverse=True)

    if len(scores) <= 5:
        # All entries: simple average
        combined = sum(scores) / len(scores)
    else:
        # Best 5 + average of rest (with slight diminishing weight to encourage quality over quantity)
        best_5_sum = sum(scores[:5])
        rest_avg = sum(scores[5:]) / len(scores[5:])
        combined = (best_5_sum / 5) * 0.7 + rest_avg * 0.3  # 70% best, 30% breadth

    final_score = min(100.0, combined)

    return SubScore(
        value=round(final_score, 1),
        rationale=(
            f"{len(entries)} hackathon(s) recorded "
            f"({sum(1 for e in entries if e['source'] == 'platform')} platform, "
            f"{sum(1 for e in entries if e['source'] == 'self-reported')} self-reported)."
        ),
    )
