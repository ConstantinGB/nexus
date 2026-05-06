"""
PTY-backed terminal widget for Textual.

Forked from textual-terminal 0.3.0 (MIT) with three fixes:
  1. DEFAULT_COLORS import guarded — removed in Textual 8.x
  2. TerminalEmulator inherits parent os.environ so PATH / API keys reach claude
  3. cwd parameter lets the child process start in the project directory
  4. Terminal.ProcessStopped message posted when the subprocess exits
"""

from __future__ import annotations

import asyncio
import fcntl
import os
import pty
import re
import shlex
import signal
import struct
import termios
from asyncio import Task
from pathlib import Path

import pyte
from pyte.screens import Char

from rich.color import ColorParseError
from rich.style import Style
from rich.text import Text

from textual import events
from textual.message import Message
from textual.widget import Widget

try:
    from textual.app import DEFAULT_COLORS
except ImportError:
    DEFAULT_COLORS = {}


_re_ansi_sequence = re.compile(r"(\x1b\[\??[\d;]*[a-zA-Z])")
DECSET_PREFIX = "\x1b[?"


class TerminalPyteScreen(pyte.Screen):
    def set_margins(self, *args, **kwargs):
        kwargs.pop("private", None)
        return super().set_margins(*args, **kwargs)


class TerminalDisplay:
    def __init__(self, lines):
        self.lines = lines

    def __rich_console__(self, _console, _options):
        for line in self.lines:
            yield line


class Terminal(Widget, can_focus=True):
    """PTY-backed terminal widget."""

    DEFAULT_CSS = """
    Terminal {
        background: $background;
    }
    """

    class ProcessStopped(Message):
        """Posted when the subprocess inside the terminal exits."""

    def __init__(
        self,
        command: str,
        cwd: str | None = None,
        default_colors: str = "system",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.default_colors = default_colors
        self.textual_colors: dict | None = None

        self.ncol = 80
        self.nrow = 24
        self.mouse_tracking = False

        self.emulator: TerminalEmulator | None = None
        self.send_queue: asyncio.Queue | None = None
        self.recv_queue: asyncio.Queue | None = None
        self.recv_task: Task | None = None

        self.ctrl_keys = {
            "up": "\x1bOA", "down": "\x1bOB", "right": "\x1bOC", "left": "\x1bOD",
            "home": "\x1bOH", "end": "\x1b[F", "delete": "\x1b[3~",
            "pageup": "\x1b[5~", "pagedown": "\x1b[6~", "shift+tab": "\x1b[Z",
            "f1": "\x1bOP", "f2": "\x1bOQ", "f3": "\x1bOR", "f4": "\x1bOS",
            "f5": "\x1b[15~", "f6": "\x1b[17~", "f7": "\x1b[18~", "f8": "\x1b[19~",
            "f9": "\x1b[20~", "f10": "\x1b[21~", "f11": "\x1b[23~", "f12": "\x1b[24~",
        }
        self._display = TerminalDisplay([Text()])
        self._screen = TerminalPyteScreen(self.ncol, self.nrow)
        self.stream = pyte.Stream(self._screen)

        super().__init__(name=name, id=id, classes=classes)

    def start(self) -> None:
        if self.emulator is not None:
            return
        self.emulator = TerminalEmulator(command=self.command, cwd=self.cwd)
        self.emulator.start()
        self.send_queue = self.emulator.recv_queue
        self.recv_queue = self.emulator.send_queue
        self.recv_task = asyncio.create_task(self.recv())

    def stop(self) -> None:
        if self.emulator is None:
            return
        self._display = TerminalDisplay([Text()])
        if self.recv_task:
            self.recv_task.cancel()
        self.emulator.stop()
        self.emulator = None

    def render(self):
        return self._display

    async def on_key(self, event: events.Key) -> None:
        if self.emulator is None:
            return
        if event.key == "ctrl+f1":
            self.app.set_focus(None)
            return
        # Escape: forward to process but let it bubble so the screen's dismiss
        # binding still fires (e.g. pressing Escape to go back from a project).
        if event.key == "escape":
            await self.send_queue.put(["stdin", "\x1b"])
            return
        event.stop()
        char = self.ctrl_keys.get(event.key) or event.character
        if char:
            await self.send_queue.put(["stdin", char])

    async def on_resize(self, _event: events.Resize) -> None:
        if self.emulator is None:
            return
        self.ncol = self.size.width
        self.nrow = self.size.height
        await self.send_queue.put(["set_size", self.nrow, self.ncol])
        self._screen.resize(self.nrow, self.ncol)

    async def recv(self):
        try:
            while True:
                message = await self.recv_queue.get()
                cmd = message[0]
                if cmd == "setup":
                    await self.send_queue.put(["set_size", self.nrow, self.ncol])
                elif cmd == "stdout":
                    chars = message[1]
                    for sep_match in re.finditer(_re_ansi_sequence, chars):
                        sequence = sep_match.group(0)
                        if sequence.startswith(DECSET_PREFIX):
                            parameters = sequence.removeprefix(DECSET_PREFIX).split(";")
                            if "1000h" in parameters:
                                self.mouse_tracking = True
                            if "1000l" in parameters:
                                self.mouse_tracking = False
                    try:
                        self.stream.feed(chars)
                    except TypeError:
                        pass

                    lines = []
                    for y in range(self._screen.lines):
                        line_text = Text()
                        line = self._screen.buffer[y]
                        style_change_pos = 0
                        for x in range(self._screen.columns):
                            char: Char = line[x]
                            line_text.append(char.data)
                            if x > 0:
                                last_char = line[x - 1]
                                if not self._char_style_cmp(char, last_char) or x == self._screen.columns - 1:
                                    last_style = self._char_rich_style(last_char)
                                    line_text.stylize(last_style, style_change_pos, x + 1)
                                    style_change_pos = x
                            if self._screen.cursor.x == x and self._screen.cursor.y == y:
                                line_text.stylize("reverse", x, x + 1)
                        lines.append(line_text)

                    self._display = TerminalDisplay(lines)
                    self.refresh()

                elif cmd == "disconnect":
                    self.stop()
                    self.post_message(self.ProcessStopped())
        except asyncio.CancelledError:
            pass

    def _char_rich_style(self, char: Char) -> Style:
        fg = self._detect_color(char.fg)
        bg = self._detect_color(char.bg)
        try:
            return Style(color=fg, bgcolor=bg, bold=char.bold)
        except ColorParseError:
            return Style()

    def _char_style_cmp(self, a: Char, b: Char) -> bool:
        return (a.fg == b.fg and a.bg == b.bg and a.bold == b.bold
                and a.italics == b.italics and a.underscore == b.underscore
                and a.strikethrough == b.strikethrough and a.reverse == b.reverse
                and a.blink == b.blink)

    def _detect_color(self, color: str) -> str:
        if color == "brown":
            return "yellow"
        if color == "brightblack":
            return "#808080"
        if re.match("[0-9a-f]{6}", color, re.IGNORECASE):
            return f"#{color}"
        return color


class TerminalEmulator:
    def __init__(self, command: str, cwd: str | None = None) -> None:
        self.ncol = 80
        self.nrow = 24
        self.cwd = cwd
        self.data_or_disconnect = None
        self.run_task: asyncio.Task | None = None
        self.send_task: asyncio.Task | None = None

        self.fd = self._open_terminal(command)
        self.p_out = os.fdopen(self.fd, "w+b", 0)
        self.recv_queue: asyncio.Queue = asyncio.Queue()
        self.send_queue: asyncio.Queue = asyncio.Queue()
        self.event = asyncio.Event()

    def start(self) -> None:
        self.run_task = asyncio.create_task(self._run())
        self.send_task = asyncio.create_task(self._send_data())

    def stop(self) -> None:
        if self.run_task:
            self.run_task.cancel()
        if self.send_task:
            self.send_task.cancel()
        try:
            os.kill(self.pid, signal.SIGTERM)
        except (ProcessLookupError, ChildProcessError):
            pass
        try:
            os.waitpid(self.pid, os.WNOHANG)
        except (ProcessLookupError, ChildProcessError, ChildProcessError):
            pass

    def _open_terminal(self, command: str) -> int:
        self.pid, fd = pty.fork()
        if self.pid == 0:
            if self.cwd:
                os.chdir(self.cwd)
            argv = shlex.split(command)
            env = {**os.environ, "TERM": "xterm", "LC_ALL": "en_US.UTF-8"}
            os.execvpe(argv[0], argv, env)
        return fd

    async def _run(self):
        loop = asyncio.get_running_loop()

        def on_output():
            try:
                self.data_or_disconnect = self.p_out.read(65536).decode()
                self.event.set()
            except UnicodeDecodeError:
                pass
            except Exception:
                loop.remove_reader(self.p_out)
                self.data_or_disconnect = None
                self.event.set()

        loop.add_reader(self.p_out, on_output)
        await self.send_queue.put(["setup", {}])
        try:
            while True:
                msg = await self.recv_queue.get()
                if msg[0] == "stdin":
                    self.p_out.write(msg[1].encode())
                elif msg[0] == "set_size":
                    winsize = struct.pack("HH", msg[1], msg[2])
                    try:
                        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)
                    except OSError:
                        pass  # WSL 1 / limited POSIX environments
        except asyncio.CancelledError:
            pass

    async def _send_data(self):
        try:
            while True:
                await self.event.wait()
                self.event.clear()
                if self.data_or_disconnect is not None:
                    await self.send_queue.put(["stdout", self.data_or_disconnect])
                else:
                    await self.send_queue.put(["disconnect", 1])
        except asyncio.CancelledError:
            pass
