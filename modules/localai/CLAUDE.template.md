# {project_name} — LocalAI

This project runs a local AI model set up and managed by Nexus. The model and runtime were
configured during the setup wizard; all settings are stored in `config.yaml`.

## Runtime config (read from config.yaml)

| Key | Meaning |
|-----|---------|
| `localai.vram` | VRAM available at setup time |
| `localai.purpose` | Intended use (text generation, image generation, audio, etc.) |
| `localai.model` | Model name / path |
| `localai.output_type` | `text` (LLM output) or `file` (image / audio output) |
| `localai.run_command` | Shell command to invoke inference; use `{prompt}` and `{negative_prompt}` as placeholders |
| `localai.output_dir` | Directory where output files are saved (file output only) |
| `localai.setup_done` | `true` once setup has completed successfully |

## Setup script

The AI-generated installation script is saved at `setup.sh`. Re-run it if you need to
reinstall or update dependencies:
```bash
bash setup.sh
```

## Inference

- **Text output** — printed live in the inference log inside the Nexus UI
- **File output** — images or audio saved to `outputs/`; use "Open Output" in the UI

## Modifying the run command

Edit `localai.run_command` in `config.yaml` to change how the model is invoked — for
example to add sampling parameters, change the number of output steps, or switch models:
```yaml
localai:
  run_command: "ollama run llama3.2 --temperature 0.7 --prompt \"{prompt}\""
```

## Common runtimes and their patterns

| Runtime | Typical run command |
|---------|-------------------|
| Ollama (LLM) | `ollama run <model> --prompt "{prompt}"` |
| LM Studio (LLM) | served via OpenAI-compatible API on port 1234 |
| Stable Diffusion (ComfyUI) | `python main.py --prompt "{prompt}" --output outputs/` |
| Stable Diffusion (AUTOMATIC1111) | `python webui.py` then POST to API |
| Whisper (transcription) | `whisper audio.wav --model medium` |

## Skills

| Skill | Inputs | Description |
|-------|--------|-------------|
| `localai_run_inference` | `project_slug`, `prompt`, `negative_prompt?` | Run inference using the configured run command |

## Local Model Guidance

This module *is* a local model runner — "local model" here refers to the model Nexus is configured to talk to via `ai.provider: local`. Those are separate from the model this LocalAI project runs.

- `localai_run_inference` — calls the shell command in `localai.run_command`. Reliable regardless of AI provider; the skill itself just runs a subprocess.
- For text output prompts: be explicit and self-contained. Avoid pronouns that reference earlier conversation turns.
- For image generation prompts: describe subject, style, lighting, composition, and quality in a single sentence or comma-separated tag list.
- If the Nexus AI provider is also a small local model and doesn't produce a tool call: re-prompt with "Call localai_run_inference with project_slug: X and prompt: Y."

## Notes for the AI

<!-- Any model-specific parameters, sampling settings, LoRA adapters in use,
     or workflow changes you want to make to the setup. -->
