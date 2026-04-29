# {project_name} — Git

This project manages one or more Git repositories. Repositories may be hosted on GitHub,
a self-hosted server (GitLab, Gitea, Forgejo), or exist only on this machine. Nexus clones
and tracks each repo under `repos/<name>/`; the project config lives in `config.yaml → git`.

## Key software

- **git** — core VCS; `git status`, `git log --oneline`, `git diff`
- **gh** (GitHub CLI) — create PRs, view issues, manage releases: `gh pr create`, `gh issue list`
- **SSH agent** — `ssh-add ~/.ssh/id_ed25519` to load key; `ssh -T git@github.com` to test
- **GPG** — optional commit signing: `git commit -S`, verify with `git log --show-signature`
- **git-lfs** — large file storage for assets: `git lfs install`, `git lfs track "*.psd"`

## Typical tasks

- Create, switch, and merge branches; resolve merge conflicts
- Interactive rebase: `git rebase -i HEAD~N` to squash, reorder, or edit commits
- Stash and restore work: `git stash push -m "wip"`, `git stash pop`
- Cherry-pick commits across branches: `git cherry-pick <hash>`
- Create and manage pull requests / merge requests via `gh` or web UI
- Tag releases: `git tag -a v1.0.0 -m "Release notes"`, `git push --tags`
- Bisect to find regressions: `git bisect start`, `git bisect bad`, `git bisect good <hash>`

## File and config conventions

- **`~/.gitconfig`** — global identity (`user.name`, `user.email`), aliases, default branch
- **`.git/config`** per repo — remotes, upstream tracking branches
- **`.gitignore`** — patterns for untracked files
- **`config.yaml → git.token`** — stored HTTPS token (SSH URLs bypass this; SSH uses system agent)
- **`config.yaml → git.repos`** — list of repos tracked by this Nexus project
- **`repos/<name>/`** — each cloned repository lives here

## Commit message convention

Conventional Commits format is recommended:
```
feat: add user authentication
fix: handle empty response from API
chore: update dependencies
docs: clarify setup instructions
```

---

## Your setup

<!-- Branching strategy:
     e.g. trunk-based (main only), gitflow (main + develop + feature/*), GitHub flow -->

<!-- Default branch name: main / master / other -->

<!-- GPG signing: yes / no
     If yes, key fingerprint: -->

<!-- SSH key in use:
     e.g. ~/.ssh/id_ed25519 (GitHub), ~/.ssh/id_work (company GitLab) -->

<!-- Any monorepo tooling: turborepo, nx, Lerna, Cargo workspaces, etc. -->

## Skills

| Skill | Inputs | Description |
|-------|--------|-------------|
| `git_status` | `project_slug`, `repo` | Branch, ahead/behind counts, dirty flag, last 5 commits |
| `git_pull` | `project_slug`, `repo` | Pull latest commits |
| `git_push` | `project_slug`, `repo` | Push local commits to remote |
| `git_commit` | `project_slug`, `repo`, `message` | Stage all, commit, and push |
| `git_log` | `project_slug`, `repo`, `n?` | Recent commit history (default 10) |
| `git_clone` | `project_slug`, `url`, `name?` | Clone a repo and register it |
| `git_diff` | `project_slug`, `repo`, `staged?` | Output of git diff or git diff --staged |
| `git_stash` | `project_slug`, `repo`, `action` | git stash push or git stash pop |

## Local Model Guidance

- `git_status`, `git_pull`, `git_push`, `git_log`, `git_diff`, `git_stash` — all mechanical subprocess calls; reliable with any model.
- `git_commit` — requires a good commit message. Provide the message explicitly in your prompt: "Commit with message: fix: handle empty response."
- `git_clone` — reliable; just needs a URL.
- Prompt style: always specify `repo` by exact name (as shown in the Nexus UI). Use one operation per call.
- If the model returns no tool call: re-prompt with "Call the git_status tool with project_slug: X and repo: Y."

## Notes for the AI

<!-- Preferred merge strategy (merge commit / squash / rebase),
     protected branches, CI/CD system in use, code review requirements. -->
