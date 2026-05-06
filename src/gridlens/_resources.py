"""Resolve packaged asset paths in dev and PyInstaller frozen builds.

In a frozen --onefile build PyInstaller extracts data files under
``sys._MEIPASS / "gridlens" / ...``. In dev they live next to the source
on disk. This helper papers over the difference so callers can write
``package_dir() / "ui" / "theme" / "style.qss"`` and not care.
"""
from __future__ import annotations

import sys
from pathlib import Path


def package_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "gridlens"
    return Path(__file__).resolve().parent


def resource(*parts: str) -> Path:
    return package_dir().joinpath(*parts)
