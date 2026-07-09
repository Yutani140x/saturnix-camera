# logger.py — Centralized logging for SATURNIX Dione
# Uses Python logging with rotating file handler.
# Replaces scattered print() statements.

import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from pathlib import Path

# Default log location
_LOG_DIR = Path(__file__).resolve().parent
_LOG_FILE = _LOG_DIR / "saturnix.log"
_MAX_BYTES = 1024 * 1024  # 1 MB
_BACKUP_COUNT = 3  # keeps saturnix.log + 3 rotated = 4 MB max

_logger = None


def get_logger(name="saturnix"):
    """Return configured logger. Creates handlers on first call."""
    global _logger
    if _logger is not None:
        return _logger

    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    log.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler with rotation
    try:
        fh = RotatingFileHandler(
            str(_LOG_FILE),
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT
        )
        fh.setLevel(logging.INFO)
        fh.setFormatter(fmt)
        log.addHandler(fh)
    except Exception as e:
        print(f"[LOG] file handler init failed: {e}", flush=True)

    # Console handler (stdout)
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    log.addHandler(sh)

    _logger = log
    return log


# Convenience top-level functions
def info(msg, *args):
    get_logger().info(msg, *args)


def warn(msg, *args):
    get_logger().warning(msg, *args)


def error(msg, *args):
    get_logger().error(msg, *args)


def debug(msg, *args):
    get_logger().debug(msg, *args)
