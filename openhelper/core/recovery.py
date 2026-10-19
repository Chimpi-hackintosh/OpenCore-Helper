from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from threading import Event
from types import SimpleNamespace

from openhelper.core.efi import sha256_file
from openhelper.errors import AppError
from openhelper.paths import data_root, resource_root


def recovery_worker(board: str, mlb: str, variant: str, destination: str, log: str) -> int:
    """Child-process entry, also supported by the windowed frozen executable."""
    from openhelper.vendor.macrecovery import upstream

    socket.setdefaulttimeout(60)
    with open(log, "w", encoding="utf-8", buffering=1) as stream:
        sys.stdout = sys.stderr = stream
        try:
            return upstream.action_download(SimpleNamespace(board_id=board, mlb=mlb, os_type=variant,
                                                           outdir=destination, diagnostics=False,
                                                           basename="BaseSystem", verbose=False))
        except Exception:
            import traceback

            traceback.print_exc()
            return 1


def download_recovery(board: str, mlb: str, variant: str, destination: Path, cancelled: Event) -> dict:
    if not re.fullmatch(r"Mac-[0-9A-Fa-f]{8,20}", board) or not re.fullmatch(r"[A-Za-z0-9]{17}", mlb):
        raise AppError("invalid_recovery_parameters")
    if variant not in ("default", "latest"):
        raise AppError("invalid_recovery_parameters")
    if destination.exists():
        raise AppError("destination_exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    log = data_root() / "recovery.log"
    with tempfile.TemporaryDirectory(prefix=".och-recovery-", dir=destination.parent) as temp:
        output = Path(temp) / "com.apple.recovery.boot"
        command = [sys.executable]
        if not getattr(sys, "frozen", False):
            command.append(str(resource_root() / "main.py"))
        command.extend(["--recovery-worker", board, mlb, variant, str(output), str(log)])
        process = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            while process.poll() is None:
                if cancelled.wait(0.2):
                    raise AppError("cancelled")
            if process.returncode:
                detail = log.read_text(encoding="utf-8", errors="replace")[-4000:] if log.exists() else ""
                raise AppError("recovery_failed", detail=detail)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        image = output / "BaseSystem.dmg"
        if not image.is_file() or not (output / "BaseSystem.chunklist").is_file():
            raise AppError("recovery_failed", detail="BaseSystem.dmg / BaseSystem.chunklist")
        digest = sha256_file(image)
        output.rename(destination)
    return {"path": str(destination), "sha256": digest, "chunklist_verified": True, "log": str(log)}

