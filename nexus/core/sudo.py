from __future__ import annotations

_password: str | None = None


def has() -> bool:
    return _password is not None


def set_password(pw: str) -> None:
    global _password
    _password = pw


def clear() -> None:
    global _password
    _password = None


def inject_shell(cmd: str) -> tuple[str, bytes | None]:
    """Replace 'sudo ' prefix with 'sudo -S ' and return password bytes for stdin.
    Returns (cmd, None) unchanged if cmd doesn't start with 'sudo ' or no password cached."""
    if not cmd.startswith("sudo ") or _password is None:
        return cmd, None
    return "sudo -S " + cmd[len("sudo "):], (_password + "\n").encode()
