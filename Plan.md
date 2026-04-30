# New Module: YouTube

## Context

A new `youtube` module that lets users paste any YouTube URL, view video metadata, and download video, audio, or transcript to an organized project folder. Files are saved under `projects/<slug>/video/`, `projects/<slug>/audio/`, and `projects/<slug>/transcript/`. The module integrates with the existing tab system and BaseProjectScreen patterns.

---

## Tool Research

| Tool | Type | Role |
|------|------|------|
| **yt-dlp** | pip + CLI binary | Video/audio download, metadata fetch, format/quality selection |
| **youtube-transcript-api** | pip | Fetch built-in YouTube captions (fast, no local processing) |
| **faster-whisper** | pip (heavy, optional) | Local audio transcription when no captions exist |
| **ffmpeg** | system binary | Required by yt-dlp for format conversion/muxing |

**Transcript flow:** Try `youtube-transcript-api` first (milliseconds, no local model). If the video has no captions, extract audio with yt-dlp then run `faster-whisper` locally. Whisper model is user-configurable (tiny/base/small/medium/large — default `base`, ~145 MB).

**yt-dlp usage pattern:** Use the Python API (`import yt_dlp`) wrapped in `asyncio.to_thread()` — not subprocess — for metadata fetch and downloads. Progress hooks push lines to a thread-safe queue; a companion coroutine drains the queue into the `#output-log` Log widget.

**Video ID extraction** (needed for transcript API):
```python
import re
def _extract_video_id(url: str) -> str | None:
    m = re.search(r'(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})', url)
    return m.group(1) if m else None
```

---

## Files to Create / Modify

### New files
```
modules/youtube/__init__.py           (empty)
modules/youtube/project_screen.py
modules/youtube/skills.py
modules/youtube/CLAUDE.template.md
```

### Modified files
```
nexus/core/module_manager.py          register module
nexus/app.py                          import skills at startup
pyproject.toml                        add pip dependencies
```

---

## 1. `pyproject.toml` — Add Dependencies

Under `[project] dependencies`:
```toml
"yt-dlp>=2024.1.1",
"youtube-transcript-api>=0.6.0",
"faster-whisper>=1.0.0",
```

`ffmpeg` is a system binary checked via `REQUIRED_BINARIES`; it is not a pip dep.

---

## 2. `nexus/core/module_manager.py` — Register Module

**Add to `_REGISTRY`** (keep alphabetical order, before `vault`):
```python
ModuleInfo("youtube", "YouTube", "Download videos, audio and transcripts from YouTube.", ["media", "download"]),
```

**`needs_setup()`** — add before the final `return False`:
```python
if project.module == "youtube":
    cfg = load_project_config(project.slug)
    return not cfg.get("youtube", {}).get("configured", False)
```

**`get_setup_screen()`** — add case (returns same screen; BaseProjectScreen handles setup inline):
```python
if project.module == "youtube":
    from modules.youtube.project_screen import YouTubeProjectScreen
    return YouTubeProjectScreen(project)
```

**`get_project_screen()`** — add case:
```python
if project.module == "youtube":
    from modules.youtube.project_screen import YouTubeProjectScreen
    return YouTubeProjectScreen(project)
```

---

## 3. `nexus/app.py` — Register Skills

In `_register_skills()`, add:
```python
import modules.youtube.skills    # noqa: F401
```

---

## 4. `modules/youtube/project_screen.py`

### Class skeleton
```python
class YouTubeProjectScreen(BaseProjectScreen):
    MODULE_KEY        = "youtube"
    MODULE_LABEL      = "YOUTUBE"
    REQUIRED_BINARIES = [("yt-dlp", "yt-dlp"), ("ffmpeg", "ffmpeg")]
    SETUP_FIELDS      = [
        {"id": "whisper_model",
         "label": "Whisper model for transcription fallback (tiny/base/small/medium/large)",
         "placeholder": "base"},
    ]
```

### State attributes (set in `__init__` or as class vars)
```python
_video_info: dict | None = None   # fetched yt-dlp metadata
```

### `_compose_action_buttons()`
```python
return [
    Button("Open Video Folder",      id="btn-open-video-dir"),
    Button("Open Audio Folder",      id="btn-open-audio-dir"),
    Button("Open Transcript Folder", id="btn-open-transcript-dir"),
]
```

### `_primary_folder()`
Returns `Path(self.project.path)` (the project root, which contains `video/`, `audio/`, `transcript/`).

### `async _populate_content()`

The content area has two sections:

**Section A — URL input row** (always visible):
```python
Horizontal(
    Input(placeholder="https://youtube.com/watch?v=...", id="url-input"),
    Button("Fetch Info", id="btn-fetch", variant="primary"),
    classes="url-row",
)
```

**Section B — video info** (only when `_video_info` is set):
```python
Label("Video Info", classes="section-label")
Horizontal(Label("Title:",    classes="info-key"), Label(title,    classes="info-val"), classes="info-row")
Horizontal(Label("Channel:",  classes="info-key"), Label(channel,  classes="info-val"), classes="info-row")
Horizontal(Label("Duration:", classes="info-key"), Label(duration, classes="info-val"), classes="info-row")
Horizontal(Label("Date:",     classes="info-key"), Label(date,     classes="info-val"), classes="info-row")
Label("Download", classes="section-label")
# Video download row
Horizontal(
    Select(video_quality_options, id="video-quality-select"),
    Select(VIDEO_FORMATS, id="video-format-select"),
    Button("Download Video", id="btn-dl-video", variant="primary"),
    classes="dl-row",
)
# Audio download row
Horizontal(
    Select(AUDIO_QUALITY_OPTIONS, id="audio-quality-select"),
    Select(AUDIO_FORMATS, id="audio-format-select"),
    Button("Download Audio", id="btn-dl-audio", variant="success"),
    classes="dl-row",
)
# Transcript row
Horizontal(
    Button("Download Transcript", id="btn-dl-transcript"),
    classes="dl-row",
)
```

**Constants:**
```python
VIDEO_FORMATS       = [("mp4","mp4"),("mkv","mkv"),("webm","webm")]
VIDEO_QUALITIES     = [("best","Best"),("1080","1080p"),("720","720p"),("480","480p"),("360","360p")]
AUDIO_FORMATS       = [("mp3","mp3"),("m4a","m4a"),("opus","opus"),("flac","flac")]
AUDIO_QUALITY_OPTIONS = [("320","320k"),("192","192k"),("128","128k")]
```

### `_handle_action(bid)`

| Button ID | Action |
|-----------|--------|
| `btn-fetch` | Read `#url-input`, run `_fetch_info(url)` worker |
| `btn-dl-video` | Read quality+format selects, run `_download_video(url, quality, fmt)` worker |
| `btn-dl-audio` | Read quality+format selects, run `_download_audio(url, quality, fmt)` worker |
| `btn-dl-transcript` | Run `_download_transcript(url)` worker |
| `btn-open-video-dir` | `_run_cmd(open_path(project.path / "video"))` |
| `btn-open-audio-dir` | `_run_cmd(open_path(project.path / "audio"))` |
| `btn-open-transcript-dir` | `_run_cmd(open_path(project.path / "transcript"))` |

Note: `btn-fetch` is inside `#content-area`, not the action bar. Handle it via `on_button_pressed` override checking the button ID before falling through to `_handle_action`.

### `async _fetch_info(url: str)`
```python
async def _fetch_info(self, url: str) -> None:
    try:
        ui_log = self.query_one("#output-log", Log)
    except Exception:
        return
    ui_log.write_line(f"$ Fetching info: {url}")
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        info = await asyncio.to_thread(
            lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=False)
        )
    except Exception as exc:
        ui_log.write_line(f"✗ Could not fetch info: {exc}")
        self.app.notify("Failed to fetch video info.", severity="error")
        return
    self._video_info = info
    self._current_url = url
    await self._populate_content()
    ui_log.write_line(f"✓ Fetched: {info.get('title', 'Unknown')}")
```

### `async _download_video(url, quality, fmt)`
```python
async def _download_video(self, url: str, quality: str, fmt: str) -> None:
    out_dir = self.project.path / "video"
    out_dir.mkdir(exist_ok=True)
    height_filter = f"[height<={quality}]" if quality != "best" else ""
    ydl_opts = {
        "format": f"bestvideo{height_filter}+bestaudio/best",
        "merge_output_format": fmt,
        "outtmpl": str(out_dir / "%(title)s.%(ext)s"),
        "progress_hooks": [self._make_progress_hook()],
        "quiet": True,
    }
    try:
        await asyncio.to_thread(
            lambda: yt_dlp.YoutubeDL(ydl_opts).download([url])
        )
        self.app.notify("Video download complete.", severity="information")
    except Exception as exc:
        self.app.notify(f"Download failed: {exc}", severity="error")
```

`_make_progress_hook()` returns a closure that formats progress lines and writes to `#output-log` via `self.app.call_from_thread(ui_log.write_line, line)`.

### `async _download_audio(url, quality, fmt)` — same pattern as video

### `async _download_transcript(url: str)`
```python
async def _download_transcript(self, url: str) -> None:
    out_dir = self.project.path / "transcript"
    out_dir.mkdir(exist_ok=True)
    video_id = _extract_video_id(url)
    title = (self._video_info or {}).get("title", video_id or "transcript")
    safe_title = re.sub(r'[^\w\s-]', '', title).strip()[:80]
    out_path = out_dir / f"{safe_title}.md"

    # 1. Try YouTube captions
    transcript_lines = await asyncio.to_thread(_try_youtube_captions, video_id)

    if transcript_lines is None:
        # 2. Whisper fallback: extract audio then transcribe
        transcript_lines = await self._whisper_transcribe(url, safe_title)

    if transcript_lines is None:
        self.app.notify("Could not obtain transcript.", severity="error")
        return

    md_content = f"# {title}\n\n" + "\n".join(transcript_lines)
    out_path.write_text(md_content, encoding="utf-8")
    self.app.notify(f"Saved: {out_path.name}", severity="information")
```

**`_try_youtube_captions(video_id)` (sync, runs in thread):**
```python
def _try_youtube_captions(video_id: str | None) -> list[str] | None:
    if not video_id:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        segments = YouTubeTranscriptApi.get_transcript(video_id)
        return [s["text"] for s in segments]
    except Exception:
        return None
```

**`async _whisper_transcribe(url, title)`:**
1. Extract audio: `yt-dlp --extract-audio --audio-format wav -o /tmp/nexus_yt_audio.wav`
2. Run `faster-whisper` via `asyncio.to_thread`
3. Return list of segment texts

```python
async def _whisper_transcribe(self, url: str, title: str) -> list[str] | None:
    tmp_audio = Path(tempfile.mktemp(suffix=".wav", prefix="nexus_yt_"))
    try:
        # Step 1: extract audio
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
            "outtmpl": str(tmp_audio.with_suffix("")),  # yt-dlp appends extension
            "quiet": True,
        }
        await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))

        # Step 2: transcribe
        model_name = self._mod.get("whisper_model", "base")
        def _run_whisper():
            from faster_whisper import WhisperModel
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            segments, _ = model.transcribe(str(tmp_audio))
            return [s.text.strip() for s in segments]

        return await asyncio.to_thread(_run_whisper)
    except Exception as exc:
        log.exception("Whisper transcription failed")
        self.app.notify(f"Transcription failed: {exc}", severity="error")
        return None
    finally:
        tmp_audio.unlink(missing_ok=True)
```

---

## 5. `modules/youtube/skills.py`

Register 4 skills under scope `"youtube"`:

| Skill | Inputs | Description |
|-------|--------|-------------|
| `youtube_fetch_info` | `project_slug`, `url` | Return title/channel/duration/date as JSON |
| `youtube_download_video` | `project_slug`, `url`, `quality?` (default "best"), `format?` (default "mp4") | Download video, return saved path |
| `youtube_download_audio` | `project_slug`, `url`, `format?` (default "mp3"), `quality?` (default "192") | Download audio, return saved path |
| `youtube_get_transcript` | `project_slug`, `url`, `use_whisper?` (default False) | Return transcript text or save as MD |

Each handler loads `load_project_config(slug).get("youtube", {})` for the whisper model setting.

---

## 6. `modules/youtube/CLAUDE.template.md`

Covers: yt-dlp format strings, common quality codes, transcript API usage, whisper model sizes and tradeoffs, folder layout, and a section for the user to describe their preferred quality defaults.

---

## CSS additions (in `project_screen.py` `DEFAULT_CSS`)

```css
YouTubeProjectScreen .url-row {
    height: 3;
    padding: 0 1;
}
YouTubeProjectScreen .url-row Input {
    width: 1fr;
}
YouTubeProjectScreen .dl-row {
    height: 3;
    padding: 0 1;
}
YouTubeProjectScreen .dl-row Select {
    width: 16;
}
```

---

## Verification

1. `uv sync` — installs yt-dlp, youtube-transcript-api, faster-whisper
2. `uv run nexus` → Add Project → YouTube tile visible
3. Create a YouTube project → setup pane asks for whisper model (accept default)
4. Paste a URL → click Fetch Info → video title/channel/duration/date appear
5. Click Download Video → mp4 appears in `projects/<slug>/video/`
6. Click Download Audio → mp3 appears in `projects/<slug>/audio/`
7. Click Download Transcript → try a video with subtitles → MD saved in `projects/<slug>/transcript/`
8. Try a video without subtitles with faster-whisper installed → whisper fallback runs
9. Open Video Folder button opens file manager to the video subdirectory
10. Tab bar visible; Ctrl+Tab cycles correctly; Escape goes back to tile grid
