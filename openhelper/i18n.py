from __future__ import annotations

import ctypes
import json
import locale
import os
import re
import subprocess
import sys

from openhelper.paths import resource_root


def preferred_languages() -> list[str]:
    if os.name == "nt":
        count = ctypes.c_ulong()
        size = ctypes.c_ulong()
        api = ctypes.windll.kernel32.GetUserPreferredUILanguages
        if api(0x8, ctypes.byref(count), None, ctypes.byref(size)) and size.value:
            buffer = ctypes.create_unicode_buffer(size.value)
            if api(0x8, ctypes.byref(count), buffer, ctypes.byref(size)):
                return [part for part in buffer[:size.value].split("\0") if part]
        return []
    if sys.platform == "darwin":
        try:
            result = subprocess.run(["/usr/bin/defaults", "read", "-g", "AppleLanguages"],
                                    capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                languages = re.findall(r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*", result.stdout)
                if languages:
                    return languages
        except (OSError, subprocess.TimeoutExpired):
            pass
    return [locale.getlocale()[0] or "en"]


def resolve_language(override: str, candidates: list[str]) -> str:
    for candidate in ([override] if override and override != "auto" else candidates):
        normalized = candidate.replace("_", "-").lower()
        if normalized == "pt-br" or normalized.split("-")[0] == "pt":
            return "pt-BR"
        if normalized.split("-")[0] == "en":
            return "en"
    return "en"


class Translator:
    def __init__(self, language="auto"):
        self.language = resolve_language(language, preferred_languages())
        directory = resource_root() / "locales"
        self.fallback = json.loads((directory / "en.json").read_text(encoding="utf-8"))
        self.strings = json.loads((directory / f"{self.language}.json").read_text(encoding="utf-8"))

    def __call__(self, message_key: str, **params) -> str:
        return self.strings.get(message_key, self.fallback.get(message_key, message_key)).format(**params)
