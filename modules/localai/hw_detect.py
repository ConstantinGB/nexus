from __future__ import annotations
import platform
import shutil
import subprocess
from pathlib import Path

from nexus.core.logger import get

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
