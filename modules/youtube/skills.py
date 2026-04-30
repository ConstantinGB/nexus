from __future__ import annotations
import asyncio
import json
import re
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


def _youtube_cfg(slug: str) -> dict:
    return load_project_config(slug).get("youtube", {})


def _extract_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})", url)
    return m.group(1) if m else None


async def _youtube_fetch_info(args: dict) -> str:
    slug = args.get("project_slug", "")
    url  = args.get("url", "")
    if not url:
        return json.dumps({"error": "url is required"})
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        info = await asyncio.to_thread(
            lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=False)
        )
        return json.dumps({
            "title":       info.get("title", ""),
            "channel":     info.get("channel") or info.get("uploader", ""),
            "duration":    info.get("duration"),
            "upload_date": info.get("upload_date"),
            "view_count":  info.get("view_count"),
            "url":         url,
        })
    except Exception as exc:
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "youtube",
    name        = "youtube_fetch_info",
    description = "Fetch metadata (title, channel, duration, date) for a YouTube URL.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string", "description": "Nexus project slug"},
            "url":          {"type": "string", "description": "YouTube URL"},
        },
        "required": ["project_slug", "url"],
    },
    handler = _youtube_fetch_info,
)


async def _youtube_download_video(args: dict) -> str:
    slug    = args.get("project_slug", "")
    url     = args.get("url", "")
    quality = args.get("quality", "best")
    fmt     = args.get("format", "mp4")
    if not url:
        return json.dumps({"error": "url is required"})

    out_dir = _PROJECTS_DIR / slug / "video"
    out_dir.mkdir(parents=True, exist_ok=True)

    fmt_str = (
        "bestvideo+bestaudio/best"
        if quality == "best"
        else f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best"
    )

    try:
        import yt_dlp
        opts = {
            "format":              fmt_str,
            "merge_output_format": fmt,
            "outtmpl":             str(out_dir / "%(title)s.%(ext)s"),
            "quiet":               True,
        }
        await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(opts).download([url]))
        return json.dumps({"status": "ok", "saved_to": str(out_dir)})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "youtube",
    name        = "youtube_download_video",
    description = "Download a YouTube video to the project's video/ folder.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "url":          {"type": "string"},
            "quality":      {"type": "string", "description": "best / 1080 / 720 / 480 / 360", "default": "best"},
            "format":       {"type": "string", "description": "mp4 / mkv / webm",               "default": "mp4"},
        },
        "required": ["project_slug", "url"],
    },
    handler = _youtube_download_video,
)


async def _youtube_download_audio(args: dict) -> str:
    slug    = args.get("project_slug", "")
    url     = args.get("url", "")
    fmt     = args.get("format", "mp3")
    quality = args.get("quality", "192")
    if not url:
        return json.dumps({"error": "url is required"})

    out_dir = _PROJECTS_DIR / slug / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        import yt_dlp
        opts = {
            "format":         "bestaudio/best",
            "postprocessors": [{
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   fmt,
                "preferredquality": str(quality),
            }],
            "outtmpl":  str(out_dir / "%(title)s.%(ext)s"),
            "quiet":    True,
        }
        await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(opts).download([url]))
        return json.dumps({"status": "ok", "saved_to": str(out_dir)})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "youtube",
    name        = "youtube_download_audio",
    description = "Download the audio track of a YouTube video to the project's audio/ folder.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "url":          {"type": "string"},
            "format":       {"type": "string", "description": "mp3 / m4a / opus / flac", "default": "mp3"},
            "quality":      {"type": "string", "description": "320 / 192 / 128 (kbps)",  "default": "192"},
        },
        "required": ["project_slug", "url"],
    },
    handler = _youtube_download_audio,
)


async def _youtube_get_transcript(args: dict) -> str:
    slug        = args.get("project_slug", "")
    url         = args.get("url", "")
    use_whisper = args.get("use_whisper", False)
    if not url:
        return json.dumps({"error": "url is required"})

    video_id = _extract_video_id(url)

    # Try built-in captions first (unless caller explicitly requests whisper)
    if not use_whisper:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            segments = await asyncio.to_thread(
                lambda: YouTubeTranscriptApi.get_transcript(video_id) if video_id else None
            )
            if segments:
                text = "\n".join(s["text"] for s in segments)
                out_dir = _PROJECTS_DIR / slug / "transcript"
                out_dir.mkdir(parents=True, exist_ok=True)
                title = args.get("title", video_id or "transcript")
                safe  = re.sub(r"[^\w\s-]", "", title).strip()[:80] or "transcript"
                out   = out_dir / f"{safe}.md"
                out.write_text(f"# {title}\n\n{text}\n", encoding="utf-8")
                return json.dumps({"status": "ok", "source": "captions", "saved_to": str(out)})
        except Exception:
            pass

    # Whisper fallback
    cfg        = _youtube_cfg(slug)
    model_name = cfg.get("whisper_model", "base")
    import tempfile
    tmp_stem  = Path(tempfile.mktemp(prefix="nexus_yt_"))
    tmp_audio = Path(str(tmp_stem) + ".wav")
    try:
        import yt_dlp
        ydl_opts = {
            "format":         "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
            "outtmpl":  str(tmp_stem),
            "quiet":    True,
        }
        await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))

        if not tmp_audio.exists():
            candidates = list(tmp_stem.parent.glob(f"{tmp_stem.name}.*"))
            if candidates:
                tmp_audio = candidates[0]

        def _run_whisper() -> list[str]:
            from faster_whisper import WhisperModel
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            segs, _ = model.transcribe(str(tmp_audio))
            return [s.text.strip() for s in segs if s.text.strip()]

        lines = await asyncio.to_thread(_run_whisper)
        title = args.get("title", video_id or "transcript")
        safe  = re.sub(r"[^\w\s-]", "", title).strip()[:80] or "transcript"
        out_dir = _PROJECTS_DIR / slug / "transcript"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{safe}.md"
        out.write_text(f"# {title}\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
        return json.dumps({"status": "ok", "source": "whisper", "saved_to": str(out)})
    except Exception as exc:
        return json.dumps({"error": str(exc)})
    finally:
        for p in [tmp_audio, tmp_stem]:
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass


registry.register(
    scope       = "youtube",
    name        = "youtube_get_transcript",
    description = (
        "Get the transcript for a YouTube video. "
        "Tries built-in captions first; falls back to local Whisper transcription."
    ),
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "url":          {"type": "string"},
            "title":        {"type": "string", "description": "Optional title for the saved .md file"},
            "use_whisper":  {"type": "boolean", "description": "Force Whisper even when captions exist", "default": False},
        },
        "required": ["project_slug", "url"],
    },
    handler = _youtube_get_transcript,
)
