# {project_name} — Game

This project is a Godot game. Check `project.godot` at the project root to confirm the
Godot version — Godot 4.x and 3.x have incompatible APIs. The AI helps with GDScript,
scene architecture, game mechanics, shaders, and export configuration.

## Key software

- **Godot Engine** — download from godotengine.org; Godot 4.x is the current major version
- **Godot .NET build** — separate download if using C#; `.csproj` will be present in root
- **Blender** — 3D modelling; export as `.glb` for Godot 4 import
- **Aseprite / LibreSprite** — pixel art and spritesheet creation
- **Krita / GIMP** — general 2D art assets
- **Audacity / LMMS / Bfxr** — sound effects and music
- **gdtoolkit** — GDScript linter/formatter: `pip install gdtoolkit`, then `gdlint *.gd`

## GDScript quick reference (Godot 4.x)

```gdscript
extends CharacterBody2D

@export var speed: float = 200.0
@export var jump_force: float = 400.0

signal jumped

func _ready() -> void:
    pass  # called once on spawn

func _physics_process(delta: float) -> void:
    # gravity
    if not is_on_floor():
        velocity += get_gravity() * delta

    # jump
    if Input.is_action_just_pressed("jump") and is_on_floor():
        velocity.y = -jump_force
        jumped.emit()

    # horizontal movement
    var dir := Input.get_axis("move_left", "move_right")
    velocity.x = dir * speed
    move_and_slide()
```

## Project structure conventions

```
project.godot            — project settings and Godot version
scenes/
  player/player.tscn     — player scene
  ui/hud.tscn
scripts/                 — .gd scripts (may also be co-located with scenes)
assets/
  sprites/               — .png, .aseprite
  audio/                 — .ogg (recommended for music), .wav (for sfx)
  fonts/                 — .ttf, .otf
  3d/                    — .glb, .gltf
autoloads/               — singleton scripts (register in Project → Autoload)
```

## Key node types (Godot 4.x)

| Node | Common use |
|------|-----------|
| `CharacterBody2D` / `3D` | Player, NPCs with controlled movement |
| `Area2D` / `3D` | Hitboxes, pickup zones, triggers |
| `StaticBody2D` / `3D` | Walls, floors, immovable terrain |
| `RigidBody2D` / `3D` | Physics-simulated objects |
| `AnimationPlayer` | Keyframe animations on any property |
| `AnimationTree` | State machine for blending animations |
| `Control` (+ children) | UI: `Label`, `Button`, `TextureRect`, `VBoxContainer` |
| `TileMapLayer` | 2D tile-based levels (replaces TileMap in Godot 4.3+) |
| `GPUParticles2D` / `3D` | Visual effects |

## Typical tasks

- Write GDScript for movement, enemy AI, interaction, inventory, UI
- Design scene trees and recommend node hierarchies for a mechanic
- Implement signals for loose coupling between nodes
- Write CanvasItem or Spatial shaders (vertex + fragment functions)
- Configure input actions (`Project → Input Map`) and read them in code
- Set up export presets for Linux, Windows, Web (HTML5), or Android
- Debug: read Godot error messages, check physics collision layers, trace scene tree

---

## Your setup

<!-- Godot version: e.g. 4.3, 4.2.2, 3.5.3 -->

<!-- Scripting language: GDScript / C# -->

<!-- Game genre / type:
     e.g. 2D platformer, top-down RPG, 3D FPS, puzzle, visual novel, tower defence -->

<!-- Project path on disk:
     e.g. ~/projects/my-game -->

<!-- Target platforms: Linux / Windows / macOS / Web / Android / iOS -->

<!-- Plugins / addons in use:
     e.g. Dialogic (dialogue), GodotSteam, Phantom Camera, Beehave (behaviour trees) -->

## Notes for the AI

<!-- Art style (pixel art, vector, 3D low-poly), performance budget,
     any architectural decisions already made (e.g. ECS via composition,
     event bus autoload, specific save-data format). -->
