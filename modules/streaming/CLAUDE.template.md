# {project_name} — Streaming

This project manages a live streaming and recording setup centred on OBS Studio.
The AI helps configure scenes and sources, tune audio routing, write OBS scripts,
optimise encoding settings, and troubleshoot stream quality issues.

## Key software

- **OBS Studio** — primary streaming/recording tool; config at `~/.config/obs-studio/`
- **obs-vkcapture** — Linux game capture via Vulkan layer (low overhead, recommended over window capture)
- **obs-move-transition** — smooth animated scene transitions plugin
- **obs-ndi** — NDI source/output plugin for network video routing
- **PipeWire** — modern Linux audio router; `pw-link` to connect virtual sources
- **pavucontrol** — PulseAudio/PipeWire volume control GUI; set per-app routing here
- **Helvum** — graphical PipeWire patchbay for routing audio between apps and OBS
- **FFmpeg** — remux, transcode, or inspect recordings: `ffmpeg -i recording.mkv output.mp4`
- **Streamlink** — record/relay streams: `streamlink twitch.tv/channel best`

## Encoding presets

| Scenario | Encoder | Settings |
|----------|---------|----------|
| NVIDIA GPU | NVENC H.264 | CQP 18–23, High profile |
| AMD GPU | VA-API H.264 | CQP mode or CBR |
| Intel GPU | VA-API / QSV | CBR, High profile |
| CPU fallback | x264 | `veryfast` or `faster`, CRF 18–23 |

## Streaming bitrate guidelines (Twitch / YouTube)

| Resolution | FPS | Bitrate |
|-----------|-----|---------|
| 1080p | 60 | 6,000 kbps |
| 1080p | 30 | 4,500 kbps |
| 720p | 60 | 4,500 kbps |
| 720p | 30 | 3,000 kbps |

## OBS Python scripting

```python
import obspython as obs

def script_description():
    return "Example: mute mic when game starts"

def on_event(event):
    if event == obs.OBS_FRONTEND_EVENT_SCENE_CHANGED:
        scene = obs.obs_frontend_get_current_scene()
        name  = obs.obs_source_get_name(scene)
        obs.obs_source_release(scene)
        # do something based on scene name
```

Scripts live in `~/.config/obs-studio/scripts/`. Add them via Tools → Scripts.

## Typical tasks

- Design or refactor a scene collection (sources, filters, transitions)
- Diagnose dropped frames (network vs encoding: check OBS stats panel)
- Write a PipeWire routing script to separate game audio from voice
- Write or debug an OBS Python or Lua automation script
- Configure a virtual camera for use in video calls
- Set up a local RTMP relay with nginx for redundant streaming
- Optimise recording settings for local archiving (lossless / near-lossless)

## Security note

Stream keys grant full broadcast access — store them in the Vault module or a password
manager, never in plain text files in this directory.

---

## Your setup

<!-- Hardware:
     GPU model (for encoder selection), CPU, capture card (if any), microphone model -->

<!-- Target platforms:
     e.g. Twitch (channel: …), YouTube Live, local recording only -->

<!-- Audio setup:
     microphone (USB / XLR + interface), desktop audio capture preferences,
     mixer software (PipeWire / Helvum / JACK / Voicemeeter) -->

<!-- OBS scenes in use:
     e.g. Gaming, BRB, Starting Soon, Just Chatting, Ending Screen -->

<!-- Plugins installed:
     e.g. obs-vkcapture, obs-move-transition, obs-browser, StreamFX -->

## Notes for the AI

<!-- Resolution and framerate targets, recurring issues (audio desync, frame drops),
     OBS scripting goals, or any hardware/software constraints. -->
