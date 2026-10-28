"""Offline trainer for the FR-4.4 salary regression artifact — NOT imported by app code
at runtime (only `salary_model.py`'s `predict_salary_range` loads the resulting
joblib file). Run this once, manually, after downloading the public Stack Overflow
Developer Survey CSV:

    1. Download the "Stack Overflow Annual Developer Survey" results CSV from
       https://survey.stackoverflow.co/ (genuine public dataset, per doc 01 §8 — no
       other salary-data source is used).
    2. Save it somewhere, e.g. `data/stack_overflow_survey.csv`.
    3. Run:
           uv run --python services/api/.venv python -m \
               services.agents.candidate_intelligence.tools.train_salary_model \
               --csv data/stack_overflow_survey.csv \
               --out data/models/salary_regressor.joblib
    4. Set SALARY_MODEL_PATH (or leave the default `data/models/salary_regressor.joblib`)
       so `services/api/core/config.py` picks it up.

This could not be run in this environment — no survey CSV is present in the repo (it's
several hundred MB and under Stack Overflow's own redistribution terms, so it isn't
checked in). `predict_salary_range` raises `SalaryModelUnavailable` until someone runs
this script for real.

Expected survey columns (2023/2024 schema — adjust `--role-col`/`--location-col`/
`--experience-col`/`--salary-col` if a different survey year renames them):
  - DevType            (role — comma-separated multi-select, first value used)
  - Country            (location)
  - YearsCodePro       (years-of-experience-proxy)
  - ConvertedCompYearly (salary, already USD-normalized by Stack Overflow)

Trains two GradientBoostingRegressor models with quantile loss (alpha=0.25 and 0.75 —
doc/SRS/01 §7's own example range) so inference returns a genuine prediction interval,
not a point estimate +/- a guessed margin. `talent_score` is deliberately NOT a
training feature — see salary_model.py's module docstring for why (no ground truth for
it exists in the survey).
"""

import argparse
import csv
from collections import Counter

import joblib
from sklearn.ensemble import GradientBoostingRegressor

_TOP_N_CATEGORIES = 25  # keep the N most frequent roles/locations, bucket the rest as __other__
_MIN_SALARY = 5_000
_MAX_SALARY = 1_000_000


def _build_encoder(values: list[str]) -> dict[str, int]:
    counts = Counter(values)
    top = [name for name, _ in counts.most_common(_TOP_N_CATEGORIES)]
    encoder = {name: i + 1 for i, name in enumerate(top)}
    encoder["__other__"] = 0
    return encoder


def _encode(value: str, encoder: dict[str, int]) -> int:
    return encoder.get(value, encoder.get("__other__", 0))


def load_rows(csv_path: str, role_col: str, location_col: str, experience_col: str, salary_col: str):
    roles, locations, years, salaries = [], [], [], []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                salary = float(row[salary_col])
                exp_years = float(row[experience_col])
            except (KeyError, ValueError, TypeError):
                continue
            if not (_MIN_SALARY <= salary <= _MAX_SALARY):
                continue
            role_raw = (row.get(role_col) or "").split(";")[0].strip()
            location_raw = (row.get(location_col) or "").strip()
            if not role_raw:
                continue
            roles.append(role_raw)
            locations.append(location_raw)
            years.append(exp_years)
            salaries.append(salary)
    return roles, locations, years, salaries


def train(csv_path: str, out_path: str, role_col: str, location_col: str, experience_col: str, salary_col: str) -> None:
    roles, locations, years, salaries = load_rows(csv_path, role_col, location_col, experience_col, salary_col)
    if len(salaries) < 200:
        raise SystemExit(
            f"Only {len(salaries)} usable rows after cleaning — need at least 200 to train a "
            "meaningful model. Check --role-col/--location-col/--experience-col/--salary-col "
            "match this survey year's actual column names."
        )

    role_encoder = _build_encoder(roles)
    location_encoder = _build_encoder(locations)

    features = [
        [_encode(r, role_encoder), _encode(l, location_encoder), y]
        for r, l, y in zip(roles, locations, years)
    ]

    low_model = GradientBoostingRegressor(loss="quantile", alpha=0.25, n_estimators=200, max_depth=3)
    high_model = GradientBoostingRegressor(loss="quantile", alpha=0.75, n_estimators=200, max_depth=3)
    low_model.fit(features, salaries)
    high_model.fit(features, salaries)

    joblib.dump(
        {
            "low_model": low_model,
            "high_model": high_model,
            "role_encoder": role_encoder,
            "location_encoder": location_encoder,
            "trained_on_rows": len(salaries),
        },
        out_path,
    )
    print(f"Trained on {len(salaries)} rows. Artifact saved to {out_path}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Path to the downloaded Stack Overflow Developer Survey CSV")
    parser.add_argument("--out", default="data/models/salary_regressor.joblib")
    parser.add_argument("--role-col", default="DevType")
    parser.add_argument("--location-col", default="Country")
    parser.add_argument("--experience-col", default="YearsCodePro")
    parser.add_argument("--salary-col", default="ConvertedCompYearly")
    args = parser.parse_args()
    train(args.csv, args.out, args.role_col, args.location_col, args.experience_col, args.salary_col)


if __name__ == "__main__":
    main()
