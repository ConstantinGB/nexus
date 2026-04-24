# {project_name} — VTube

This project manages a virtual avatar (VTuber) setup: model, face tracking, and
integration with OBS. The AI helps configure tracking, diagnose expression and physics
issues, write hotkey scripts, and integrate with streaming software.

## Key software

- **VTubeStudio** — most popular runtime; iOS/Android ARKit tracking + PC display; Steam
- **VSeeFace** — free, Windows; uses OpenSeeFace webcam tracker or VMC protocol input
- **VNyan** — node-based automation and effects engine; strong plugin/scripting ecosystem
- **3tene** — beginner-friendly Live2D and VRM runtime; Steam
- **OpenSeeFace** — open-source CPU-based face tracker; outputs via UDP to VSeeFace/VNyan
  - Run: `python facetracker.py -c 0 -v 3 --model 3`
- **iFacialMocap / FaceMotion3D** — iPhone ARKit → PC over Wi-Fi (high fidelity)
- **VirtualMotionCapture** — full-body VR tracking to VMC output
- **OBS** — receives avatar via virtual camera output or window/game capture

## Model formats

| Format | Extension | Runtime |
|--------|-----------|---------|
| Live2D | `.moc3` + `.model3.json` | VTubeStudio, VSeeFace, Vtube Studio |
| VRM 0.x | `.vrm` | VSeeFace, VNyan, 3tene |
| VRM 1.0 | `.vrm` | VNyan, UniVRM-based apps |
| VSF | `.vsf` | VSeeFace (native format) |

## Tracking pipeline

```
Camera / iPhone
      │
      ▼
Tracker (OpenSeeFace / ARKit / iFacialMocap)
      │  UDP / VMC / network socket
      ▼
Avatar runtime (VSeeFace / VTubeStudio / VNyan)
      │  virtual camera / Spout / NDI
      ▼
OBS  →  stream / recording
```

## Common issues and fixes

| Issue | Likely cause | Fix |
|-------|-------------|-----|
| Head jitter | Low lighting or camera noise | Increase room light; lower tracking sensitivity |
| Mouth not opening | Expression threshold too high | Lower mouth-open parameter threshold in runtime |
| Eyes not blinking | Blink threshold mismatch | Calibrate blink in VTubeStudio settings |
| High latency | Software rendering path | Enable GPU acceleration in tracker settings |
| Avatar drifts sideways | Head-rotation offset | Recalibrate neutral pose |

## Typical tasks

- Diagnose and fix tracking jitter or expression mapping problems
- Configure expression hotkeys and toggle bindings in VTubeStudio or VNyan
- Tune Live2D physics parameters (spring, gravity, output scale)
- Write a VNyan node graph for a triggered effect (particle burst, overlay)
- Set up OpenSeeFace for a webcam without ARKit hardware
- Configure OBS virtual camera or Spout output from the avatar runtime
- Help select a face tracker given available hardware

---

## Your setup

<!-- Avatar model:
     format (Live2D / VRM), file path, character name -->

<!-- Runtime in use: VTubeStudio / VSeeFace / VNyan / 3tene / other -->

<!-- Tracking hardware:
     - Webcam model (for OpenSeeFace)
     - iPhone model (for ARKit / iFacialMocap)
     - VR headset (for VirtualMotionCapture) -->

<!-- OBS integration method:
     virtual camera / Spout / NDI / window capture -->

<!-- Hotkeys / expressions already configured:
     e.g. F1 = smile, F2 = angry, F3 = toggle glasses -->

## Notes for the AI

<!-- Physics tuning goals, plugins installed in VNyan, known tracking quirks,
     latency requirements, or any automation you want to script. -->
