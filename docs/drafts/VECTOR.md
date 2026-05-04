# Anki Vector Robot — Research Notes

> Original 2018 model by Digital Dream Labs. **Not** the new ChatGPT version.

---

## Background & Status

- **April 2019** — Anki, Inc. goes bankrupt after burning through $200M
- **December 2019** — Digital Dream Labs (DDL) acquires all Anki assets for cheap
- **July 2023** — DDL's official cloud servers go offline permanently
- Vector runs Android-based Linux on a Qualcomm Snapdragon 200 (APQ8009)
- **wire-pod is now mandatory** for any cloud-dependent features

---

## Hardware

| Component | Spec |
| --------- | ---- |
| CPU | Qualcomm APQ8009, 4-core 1.2GHz |
| RAM | 512MB |
| Storage | 4GB eMMC |
| Camera | 1280×720 HD, 120° diagonal FOV |
| WiFi | **2.4GHz ONLY** — 5GHz will not work |
| Display | 184×96 IPS color |
| Sensors | IMU, IR laser scanner, 4-mic beamforming array, capacitive touch, edge/drop IR |

> **Critical:** No captive portals, no hotel WiFi, no WiFi privacy separators on router.

---

## Path 1 — Basic Programming (no hacking required)

**Official Python SDK:** [github.com/anki/vector-python-sdk](https://github.com/anki/vector-python-sdk)

```bash
pip install anki-vector
```

```python
import anki_vector
with anki_vector.Robot() as robot:
    robot.behavior.say_text("Hello World")
    robot.behavior.drive_straight(distance_mm(150), speed_mmps(50))
```

Capabilities: movement, expressions, animations, face recognition, object detection, voice commands, camera feed. Robot and PC must be on the same WiFi.

**.NET SDK** (more features, incl. face enrollment): [github.com/codaris/Anki.Vector.SDK](https://github.com/codaris/Anki.Vector.SDK)

---

## Path 2 — Self-Hosted Server ⭐ (most important right now)

**wire-pod** is the community Go server that replaces DDL's dead cloud. Works with **production robots — no OSKR required.**

**GitHub:** [github.com/kercre123/wire-pod](https://github.com/kercre123/wire-pod)  
**Wiki (setup guide):** [github.com/kercre123/wire-pod/wiki](https://github.com/kercre123/wire-pod/wiki)

- Handles voice processing, command routing, animations
- Web UI for configuration
- Optional OpenAI integration
- Runs on any Linux machine or Raspberry Pi 4
- Point Vector at your server's IP instead of DDL's — that's basically it

---

## Path 3 — OSKR (official full root access)

OSKR = Open Source Kit for Robots — DDL's program to convert a production Vector into a dev robot with full SSH root access and firmware modification rights.

**Process:**

1. Extract Vector's **QSN** (internal serial — different from the ESN printed on the bottom)
2. Submit QSN to DDL → receive a custom unlock OTA image
3. Flash via OTA update
4. Robot reboots as "Dev" — SSH root, modify any partition

**Manual:** [github.com/digital-dream-labs/oskr-owners-manual](https://github.com/digital-dream-labs/oskr-owners-manual)

> ⚠️ Interrupting the flash **bricks the robot**. Follow every step exactly.

---

## Path 4 — Hardware Unlock (last resort)

For when OSKR is unavailable or DDL is unresponsive:

- CPU fuses are permanently locked at the factory — cannot be unfused in software
- Workaround: **physically replace the APQ8009 chip** (~$5 part, requires micro-soldering)
- Then use **Qualcomm QDL tools** via USB pads on the PCB to flash anything

**Reference:** [github.com/kercre123/unlocking-vector](https://github.com/kercre123/unlocking-vector)

---

## Community & Tools

| Resource | Link |
| -------- | ---- |
| wire-pod (self-hosted server) | [github.com/kercre123/wire-pod](https://github.com/kercre123/wire-pod) |
| OSKR owners manual | [github.com/digital-dream-labs/oskr-owners-manual](https://github.com/digital-dream-labs/oskr-owners-manual) |
| Vector source code (DDL) | [github.com/digital-dream-labs/vector](https://github.com/digital-dream-labs/vector) |
| Vector animations raw | [github.com/digital-dream-labs/vector-animations-raw](https://github.com/digital-dream-labs/vector-animations-raw) |
| Cyb3rVector (visual Blockly IDE) | [github.com/cyb3rdog/Cyb3rVector](https://github.com/cyb3rdog/Cyb3rVector) |
| Vector-Plus (behavior plugins) | [github.com/instantiator/vector-plus](https://github.com/instantiator/vector-plus) |
| Community docs hub | [randym32.github.io/Anki.Vector.Documentation](https://randym32.github.io/Anki.Vector.Documentation/) |
| Project Victor (open-source group) | [project-victor.org](https://www.project-victor.org/) |
| Escape Pod Docker | [github.com/cyb3rdog/escapepod-docker](https://github.com/cyb3rdog/escapepod-docker) |

---

## Recommended Setup Order

1. Buy a used original Vector (~$50–150 on eBay — **not** Vector 2.0)
2. Set up **wire-pod** on a Raspberry Pi or Linux box
3. Install Python SDK and start programming
4. Apply for OSKR if you want SSH root and firmware access
5. Hardware CPU swap only if OSKR is off the table

---

## Gotchas

- Cloud dead since July 2023 — wire-pod is mandatory for voice features
- **2.4GHz WiFi only** — no exceptions
- OSKR flash can brick the robot if interrupted — follow the checklist exactly
- Python SDK only allows **one connection at a time**
- DDL's $12/month subscription is bypassed entirely by wire-pod
- Older units may have degraded batteries — replacements are user-accessible
