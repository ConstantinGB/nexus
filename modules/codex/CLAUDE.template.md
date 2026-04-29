# {project_name} — Codex

This is a personal knowledge base. Each entry is a short, atomic note on a single concept,
fact, or idea. Notes link to each other forming a navigable network. The AI helps create
well-formed entries, find gaps, suggest connections, and distil research into reusable notes.

## Key software

- **Obsidian** — recommended Markdown vault; renders `[[WikiLinks]]` and backlinks natively
- **Logseq** — alternative; block-based, also uses `[[links]]`
- **ripgrep (`rg`)** — fast full-text search across all notes: `rg "search term" notes/`
- **Pandoc** — export notes to PDF, HTML, or DOCX: `pandoc note.md -o note.pdf`
- **git** — version-control the vault; commit frequently for history and backup

## Note anatomy

A well-formed Codex entry:
```markdown
# Concept Title

One clear definition or summary sentence.

## Detail

2–5 sentences expanding on the concept.

## Links

- [[Related Concept A]]
- [[Related Concept B]]
- Source: @AuthorYear or URL

## Tags

#topic #subtopic
```

## Typical tasks

- Distil a research summary or article into one or more atomic notes
- Find existing notes that relate to a new concept and suggest `[[links]]`
- Identify gaps: topics mentioned in notes but not yet having their own entry
- Refactor an overly long note by splitting it into smaller linked notes
- Generate an index or MOC (Map of Content) for a topic cluster
- Search for notes matching a query and summarise findings

## File and config conventions

- **`INDEX.md`** — top-level Map of Content listing all entries by category
- **`notes/<category>/`** — entries grouped by domain (flat is also fine)
- **`assets/`** — images and diagrams referenced in notes
- Filename = note title in kebab-case: `gradient-descent.md`
- `[[WikiLinks]]` use the note filename without the `.md` extension

## Zettelkasten principles

- One idea per note (atomicity)
- Write in your own words — no copy-paste
- Link liberally — value comes from connections, not individual notes
- Notes are permanent: edit and refine rather than delete

---

## Your setup

<!-- Domain / subject area:
     e.g. software engineering, history, biology, personal philosophy -->

<!-- Vault / notes directory path: -->

<!-- Tools in use: Obsidian / Logseq / plain Markdown + ripgrep / other -->

<!-- Tagging conventions:
     e.g. #concept #person #place #event #tool — or free-form -->

<!-- Cross-module feeds: which modules contribute notes here?
     e.g. Research module feeds summaries; Journal reflects on entries -->

## Skills

| Skill | Inputs | Description |
|-------|--------|-------------|
| `codex_list` | `project_slug` | List all vault entries with their first heading |
| `codex_new_entry` | `project_slug`, `title`, `content?` | Create a new Zettelkasten entry with date-based ID frontmatter |
| `codex_search` | `project_slug`, `query` | Search vault entries via grep |
| `codex_get_entry` | `project_slug`, `filename` | Read full content of a named entry |

## Local Model Guidance

- `codex_list`, `codex_get_entry`, `codex_search` — file I/O or process calls; reliable with any model.
- `codex_new_entry` — requires generating a well-formed atomic note. Use explicit prompts: "Create a Codex entry titled X. Write one clear definition sentence, then 2–4 sentences of detail. Return JSON with keys title and content."
- Prompt style: one note at a time; provide the full concept in the prompt.
- If the model returns explanation text instead of a tool call: re-prompt with "Call the codex_new_entry tool now with title: X and content: Y."
- Linking (`[[WikiLinks]]`) works best with models that can reason about existing entries — provide the output of `codex_list` as context first.

## Notes for the AI

<!-- Structure preferences: flat vs nested folders, date-prefixed filenames,
     MOC vs tag-based navigation, writing language. -->
