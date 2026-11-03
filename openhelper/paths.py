from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from openhelper import APP_NAME, PUBLISHER


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return Path(sys.executable).resolve().parent.parent / "Resources"
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundled_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", resource_root()))


def data_root() -> Path:
    if os.name == "nt":
        # CSIDL_LOCAL_APPDATA, independent of drive letters and shell environment.
        buffer = ctypes.create_unicode_buffer(32768)
        result = ctypes.windll.shell32.SHGetFolderPathW(None, 28, None, 0, buffer)
        if result != 0:
            raise OSError("SHGetFolderPathW failed", result)
        root = Path(buffer.value)
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:  # Development and automated QA on Linux.
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    target = root / PUBLISHER / APP_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target
