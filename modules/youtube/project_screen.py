from __future__ import annotations
import asyncio
import re
import tempfile
from pathlib import Path

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.widgets import Label, Button, Log, Input, Select
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.platform import open_path
from nexus.ui.base_project_screen import BaseProjectScreen, _screen_css

log = get("youtube.project_screen")

_VIDEO_QUALITY_OPTS = [
    ("Best",  "best"),
    ("4K",    "2160"),
    ("1080p", "1080"),
    ("720p",  "720"),
    ("480p",  "480"),
    ("360p",  "360"),
]
_VIDEO_FORMAT_OPTS  = [("MP4",  "mp4"),  ("MKV",  "mkv"),  ("WebM", "webm")]
_AUDIO_FORMAT_OPTS  = [("MP3",  "mp3"),  ("M4A",  "m4a"),  ("Opus", "opus"),  ("FLAC", "flac")]
_AUDIO_QUALITY_OPTS = [("320k", "320"),  ("192k", "192"),  ("128k", "128")]


def _extract_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})", url)
    return m.group(1) if m else None


def _fmt_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "unknown"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _fmt_date(yyyymmdd: str | None) -> str:
    if not yyyymmdd or len(yyyymmdd) != 8:
        return yyyymmdd or "unknown"
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def _try_youtube_captions(video_id: str | None) -> list[str] | None:
    if not video_id:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        segments = YouTubeTranscriptApi.get_transcript(video_id)
        return [s["text"] for s in segments]
    except Exception:
        return None


class YouTubeProjectScreen(BaseProjectScreen):
    MODULE_KEY        = "youtube"
    MODULE_LABEL      = "YOUTUBE"
    REQUIRED_BINARIES = [("yt-dlp", "yt-dlp"), ("ffmpeg", "ffmpeg")]
    SETUP_FIELDS      = [
        {
            "id":          "whisper_model",
            "label":       "Whisper model for transcription fallback (tiny / base / small / medium / large)",
            "placeholder": "base",
            "optional":    True,
        },
    ]

    DEFAULT_CSS = (
        _screen_css("YouTubeProjectScreen")
        + """
        YouTubeProjectScreen .url-row {
            height: 3;
            padding: 0 0;
            margin-bottom: 1;
        }
        YouTubeProjectScreen .url-row Input {
            width: 1fr;
        }
        YouTubeProjectScreen .url-row Button {
            width: 12;
            margin-left: 1;
        }
        YouTubeProjectScreen .dl-row {
            height: 3;
            margin-top: 1;
        }
        YouTubeProjectScreen .dl-row Select {
            width: 12;
            margin-right: 1;
        }
        YouTubeProjectScreen .dl-row Button {
            margin-left: 1;
        }
        YouTubeProjectScreen .info-section {
            margin-top: 1;
        }
        """
    )

    def __init__(self, project, **kwargs) -> None:
        super().__init__(project, **kwargs)
        self._video_info: dict | None = None
        self._current_url: str = ""

    def _on_before_save(self, data: dict) -> dict:
        if not data.get("whisper_model"):
            data["whisper_model"] = "base"
        return {}

    def _compose_action_buttons(self) -> list:
        return [
            Button("📁 Video",      id="btn-open-video-dir"),
            Button("📁 Audio",      id="btn-open-audio-dir"),
            Button("📁 Transcript", id="btn-open-transcript-dir"),
        ]

    def _primary_folder(self) -> Path | None:
        return self.project.path

    # ── Content area ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        try:
            area = self.query_one("#content-area", Vertical)
        except NoMatches:
            return
        await area.remove_children()

        widgets: list = [
            Label("YouTube Downloader", classes="section-label"),
            Horizontal(
                Input(
                    value=self._current_url,
                    placeholder="https://www.youtube.com/watch?v=...  or  https://youtu.be/...",
                    id="url-input",
                ),
                Button("Fetch Info", id="btn-fetch", variant="primary"),
                classes="url-row",
            ),
        ]

        if self._video_info:
            info = self._video_info
            title    = info.get("title", "")
            channel  = info.get("channel") or info.get("uploader", "")
            duration = _fmt_duration(info.get("duration"))
            date_str = _fmt_date(info.get("upload_date"))
            views    = info.get("view_count")
            views_str = f"{views:,}" if views else "unknown"

            widgets += [
                Label("", classes="hint"),
                Label("Video Info", classes="section-label"),
                Horizontal(Label("Title:",    classes="info-key"), Label(title,    classes="info-val"), classes="info-row"),
                Horizontal(Label("Channel:",  classes="info-key"), Label(channel,  classes="info-val"), classes="info-row"),
                Horizontal(Label("Duration:", classes="info-key"), Label(duration, classes="info-val"), classes="info-row"),
                Horizontal(Label("Date:",     classes="info-key"), Label(date_str, classes="info-val"), classes="info-row"),
                Horizontal(Label("Views:",    classes="info-key"), Label(views_str, classes="info-val"), classes="info-row"),
                Label("", classes="hint"),
                Label("Download", classes="section-label"),
                Horizontal(
                    Select(_VIDEO_QUALITY_OPTS, id="video-quality", allow_blank=False, value="best"),
                    Select(_VIDEO_FORMAT_OPTS,  id="video-format",  allow_blank=False, value="mp4"),
                    Button("⬇ Download Video",      id="btn-dl-video",      variant="primary"),
                    classes="dl-row",
                ),
                Horizontal(
                    Select(_AUDIO_FORMAT_OPTS,  id="audio-format",  allow_blank=False, value="mp3"),
                    Select(_AUDIO_QUALITY_OPTS, id="audio-quality", allow_blank=False, value="192"),
                    Button("⬇ Download Audio",      id="btn-dl-audio",      variant="success"),
                    classes="dl-row",
                ),
                Horizontal(
                    Button("⬇ Download Transcript", id="btn-dl-transcript"),
                    classes="dl-row",
                ),
            ]
        else:
            # Show folder stats when idle
            for subdir, label in [("video", "Videos"), ("audio", "Audio"), ("transcript", "Transcripts")]:
                folder = self.project.path / subdir
                count = len(list(folder.iterdir())) if folder.exists() else 0
                widgets.append(
                    Horizontal(
                        Label(f"{label}:", classes="info-key"),
                        Label(str(count), classes="info-val"),
                        classes="info-row",
                    )
                )

        await area.mount(*widgets)

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        if bid == "btn-fetch":
            self._do_fetch()
        elif bid == "btn-dl-video":
            self._do_download_video()
        elif bid == "btn-dl-audio":
            self._do_download_audio()
        elif bid == "btn-dl-transcript":
            self.run_worker(self._download_transcript(self._current_url))
        elif bid == "btn-open-video-dir":
            folder = self.project.path / "video"
            folder.mkdir(exist_ok=True)
            self.run_worker(self._run_cmd(open_path(folder)))
        elif bid == "btn-open-audio-dir":
            folder = self.project.path / "audio"
            folder.mkdir(exist_ok=True)
            self.run_worker(self._run_cmd(open_path(folder)))
        elif bid == "btn-open-transcript-dir":
            folder = self.project.path / "transcript"
            folder.mkdir(exist_ok=True)
            self.run_worker(self._run_cmd(open_path(folder)))

    def _do_fetch(self) -> None:
        try:
            url = self.query_one("#url-input", Input).value.strip()
        except NoMatches:
            return
        if not url:
            self.app.notify("Enter a YouTube URL first.", severity="warning")
            return
        self.run_worker(self._fetch_info(url))

    def _do_download_video(self) -> None:
        try:
            quality = self.query_one("#video-quality", Select).value
            fmt     = self.query_one("#video-format",  Select).value
        except NoMatches:
            return
        if quality is Select.BLANK:
            quality = "best"
        if fmt is Select.BLANK:
            fmt = "mp4"
        self.run_worker(self._download_video(self._current_url, str(quality), str(fmt)))

    def _do_download_audio(self) -> None:
        try:
            fmt     = self.query_one("#audio-format",  Select).value
            quality = self.query_one("#audio-quality", Select).value
        except NoMatches:
            return
        if fmt is Select.BLANK:
            fmt = "mp3"
        if quality is Select.BLANK:
            quality = "192"
        self.run_worker(self._download_audio(self._current_url, str(fmt), str(quality)))

    # ── Fetch info ────────────────────────────────────────────────────────────

    async def _fetch_info(self, url: str) -> None:
        try:
            ui_log = self.query_one("#output-log", Log)
        except NoMatches:
            return
        ui_log.write_line(f"$ Fetching info: {url}")
        try:
            import yt_dlp
            opts = {"quiet": True, "no_warnings": True, "skip_download": True}
            info = await asyncio.to_thread(
                lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=False)
            )
        except Exception as exc:
            try:
                ui_log.write_line(f"✗ Could not fetch info: {exc}")
            except Exception:
                pass
            self.app.notify("Failed to fetch video info.", severity="error")
            return
        self._video_info = info
        self._current_url = url
        try:
            ui_log.write_line(f"✓ {info.get('title', 'fetched')}")
        except Exception:
            pass
        await self._safe_populate()

    # ── Download helpers ──────────────────────────────────────────────────────

    def _make_progress_hook(self) -> object:
        def hook(d: dict) -> None:
            if d["status"] == "downloading":
                pct   = d.get("_percent_str", "").strip()
                speed = d.get("_speed_str",   "").strip()
                eta   = d.get("_eta_str",     "").strip()
                if pct:
                    line = f"  {pct}  {speed}  ETA {eta}"
                    self.app.call_from_thread(self._log_line, line)
            elif d["status"] == "finished":
                filename = Path(d.get("filename", "")).name
                self.app.call_from_thread(self._log_line, f"✓ Merged: {filename}")
        return hook

    def _log_line(self, line: str) -> None:
        try:
            self.query_one("#output-log", Log).write_line(line)
        except Exception:
            pass

    async def _download_video(self, url: str, quality: str, fmt: str) -> None:
        try:
            ui_log = self.query_one("#output-log", Log)
        except NoMatches:
            return
        out_dir = self.project.path / "video"
        out_dir.mkdir(exist_ok=True)

        if quality == "best":
            fmt_str = "bestvideo+bestaudio/best"
        else:
            fmt_str = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best[height<={quality}]"

        import yt_dlp
        opts = {
            "format":             fmt_str,
            "merge_output_format": fmt,
            "outtmpl":            str(out_dir / "%(title)s.%(ext)s"),
            "progress_hooks":     [self._make_progress_hook()],
            "quiet":              True,
            "no_warnings":        True,
        }
        try:
            ui_log.write_line(f"$ Downloading video ({quality}, {fmt}): {url}")
            await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(opts).download([url]))
            self.app.notify("Video download complete.", severity="information")
            try:
                ui_log.write_line(f"✓ Saved to {out_dir}/")
            except Exception:
                pass
        except Exception as exc:
            log.exception("Video download failed")
            try:
                ui_log.write_line(f"✗ Download failed: {exc}")
            except Exception:
                pass
            self.app.notify("Video download failed — see log.", severity="error")

    async def _download_audio(self, url: str, fmt: str, quality: str) -> None:
        try:
            ui_log = self.query_one("#output-log", Log)
        except NoMatches:
            return
        out_dir = self.project.path / "audio"
        out_dir.mkdir(exist_ok=True)

        import yt_dlp
        opts = {
            "format":         "bestaudio/best",
            "postprocessors": [{
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   fmt,
                "preferredquality": quality,
            }],
            "outtmpl":         str(out_dir / "%(title)s.%(ext)s"),
            "progress_hooks":  [self._make_progress_hook()],
            "quiet":           True,
            "no_warnings":     True,
        }
        try:
            ui_log.write_line(f"$ Downloading audio ({fmt}, {quality}k): {url}")
            await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(opts).download([url]))
            self.app.notify("Audio download complete.", severity="information")
            try:
                ui_log.write_line(f"✓ Saved to {out_dir}/")
            except Exception:
                pass
        except Exception as exc:
            log.exception("Audio download failed")
            try:
                ui_log.write_line(f"✗ Download failed: {exc}")
            except Exception:
                pass
            self.app.notify("Audio download failed — see log.", severity="error")

    # ── Transcript ────────────────────────────────────────────────────────────

    async def _download_transcript(self, url: str) -> None:
        try:
            ui_log = self.query_one("#output-log", Log)
        except NoMatches:
            return
        if not url:
            self.app.notify("Fetch video info first.", severity="warning")
            return

        out_dir = self.project.path / "transcript"
        out_dir.mkdir(exist_ok=True)

        title    = (self._video_info or {}).get("title", "transcript")
        safe_title = re.sub(r"[^\w\s-]", "", title).strip()[:80] or "transcript"
        out_path = out_dir / f"{safe_title}.md"

        video_id = _extract_video_id(url)
        ui_log.write_line("$ Trying YouTube captions…")

        lines = await asyncio.to_thread(_try_youtube_captions, video_id)

        if lines is None:
            ui_log.write_line("  No captions found — starting local transcription (Whisper)…")
            lines = await self._whisper_transcribe(url, safe_title)

        if lines is None:
            return

        md = f"# {title}\n\n" + "\n".join(lines) + "\n"
        try:
            out_path.write_text(md, encoding="utf-8")
        except Exception as exc:
            log.exception("Failed to write transcript")
            try:
                ui_log.write_line(f"✗ Could not save: {exc}")
            except Exception:
                pass
            self.app.notify("Could not save transcript.", severity="error")
            return

        try:
            ui_log.write_line(f"✓ Saved: {out_path.name}")
        except Exception:
            pass
        self.app.notify(f"Transcript saved: {out_path.name}", severity="information")

    async def _whisper_transcribe(self, url: str, safe_title: str) -> list[str] | None:
        try:
            ui_log = self.query_one("#output-log", Log)
        except NoMatches:
            return None

        tmp_stem = Path(tempfile.mktemp(prefix="nexus_yt_", suffix=""))
        tmp_audio = Path(str(tmp_stem) + ".wav")

        try:
            import yt_dlp
            ydl_opts = {
                "format":         "bestaudio/best",
                "postprocessors": [{
                    "key":            "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                }],
                "outtmpl":  str(tmp_stem),
                "quiet":    True,
                "no_warnings": True,
            }
            try:
                ui_log.write_line("  Extracting audio for transcription…")
            except Exception:
                pass
            await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))

            if not tmp_audio.exists():
                # yt-dlp sometimes names the file differently
                candidates = list(tmp_stem.parent.glob(f"{tmp_stem.name}.*"))
                if candidates:
                    tmp_audio = candidates[0]

            model_name = self._mod.get("whisper_model", "base")
            try:
                ui_log.write_line(f"  Running Whisper ({model_name})…")
            except Exception:
                pass

            def _run_whisper() -> list[str]:
                from faster_whisper import WhisperModel
                model = WhisperModel(model_name, device="cpu", compute_type="int8")
                segments, _ = model.transcribe(str(tmp_audio))
                return [s.text.strip() for s in segments if s.text.strip()]

            return await asyncio.to_thread(_run_whisper)

        except ImportError:
            try:
                ui_log.write_line("✗ faster-whisper not installed — cannot transcribe without captions.")
            except Exception:
                pass
            self.app.notify("Install faster-whisper for local transcription.", severity="warning")
            return None
        except Exception as exc:
            log.exception("Whisper transcription failed")
            try:
                ui_log.write_line(f"✗ Transcription failed: {exc}")
            except Exception:
                pass
            self.app.notify("Transcription failed — see log.", severity="error")
            return None
        finally:
            for p in [tmp_audio, tmp_stem]:
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
