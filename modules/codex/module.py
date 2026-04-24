# Codex module — stores and categorizes knowledge about a topic.
#
# Distinct from Research (which provides tools for active information gathering)
# in that Codex is a persistent, structured knowledge base: human-readable for
# the user, but also organized so the AI can navigate and reason over it efficiently.
#
# Intended knowledge flow into Codex:
#   - Research findings (summarized and distilled via Mycelium)
#   - Manual entries written by the user
#   - Extracted highlights from journals, git history, org plans
#
# Storage format TBD — candidates: Markdown files with YAML frontmatter,
# a local SQLite DB, or a hybrid (files + index DB for fast AI retrieval).
