from __future__ import annotations

import base64
import time
from pathlib import Path

import httpx

from nexus.core.logger import get

log = get("sdforge.api_client")

_DEFAULT_TIMEOUT = 300.0


class SDForgeAPIError(Exception):
    """Raised when the SD Forge API returns an error or is unreachable."""


async def ping(endpoint: str) -> float:
    """Return round-trip time in ms, or raise SDForgeAPIError."""
    url = endpoint.rstrip("/") + "/sdapi/v1/progress"
    try:
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url)
        ms = (time.monotonic() - t0) * 1000
        if r.status_code != 200:
            raise SDForgeAPIError(f"HTTP {r.status_code}")
        return ms
    except httpx.ConnectError as exc:
        raise SDForgeAPIError(f"Cannot connect to {endpoint}") from exc
    except SDForgeAPIError:
        raise
    except Exception as exc:
        raise SDForgeAPIError(str(exc)) from exc


async def list_models(endpoint: str) -> list[dict]:
    """Return list of checkpoint dicts from GET /sdapi/v1/sd-models."""
    url = endpoint.rstrip("/") + "/sdapi/v1/sd-models"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url)
        if r.status_code != 200:
            raise SDForgeAPIError(f"HTTP {r.status_code}")
        return r.json()
    except httpx.ConnectError as exc:
        raise SDForgeAPIError(f"Cannot connect to {endpoint}") from exc
    except SDForgeAPIError:
        raise
    except Exception as exc:
        raise SDForgeAPIError(str(exc)) from exc


async def get_options(endpoint: str) -> dict:
    """Return current options from GET /sdapi/v1/options."""
    url = endpoint.rstrip("/") + "/sdapi/v1/options"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
        if r.status_code != 200:
            raise SDForgeAPIError(f"HTTP {r.status_code}")
        return r.json()
    except httpx.ConnectError as exc:
        raise SDForgeAPIError(f"Cannot connect to {endpoint}") from exc
    except SDForgeAPIError:
        raise
    except Exception as exc:
        raise SDForgeAPIError(str(exc)) from exc


async def set_model(endpoint: str, model_title: str) -> None:
    """POST /sdapi/v1/options to change the active checkpoint. Blocks until loaded."""
    url = endpoint.rstrip("/") + "/sdapi/v1/options"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, json={"sd_model_checkpoint": model_title})
        if r.status_code not in (200, 204):
            raise SDForgeAPIError(f"HTTP {r.status_code}")
    except httpx.ConnectError as exc:
        raise SDForgeAPIError(f"Cannot connect to {endpoint}") from exc
    except SDForgeAPIError:
        raise
    except Exception as exc:
        raise SDForgeAPIError(str(exc)) from exc


async def get_progress(endpoint: str) -> dict:
    """Return progress dict from GET /sdapi/v1/progress."""
    url = endpoint.rstrip("/") + "/sdapi/v1/progress"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url)
        if r.status_code != 200:
            raise SDForgeAPIError(f"HTTP {r.status_code}")
        return r.json()
    except httpx.ConnectError as exc:
        raise SDForgeAPIError(f"Cannot connect to {endpoint}") from exc
    except SDForgeAPIError:
        raise
    except Exception as exc:
        raise SDForgeAPIError(str(exc)) from exc


async def txt2img(
    endpoint: str,
    prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg_scale: float = 7.0,
    sampler_name: str = "Euler a",
    seed: int = -1,
    batch_size: int = 1,
) -> list[bytes]:
    """POST /sdapi/v1/txt2img. Returns raw PNG bytes for each generated image."""
    url = endpoint.rstrip("/") + "/sdapi/v1/txt2img"
    payload = {
        "prompt":          prompt,
        "negative_prompt": negative_prompt,
        "width":           width,
        "height":          height,
        "steps":           steps,
        "cfg_scale":       cfg_scale,
        "sampler_name":    sampler_name,
        "seed":            seed,
        "batch_size":      batch_size,
    }
    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            r = await client.post(url, json=payload)
        if r.status_code != 200:
            raise SDForgeAPIError(f"HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        images = data.get("images", [])
        if not images:
            raise SDForgeAPIError("No images returned from API.")
        return [base64.b64decode(img) for img in images]
    except httpx.ConnectError as exc:
        raise SDForgeAPIError(f"Cannot connect to {endpoint}") from exc
    except SDForgeAPIError:
        raise
    except Exception as exc:
        raise SDForgeAPIError(str(exc)) from exc


def save_image(image_bytes: bytes, output_dir: Path, prefix: str = "img") -> Path:
    """Save PNG bytes to output_dir. Returns the saved Path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts  = int(time.time())
    seq = len(list(output_dir.glob(f"{prefix}_*.png")))
    path = output_dir / f"{prefix}_{ts}_{seq:04d}.png"
    path.write_bytes(image_bytes)
    log.debug("Image saved: %s", path)
    return path
