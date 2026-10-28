"""Verified Credentials sub-score — certificates and resume, weighted by how verifiable each is.

The resume is the least trustworthy input in the pipeline, so it can never carry this
score on its own: claimed experience and education are capped well below what verified
certificates and corroborated skills can earn. A certificate only earns full credit once
it is verified; one awaiting review earns a little, provided OCR could actually read it.
"""

from packages.shared_schemas.candidates import SubScore

# Points per certificate and the cap on each bucket. Caps sum to 100.
_VERIFIED_CERT_POINTS, _VERIFIED_CERT_CAP = 25.0, 50.0
_PENDING_CERT_POINTS, _PENDING_CERT_CAP = 6.0, 12.0
# Pending certificates OCR could barely read earn nothing until reviewed.
_MIN_OCR_CONFIDENCE = 0.5
_YEARS_POINTS, _YEARS_CAP = 4.0, 16.0
_EDUCATION_POINTS = 6.0
_CORROBORATION_CAP = 16.0
# Skill sources backed by something other than the candidate's own claim.
_CORROBORATED_SOURCES = {"github_analysis", "verified", "certificate", "assessment"}


def _skill_source(skill: object) -> str | None:
    return skill.get("source") if isinstance(skill, dict) else None


def verified_credentials(
    certifications: list[dict],
    *,
    experience: list[dict],
    education: list[dict],
    skills: list,
) -> SubScore:
    """0-100 from certificates and resume. `None` when the candidate has provided neither."""
    verified = [c for c in certifications if c.get("verification_status") == "verified"]
    pending = [
        c
        for c in certifications
        if c.get("verification_status") in ("unverified", "pending")
        and (c.get("ocr_confidence") or 0.0) >= _MIN_OCR_CONFIDENCE
    ]
    years = sum(float(e.get("years") or 0.0) for e in experience)

    if not certifications and not experience and not education and not skills:
        return SubScore(value=None, rationale="No certificates or resume provided yet.")

    cert_points = min(_VERIFIED_CERT_CAP, len(verified) * _VERIFIED_CERT_POINTS) + min(
        _PENDING_CERT_CAP, len(pending) * _PENDING_CERT_POINTS
    )
    resume_points = min(_YEARS_CAP, years * _YEARS_POINTS) + (_EDUCATION_POINTS if education else 0.0)
    corroborated = sum(1 for s in skills if _skill_source(s) in _CORROBORATED_SOURCES)
    corroboration_points = _CORROBORATION_CAP * corroborated / len(skills) if skills else 0.0

    value = min(100.0, cert_points + resume_points + corroboration_points)
    return SubScore(
        value=round(value, 1),
        evidence=[c.get("title") for c in verified if c.get("title")],
        rationale=(
            f"{len(verified)} verified and {len(pending)} pending certificate(s); "
            f"resume claims {years:g} year(s) of experience and "
            f"{len(education)} education entr{'y' if len(education) == 1 else 'ies'} (self-reported); "
            f"{corroborated} of {len(skills)} skill(s) corroborated by GitHub or a certificate."
        ),
    )
