"""Path helpers that work from source, from the installed app and inside a PyInstaller build."""

from __future__ import annotations

import os
import sys

APP_NAME = "MailBlaster"
HERE = os.path.dirname(os.path.abspath(__file__))


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def is_installed() -> bool:
    """Installed copies carry an `.installed` marker next to the code (see build.ps1)."""
    return is_frozen() or os.path.isfile(os.path.join(HERE, ".installed"))


def resource_dir() -> str:
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return HERE


def static_dir() -> str:
    return os.path.join(resource_dir(), "static")


def data_dir() -> str:
    """Writable per-user folder for the database + logs."""
    if is_installed():
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        d = os.path.join(base, APP_NAME)
    else:
        d = HERE
    os.makedirs(d, exist_ok=True)
    return d
