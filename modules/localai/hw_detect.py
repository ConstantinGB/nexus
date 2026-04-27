from __future__ import annotations
import json
import platform
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from nexus.core.logger import get

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"

log = get("localai.hw_detect")


def detect_hardware() -> dict:
    """Return a dict of hardware info. All sub-calls are safe/non-crashing."""
    log.info("Detecting hardware")
    hw = {
        "gpu":  _detect_gpu(),
        "ram":  _detect_ram(),
        "cpu":  _detect_cpu(),
        "os":   _detect_os(),
        "disk": _detect_disk(),
    }
    log.debug("Hardware detected: %s", hw)
    return hw


def format_hardware(hw: dict) -> str:
    """Human-readable multi-line summary for Claude's context."""
    lines = [
        f"OS:   {hw['os']}",
        f"CPU:  {hw['cpu']}",
        f"RAM:  {hw['ram']}",
        f"GPU:  {hw['gpu']}",
        f"Disk: {hw['disk']}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GPU
# ---------------------------------------------------------------------------

def _detect_gpu() -> str:
    # NVIDIA
    if shutil.which("nvidia-smi"):
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            log.debug("GPU (nvidia-smi): %s", r.stdout.strip())
            return r.stdout.strip()

    # AMD ROCm
    if shutil.which("rocm-smi"):
        r = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram", "--csv"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            log.debug("GPU (rocm-smi): %s", r.stdout.strip()[:200])
            return r.stdout.strip()[:200]

    # Generic lspci fallback
    if shutil.which("lspci"):
        r = subprocess.run(["lspci"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            lines = [l for l in r.stdout.splitlines()
                     if any(k in l for k in ("VGA", "3D", "Display", "GPU"))]
            if lines:
                log.debug("GPU (lspci): %s", lines[0])
                return "\n".join(lines)

    log.warning("GPU not detected")
    return "Unknown GPU (nvidia-smi / rocm-smi / lspci not available)"


# ---------------------------------------------------------------------------
# RAM
# ---------------------------------------------------------------------------

def _detect_ram() -> str:
    mem_path = Path("/proc/meminfo")
    if mem_path.exists():
        try:
            for line in mem_path.read_text().splitlines():
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    gb = kb / 1_048_576
                    result = f"{gb:.1f} GB"
                    log.debug("RAM: %s", result)
                    return result
        except Exception:
            log.exception("Failed to parse /proc/meminfo")

    # Fallback: free command
    if shutil.which("free"):
        r = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if line.startswith("Mem:"):
                    return line.split()[1]

    return "Unknown"


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------

def _detect_cpu() -> str:
    cpu_path = Path("/proc/cpuinfo")
    if cpu_path.exists():
        try:
            cores = 0
            model = ""
            for line in cpu_path.read_text().splitlines():
                if line.startswith("model name") and not model:
                    model = line.split(":", 1)[1].strip()
                if line.startswith("processor"):
                    cores += 1
            if model:
                result = f"{model} ({cores} logical cores)"
                log.debug("CPU: %s", result)
                return result
        except Exception:
            log.exception("Failed to parse /proc/cpuinfo")

    return platform.processor() or "Unknown CPU"


# ---------------------------------------------------------------------------
# OS
# ---------------------------------------------------------------------------

def _detect_os() -> str:
    try:
        result = f"{platform.system()} {platform.release()} ({platform.machine()})"
        log.debug("OS: %s", result)
        return result
    except Exception:
        return "Unknown OS"


# ---------------------------------------------------------------------------
# Disk
# ---------------------------------------------------------------------------

def _detect_disk() -> str:
    try:
        usage = shutil.disk_usage(Path.home())
        free_gb  = usage.free  / 1_073_741_824
        total_gb = usage.total / 1_073_741_824
        result = f"{free_gb:.1f} GB free of {total_gb:.1f} GB"
        log.debug("Disk: %s", result)
        return result
    except Exception:
        log.exception("Failed to detect disk space")
        return "Unknown"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_vram_gb(gpu_str: str) -> float:
    """Extract VRAM in GB from nvidia-smi/rocm-smi output. Returns 0.0 if no GPU."""
    m = re.search(r'(\d+)\s*MiB', gpu_str)
    if m:
        return round(int(m.group(1)) / 1024, 1)
    m = re.search(r'(\d+(?:\.\d+)?)\s*GB', gpu_str, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return 0.0


def parse_ram_gb(ram_str: str) -> float:
    """Extract RAM in GB from a string like '32.0 GB'."""
    m = re.search(r'(\d+(?:\.\d+)?)\s*GB', ram_str, re.IGNORECASE)
    return float(m.group(1)) if m else 0.0


def parse_gpu_vendor(gpu_str: str) -> str:
    """Return 'nvidia', 'amd', or 'unknown'."""
    low = gpu_str.lower()
    if any(k in low for k in ("nvidia", "geforce", "quadro", "tesla")):
        return "nvidia"
    if any(k in low for k in ("amd", "radeon", "rocm")):
        return "amd"
    return "unknown"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_hardware_json(slug: str, hw: dict) -> None:
    """Enrich hw dict with parsed numeric fields and write to projects/<slug>/hardware.json."""
    data = {
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "gpu":         hw.get("gpu", ""),
        "vram_gb":     parse_vram_gb(hw.get("gpu", "")),
        "gpu_vendor":  parse_gpu_vendor(hw.get("gpu", "")),
        "ram":         hw.get("ram", ""),
        "ram_gb":      parse_ram_gb(hw.get("ram", "")),
        "cpu":         hw.get("cpu", ""),
        "os":          hw.get("os", ""),
        "disk":        hw.get("disk", ""),
    }
    out_path = _PROJECTS_DIR / slug / "hardware.json"
    try:
        out_path.write_text(json.dumps(data, indent=2))
        log.info("hardware.json saved: %s", out_path)
    except Exception:
        log.exception("Failed to save hardware.json for %s", slug)


def load_hardware_json(slug: str) -> dict | None:
    """Return hardware.json contents for a project, or None if missing/unreadable."""
    path = _PROJECTS_DIR / slug / "hardware.json"
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def hw_summary_str(hw: dict | None) -> str:
    """One-line human-readable summary for the project screen top bar."""
    if not hw:
        return "Not detected"
    gpu = hw.get("gpu", "")
    gpu_name = gpu.split(",")[0].strip()
    gpu_name = (gpu_name
                .replace("NVIDIA GeForce ", "")
                .replace("NVIDIA ", "")
                .replace("AMD Radeon ", ""))
    if len(gpu_name) > 36:
        gpu_name = gpu_name[:33] + "…"
    parts: list[str] = [gpu_name] if gpu_name else []
    vram = hw.get("vram_gb", 0.0)
    if vram:
        parts.append(f"{vram:.1f} GB VRAM")
    ram = hw.get("ram", "")
    if ram:
        parts.append(f"{ram} RAM")
    return "  ·  ".join(parts) if parts else "Unknown GPU"
