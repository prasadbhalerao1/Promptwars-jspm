"""Salary Predictions — FR-4.4. Gradient-boosted quantile regression trained on the
public Stack Overflow Developer Survey (doc 01 §8), always returned as a `[low, high]`
range — never a point estimate, to avoid false precision.

Real inference code against a trained model artifact produced by
`train_salary_model.py` (run once, offline, against a downloaded Developer Survey
CSV — see that script's docstring). Same "write the real integration code, raise a
clear typed error rather than fabricate" convention as `tools/resume.py` /
`services/api/core/storage.py`: if the artifact isn't on disk yet, this raises
`SalaryModelUnavailable` rather than guessing a number.

**Talent Score caveat (disclosed, not hidden):** doc 01 §8 lists "talent score" as one
of the regression's features, but the Stack Overflow survey obviously has no such
column — it's this platform's own derived metric, so there's no ground truth to train
against for it directly. The base model is trained on real survey features only
(role, location, years-of-experience-proxy); `talent_score` is then applied as a
disclosed post-hoc adjustment (+/-15% max, linear around a 50-point baseline) rather
than a fabricated training column. See `.agents/decisions.md` for the full reasoning.
"""

import os
from dataclasses import dataclass

import joblib

from services.api.core.config import get_settings

# How much a Talent Score above/below the 50-point baseline can shift the predicted
# range, applied symmetrically to both ends. Deliberately mild — this is a disclosed
# heuristic bridging model and product, not a trained coefficient.
_TALENT_SCORE_MAX_ADJUSTMENT = 0.15
_TALENT_SCORE_BASELINE = 50.0


class SalaryModelUnavailable(RuntimeError):
    """Raised when the trained salary regression artifact isn't present on disk."""


@dataclass
class SalaryRangeResult:
    low: int
    high: int
    currency: str
    rationale: str


_cached_artifact = None


def _load_artifact() -> dict:
    global _cached_artifact
    if _cached_artifact is not None:
        return _cached_artifact

    settings = get_settings()
    path = settings.salary_model_path
    if not os.path.exists(path):
        raise SalaryModelUnavailable(
            f"No trained salary model found at '{path}'. Run "
            "services/agents/candidate_intelligence/tools/train_salary_model.py against a "
            "downloaded Stack Overflow Developer Survey CSV (survey.stackoverflow.co) to "
            "produce it, then set SALARY_MODEL_PATH if you saved it elsewhere."
        )
    _cached_artifact = joblib.load(path)
    return _cached_artifact


def _encode(value: str | None, encoder: dict[str, int]) -> int:
    if value is None:
        return encoder.get("__other__", 0)
    return encoder.get(value, encoder.get("__other__", 0))


def predict_salary_range(
    role: str,
    location: str | None,
    years_experience_proxy: float,
    talent_score: float,
) -> SalaryRangeResult:
    artifact = _load_artifact()
    low_model = artifact["low_model"]
    high_model = artifact["high_model"]
    role_encoder: dict[str, int] = artifact["role_encoder"]
    location_encoder: dict[str, int] = artifact["location_encoder"]

    features = [[
        _encode(role, role_encoder),
        _encode(location, location_encoder),
        years_experience_proxy,
    ]]

    base_low = float(low_model.predict(features)[0])
    base_high = float(high_model.predict(features)[0])
    if base_high < base_low:
        base_low, base_high = base_high, base_low

    adjustment = max(
        -_TALENT_SCORE_MAX_ADJUSTMENT,
        min(_TALENT_SCORE_MAX_ADJUSTMENT, (talent_score - _TALENT_SCORE_BASELINE) / _TALENT_SCORE_BASELINE),
    )
    low = base_low * (1 + adjustment)
    high = base_high * (1 + adjustment)

    return SalaryRangeResult(
        low=max(0, int(round(low, -3))),
        high=max(0, int(round(high, -3))),
        currency="USD",
        rationale=(
            "Gradient-boosted quantile regression (25th/75th percentile, per doc/SRS/01 §7) "
            f"trained on the Stack Overflow Developer Survey; base features: role={role}, "
            f"location={location or 'unspecified'}, years_experience_proxy={years_experience_proxy:.1f}; "
            f"Talent Score {talent_score:.0f}/100 applied as a {adjustment:+.0%} adjustment "
            "(disclosed heuristic — the survey has no Talent Score ground truth to train against)."
        ),
    )
