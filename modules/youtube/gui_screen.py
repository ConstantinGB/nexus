from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QHBoxLayout, QLabel
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("youtube.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "youtube"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"YouTube — {project.name}")
        self._mod = self._cfg.get("youtube", {})
        self._populate()

    def _build_toolbar(self) -> None:
        self._add_btn("Download Video",      self._dl_video,      primary=True)
        self._add_btn("Download Audio",      self._dl_audio)
        self._add_btn("Download Transcript", self._dl_transcript)
        self._add_btn("Open Video Dir",      self._open_video)
        self._add_btn("Open Audio Dir",      self._open_audio)
        self._add_btn("Open Transcript Dir", self._open_transcript)

    def _build_extra(self) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel("URL:"))
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        row.addWidget(self._url_input)
        self._extra_layout.addLayout(row)

    def _populate(self) -> None:
        m = self._mod
        self._set_info([
            ("Whisper model",   m.get("whisper_model", "base")),
            ("Video dir",       m.get("video_dir", "")),
            ("Audio dir",       m.get("audio_dir", "")),
            ("Transcript dir",  m.get("transcript_dir", "")),
        ])

    def _url(self) -> str:
        return self._url_input.text().strip()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _dl_video(self) -> None:
        url = self._url()
        if not url:
            self._append("[warn] Enter a YouTube URL first.")
            return
        out = self._mod.get("video_dir", ".")
        self._run_cmd(["yt-dlp", "-f", "bestvideo+bestaudio", "-o",
                        f"{out}/%(title)s.%(ext)s", url])

    def _dl_audio(self) -> None:
        url = self._url()
        if not url:
            self._append("[warn] Enter a YouTube URL first.")
            return
        out = self._mod.get("audio_dir", ".")
        self._run_cmd(["yt-dlp", "-x", "--audio-format", "mp3",
                        "-o", f"{out}/%(title)s.%(ext)s", url])

    def _dl_transcript(self) -> None:
        url = self._url()
        if not url:
            self._append("[warn] Enter a YouTube URL first.")
            return
        self._not_implemented("Transcript download")

    def _open_video(self) -> None:
        d = self._mod.get("video_dir", "")
        if d:
            from nexus.core.platform import open_path
            open_path(d)

    def _open_audio(self) -> None:
        d = self._mod.get("audio_dir", "")
        if d:
            from nexus.core.platform import open_path
            open_path(d)

    def _open_transcript(self) -> None:
        d = self._mod.get("transcript_dir", "")
        if d:
            from nexus.core.platform import open_path
            open_path(d)
