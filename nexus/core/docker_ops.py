from __future__ import annotations

import asyncio
import shutil
from typing import AsyncIterator


class DockerError(Exception):
    pass


async def is_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "ps",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception:
        return False


async def container_status(name: str) -> str:
    """Return 'running', 'exited', or 'not_found'."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "inspect", "--format", "{{.State.Status}}", name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return "not_found"
        return stdout.decode().strip() or "not_found"
    except Exception:
        return "not_found"


async def pull_image(image: str) -> AsyncIterator[str]:
    """Stream status lines from docker pull."""
    proc = await asyncio.create_subprocess_exec(
        "docker", "pull", image,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if proc.stdout is None:
        raise DockerError("docker pull: stdout unavailable")
    async for raw in proc.stdout:
        # Docker uses \r for in-place progress; take the last segment
        line = raw.decode(errors="replace").split("\r")[-1].rstrip()
        if line:
            yield line
    await proc.wait()
    if proc.returncode != 0:
        raise DockerError(f"docker pull exited with code {proc.returncode}")


async def run_container(
    name: str,
    image: str,
    ports: dict[str, str],
    volumes: dict[str, str],
    env: dict[str, str],
    extra_args: list[str],
) -> None:
    """Start a detached container. Raises DockerError on failure."""
    status = await container_status(name)
    if status == "running":
        raise DockerError(f"Container '{name}' is already running.")
    if status != "not_found":
        await _remove(name)

    args = ["docker", "run", "-d", "--name", name]
    for host_port, container_port in ports.items():
        args += ["-p", f"{host_port}:{container_port}"]
    for host_path, container_path in volumes.items():
        args += ["-v", f"{host_path}:{container_path}"]
    for k, v in env.items():
        args += ["-e", f"{k}={v}"]
    args += extra_args
    args.append(image)

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = stderr.decode(errors="replace").strip()
        raise DockerError(msg or f"docker run failed (code {proc.returncode})")


async def stop_container(name: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "docker", "stop", name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = stderr.decode(errors="replace").strip()
        if "No such container" not in msg:
            raise DockerError(msg or f"docker stop failed (code {proc.returncode})")


async def remove_container(name: str) -> None:
    await _remove(name)


async def _remove(name: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "docker", "rm", "-f", name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = stderr.decode(errors="replace").strip()
        raise DockerError(msg or f"docker rm failed (code {proc.returncode})")


async def get_logs(name: str, tail: int = 100) -> str:
    proc = await asyncio.create_subprocess_exec(
        "docker", "logs", "--tail", str(tail), name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode(errors="replace")
