# Operator — AI Daily Assistant

This project is your personal AI operator: calendar, notes, and tasks, all managed through a chat interface powered by Claude's native tool use.

## How it works

Open this project and use the **Chat** panel (💬) to talk to your operator. It can:

- Add, list, and delete calendar events
- Create, search, update, and delete markdown notes
- Add tasks, list pending items, complete tasks, and delete tasks
- Answer questions about your other Nexus projects (git, backups, server status, etc.) through cross-module skills

The **Today's Brief** button sends a morning summary prompt automatically — events for today, pending tasks, and any recent notes worth mentioning.

## Data storage

All data lives in `projects/<slug>/data/`:

```
data/
  calendar/events.json   — calendar events (ISO 8601 datetimes)
  notes/index.json       — note metadata index
  notes/*.md             — one markdown file per note
  todo/tasks.json        — task lists with subtask support
```

## Calendar

Events are stored as JSON with ISO 8601 datetimes. Recurring events support `daily`, `weekly`, `monthly`, and `yearly` types with an optional `until` date and `interval`.

Example event object:
```json
{
  "id": "2026-05-02T09:00:00",
  "title": "Team sync",
  "start": "2026-05-02T09:00:00",
  "end": "2026-05-02T09:30:00",
  "description": "Weekly engineering standup",
  "location": "",
  "recurrence": null
}
```

To add a recurring weekly event via chat:
> "Add a weekly team sync every Monday at 9am"

## Notes

Notes are markdown files with a metadata entry in `index.json`. The ID is a `YYYYMMDD_HHMMSS` timestamp. Use tags to organise:

> "Create a note called 'Architecture decision — auth service' with tags: architecture, backend"

To search:
> "Find my notes about authentication"

To read and update:
> "Show me the content of my architecture note and add a section about JWT rotation"

## Tasks

Tasks support priorities (`low`, `medium`, `high`), deadlines, subtasks, and named lists. The default list is called "Tasks".

> "Add a high-priority task: Deploy new auth service — deadline 2026-05-10"
> "What are my pending tasks?"
> "Mark the deploy task as complete"

## Cross-module awareness

The operator has access to global Nexus skills. You can ask:

> "What's the status of my main git project?"
> "When did my last backup run?"
> "List my running services"

The operator will call the appropriate module skill and summarise the result.

## User setup

<!-- Fill in the details about your setup so the operator knows your context. -->

### My role and focus areas

<!-- e.g. "I'm a solo developer working on open-source tools. Primary language: Python. Current focus: Nexus 2.0 release." -->

### Regular commitments

<!-- e.g. "Weekly team sync: Monday 9am. Monthly retro: last Friday of each month." -->

### Projects I care about

<!-- e.g. "nexus (main dev project), thallid (archived), homelab (self-hosted infra)" -->

### Preferred task lists

<!-- e.g. "Work, Personal, Someday" — the operator will create lists by these names when you ask. -->

### Tone preferences

<!-- e.g. "Concise. Skip pleasantries. Surface blockers and priorities first." -->
