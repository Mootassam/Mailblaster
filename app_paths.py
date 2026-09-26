"""Path helpers that work from source and inside a PyInstaller build."""

from __future__ import annotations

import os
import sys

APP_NAME = "MailBlaster"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_dir() -> str:
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def static_dir() -> str:
    return os.path.join(resource_dir(), "static")


def data_dir() -> str:
    """Writable per-user folder for the database + logs."""
    if is_frozen():
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        d = os.path.join(base, APP_NAME)
    else:
        d = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(d, exist_ok=True)
    return d
