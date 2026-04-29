# {project_name} — Prompt Opt

This module takes a raw prompt and rewrites it using AI in one of three modes:
**Text** (clearer AI prompt), **Instruct** (structured instruction), or **Image** (Stable Diffusion tag prompt).
Enter your prompt, choose a mode, click Optimize, then copy the result.

## Modes

| Mode | What it does |
|------|-------------|
| `text` | Rewrites for clarity — more precise, unambiguous, AI-readable |
| `instruct` | Converts to an imperative AI instruction with explicit constraints and structure |
| `image` | Converts a natural-language description to comma-separated SD tags with style/lighting/quality hints |

## Skills

| Skill | Inputs | Description |
|-------|--------|-------------|
| `promptopt_optimize` | `project_slug`, `prompt`, `mode` | Optimize a prompt for the given mode |

## Local Model Guidance

All three modes work well with local models. For best results:
- Use explicit, one-shot requests: "Optimize this prompt for Stable Diffusion: ..."
- If the model returns explanation text alongside the result, re-prompt with "Return only the improved prompt, nothing else."
- `text` and `instruct` modes are reliable with most 7B+ models; `image` mode may need a larger model to produce well-structured SD tags.

## Notes for the AI

<!-- Any prompt style preferences, SD model in use, or domains this project focuses on. -->
