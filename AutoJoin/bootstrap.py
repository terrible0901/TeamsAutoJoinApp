from __future__ import annotations

import os
import sys
from pathlib import Path

_dll_directory = None


def init_deps() -> None:
    """Make workspace-local dependencies available during development."""
    global _dll_directory
    base = Path(__file__).resolve().parents[1] / ".deps"
    if not base.exists():
        return
    for path in (base, base / "win32", base / "win32" / "lib", base / "Pythonwin", base / "pywin32_system32"):
        sys.path.insert(0, str(path))
    if hasattr(os, "add_dll_directory"):
        _dll_directory = os.add_dll_directory(str(base / "pywin32_system32"))
