# {project_name} — Research

This project supports structured research: collecting sources, extracting and summarising
information, organising notes, and producing output (reports, bibliographies, datasets).
The AI can fetch web pages, search the web (if MCP tools are configured), and distil raw
material into structured notes.

## Key software

- **MCP: fetch** — retrieve a web page as clean text; useful for reading articles and docs
- **MCP: brave-search** — web search directly from the AI; configure in Nexus MCP settings
- **requests + BeautifulSoup4** — Python web scraping for bulk or structured extraction
- **Playwright** — headless browser for JS-heavy sites: `playwright install chromium`
- **Zotero** — citation manager with browser clipper; exports BibTeX, RIS, CSV
- **Pandoc** — convert between Markdown, LaTeX, DOCX, PDF: `pandoc notes.md -o report.pdf`
- **pdftotext / pypdf** — extract text from PDFs for AI processing
- **Obsidian** — Markdown knowledge base; pairs well with the Codex module

## Typical tasks

- Fetch and summarise a URL or PDF into structured Markdown notes
- Search for sources on a topic and evaluate relevance
- Extract key claims, statistics, or quotes from a document
- Generate a bibliography in BibTeX or a chosen citation style
- Organise findings into a structured outline or draft report
- Cross-reference sources and flag contradictions or gaps
- Export polished notes to the Codex module for long-term storage

## File and config conventions

- **`notes/`** — primary note storage; one `.md` file per source or sub-topic
- **`sources/`** — downloaded PDFs, saved HTML, raw data files
- **`bib/references.bib`** — BibTeX bibliography; maintained by Zotero or by hand
- **`output/`** — compiled reports, generated PDFs
- **`queries.md`** — log of search queries and their results (optional but useful)

## Source reliability heuristics

Prefer: peer-reviewed papers (ArXiv, PubMed, ACM, IEEE), official documentation, primary
sources. Flag: news articles, blogs, social media. Avoid: anonymous wikis, unverifiable claims.

---

## Your setup

<!-- Research topic / domain:
     e.g. "machine learning interpretability", "17th century Dutch painting", "ADHD treatment" -->

<!-- Primary sources:
     e.g. ArXiv, PubMed, Google Scholar, specific websites, local PDF collection at ~/papers/ -->

<!-- Citation manager: Zotero / Mendeley / hand-written BibTeX / none -->

<!-- Output format: Markdown report / LaTeX paper / slide deck / dataset -->

<!-- Notes directory path: -->

## Skills

| Skill | Inputs | Description |
|-------|--------|-------------|
| `research_list_notes` | `project_slug` | List all Markdown notes with their first line |
| `research_new_note` | `project_slug`, `filename`, `content` | Create a new note |
| `research_search` | `project_slug`, `query` | Search notes via grep |
| `research_get_note` | `project_slug`, `filename` | Read full content of a note |
| `research_delete_note` | `project_slug`, `filename` | Delete a note (errors if not found) |

## Local Model Guidance

- `research_list_notes`, `research_get_note`, `research_delete_note` — purely mechanical file I/O; reliable with any model.
- `research_new_note` — requires the model to generate Markdown content. Use explicit prompts: "Create a note about X. Return JSON with keys filename and content."
- `research_search` — mechanical grep call; reliable.
- Prompt style: one operation per call; include the exact filename when reading or deleting.
- MCP tools (fetch, brave-search) require a larger model with reliable tool-calling (13B+). With smaller local models, paste content directly into the chat rather than expecting the model to call fetch.
- If the model returns no tool call: re-prompt with "Call the research_get_note tool with project_slug: X and filename: Y."

## Notes for the AI

<!-- Any constraints: language of sources, date range, institutional access,
     depth of coverage required, audience for the final output. -->
