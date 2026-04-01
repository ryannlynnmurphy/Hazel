"""
hzl_logger.py — HZL AI Centralized Logger
All integrations import this. Logs to ~/jarvis/logs/ with rotation.
Color-coded terminal output + persistent file logs per module.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

_HZL_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(_HZL_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ── ANSI colors ───────────────────────────────────────────────────────────────
COLORS = {
    "DEBUG":    "\033[94m",   # blue
    "INFO":     "\033[92m",   # green
    "WARNING":  "\033[93m",   # yellow
    "ERROR":    "\033[91m",   # red
    "CRITICAL": "\033[95m",   # purple
}
RESET  = "\033[0m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
PURPLE = "\033[95m"


class ColorFormatter(logging.Formatter):
    def format(self, record):
        color = COLORS.get(record.levelname, "")
        ts    = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        mod   = f"{record.name:<12}"
        level = f"{record.levelname:<8}"
        msg   = record.getMessage()

        # Exceptions
        exc = ""
        if record.exc_info:
            import traceback
            exc = "\n" + "".join(traceback.format_exception(*record.exc_info))

        return (
            f"{DIM}{ts}{RESET} "
            f"{PURPLE}{BOLD}HZL{RESET} "
            f"{DIM}{mod}{RESET} "
            f"{color}{level}{RESET} "
            f"{msg}{exc}"
        )


class FileFormatter(logging.Formatter):
    def format(self, record):
        ts  = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        exc = ""
        if record.exc_info:
            import traceback
            exc = "\n" + "".join(traceback.format_exception(*record.exc_info))
        return f"{ts} | {record.name:<12} | {record.levelname:<8} | {record.getMessage()}{exc}"


def get_logger(name: str, level: str = None) -> logging.Logger:
    """
    Get a named logger with color console output + rotating file output.

    Args:
        name:  Module name, e.g. "spotify", "todoist"
        level: Override log level (DEBUG/INFO/WARNING/ERROR). Defaults to
               HZL_LOG_LEVEL env var or INFO.
    """
    log_level_str = level or os.getenv("HZL_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    logger = logging.getLogger(f"hzl.{name}")
    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(logging.DEBUG)  # Let handlers filter

    # ── Console handler (color) ───────────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(ColorFormatter())
    logger.addHandler(console)

    # ── File handler (rotating, 1MB x 3 files per module) ────────────────────
    log_file = os.path.join(LOG_DIR, f"{name}.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)  # Always log everything to file
    file_handler.setFormatter(FileFormatter())
    logger.addHandler(file_handler)

    # ── Master log (all modules in one file) ─────────────────────────────────
    master_file = os.path.join(LOG_DIR, "hzl_all.log")
    master_handler = RotatingFileHandler(
        master_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    master_handler.setLevel(logging.DEBUG)
    master_handler.setFormatter(FileFormatter())
    logger.addHandler(master_handler)

    logger.propagate = False
    return logger


def get_log_tail(module: str = "hzl_all", lines: int = 50) -> str:
    """Return the last N lines from a module's log file."""
    log_file = os.path.join(LOG_DIR, f"{module}.log")
    if not os.path.exists(log_file):
        return f"No log file found for '{module}'"
    with open(log_file, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    return "".join(all_lines[-lines:])


def list_logs() -> str:
    """List all log files and their sizes."""
    files = sorted(os.listdir(LOG_DIR))
    if not files:
        return "No log files yet."
    lines = []
    for f in files:
        path = os.path.join(LOG_DIR, f)
        size = os.path.getsize(path)
        lines.append(f"  {f:<30} {size/1024:.1f} KB")
    return "\n".join(lines)
