# {project_name} — Journal

This is a personal journal formatted with LaTeX and compiled to PDF. Entries are individual
`.tex` files included by a master document. The AI helps draft entries from notes or bullet
points, suggests reflection prompts, formats text to valid LaTeX, and diagnoses compile errors.

## Key software

- **pdflatex** — compile: `pdflatex entry.tex`; install via `texlive-full` or `MiKTeX`
- **latexmk** — smart compilation (reruns as needed): `latexmk -pdf entry.tex`
- **TeXstudio / VS Code + LaTeX Workshop** — editors with live PDF preview
- **Pandoc** — convert rough Markdown → LaTeX: `pandoc notes.md -o entry.tex`
- **aspell / hunspell** — spell check `.tex` files: `aspell -t check entry.tex`

## Minimal entry template

```latex
\documentclass[12pt, a4paper]{article}
\usepackage[margin=2.5cm]{geometry}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}
\usepackage{parskip}

\title{Journal — \today}
\date{}
\author{}

\begin{document}
\maketitle

\section{Reflection}
% ...

\section{What I learned}
% ...

\end{document}
```

## Master journal file pattern

```latex
% journal.tex — compile this to produce the full journal
\documentclass{book}
\begin{document}
\input{2024/2024-01-15}
\input{2024/2024-01-22}
\end{document}
```

## Typical tasks

- Draft a new entry from bullet-point notes or a voice transcript
- Suggest reflection prompts for today or a recent period
- Format plain text into correct LaTeX (escape special characters)
- Compile and report LaTeX errors with plain-English explanations
- Summarise a month or year of entries into a retrospective
- Design or modify the LaTeX template (fonts, layout, section headers)

## LaTeX special character escapes

`&` → `\&` · `%` → `\%` · `$` → `\$` · `#` → `\#` · `_` → `\_` ·
`{` → `\{` · `}` → `\}` · `~` → `\textasciitilde{}` · `^` → `\textasciicircum{}`

## File and config conventions

- **Entry naming:** `YYYY-MM-DD.tex` (daily) or `YYYY-WXX.tex` (weekly)
- **Directory layout:** `entries/YYYY/YYYY-MM-DD.tex`
- **`journal.tex`** — master file that `\input`s all entries
- **`preamble.tex`** — shared preamble if entries compile standalone
- **`compiled/`** — output PDFs (git-ignored or archived)

---

## Your setup

<!-- Journal purpose:
     e.g. daily reflection, work log, creative writing, travel diary, learning log -->

<!-- Entry frequency: daily / weekly / freeform -->

<!-- Language: English / other -->

<!-- LaTeX preferences:
     font (default Computer Modern / libertine / palatino / EB Garamond),
     paper size (A4 / letter), line spacing, any extra packages -->

<!-- Journal directory path: -->

## Skills

| Skill | Inputs | Description |
|-------|--------|-------------|
| `journal_list_entries` | `project_slug` | List .tex entries newest-first with word counts |
| `journal_new_entry` | `project_slug`, `content?` | Create a new LaTeX journal entry |
| `journal_compile` | `project_slug` | Run pdflatex and return error/warning summary |

## Local Model Guidance

- `journal_list_entries`, `journal_compile` — mechanical calls; reliable with any model.
- `journal_new_entry` — ask the model to draft the entry body in plain text, then pass it as `content`. Avoid asking it to generate raw LaTeX; local models often produce syntax errors.
- If compile fails, paste the error output into chat and ask "What LaTeX fix resolves this error?" — straightforward for most models.
- Prompt style: one entry at a time; provide the full content in a single call.
- If the model returns no tool call: re-prompt with "Call journal_new_entry with project_slug: X and content: Y."

## Notes for the AI

<!-- Recurring sections in every entry (e.g. gratitude, goals, mood rating).
     Tone: formal / conversational / stream-of-consciousness. -->
