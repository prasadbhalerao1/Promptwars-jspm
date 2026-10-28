"""Technical Feasibility Agent's repo cross-check — FR-5: "cross-check technical claims
in the deck against the team's actual repo if linked".

Module 01's `candidate_project_embeddings` Qdrant collection and Module 03's static
analysis tables don't exist yet (per the task brief and .agents/decisions.md's
"Problem Solving is always None" cold-start note) — this can't join against either.
Degradation path per the task brief: treat `linked_repo` as an optional plain string
(no FK, no cross-module table join), and when present, pull a lightweight public
snapshot directly from the GitHub API (unauthenticated — this is a team's own repo
link, not per-candidate ingestion, so there's no OAuth token to use here) to hand the
Sonnet judgment call real evidence instead of nothing. Any failure (repo doesn't exist,
private, rate-limited, no repo linked) degrades to `None` — never fabricates evidence.

When Module 01 ingestion and/or Module 03 static analysis exist, this is the function to
extend — swap the GitHub-API-only snapshot for a read via the `events` bus or a nullable
reference to `candidate_project_embeddings`/Module 03's tables, without changing this
tool's call signature.
"""

from github import Github
from github.GithubException import GithubException


def _parse_repo_full_name(linked_repo: str) -> str | None:
    value = linked_repo.strip()
    if value.startswith("http"):
        parts = [p for p in value.rstrip("/").split("/") if p]
        if len(parts) < 2:
            return None
        return f"{parts[-2]}/{parts[-1]}"
    if "/" in value:
        return value
    return None


def fetch_repo_evidence(linked_repo: str | None) -> str | None:
    if not linked_repo:
        return None

    full_name = _parse_repo_full_name(linked_repo)
    if full_name is None:
        return None

    try:
        client = Github(retry=None)
        repo = client.get_repo(full_name)
        languages = repo.get_languages()
        readme_excerpt = ""
        try:
            readme = repo.get_readme()
            readme_excerpt = readme.decoded_content.decode("utf-8", errors="ignore")[:1500]
        except GithubException:
            pass

        return (
            f"repo={full_name}, languages={languages}, stars={repo.stargazers_count}, "
            f"last_pushed={repo.pushed_at}\nREADME excerpt:\n{readme_excerpt}"
        )
    except GithubException:
        return None
    except Exception:
        return None
