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

## Notes for the AI

<!-- Structure preferences: flat vs nested folders, date-prefixed filenames,
     MOC vs tag-based navigation, writing language. -->
