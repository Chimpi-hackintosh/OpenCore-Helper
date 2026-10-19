from __future__ import annotations

import hashlib
import json
import os
import plistlib
import shutil
import stat
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from openhelper.core.validation import Issue, validate_config
from openhelper.errors import AppError


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def locate_oc(folder: Path) -> Path:
    for candidate in (folder, folder / "OC", folder / "EFI" / "OC"):
        if (candidate / "config.plist").is_file():
            return candidate.resolve()
    raise AppError("efi_not_found")


def inspect_efi(folder: Path) -> list[Issue]:
    oc = locate_oc(folder)
    data = plistlib.loads((oc / "config.plist").read_bytes())
    if not isinstance(data, dict):
        raise AppError("root_dictionary")
    issues = validate_config(data, oc)
    for file in (oc / "OpenCore.efi", oc.parent / "BOOT" / "BOOTx64.efi"):
        if not file.is_file():
            issues.insert(0, Issue("error", "missing_file", str(file), {"file": file.name}))
    return issues


def backup_efi(source: Path, destination: Path) -> Path:
    source, destination = source.resolve(), destination.resolve()
    if not source.is_dir():
        raise AppError("efi_not_found")
    if destination.is_relative_to(source):
        raise AppError("backup_inside_source")
    if destination.exists():
        raise AppError("destination_exists")
    files = sorted(source.rglob("*"))
    if any(file.is_symlink() or (hasattr(file, "is_junction") and file.is_junction()) for file in files):
        raise AppError("symlink_refused")
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "files": {}}
    fd, temporary = tempfile.mkstemp(suffix=".zip", dir=destination.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                if file.is_file():
                    name = (PurePosixPath(source.name) / file.relative_to(source).as_posix()).as_posix()
                    digest = hashlib.sha256()
                    with file.open("rb") as src, archive.open(name, "w") as dst:
                        while chunk := src.read(1024 * 1024):
                            dst.write(chunk)
                            digest.update(chunk)
                    manifest["files"][name] = digest.hexdigest()
            archive.writestr("__och_manifest__.json", json.dumps(manifest, indent=2))
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination


def extract_zip(archive_path: Path, destination: Path, verify_backup: bool = False) -> Path:
    """Extract to a NEW directory only, reject traversal, links and oversized archives."""
    if destination.exists():
        raise AppError("destination_exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".och-extract-", dir=destination.parent))
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            if len(entries) > 30000 or sum(item.file_size for item in entries) > 2 * 1024**3:
                raise AppError("archive_too_large")
            names = set()
            for item in entries:
                name = item.filename.replace("\\", "/")
                path = PurePosixPath(name)
                # Windows aliases, reserved device names and trailing dots are rejected too.
                reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10)}
                invalid = any(part.rstrip(" .") != part or part.split(".")[0].upper() in reserved
                              for part in path.parts)
                target = temporary.joinpath(*path.parts)
                mode = item.external_attr >> 16
                if (path.is_absolute() or ".." in path.parts or ":" in name or invalid or
                        not target.resolve().is_relative_to(temporary) or stat.S_ISLNK(mode)):
                    raise AppError("unsafe_archive")
                folded = name.rstrip("/").casefold()
                if folded in names:
                    raise AppError("unsafe_archive")
                names.add(folded)
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
            if verify_backup:
                manifest_path = temporary / "__och_manifest__.json"
                if not manifest_path.is_file():
                    raise AppError("manifest_missing")
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                expected = manifest.get("files")
                actual = {p.relative_to(temporary).as_posix() for p in temporary.rglob("*")
                          if p.is_file() and p != manifest_path}
                if not isinstance(expected, dict) or set(expected) != actual:
                    raise AppError("checksum_mismatch")
                for name, digest in expected.items():
                    if sha256_file(temporary / name) != digest:
                        raise AppError("checksum_mismatch")
        temporary.rename(destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def prepare_workspace(package: Path, destination: Path) -> Path:
    """Copy OpenCore's X64 EFI and sample into an isolated, new workspace."""
    if destination.exists():
        raise AppError("destination_exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        unpacked = extract_zip(package, Path(temp) / "package")
        efi = unpacked / "X64" / "EFI"
        sample = unpacked / "Docs" / "Sample.plist"
        if not efi.is_dir() or not sample.is_file():
            raise AppError("invalid_oc_package")
        staged = Path(temp) / "workspace"
        shutil.copytree(efi, staged / "EFI")
        shutil.copy2(sample, staged / "EFI" / "OC" / "config.plist")
        (staged / "README.txt").write_text(
            "OpenCore sample workspace. Configure for your hardware and run matching ocvalidate before use.\n",
            encoding="utf-8")
        staged.rename(destination)
    return destination

