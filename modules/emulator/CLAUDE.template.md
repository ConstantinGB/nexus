# {project_name} — Emulator

This project manages retro console emulation: emulator installation, per-system
configuration, controller mapping, shaders, and ROM organisation. The AI helps with
emulator settings, compatibility workarounds, and automation scripts.

## Key software

- **RetroArch** — multi-system libretro frontend; config at `~/.config/retroarch/`
- **PCSX2** — PlayStation 2; config at `~/.config/PCSX2/`; needs BIOS (`scph*.bin`)
- **Dolphin** — GameCube / Wii; Vulkan backend recommended; config at `~/.config/dolphin-emu/`
- **Citra / Lime3DS** — Nintendo 3DS; check current maintained fork
- **Ryujinx** — Nintendo Switch (open-source); `~/.config/Ryujinx/`
- **RPCS3** — PlayStation 3; needs PS3 firmware from PlayStation website
- **MAME** — arcade; `mame <romname>`; ROMs must match exact MAME version

## Recommended RetroArch cores by system

| System | Core |
|--------|------|
| NES | Nestopia UE, Mesen |
| SNES | snes9x |
| Game Boy / GBC | Gambatte |
| GBA | mGBA |
| N64 | Mupen64Plus-Next (Vulkan), Parallel-N64 |
| PS1 | Beetle PSX HW (accurate), PCSX-ReARMed (fast) |
| Sega MD/Genesis | Genesis Plus GX |
| Sega Saturn | Beetle Saturn |
| Neo Geo | FinalBurn Neo |
| Arcade (MAME) | MAME (current) |

## BIOS requirements

BIOS files must be sourced personally (dump from hardware you own). Common placements:

| Emulator | BIOS location |
|----------|--------------|
| RetroArch | `~/.config/retroarch/system/` |
| PCSX2 | `~/.config/PCSX2/bios/` (`scph10000.bin`, `scph77000.bin`, etc.) |
| Dolphin | Not required (open-source HLE BIOS) |
| RPCS3 | Install via File → Install Firmware |

## Shader recommendations

| Shader | Use case |
|--------|----------|
| `crt-royale` | High-quality CRT simulation; GPU-intensive |
| `crt-geom` | Fast CRT approximation |
| `xBR` / `xBRZ` | Pixel art upscaling |
| `HQx` | Smooth pixel art upscaling |
| `scalefx` | Sharp pixel art upscaling |
| `nearest` | Raw pixels, no filter |

In RetroArch: Quick Menu → Shaders → Load Shader Preset → `shaders_glsl/` or `shaders_slang/`

## Typical tasks

- Configure a specific emulator or RetroArch core for a system
- Set per-game overrides (resolution, shader, CPU speed) in RetroArch
- Map controllers in RetroArch or a standalone emulator
- Diagnose performance issues (enable frame limiter, lower IR, disable enhancements)
- Set up RetroAchievements (Settings → Achievements → enter username + API key)
- Configure netplay in RetroArch for online multiplayer
- Create a playlist or scrape box art with Pegasus or ES-DE frontend

## File and config conventions

- **`~/.config/retroarch/`** — RetroArch global config and cores
- **`~/Roms/<System>/`** — recommended ROM directory layout
- **`~/Roms/BIOS/`** — copy of BIOS files (symlinked to emulator system dirs)
- **`.srm`** — save RAM files (same name and location as ROM)
- **`.state0` … `.state9`** — RetroArch save states

---

## Your setup

<!-- Systems and emulators:
     e.g.
     - SNES  → RetroArch (snes9x core)
     - PS2   → PCSX2
     - GC    → Dolphin
     - Switch → Ryujinx -->

<!-- ROM storage path: e.g. ~/Roms/ or /mnt/games/ -->

<!-- BIOS files available and their locations: -->

<!-- Controllers:
     model, connection type (USB / Bluetooth / adapter),
     any per-emulator mapping quirks -->

<!-- GPU and performance targets:
     resolution upscaling (2x, 4x, native), shader preference,
     VRR / vsync / 60 Hz cap -->

## Notes for the AI

<!-- Per-game compatibility notes, RetroAchievements account in use,
     netplay goals, or frontend (ES-DE, Pegasus, Launchbox) details. -->
