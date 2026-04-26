# SD Forge Project — AI Instructions

This project manages a **Stable Diffusion Forge** (`sd-webui-forge`) installation.
SD Forge is a fork of AUTOMATIC1111 that runs a local image generation server.

## Overview

| Item | Details |
|------|---------|
| Repository | `https://github.com/lllyasviel/stable-diffusion-webui-forge` |
| Default port | 7860 |
| API compatibility | A1111-compatible REST API |
| Model format | `.ckpt` and `.safetensors` checkpoint files |
| Output format | PNG images |

## Config keys (`config.yaml` → `sdforge` section)

| Key | Description |
|-----|-------------|
| `install_dir` | Absolute path to the SD Forge clone |
| `endpoint` | REST API base URL (default `http://localhost:7860`) |
| `vram` | GPU VRAM used to determine launch flags |
| `model` | Active checkpoint model title |
| `launch_args` | Flags passed to `webui.sh` |
| `output_dir` | Relative path for saved images (default `outputs/`) |
| `setup_done` | `true` once setup wizard completed |

## Starting the server manually

```bash
cd <install_dir>
./webui.sh --api --xformers    # for 4 GB+ VRAM
./webui.sh --api --lowvram     # for < 4 GB VRAM
./webui.sh --api --skip-torch-cuda-test --use-cpu=all   # CPU only
```

The server is ready when the log shows: `Running on local URL: http://127.0.0.1:7860`

## REST API quick reference

```bash
# List available checkpoint models
curl http://localhost:7860/sdapi/v1/sd-models

# Generate an image (txt2img)
curl -s -X POST http://localhost:7860/sdapi/v1/txt2img \
  -H "Content-Type: application/json" \
  -d '{"prompt":"a cyberpunk city","width":512,"height":512,"steps":20}' \
  | python3 -c "import sys,json,base64; d=json.load(sys.stdin); open('out.png','wb').write(base64.b64decode(d['images'][0]))"

# Check generation progress
curl http://localhost:7860/sdapi/v1/progress

# Get / set active model
curl http://localhost:7860/sdapi/v1/options
curl -X POST http://localhost:7860/sdapi/v1/options \
  -H "Content-Type: application/json" \
  -d '{"sd_model_checkpoint":"v1-5-pruned.ckpt [abc123]"}'
```

## Launch args reference

| Flag | Purpose |
|------|---------|
| `--api` | Enable REST API (required for Nexus integration) |
| `--xformers` | Memory-efficient attention — recommended for 4 GB+ VRAM |
| `--lowvram` | Low VRAM mode for < 4 GB GPUs |
| `--skip-torch-cuda-test` | Skip CUDA check (CPU mode) |
| `--use-cpu=all` | Force CPU inference (slow) |
| `--listen` | Bind to all interfaces (allows remote access) |
| `--port 7861` | Use a different port |
| `--no-half` | Disable half-precision — needed for some older GPUs |

## Skills available

| Skill | Required inputs | Description |
|-------|----------------|-------------|
| `sdforge_txt2img` | `project_slug`, `prompt` | Generate image; server must be running |

Optional inputs: `negative_prompt`, `width`, `height`, `steps`, `cfg_scale`, `sampler_name`, `seed`

## Installing models

Place `.safetensors` or `.ckpt` files in:
```
<install_dir>/models/Stable-diffusion/
```

Then use "Browse Models" in Nexus to select and activate one.

Popular sources: CivitAI (`civitai.com`), Hugging Face (`huggingface.co`)

## User setup notes

<!--
Fill in your specifics so the AI can give accurate advice:

- Install directory:
  [ your answer here ]

- GPU and available VRAM:
  [ your answer here ]

- Preferred model(s):
  [ your answer here ]

- Typical prompt style or workflow:
  [ your answer here ]

- Any ControlNet or LoRA setups:
  [ your answer here ]
-->
