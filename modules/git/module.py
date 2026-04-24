# Git module — manages one or more repositories for a single git identity.
#
# One instance = one account (GitHub, self-hosted, or local).
# Users can have multiple instances for separate identities (e.g. work + personal).
#
# Setup: nexus/modules/git/setup_screen.py  (multi-step wizard)
# View:  nexus/modules/git/project_screen.py (repo list + git operations)
# Ops:   nexus/modules/git/git_ops.py        (subprocess wrappers)
# API:   nexus/modules/git/github_api.py     (GitHub REST API via httpx)
