# [Project Name] — YouTube

A YouTube download project managed by Nexus.

## About this project

<!-- Describe what content you download here. Examples:
- Music videos from a specific channel
- Tutorials for offline viewing
- Podcast episodes for transcription
-->

## Folder layout

```
projects/<slug>/
  video/       — downloaded video files
  audio/       — extracted audio files
  transcript/  — transcripts (.md files)
```

## Tools

| Tool | Purpose |
|------|---------|
| yt-dlp | Video/audio download and metadata extraction |
| youtube-transcript-api | Fetch built-in YouTube captions (fast, no local model) |
| faster-whisper | Local speech-to-text for videos without captions |
| ffmpeg | Audio/video muxing and format conversion (system binary) |

## Whisper model tradeoffs

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| tiny  | 75 MB  | fastest | lowest |
| base  | 145 MB | fast    | good (default) |
| small | 465 MB | medium  | better |
| medium | 1.5 GB | slow   | best for most use cases |
| large  | 3 GB   | slowest | highest accuracy |

The model is configurable in project setup. Change it if transcription quality is insufficient.

## yt-dlp format strings

```bash
# Best video + audio, merged to mp4
yt-dlp -f "bestvideo+bestaudio" --merge-output-format mp4 URL

# Limit to 720p
yt-dlp -f "bestvideo[height<=720]+bestaudio" --merge-output-format mp4 URL

# Audio only, converted to mp3
yt-dlp -f bestaudio --extract-audio --audio-format mp3 --audio-quality 192k URL
```

## Supported URL formats

- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/shorts/VIDEO_ID`
- Most other YouTube URL variants (yt-dlp normalises them)

## AI context

<!-- Fill in to help the AI assistant: -->

**Preferred quality defaults:** e.g., 1080p MP4 for videos, 192k MP3 for audio

**Common use cases:** e.g., downloading conference talks for offline review and transcription

**Language of transcribed content:** e.g., English (affects Whisper accuracy)
