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

## Notes for the AI

<!-- Preferred merge strategy (merge commit / squash / rebase),
     protected branches, CI/CD system in use, code review requirements. -->
