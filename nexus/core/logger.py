from __future__ import annotations
import logging
import logging.handlers
from pathlib import Path

_LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
_LOG_FILE = _LOGS_DIR / "nexus.log"

_FMT      = "%(asctime)s | %(levelname)-8s | %(name)-36s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup(level: int = logging.DEBUG) -> None:
    """Initialise file logging. Call once at app startup."""
    _LOGS_DIR.mkdir(exist_ok=True)

    root = logging.getLogger("nexus")
    if root.handlers:
        return  # already initialised

    root.setLevel(level)

    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=5 * 1024 * 1024,   # 5 MB per file
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_FMT, _DATE_FMT))
    root.addHandler(fh)

    root.info("=" * 72)
    root.info("Nexus started")
    root.info("=" * 72)


def get(name: str) -> logging.Logger:
    """Return a named child logger under the 'nexus' hierarchy."""
    return logging.getLogger(f"nexus.{name}")
