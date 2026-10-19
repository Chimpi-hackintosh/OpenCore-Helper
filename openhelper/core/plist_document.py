from __future__ import annotations

import copy
import hashlib
import plistlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

from openhelper.errors import AppError
from openhelper.storage import atomic_write

PathKey = tuple[str | int, ...]
TYPES = ("String", "Boolean", "Integer", "Real", "Data", "Date", "Dictionary", "Array")


def value_type(value) -> str:
    for cls, name in ((bool, "Boolean"), (str, "String"), (int, "Integer"), (float, "Real"),
                      (bytes, "Data"), (datetime, "Date"), (dict, "Dictionary"), (list, "Array")):
        if isinstance(value, cls):
            return name
    raise AppError("unsupported_type", type=type(value).__name__)


def display_value(value) -> str:
    kind = value_type(value)
    if kind in ("Dictionary", "Array"):
        return f"[{len(value)}]"
    if kind == "Data":
        return value.hex().upper()
    if kind == "Boolean":
        return "true" if value else "false"
    if kind == "Date":
        return value.isoformat() + ("Z" if value.tzinfo is None else "")
    return str(value)


def parse_value(kind: str, text: str):
    try:
        if kind == "String":
            return text
        if kind == "Boolean":
            if text.strip().lower() not in ("true", "false"):
                raise ValueError("true / false")
            return text.strip().lower() == "true"
        if kind == "Integer":
            stripped = text.strip()
            return int(stripped, 16 if stripped.lower().startswith(("0x", "-0x")) else 10)
        if kind == "Real":
            import math
            number = float(text)
            if not math.isfinite(number):
                raise ValueError("finite number required")
            return number
        if kind == "Data":
            return bytes.fromhex(text.replace("<", "").replace(">", ""))
        if kind == "Date":
            date = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
            return date.astimezone(timezone.utc).replace(tzinfo=None) if date.tzinfo else date
        if kind == "Dictionary":
            return {}
        if kind == "Array":
            return []
    except (ValueError, OverflowError) as error:
        raise AppError("invalid_value", type=kind, detail=str(error)) from error
    raise AppError("unsupported_type", type=kind)


class PlistDocument:
    def __init__(self):
        self.data: dict = {}
        self.path: Path | None = None
        self.binary = False
        self.dirty = False
        self._fingerprint: str | None = None
        self._undo: list[dict] = []
        self._redo: list[dict] = []

    def load(self, path: Path) -> None:
        payload = Path(path).read_bytes()
        try:
            parsed = plistlib.loads(payload)
        except (ValueError, TypeError, OverflowError, plistlib.InvalidFileException) as error:
            raise AppError("invalid_plist", detail=str(error)) from error
        if not isinstance(parsed, dict):
            raise AppError("root_dictionary")
        self.data = parsed
        self.path = Path(path).resolve()
        self.binary = payload.startswith(b"bplist")
        self._fingerprint = hashlib.sha256(payload).hexdigest()
        self.dirty = False
        self._undo.clear()
        self._redo.clear()

    def get(self, path: PathKey):
        node = self.data
        for key in path:
            node = node[key]
        return node

    def checkpoint(self):
        self._undo.append(copy.deepcopy(self.data))
        self._undo = self._undo[-50:]
        self._redo.clear()
        self.dirty = True

    def set(self, path: PathKey, value):
        if not path:
            raise AppError("root_edit")
        self.checkpoint()
        self.get(path[:-1])[path[-1]] = value

    def add(self, path: PathKey, key: str, value):
        parent = self.get(path)
        if isinstance(parent, dict):
            if not key or key in parent:
                raise AppError("duplicate_key", key=key)
        elif not isinstance(parent, list):
            raise AppError("select_container")
        self.checkpoint()
        if isinstance(parent, dict):
            parent[key] = value
        else:
            parent.append(value)

    def delete(self, path: PathKey):
        if not path:
            raise AppError("root_edit")
        self.checkpoint()
        del self.get(path[:-1])[path[-1]]

    def rename(self, path: PathKey, key: str):
        if not path or not isinstance(path[-1], str):
            raise AppError("select_dictionary_key")
        parent = self.get(path[:-1])
        if not key or (key != path[-1] and key in parent):
            raise AppError("duplicate_key", key=key)
        self.checkpoint()
        # Preserve insertion order, including when renaming a key in NVRAM.
        entries = [(key if old == path[-1] else old, value) for old, value in parent.items()]
        parent.clear()
        parent.update(entries)

    def move(self, path: PathKey, offset: int):
        if not path or not isinstance(path[-1], int):
            raise AppError("select_array_item")
        items = self.get(path[:-1])
        index = path[-1]
        target = index + offset
        if not 0 <= target < len(items):
            return
        self.checkpoint()
        items[index], items[target] = items[target], items[index]

    def undo(self):
        if self._undo:
            self._redo.append(copy.deepcopy(self.data))
            self.data = self._undo.pop()
            self.dirty = True

    def redo(self):
        if self._redo:
            self._undo.append(copy.deepcopy(self.data))
            self.data = self._redo.pop()
            self.dirty = True

    def save(self, path: Path | None = None) -> Path | None:
        target = Path(path).resolve() if path is not None else self.path
        if target is None:
            raise AppError("no_config")
        backup = None
        same_file = self.path is not None and target == self.path
        if same_file and target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != self._fingerprint:
                raise AppError("external_change")
        try:
            content = plistlib.dumps(self.data, fmt=plistlib.FMT_BINARY if self.binary else plistlib.FMT_XML,
                                     sort_keys=False)
        except (ValueError, TypeError, OverflowError) as error:
            raise AppError("invalid_plist", detail=str(error)) from error
        if target.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            backup = target.with_name(f"{target.name}.{stamp}.bak")
            shutil.copy2(target, backup)
        atomic_write(target, content)
        self.path = target
        self._fingerprint = hashlib.sha256(content).hexdigest()
        self.dirty = False
        return backup
