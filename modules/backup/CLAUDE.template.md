# Backup Project — AI Instructions

This project manages encrypted, deduplicated backups via **restic**.

## Key software

| Tool | Purpose | Install |
|------|---------|---------|
| `restic` | Backup engine | `apt install restic` |
| `ssh` | SFTP backend transport | usually pre-installed |
| `mount` | NFS backend | `apt install nfs-common` |

## restic quick reference

```bash
# Check repo status
RESTIC_PASSWORD=<pw> restic -r /path/to/repo snapshots

# Run backup
RESTIC_PASSWORD=<pw> restic -r /path/to/repo backup ~/docs ~/projects

# List snapshots
RESTIC_PASSWORD=<pw> restic -r /path/to/repo snapshots --compact

# Restore latest to /tmp/restore
RESTIC_PASSWORD=<pw> restic -r /path/to/repo restore latest --target /tmp/restore

# Check integrity
RESTIC_PASSWORD=<pw> restic -r /path/to/repo check

# Forget old snapshots (keep 7 daily, 4 weekly) and prune
RESTIC_PASSWORD=<pw> restic -r /path/to/repo forget --keep-daily 7 --keep-weekly 4 --prune
```

## Backend types

| Backend | Repo format | Notes |
|---------|-------------|-------|
| Local   | `/path/to/repo` | Simplest; same machine |
| SFTP    | `sftp:user@host:/path` | NAS or remote server via SSH |
| NFS     | `/mnt/nas/repo` (mount first) | Mount NFS share, then use local path |
| S3      | `s3:https://s3.amazonaws.com/bucket` | Cloud; needs `AWS_ACCESS_KEY_ID` etc. |

## Skills available

- `backup_run_backup(project_slug)` — trigger a backup job
- `backup_list_snapshots(project_slug)` — list all snapshots
- `backup_check(project_slug)` — integrity check

## User setup notes

<!--
Fill in your specifics so the AI can give accurate advice:

- What am I backing up?
  [ your answer here ]

- Where does the backup go (local path / NAS address / cloud)?
  [ your answer here ]

- How often should backups run?
  [ daily / weekly / manual ]

- Are there any paths to exclude?
  [ your answer here ]
-->

## Skills

| Skill | Inputs | Description |
|-------|--------|-------------|
| `backup_run_backup` | `project_slug` | Trigger a restic backup (auto-initialises repo if needed) |
| `backup_list_snapshots` | `project_slug` | List all restic snapshots |
| `backup_check` | `project_slug` | Run integrity check on backup repository |
| `backup_restore` | `project_slug`, `target`, `snapshot?` | Restore snapshot to a directory (default: latest) |
| `backup_forget` | `project_slug`, `keep_last?` | Prune old snapshots keeping the last N (default 10) |

## Local Model Guidance

All backup skills are mechanical subprocess calls — no content generation needed. Reliable with any model.

- Specify `project_slug` exactly as shown in the Nexus UI.
- `backup_restore` requires an absolute `target` path; always provide it explicitly.
- `backup_forget` defaults to `keep_last=10`; override if you need a different retention policy.
- If the model returns no tool call: re-prompt with "Call backup_run_backup with project_slug: X."
