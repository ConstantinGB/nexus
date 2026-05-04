from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

_DEFAULT_LIST_NAME = "Tasks"


class TodoData:
    """Todo storage — ported from Thallid, PyQt6 removed."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.data_dir / "tasks.json"
        self.lists: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if self.tasks_file.exists():
            with open(self.tasks_file) as f:
                data = json.load(f)
            # Migrate old flat-task format
            if data and isinstance(data, list) and not any("tasks" in item for item in data if isinstance(item, dict)):
                return [{"id": "default", "name": _DEFAULT_LIST_NAME, "created": datetime.now().isoformat(), "tasks": data}]
            return data
        return []

    def _save(self) -> None:
        with open(self.tasks_file, "w") as f:
            json.dump(self.lists, f, indent=2)

    # ── List management ───────────────────────────────────────────────────────

    def ensure_default_list(self) -> dict:
        if not self.lists:
            return self.add_list(_DEFAULT_LIST_NAME)
        return self.lists[0]

    def add_list(self, name: str) -> dict:
        task_list = {"id": datetime.now().isoformat(), "name": name, "created": datetime.now().isoformat(), "tasks": []}
        self.lists.append(task_list)
        self._save()
        return task_list

    def delete_list(self, list_id: str) -> None:
        self.lists = [l for l in self.lists if l["id"] != list_id]
        self._save()

    def get_list_by_name(self, name: str) -> dict | None:
        return next((l for l in self.lists if l["name"].lower() == name.lower()), None)

    def get_list_by_id(self, list_id: str) -> dict | None:
        return next((l for l in self.lists if l["id"] == list_id), None)

    # ── Task management ───────────────────────────────────────────────────────

    def add_task(self, list_id: str, title: str, priority: str = "medium", deadline: str | None = None, parent_id: str | None = None) -> dict:
        task = {
            "id": datetime.now().isoformat(),
            "title": title,
            "priority": priority,
            "deadline": deadline,
            "completed": False,
            "created": datetime.now().isoformat(),
            "subtasks": [],
        }
        for lst in self.lists:
            if lst["id"] == list_id:
                if parent_id:
                    self._add_subtask(lst["tasks"], parent_id, task)
                else:
                    lst["tasks"].append(task)
                break
        self._save()
        return task

    def _add_subtask(self, tasks: list, parent_id: str, subtask: dict) -> bool:
        for task in tasks:
            if task["id"] == parent_id:
                task.setdefault("subtasks", []).append(subtask)
                return True
            if self._add_subtask(task.get("subtasks", []), parent_id, subtask):
                return True
        return False

    def toggle_task(self, list_id: str, task_id: str) -> None:
        for lst in self.lists:
            if lst["id"] == list_id:
                self._toggle(lst["tasks"], task_id)
                break
        self._save()

    def _toggle(self, tasks: list, task_id: str) -> bool:
        for task in tasks:
            if task["id"] == task_id:
                task["completed"] = not task["completed"]
                return True
            if self._toggle(task.get("subtasks", []), task_id):
                return True
        return False

    def complete_task(self, list_id: str, task_id: str) -> None:
        for lst in self.lists:
            if lst["id"] == list_id:
                self._set_completed(lst["tasks"], task_id, True)
                break
        self._save()

    def _set_completed(self, tasks: list, task_id: str, value: bool) -> bool:
        for task in tasks:
            if task["id"] == task_id:
                task["completed"] = value
                return True
            if self._set_completed(task.get("subtasks", []), task_id, value):
                return True
        return False

    def delete_task(self, list_id: str, task_id: str) -> None:
        for lst in self.lists:
            if lst["id"] == list_id:
                lst["tasks"] = self._delete(lst["tasks"], task_id)
                break
        self._save()

    def _delete(self, tasks: list, task_id: str) -> list:
        return [
            {**t, "subtasks": self._delete(t.get("subtasks", []), task_id)}
            for t in tasks if t["id"] != task_id
        ]

    def find_task(self, task_id: str) -> tuple[dict | None, dict | None]:
        """Return (list, task) or (None, None)."""
        for lst in self.lists:
            task = self._find(lst["tasks"], task_id)
            if task:
                return lst, task
        return None, None

    def _find(self, tasks: list, task_id: str) -> dict | None:
        for task in tasks:
            if task["id"] == task_id:
                return task
            found = self._find(task.get("subtasks", []), task_id)
            if found:
                return found
        return None

    def get_pending(self, list_id: str | None = None) -> list[dict]:
        result = []
        for lst in self.lists:
            if list_id and lst["id"] != list_id:
                continue
            self._collect_pending(lst["tasks"], result)
        return result

    def _collect_pending(self, tasks: list, out: list) -> None:
        for task in tasks:
            if not task["completed"]:
                out.append(task)
            self._collect_pending(task.get("subtasks", []), out)
