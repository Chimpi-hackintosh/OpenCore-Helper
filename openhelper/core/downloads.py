from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from openhelper import __version__
from openhelper.errors import AppError

REPOSITORIES = {
    "OpenCorePkg": "acidanthera/OpenCorePkg",
    "OCAT": "ic005k/OCAuxiliaryTools",
    "Lilu": "acidanthera/Lilu",
    "WhateverGreen": "acidanthera/WhateverGreen",
    "VirtualSMC": "acidanthera/VirtualSMC",
    "AppleALC": "acidanthera/AppleALC",
    "IntelMausi": "acidanthera/IntelMausi",
}


@dataclass(frozen=True)
class Asset:
    name: str
    url: str
    size: int
    digest: str | None


@dataclass(frozen=True)
class Release:
    repository: str
    tag: str
    url: str
    assets: tuple[Asset, ...]


def _request(url, **kwargs):
    return urllib.request.Request(url, headers={"User-Agent": f"OpenCore-Helper/{__version__}", **kwargs})


def latest_release(project: str) -> Release:
    repository = REPOSITORIES[project]
    url = f"https://api.github.com/repos/{repository}/releases/latest"
    try:
        with urllib.request.urlopen(_request(url, Accept="application/vnd.github+json"), timeout=30) as response:
            data = json.load(response)
    except (urllib.error.URLError, ValueError) as error:
        raise AppError("network_error", detail=str(error)) from error
    return Release(repository, data["tag_name"], data["html_url"], tuple(
        Asset(asset["name"], asset["browser_download_url"], asset.get("size", 0), asset.get("digest"))
        for asset in data.get("assets", []) if asset["name"].lower().endswith(".zip")
    ))


def download_asset(asset: Asset, destination: Path, progress=None) -> tuple[Path, str, bool]:
    parsed = urllib.parse.urlparse(asset.url)
    allowed = any(parsed.path.startswith(f"/{repo}/releases/download/") for repo in REPOSITORIES.values())
    if parsed.scheme != "https" or parsed.netloc != "github.com" or not allowed:
        raise AppError("untrusted_download")
    if destination.exists():
        raise AppError("destination_exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(suffix=".part", dir=destination.parent)
    digest = hashlib.sha256()
    received = 0
    try:
        with os.fdopen(fd, "wb") as stream:
            with urllib.request.urlopen(_request(asset.url), timeout=60) as response:
                if urllib.parse.urlparse(response.url).scheme != "https":
                    raise AppError("untrusted_download")
                while chunk := response.read(256 * 1024):
                    stream.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    if progress:
                        progress(received, asset.size)
            stream.flush()
            os.fsync(stream.fileno())
        computed = digest.hexdigest()
        if asset.size and received != asset.size:
            raise AppError("checksum_mismatch")
        verified = bool(asset.digest and asset.digest.startswith("sha256:"))
        if verified and computed != asset.digest.removeprefix("sha256:"):
            raise AppError("checksum_mismatch")
        os.replace(temporary, destination)
        return destination, computed, verified
    except urllib.error.URLError as error:
        raise AppError("network_error", detail=str(error)) from error
    finally:
        Path(temporary).unlink(missing_ok=True)

