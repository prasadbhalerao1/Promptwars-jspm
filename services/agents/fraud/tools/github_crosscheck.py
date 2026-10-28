"""Public-Repo Cross-Check Agent — doc 06 §4, "GitHub code-search API + Haiku narrative".
FR-2. Reuses the PyGithub client pattern from
`services/agents/candidate_intelligence/tools/github.py` (unauthenticated search — no
candidate token is available/appropriate here since this checks OTHER people's public
repos, not the candidate's own)."""

import re

from github import Github
from github.GithubException import GithubException

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")


def _distinctive_snippet(code: str, max_chars: int = 200) -> str:
    """GitHub code search works best on a distinctive literal substring, not the whole
    file — pick the longest non-trivial line as a search anchor."""
    lines = [l.strip() for l in code.splitlines() if len(l.strip()) > 20]
    if not lines:
        return code[:max_chars]
    longest = max(lines, key=len)
    return longest[:max_chars]


def crosscheck_public_repos(code: str, candidate_github_username: str | None) -> dict:
    """Returns {matches: [{repo_full_name, html_url}], evidence}. Degrades to an empty
    result (never raises) on any GitHub API failure — search rate limits are common for
    unauthenticated calls, and a failed lookup must never be reported as "no match found"
    with false confidence; the evidence string makes the degrade explicit."""
    snippet = _distinctive_snippet(code)
    if not snippet:
        return {"matches": [], "evidence": "No distinctive code snippet available to search for."}

    try:
        client = Github(retry=None)
        results = client.search_code(query=f'"{snippet}"')
        matches = []
        for item in results[:5]:
            repo_owner = item.repository.owner.login if item.repository and item.repository.owner else None
            if candidate_github_username and repo_owner and repo_owner.lower() == candidate_github_username.lower():
                continue  # the candidate's own repo is not evidence of copying
            matches.append({"repo_full_name": item.repository.full_name, "html_url": item.html_url})
        if matches:
            evidence = f"Matching code snippet found in {len(matches)} public repo(s) not authored by the candidate."
        else:
            evidence = "No matching public repo found for the searched snippet."
        return {"matches": matches, "evidence": evidence}
    except GithubException as exc:
        return {
            "matches": [],
            "evidence": f"GitHub code search unavailable (rate-limited or API error): {exc}. Treat as inconclusive, not clean.",
        }
