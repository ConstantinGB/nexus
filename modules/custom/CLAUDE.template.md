# {project_name}

This is a custom project with no predefined module. The AI will work from whatever
description and context you provide below. Fill in as much detail as you can — the more
specific you are about goals, constraints, and existing work, the more useful the AI can be.

## What is this project?

<!-- Describe your project clearly:
     - What are you building, doing, or learning?
     - What is the end goal?
     - What does "done" look like?
     - Any hard constraints (language, platform, deadline, budget)? -->

## Current state

<!-- What already exists? What have you tried so far?
     Links to repos, files, or docs if relevant. -->

## Tools and technologies

<!-- What languages, frameworks, libraries, or tools are involved?
     e.g. Python + FastAPI, Rust, Bash scripts, Blender, Excel, pen-and-paper -->

## Skills

| Skill | Inputs | Description |
|-------|--------|-------------|
| `custom_run_command` | `project_slug`, `label` | Run a named shell command defined in this project's config |
| `custom_ask` | `project_slug`, `question` | Ask the AI a question in the context of this project |

## Local Model Guidance

Both skills work with local models, but quality depends on the model size:

- `custom_ask` is reliable with 7B+ models. Use explicit, self-contained questions: "What is X?" not "Tell me more."
- `custom_run_command` is purely mechanical (runs a shell command) — local model quality is irrelevant for this skill.
- Prompt style: one question per call, no implicit context references, state everything the model needs.
- If the model returns no tool call: re-prompt with "Call the custom_ask tool with question: <your question>."

## Notes for the AI

<!-- Anything specific to keep in mind: preferred coding style, things to avoid,
     context about why decisions were made, or relevant background knowledge. -->
