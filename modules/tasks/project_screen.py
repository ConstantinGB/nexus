from __future__ import annotations
from pathlib import Path

from textual.widgets import Button, Label, Log
from textual.css.query import NoMatches

from nexus.core.project_manager import ProjectInfo
from nexus.ui.tui.base_project_screen import BaseProjectScreen, InputModal

_PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"


def _data_dir(slug: str) -> Path:
    return _PROJECTS_ROOT / slug / "data" / "todo"


class ProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "tasks"
    MODULE_LABEL = "Tasks"
    SETUP_FIELDS = []

    def _compose_action_buttons(self):
        yield Button("+ Add Task",      id="btn-add-task")
        yield Button("Complete Task",   id="btn-complete-task")
        yield Button("Delete Task",     id="btn-del-task")

    def _handle_action(self, bid: str | None) -> None:
        if bid == "btn-add-task":
            self.app.push_screen(
                InputModal("Add Task", "Task title:", "My task"),
                self._on_add_task,
            )
        elif bid == "btn-complete-task":
            self.app.push_screen(
                InputModal("Complete Task", "Task ID to mark complete:", ""),
                self._on_complete_task,
            )
        elif bid == "btn-del-task":
            self.app.push_screen(
                InputModal("Delete Task", "Task ID to delete:", ""),
                self._on_del_task,
            )

    def _on_add_task(self, title: str | None) -> None:
        if not title:
            return
        try:
            from nexus.core.data.tasks import TodoData
            td = TodoData(_data_dir(self.project.slug))
            lst = td.ensure_default_list()
            task = td.add_task(lst["id"], title.strip())
            self.app.notify(f"Task added: {title}", severity="information")
            self.run_worker(self._safe_populate())
        except Exception as exc:
            self.app.notify(str(exc), severity="error")

    def _on_complete_task(self, task_id: str | None) -> None:
        if not task_id:
            return
        try:
            from nexus.core.data.tasks import TodoData
            td = TodoData(_data_dir(self.project.slug))
            lst, task = td.find_task(task_id.strip())
            if task is None:
                self.app.notify(f"Task not found: {task_id}", severity="error")
                return
            td.complete_task(lst["id"], task_id.strip())
            self.app.notify(f"Task completed: {task['title']}", severity="information")
            self.run_worker(self._safe_populate())
        except Exception as exc:
            self.app.notify(str(exc), severity="error")

    def _on_del_task(self, task_id: str | None) -> None:
        if not task_id:
            return
        try:
            from nexus.core.data.tasks import TodoData
            td = TodoData(_data_dir(self.project.slug))
            lst, task = td.find_task(task_id.strip())
            if task is None:
                self.app.notify(f"Task not found: {task_id}", severity="error")
                return
            td.delete_task(lst["id"], task_id.strip())
            self.app.notify("Task deleted.", severity="information")
            self.run_worker(self._safe_populate())
        except Exception as exc:
            self.app.notify(str(exc), severity="error")

    async def _populate_content(self) -> None:
        try:
            log_widget = self.query_one("#output-log", Log)
        except NoMatches:
            return
        try:
            from nexus.core.data.tasks import TodoData
            td = TodoData(_data_dir(self.project.slug))
            log_widget.clear()
            if not td.lists:
                log_widget.write_line("No tasks yet. Use '+ Add Task' to get started.")
                return
            for lst in td.lists:
                log_widget.write_line(f"List: {lst['name']}")
                for task in lst["tasks"]:
                    done = "[x]" if task["completed"] else "[ ]"
                    pri = task.get("priority", "medium")
                    log_widget.write_line(f"  {done} [{task['id'][:8]}]  ({pri})  {task['title']}")
        except Exception as exc:
            try:
                log_widget.write_line(f"Error loading tasks: {exc}")
            except Exception:
                pass
