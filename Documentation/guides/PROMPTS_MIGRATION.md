# Prompts Migration Summary

> **Historical record — completed 2026-08. Superseded by
> [14-prompts-architecture.md](../14-prompts-architecture.md).**
>
> This documents a one-time migration off Jinja2 templates. Every `packages/prompts/*`
> path named below is gone: that package was deleted outright in the 2026-08-19 audit
> (zero importers, and it imported an undeclared `jinja2` dependency). The prompt count
> here is also out of date — there are now 24 prompt files, one per LLM call site, all
> conforming to the authoring standard described in doc 14. Kept for the "why" behind the
> move; read doc 14 for how prompts work today.


## Overview
All prompts have been migrated from inline definitions and Jinja2 templates to a centralized markdown-based system. This makes prompts:
- **Easy to read and modify** - Plain markdown files
- **Version controllable** - Clear git diffs
- **Organized** - Grouped by agent module
- **Maintainable** - Separate from code logic

## Changes Made

### 1. Deleted Jinja2 Templates (8 files)
- ❌ `packages/prompts/templates/candidate_intelligence/talent_score_v1.jinja2` (unused)
- ❌ `packages/prompts/templates/candidate_intelligence/career_guidance_v1.jinja2` (unused)
- ❌ `packages/prompts/templates/fraud/dispute_review_v1.jinja2` (unused)
- ❌ `packages/prompts/templates/fraud/risk_report_v1.jinja2` (unused)
- ❌ `packages/prompts/templates/ppt_analyzer/synthesis_v1.jinja2` (unused)
- ❌ `packages/prompts/templates/recruitment/copilot_v1.jinja2` (unused)
- ❌ `packages/prompts/templates/recruitment/match_explain_v1.jinja2` (unused)
- ❌ `packages/prompts/templates/supervisor/classifier_v1.jinja2` (converted to .md)

### 2. Created Prompt Loader Utility
**File:** `services/agents/prompts_loader.py`

Simple function to load and interpolate markdown-based prompts:
```python
from services.agents.prompts_loader import load_prompt

prompt = load_prompt("recruitment", "understand_query", raw_query=query_text)
```

### 3. New Prompt Structure

```
services/agents/
├── recruitment/prompts/
│   ├── understand_query.md
│   ├── rerank_candidates.md
│   └── explain_matches.md
├── candidate_intelligence/prompts/
│   ├── resume_extraction.md
│   ├── judgment_scores.md
│   └── fact_check.md
├── assessment/prompts/
│   ├── generate_question.md
│   ├── evaluate_turn.md
│   ├── generate_followup.md
│   └── interview_report.md
├── fraud/prompts/
│   └── risk_report.md
├── supervisor/prompts/
│   └── classifier.md
├── ppt_analyzer/prompts/
└── hackathon/prompts/
```

### 4. Updated Python Files

| File | Changes |
|------|---------|
| `services/agents/recruitment/tools/copilot_llm.py` | Inline → load_prompt for 3 functions |
| `services/agents/candidate_intelligence/tools/resume.py` | Inline → load_prompt |
| `services/agents/candidate_intelligence/tools/judgment_scores.py` | Inline → load_prompt |
| `services/agents/candidate_intelligence/tools/fact_check.py` | Inline → load_prompt |
| `services/agents/assessment/tools/interview_llm.py` | Inline → load_prompt for 4 functions |
| `services/agents/fraud/tools/report_llm.py` | Inline → load_prompt |
| `services/agents/supervisor/tools/classifier_llm.py` | Jinja2 template → load_prompt |

## Prompt Format

Each `.md` file uses simple variable interpolation:

```markdown
# [Prompt Title]

[Prompt text with variables]

{variable_name}

## Schema Description

[Description of the output schema]
```

Variables are interpolated using Python's `string.Template` format: `{variable_name}`

## Benefits

1. **Readability**: Prompts are now readable as standalone documents
2. **Maintainability**: Easy to update prompt text without touching code
3. **Consistency**: All prompts use the same loading mechanism
4. **Testing**: Prompts can be tested independently
5. **Documentation**: Markdown format is self-documenting
6. **Git-friendly**: Clear diffs when prompts change

## Migration Guide for New Prompts

1. Create `services/agents/[agent_name]/prompts/[prompt_name].md`
2. Add prompt text with `{variable}` placeholders
3. In your code:
   ```python
   from services.agents.prompts_loader import load_prompt
   
   prompt = load_prompt("[agent_name]", "[prompt_name]", variable=value)
   ```

## Cleanup

- `packages/prompts/templates/` directory is now empty (safe to delete if desired)
- `packages/prompts/registry.py` is no longer used
- `packages/prompts/__init__.py` exports are no longer used
