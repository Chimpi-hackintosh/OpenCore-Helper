from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from openhelper import __version__
from openhelper.storage import atomic_write


def make_report(*, hardware=None, findings=None, efi=None, translate=None) -> dict:
    report = {"application": "OpenCore Helper", "version": __version__,
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "hardware": hardware or {}, "findings": [issue.to_dict() for issue in (findings or [])],
              "efi": [issue.to_dict() for issue in (efi or [])]}
    if translate:
        for group in ("findings", "efi"):
            for item in report[group]:
                item["message"] = translate(item["code"], **item["params"])
    return report


def export_report(report: dict, destination: Path):
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if destination.suffix.lower() == ".html":
        payload = ("<!doctype html><html><head><meta charset='utf-8'><title>OpenCore Helper</title>"
                   "<style>body{max-width:1100px;margin:40px auto;background:#111827;color:#e5e7eb;"
                   "font:16px system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style></head>"
                   f"<body><h1>OpenCore Helper {__version__}</h1><pre>{html.escape(payload)}</pre></body></html>")
    atomic_write(destination, payload.encode("utf-8"))

