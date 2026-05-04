from __future__ import annotations

import os
import shutil

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QSpinBox, QComboBox, QLabel, QVBoxLayout,
)

from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("backup.gui_screen")


class _BackupSettingsDialog(QDialog):
    def __init__(self, mod: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Backup Settings")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        form   = QFormLayout()
        form.setSpacing(8)

        self._repo = QLineEdit(mod.get("repo", ""))
        self._repo.setPlaceholderText("/path/to/repo or sftp:user@host:/path")
        form.addRow("Repository:", self._repo)

        warn = QLabel("⚠  Changing the repository requires re-initialisation.")
        warn.setStyleSheet("color: #FF8800; font-size: 11px;")
        form.addRow("", warn)

        self._paths = QLineEdit(", ".join(mod.get("paths", [])))
        self._paths.setPlaceholderText("~/projects, ~/documents")
        form.addRow("Paths (comma-separated):", self._paths)

        self._excludes = QLineEdit(", ".join(mod.get("excludes", [])))
        self._excludes.setPlaceholderText("*.tmp, .git, node_modules")
        form.addRow("Excludes (comma-separated):", self._excludes)

        self._schedule = QComboBox()
        for label, val in [("Manual", "manual"), ("Daily", "daily"), ("Weekly", "weekly")]:
            self._schedule.addItem(label, val)
        cur = mod.get("schedule", "manual")
        idx = self._schedule.findData(cur)
        if idx >= 0:
            self._schedule.setCurrentIndex(idx)
        form.addRow("Schedule:", self._schedule)

        self._keep_daily = QSpinBox()
        self._keep_daily.setRange(1, 365)
        self._keep_daily.setValue(int(mod.get("keep_daily", 7)))
        form.addRow("Keep daily snapshots:", self._keep_daily)

        self._keep_weekly = QSpinBox()
        self._keep_weekly.setRange(1, 52)
        self._keep_weekly.setValue(int(mod.get("keep_weekly", 4)))
        form.addRow("Keep weekly snapshots:", self._keep_weekly)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_result(self) -> dict:
        paths_raw    = self._paths.text()
        excludes_raw = self._excludes.text()
        return {
            "repo":         self._repo.text().strip(),
            "paths":        [p.strip() for p in paths_raw.split(",")    if p.strip()],
            "excludes":     [p.strip() for p in excludes_raw.split(",") if p.strip()],
            "schedule":     self._schedule.currentData(),
            "keep_daily":   self._keep_daily.value(),
            "keep_weekly":  self._keep_weekly.value(),
        }


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "backup"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Backup — {project.name}")
        self._mod = self._cfg.get("backup", {})
        self._populate()

    def _build_toolbar(self) -> None:
        self._add_btn("Run Backup",     self._do_backup,    primary=True)
        self._add_btn("List Snapshots", self._do_snapshots)
        self._add_btn("Check",          self._do_check)
        self._add_btn("Forget + Prune", self._do_forget)
        self._add_btn("Restore…",       self._do_restore)
        self._add_btn("Settings…",      self._do_settings)

    def _populate(self) -> None:
        m = self._mod
        last = (m.get("last_run") or "Never")[:16].replace("T", " ")
        paths = m.get("paths", [])
        self._set_info([
            ("Backend",    m.get("backend", "local")),
            ("Repository", m.get("repo", "")),
            ("Schedule",   m.get("schedule", "manual")),
            ("Paths",      ", ".join(paths) if paths else "(none)"),
            ("Retention",  f"daily={m.get('keep_daily', 7)}  weekly={m.get('keep_weekly', 4)}"),
            ("Excludes",   ", ".join(m.get("excludes", [])) or "(none)"),
            ("Last backup", last),
        ])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _restic_env(self) -> dict:
        return {**os.environ, "RESTIC_PASSWORD": self._mod.get("password", "")}

    def _do_backup(self) -> None:
        repo = self._mod.get("repo", "")
        if not repo:
            self._append("[error] Repository not configured — open Settings.")
            return
        if not shutil.which("restic"):
            self._append("[error] restic not found — install it first.")
            return
        self._run_cmd(
            ["restic", "-r", repo, "backup"] + self._mod.get("paths", []),
            env=self._restic_env(),
        )

    def _do_snapshots(self) -> None:
        repo = self._mod.get("repo", "")
        if not repo:
            self._append("[error] Repository not configured.")
            return
        self._run_cmd(["restic", "-r", repo, "snapshots"], env=self._restic_env())

    def _do_check(self) -> None:
        repo = self._mod.get("repo", "")
        if not repo:
            return
        self._run_cmd(["restic", "-r", repo, "check"], env=self._restic_env())

    def _do_forget(self) -> None:
        repo = self._mod.get("repo", "")
        if not repo:
            return
        self._run_cmd([
            "restic", "-r", repo, "forget", "--prune",
            f"--keep-daily={self._mod.get('keep_daily', 7)}",
            f"--keep-weekly={self._mod.get('keep_weekly', 4)}",
        ], env=self._restic_env())

    def _do_restore(self) -> None:
        self._not_implemented("Snapshot picker / restore")

    def _do_settings(self) -> None:
        dlg = _BackupSettingsDialog(dict(self._mod), self)
        if dlg.exec() != QDialog.Accepted:
            return
        result = dlg.get_result()
        from nexus.core.config_manager import load_project_config, save_project_config
        cfg = load_project_config(self.project.slug)
        cfg.setdefault("backup", {}).update(result)
        save_project_config(self.project.slug, cfg)
        self._mod = cfg["backup"]
        self._populate()
        self.statusBar().showMessage("Backup settings saved.")
