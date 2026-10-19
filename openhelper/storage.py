from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from openhelper.paths import data_root, resource_root


def atomic_write(path: Path, content: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class Settings:
    def __init__(self, path: Path | None = None):
        self.path = path if path is not None else data_root() / "settings.json"
        self.values = json.loads((resource_root() / "settings.default.json").read_text(encoding="utf-8"))
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(saved, dict):
                    raise ValueError("settings must be an object")
                self.values.update({k: v for k, v in saved.items() if k in self.values})
            except (ValueError, UnicodeError):
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
                self.path.replace(self.path.with_name(f"settings.corrupt-{stamp}.json"))
        for key, default in {"language": "auto", "appearance": "System", "ocat_path": "",
                             "ocvalidate_path": "", "macserial_path": "", "qemu_img_path": "", "last_config": ""}.items():
            if not isinstance(self.values.get(key), str):
                self.values[key] = default
        if self.values["appearance"] not in ("System", "Light", "Dark"):
            self.values["appearance"] = "System"
        if self.values["language"] not in ("auto", "en", "pt-BR"):
            self.values["language"] = "auto"

    def get(self, key, default=None):
        return self.values.get(key, default)

    def save(self, **updates) -> None:
        self.values.update(updates)
        atomic_write(self.path, json.dumps(self.values, indent=2, ensure_ascii=False).encode("utf-8"))

