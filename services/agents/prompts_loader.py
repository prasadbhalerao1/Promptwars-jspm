"""Load prompts from markdown files in agent directories.

Replaces the need for inline prompts or Jinja2 templates by loading from
simple markdown files that are easy to read, version control, and modify.

Placeholders are written `{name}`. Three bugs in the original implementation are worth
recording, because each silently degraded prompt quality rather than raising:

1. It built a `string.Template` and called `.substitute()`, which only understands
   `$name`. Every prompt file uses `{name}`, so **no placeholder was ever substituted** —
   the model received the literal text `"{query}"` and `{resume_text}` instead of the
   recruiter's query or the candidate's resume. The comment claimed "$variable or
   {variable} format"; only the former was implemented, and nothing used it.
2. It dropped every line starting with `#`, intending to strip the markdown title. That
   also deleted all `##` section headings (so "Examples", "Rules" and their content ran
   together unlabeled) and any `#` comment inside a fenced code block.
3. `.substitute()` raises `KeyError` on any unrecognized `$`, so a `$` appearing in
   ordinary prompt prose (a price, a shell snippet) would crash the agent at call time.

Only the H1 title line is stripped now, `{name}` is the substitution syntax, and a
literal brace can be escaped as `{{`/`}}`.
"""

import functools
import re
from pathlib import Path

# `{name}` where name is a valid identifier. Deliberately narrow: JSON examples inside
# prompts contain plenty of braces (`{"skills": [...]}`) that must pass through
# untouched, and they never look like a bare identifier in braces.
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


@functools.lru_cache(maxsize=None)
def _load_prompt_text(agent_name: str, prompt_name: str) -> str:
    """Reads one prompt file from disk — cached since every agent LLM call re-reads the
    same handful of prompt files, and their content only changes on deploy."""
    agent_dir = Path(__file__).parent / agent_name / "prompts"
    prompt_file = agent_dir / f"{prompt_name}.md"

    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_file}")

    content = prompt_file.read_text(encoding="utf-8")

    # Strip only the leading H1 title ("# Fact-Check Prompt"), which names the file for a
    # human reader and adds nothing for the model. Everything else — `##` sections that
    # organize the instructions, `#` comments inside code examples — is content.
    lines = content.split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def load_prompt(agent_name: str, prompt_name: str, **variables) -> str:
    """Load a prompt markdown file and interpolate `{variable}` placeholders.

    Args:
        agent_name: e.g., "recruitment", "candidate_intelligence", "fraud"
        prompt_name: e.g., "understand_query", "classifier" (without .md extension)
        **variables: Values to interpolate. Every `{name}` in the file must be supplied.

    Returns:
        Interpolated prompt text.

    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
        ValueError: If the prompt references a variable the caller didn't pass — better a
            loud failure here than an LLM call carrying a literal `{merged_profile_json}`.
    """
    text = _load_prompt_text(agent_name, prompt_name)

    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            missing.append(key)
            return match.group(0)
        return str(variables[key])

    # Escaped braces first, so `{{literal}}` survives as `{literal}` without being read
    # as a placeholder.
    placeholder_pass = _PLACEHOLDER_RE.sub(replace, text.replace("{{", "\0L").replace("}}", "\0R"))
    result = placeholder_pass.replace("\0L", "{").replace("\0R", "}")

    if missing:
        raise ValueError(
            f"Missing variable(s) in prompt {agent_name}/{prompt_name}: {sorted(set(missing))}"
        )
    return result


__all__ = ["load_prompt"]
