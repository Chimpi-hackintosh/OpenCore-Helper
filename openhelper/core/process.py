from __future__ import annotations

import os
import subprocess
from pathlib import Path

from openhelper.errors import AppError


def run_tool(executable: str, arguments: list[str], *, timeout=120, cwd: Path | None = None):
    binary = Path(executable).expanduser()
    if not binary.is_file():
        raise AppError("tool_not_found", file=str(binary))
    return subprocess.run([str(binary.resolve()), *arguments], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                          check=False)


def launch_ocat(executable: str, config: Path | None):
    binary = Path(executable).expanduser()
    if not binary.is_file():
        raise AppError("tool_not_found", file=str(binary))
    return subprocess.Popen([str(binary.resolve()), *([str(config)] if config else [])],
                            cwd=binary.resolve().parent, close_fds=True)


def convert_recovery(executable: str, source: Path, destination: Path):
    if source.resolve() == destination.resolve() or destination.exists():
        raise AppError("destination_exists")
    # The conversion tool owns the new output; clean up incomplete output after failure.
    try:
        result = run_tool(executable, ["convert", "-O", "vmdk", str(source), str(destination)], timeout=7200)
        if result.returncode != 0:
            raise AppError("tool_failed", detail=result.stderr or result.stdout)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination
