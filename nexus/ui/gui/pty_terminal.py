"""PTY-backed interactive terminal widget for PySide6.

Spawns a process in a pseudo-terminal, uses pyte to track screen state, and
renders the screen buffer as HTML into a QTextEdit.  QSocketNotifier watches
the PTY master fd so the Qt event loop is never blocked.

Usage
-----
    term = PtyTerminalWidget("bash -i", cwd="/some/dir", parent=self)
    term.start()   # call when the widget becomes visible (lazy)
    term.stop()    # call on close / tab switch away if you want to kill the process
    term.process_stopped.connect(...)
"""
from __future__ import annotations

import fcntl
import html as _html_mod
import os
import pty
import re
import shlex
import shutil
import signal
import struct
import termios

import pyte
from PySide6.QtCore import Qt, Signal, QSocketNotifier, QTimer
from PySide6.QtGui import QFont, QFontMetrics, QKeyEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit

from nexus.core.logger import get

log = get("ui.gui.pty_terminal")

_DEFAULT_FG = "#E0D0FF"
_DEFAULT_BG = "#1A0A2E"

_ANSI_NAMED: dict[str, str] = {
    "black":         "#1A0A2E",
    "red":           "#FF4444",
    "green":         "#00FF88",
    "brown":         "#FFAA00",
    "blue":          "#5555FF",
    "magenta":       "#B45AFF",
    "cyan":          "#00D9FF",
    "white":         "#E0D0FF",
    "brightblack":   "#664D88",
    "brightred":     "#FF6666",
    "brightgreen":   "#44FF88",
    "brightyellow":  "#FFFF66",
    "brightblue":    "#7777FF",
    "brightmagenta": "#CC88FF",
    "brightcyan":    "#66EEFF",
    "brightwhite":   "#FFFFFF",
}

# Maps the first 8 xterm-256 indices to our named palette
_XTERM16 = list(_ANSI_NAMED.values())


def _xterm256(n: int) -> str:
    if n < 16:
        return _XTERM16[n]
    if n < 232:
        n -= 16
        r, g, b = n // 36, (n // 6) % 6, n % 6
        v = lambda x: 0 if x == 0 else 55 + x * 40
        return f"#{v(r):02x}{v(g):02x}{v(b):02x}"
    grey = 8 + (n - 232) * 10
    return f"#{grey:02x}{grey:02x}{grey:02x}"


def _resolve_color(name: str, default: str) -> str:
    if not name or name == "default":
        return default
    if name in _ANSI_NAMED:
        return _ANSI_NAMED[name]
    m = re.fullmatch(r"color(\d+)", name)
    if m:
        return _xterm256(int(m.group(1)))
    if re.fullmatch(r"[0-9a-fA-F]{6}", name):
        return f"#{name}"
    return default


# ── Key map ───────────────────────────────────────────────────────────────────

_KEY_MAP: dict[int, bytes] = {
    int(Qt.Key.Key_Up):        b"\x1b[A",
    int(Qt.Key.Key_Down):      b"\x1b[B",
    int(Qt.Key.Key_Right):     b"\x1b[C",
    int(Qt.Key.Key_Left):      b"\x1b[D",
    int(Qt.Key.Key_Home):      b"\x1b[H",
    int(Qt.Key.Key_End):       b"\x1b[F",
    int(Qt.Key.Key_Delete):    b"\x1b[3~",
    int(Qt.Key.Key_Insert):    b"\x1b[2~",
    int(Qt.Key.Key_PageUp):    b"\x1b[5~",
    int(Qt.Key.Key_PageDown):  b"\x1b[6~",
    int(Qt.Key.Key_F1):        b"\x1bOP",
    int(Qt.Key.Key_F2):        b"\x1bOQ",
    int(Qt.Key.Key_F3):        b"\x1bOR",
    int(Qt.Key.Key_F4):        b"\x1bOS",
    int(Qt.Key.Key_F5):        b"\x1b[15~",
    int(Qt.Key.Key_F6):        b"\x1b[17~",
    int(Qt.Key.Key_F7):        b"\x1b[18~",
    int(Qt.Key.Key_F8):        b"\x1b[19~",
    int(Qt.Key.Key_F9):        b"\x1b[20~",
    int(Qt.Key.Key_F10):       b"\x1b[21~",
    int(Qt.Key.Key_F11):       b"\x1b[23~",
    int(Qt.Key.Key_F12):       b"\x1b[24~",
    int(Qt.Key.Key_Backspace): b"\x7f",
    int(Qt.Key.Key_Return):    b"\r",
    int(Qt.Key.Key_Enter):     b"\r",
    int(Qt.Key.Key_Tab):       b"\t",
    int(Qt.Key.Key_Escape):    b"\x1b",
}

_CTRL_SPECIALS: dict[int, bytes] = {
    int(Qt.Key.Key_BracketLeft):  b"\x1b",
    int(Qt.Key.Key_Backslash):    b"\x1c",
    int(Qt.Key.Key_BracketRight): b"\x1d",
    int(Qt.Key.Key_Space):        b"\x00",
}


# ── Internal display widget ───────────────────────────────────────────────────

class _KeyForwardEdit(QTextEdit):
    """Read-only QTextEdit that re-emits all key events for PTY forwarding."""

    key_pressed: Signal = Signal(object)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        self.key_pressed.emit(event)
        event.accept()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        event.accept()


# ── Public widget ─────────────────────────────────────────────────────────────

class PtyTerminalWidget(QWidget):
    """PTY-backed interactive terminal for PySide6.

    Call start() when the tab/panel becomes visible.
    The widget cleans up the child process on close or when stop() is called.
    When the child exits, _started is reset so the next start() call relaunches.
    """

    process_stopped: Signal = Signal()

    def __init__(
        self,
        command: str,
        cwd: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._command  = command
        self._cwd      = cwd
        self._pid:      int | None = None
        self._fd:       int | None = None
        self._notifier: QSocketNotifier | None = None
        self._cols  = 120
        self._rows  = 40
        self._started   = False
        self._dirty     = False  # pending render

        self._screen = pyte.Screen(self._cols, self._rows)
        self._stream = pyte.Stream(self._screen)

        self._build_ui()

        # Batch renders to ~20 fps to avoid calling setHtml() on every byte
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(50)
        self._render_timer.timeout.connect(self._do_render)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._display = _KeyForwardEdit(self)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self._display.setFont(font)
        self._display.setStyleSheet(
            f"background-color:{_DEFAULT_BG}; color:{_DEFAULT_FG}; border:none;"
        )
        self._display.key_pressed.connect(self._forward_key)
        layout.addWidget(self._display)
        self.setFocusProxy(self._display)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the child process.  Safe to call multiple times; no-op if running."""
        if self._started:
            return
        self._started = True
        self._update_dimensions()
        self._fork_process()

    def _fork_process(self) -> None:
        argv0 = shlex.split(self._command)[0]
        if not shutil.which(argv0):
            self._display.setPlainText(
                f"Command not found: {argv0!r}\n"
                "Make sure it is installed and available in your PATH."
            )
            self._started = False
            return

        try:
            self._pid, self._fd = pty.fork()
        except OSError as exc:
            log.error("pty.fork() failed: %s", exc)
            self._display.setPlainText(f"[error] pty.fork(): {exc}")
            self._started = False
            return

        if self._pid == 0:
            # ── child ─────────────────────────────────────────────────────────
            if self._cwd:
                try:
                    os.chdir(self._cwd)
                except OSError:
                    pass
            env  = {**os.environ, "TERM": "xterm-256color", "LC_ALL": "en_US.UTF-8"}
            argv = shlex.split(self._command)
            os.execvpe(argv[0], argv, env)
            os._exit(1)
        else:
            # ── parent ────────────────────────────────────────────────────────
            self._set_pty_size()
            self._notifier = QSocketNotifier(self._fd, QSocketNotifier.Type.Read, self)
            self._notifier.activated.connect(self._on_data_ready)

    def stop(self) -> None:
        """Terminate the child process and release the PTY fd."""
        if self._notifier:
            self._notifier.setEnabled(False)
            self._notifier = None
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        if self._pid is not None:
            try:
                os.kill(self._pid, signal.SIGTERM)
                os.waitpid(self._pid, os.WNOHANG)
            except (OSError, ChildProcessError):
                pass
            self._pid = None
        self._started = False

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.stop()
        super().closeEvent(event)

    # ── PTY I/O ───────────────────────────────────────────────────────────────

    def _on_data_ready(self) -> None:
        if self._fd is None:
            return
        try:
            data = os.read(self._fd, 65536)
        except OSError:
            self._on_process_exit()
            return
        if not data:
            self._on_process_exit()
            return
        self._stream.feed(data.decode("utf-8", errors="replace"))
        self._dirty = True
        if not self._render_timer.isActive():
            self._render_timer.start()

    def _on_process_exit(self) -> None:
        if self._notifier:
            self._notifier.setEnabled(False)
            self._notifier = None
        self._fd  = None
        self._pid = None
        self._started = False
        # Flush any pending render first, then append the exit notice
        if self._dirty:
            self._do_render()
        self._display.append(
            '<span style="color:#664D88;font-style:italic;">'
            "[process exited — switch tabs to restart]</span>"
        )
        self.process_stopped.emit()

    def _write(self, data: bytes) -> None:
        if self._fd is None:
            return
        try:
            os.write(self._fd, data)
        except OSError:
            pass

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def _forward_key(self, event: QKeyEvent) -> None:
        if self._fd is None:
            return
        key  = int(event.key())
        mods = event.modifiers()
        text = event.text()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)

        if key in _KEY_MAP and not ctrl:
            self._write(_KEY_MAP[key])
            return

        if text:
            if ctrl:
                upper = text.upper()
                if upper.isalpha():
                    self._write(bytes([ord(upper) - 64]))
                elif key in _CTRL_SPECIALS:
                    self._write(_CTRL_SPECIALS[key])
            else:
                self._write(text.encode("utf-8", errors="replace"))

    # ── Resize ────────────────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        old = (self._cols, self._rows)
        self._update_dimensions()
        if (self._cols, self._rows) != old and self._fd is not None:
            self._screen.resize(self._rows, self._cols)
            self._set_pty_size()

    def _update_dimensions(self) -> None:
        fm = QFontMetrics(self._display.font())
        cw = max(1, fm.averageCharWidth())
        ch = max(1, fm.lineSpacing())
        w  = max(80 * cw, self.width()  - 20)
        h  = max(24 * ch, self.height() - 20)
        self._cols = max(10, w // cw)
        self._rows = max(5,  h // ch)

    def _set_pty_size(self) -> None:
        if self._fd is None:
            return
        try:
            fcntl.ioctl(self._fd, termios.TIOCSWINSZ, struct.pack("HH", self._rows, self._cols))
        except OSError:
            pass

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _do_render(self) -> None:
        self._dirty = False
        sb       = self._display.verticalScrollBar()
        at_bot   = sb.value() >= sb.maximum() - 5
        cur_y    = self._screen.cursor.y
        cur_x    = self._screen.cursor.x
        lines_html: list[str] = []

        for y in range(self._screen.lines):
            row    = self._screen.buffer[y]
            spans: list[str] = []
            run:   list[str] = []
            r_fg = r_bg = ""
            r_bold = False

            for x in range(self._screen.columns):
                ch   = row[x]
                fg   = _resolve_color(ch.fg, _DEFAULT_FG)
                bg   = _resolve_color(ch.bg, _DEFAULT_BG)
                bold = ch.bold

                if y == cur_y and x == cur_x:
                    fg, bg = _DEFAULT_BG, _DEFAULT_FG  # block cursor

                same = bool(run) and fg == r_fg and bg == r_bg and bold == r_bold
                if not same and run:
                    spans.append(_make_span(run, r_fg, r_bg, r_bold))
                    run = []
                r_fg, r_bg, r_bold = fg, bg, bold
                run.append(ch.data)

            if run:
                spans.append(_make_span(run, r_fg, r_bg, r_bold))

            lines_html.append("".join(spans))

        body = "\n".join(lines_html)
        html = (
            f'<html><body style="background-color:{_DEFAULT_BG};margin:0;padding:4px;">'
            f'<pre style="font-family:monospace;margin:0;color:{_DEFAULT_FG};">'
            f"{body}</pre></body></html>"
        )
        self._display.setHtml(html)
        if at_bot:
            sb.setValue(sb.maximum())


def _make_span(chars: list[str], fg: str, bg: str, bold: bool) -> str:
    text  = _html_mod.escape("".join(chars))
    style = f"color:{fg};"
    if bg != _DEFAULT_BG:
        style += f"background-color:{bg};"
    if bold:
        style += "font-weight:bold;"
    return f'<span style="{style}">{text}</span>'
