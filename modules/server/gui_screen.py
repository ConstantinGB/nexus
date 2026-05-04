from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("server.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "server"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Server — {project.name}")
        self._mod = self._cfg.get("server", {})
        self._populate()

    def _build_toolbar(self) -> None:
        self._add_btn("Add Service",    self._do_add,       primary=True)
        self._add_btn("Refresh",        self._populate)
        self._add_btn("Docker PS",      self._do_docker_ps)
        self._add_btn("Stats",          self._do_stats)

    def _build_extra(self) -> None:
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Name", "Port", "Type", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setMinimumHeight(160)
        self._extra_layout.addWidget(self._table)

    def _populate(self) -> None:
        self._mod = self._cfg.get("server", {})
        services = self._mod.get("services", [])
        compose  = self._mod.get("docker_compose_dir", "")
        self._set_info([
            ("Compose dir", compose or "(not set)"),
            ("Services",    str(len(services))),
        ])
        self._table.setRowCount(0)
        for svc in services:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(svc.get("name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(str(svc.get("port", ""))))
            self._table.setItem(row, 2, QTableWidgetItem(svc.get("type", "docker")))
            self._table.setItem(row, 3, QTableWidgetItem("—"))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _do_add(self) -> None:
        self._not_implemented("Add service dialog")

    def _do_docker_ps(self) -> None:
        self._run_cmd(["docker", "ps", "--format",
                       "table {{.Names}}\t{{.Status}}\t{{.Ports}}"])

    def _do_stats(self) -> None:
        self._run_cmd(["docker", "stats", "--no-stream"])
