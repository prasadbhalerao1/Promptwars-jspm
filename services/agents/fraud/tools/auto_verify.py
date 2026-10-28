"""Auto-Verify Agent — doc 06 §4, "rules". Simple match/no-match against the fetched
issuer page content from `tools/issuer_lookup.py`'s output. Only runs when the Issuer
Lookup Agent found a resolvable verification URL."""


def auto_verify(credential_id: str | None, page_text_sample: str, http_status: int | None) -> dict:
    """Returns {verified: bool|None, confidence_label, evidence}. `verified=None` means
    "couldn't determine" (e.g. 404, or credential ID doesn't literally appear on the
    page) — never guessed as True."""
    if http_status != 200:
        return {
            "verified": None,
            "confidence_label": "low",
            "evidence": f"Issuer verification page returned HTTP {http_status}, cannot confirm credential.",
        }
    if credential_id and credential_id in page_text_sample:
        return {
            "verified": True,
            "confidence_label": "high",
            "evidence": f"Credential ID '{credential_id}' found verbatim on the issuer's verification page.",
        }
    return {
        "verified": False,
        "confidence_label": "medium",
        "evidence": (
            f"Issuer verification page resolved (HTTP 200) but credential ID '{credential_id}' "
            "does not appear on the page — the credential ID does not resolve on the issuer's "
            "verification page."
        ),
    }
