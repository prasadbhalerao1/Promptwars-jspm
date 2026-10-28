"""Issuer Lookup Agent — doc 06 §4, "rules + httpx". FR-1.

Checks the candidate's entered issuer against `trusted_issuers` (Module 06's known-issuer
registry — `packages/db/models/fraud.py::TrustedIssuer`, admin-managed via
`services/api/modules/fraud/router.py`'s `/admin/trusted-issuers` endpoints). Previously
this was a small hardcoded Python dict in this file; that dict's 6 entries are now the
seed data for the DB table instead (see the `l7m8n9o0p1q2` migration), so nothing already
recognized regressed, but new issuers no longer require a code change to add — an admin
adds a row instead.

An issuer that doesn't match any trusted-registry entry is now distinguishable from one
that matches but simply has no URL template configured — the former is a genuine
"unrecognized issuer" signal (`cert_verdict.py` adds its own elevated-risk evidence for
this), the latter is just "known issuer, no automated verification path yet," which
falls through to Visual Forensics exactly as before, without the extra risk signal.

Nodes stay DB-free (this codebase's universal convention), so the router pre-fetches the
full `trusted_issuers` table into `context["trusted_issuers"]` before invoking the graph
— this module never touches the DB itself, only compares against what it's given.
"""

import httpx
from services.api.core.config import get_settings


def resolve_issuer(
    issuer: str | None, trusted_issuers: list[dict]
) -> tuple[dict | None, bool]:
    """Returns (matched_issuer_row_or_None, is_recognized). `trusted_issuers` is
    [{name, aliases, verification_url_template, trust_tier}, ...] as fetched by the
    router. Matching is case-insensitive substring matching against the canonical name
    and every alias — same flexibility the old hardcoded dict had (e.g. a candidate
    entering "Amazon Web Services (AWS)" should still match the "AWS" registry entry)."""
    if not issuer:
        return None, False
    key = issuer.strip().lower()
    for row in trusted_issuers:
        candidates = [row["name"], *(row.get("aliases") or [])]
        if any(name.lower() in key or key in name.lower() for name in candidates):
            return row, True
    return None, False


def resolve_verification_url(matched_issuer: dict | None, credential_id: str | None) -> str | None:
    if matched_issuer is None or not credential_id:
        return None
    template = matched_issuer.get("verification_url_template")
    if not template:
        return None
    return template.format(credential_id=credential_id)


async def lookup_issuer(
    issuer: str | None, credential_id: str | None, trusted_issuers: list[dict]
) -> dict:
    """Returns {resolvable, is_recognized_issuer, verification_url, http_status,
    evidence}. Never raises — a network failure degrades to `resolvable: False` (routes
    to Visual Forensics) rather than blocking the check, matching every other module's
    "typed unavailable, never fabricate" pattern applied here as "never silently treat a
    network hiccup as a positive verification".

    `is_recognized_issuer` is independent of `resolvable`: an issuer can be a recognized,
    trusted registry entry (`is_recognized_issuer=True`) with no URL-verification path
    configured yet (`resolvable=False`) — that's "known but not automatable," not
    "unrecognized." Only `is_recognized_issuer=False` should read as an elevated-risk
    signal to the caller."""
    matched, is_recognized = resolve_issuer(issuer, trusted_issuers)
    url = resolve_verification_url(matched, credential_id)
    if url is None:
        reason = (
            f"Issuer '{issuer}' is not in the trusted issuer registry."
            if not is_recognized
            else f"Issuer '{issuer}' is recognized but has no automated verification URL configured (or missing credential ID)."
        )
        return {
            "resolvable": False,
            "is_recognized_issuer": is_recognized,
            "verification_url": None,
            "http_status": None,
            "evidence": reason,
        }

    try:
        async with httpx.AsyncClient(timeout=get_settings().issuer_lookup_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url)
        return {
            "resolvable": True,
            "is_recognized_issuer": is_recognized,
            "verification_url": url,
            "http_status": response.status_code,
            "evidence": f"Fetched {url} -> HTTP {response.status_code}.",
            "page_text_sample": response.text[:2000] if response.status_code == 200 else "",
        }
    except httpx.HTTPError as exc:
        return {
            "resolvable": False,
            "is_recognized_issuer": is_recognized,
            "verification_url": url,
            "http_status": None,
            "evidence": f"Could not reach issuer verification page ({url}): {exc}.",
        }
