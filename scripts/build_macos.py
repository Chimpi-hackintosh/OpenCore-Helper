"""Build and inspect the macOS Intel app without publishing a release."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MINIMUM_MACOS = "10.15"
MAGIC = {bytes.fromhex(value) for value in (
    "feedface", "cefaedfe", "feedfacf", "cffaedfe", "cafebabe", "bebafeca", "cafebabf", "bfbafeca")}


def version_tuple(value: str) -> tuple[int, ...]:
    parts = [int(part) for part in value.split(".")]
    return tuple((parts + [0, 0, 0])[:3])


def minimum_versions(load_commands: str) -> list[str]:
    versions = []
    for block in re.split(r"Load command \d+", load_commands):
        if re.search(r"cmd LC_BUILD_VERSION\b", block):
            match = re.search(r"\bminos\s+([0-9.]+)", block)
        elif re.search(r"cmd LC_VERSION_MIN_MACOSX\b", block):
            match = re.search(r"\bversion\s+([0-9.]+)", block)
        else:
            continue
        if match:
            versions.append(match[1])
    return versions


def command(args: list[str]) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def verify_bundle(bundle: Path) -> dict:
    binary = bundle / "Contents" / "MacOS" / "OpenCoreHelper"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError("The app executable is missing or has lost its executable permission")
    command(["/usr/bin/plutil", "-lint", str(bundle / "Contents" / "Info.plist")])
    command(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(bundle)])
    native = []
    seen = set()
    for path in sorted(bundle.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() in (".py", ".pyw"):
            raise RuntimeError(f"Unbundled Python source: {path.relative_to(bundle)}")
        real = path.resolve()
        if real in seen:
            continue
        seen.add(real)
        with path.open("rb") as stream:
            if stream.read(4) not in MAGIC:
                continue
        architectures = command(["/usr/bin/lipo", "-archs", str(path)]).split()
        if architectures != ["x86_64"]:
            raise RuntimeError(f"Unexpected architecture in {path}: {architectures}")
        versions = minimum_versions(command(["/usr/bin/otool", "-arch", "x86_64", "-l", str(path)]))
        if not versions or any(version_tuple(v) > version_tuple(MINIMUM_MACOS) for v in versions):
            raise RuntimeError(f"Binary requires a newer or unknown macOS version: {path}: {versions}")
        native.append({"path": str(path.relative_to(bundle)), "minimum_macos": max(versions, key=version_tuple)})
    if not native:
        raise RuntimeError("No Mach-O executables were found")
    return {"architecture": "x86_64", "target_minimum_macos": MINIMUM_MACOS,
            "tested_macos": platform.mac_ver()[0], "binaries": native,
            "compatibility_note": "Binary minimum versions checked; older macOS releases still require runtime tests"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--bundle", type=Path, default=ROOT / "dist" / "OpenCore Helper.app")
    args = parser.parse_args()
    if sys.platform != "darwin" or platform.machine().lower() != "x86_64":
        raise SystemExit("Run on macOS with Intel x64 Python")
    if not args.verify_only:
        environment = dict(os.environ, MACOSX_DEPLOYMENT_TARGET=MINIMUM_MACOS)
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                        str(ROOT / "packaging" / "OpenCoreHelper-macOS.spec")],
                       cwd=ROOT, env=environment, check=True)
    report = verify_bundle(args.bundle)
    if args.verify_only:
        print(json.dumps(report, indent=2))
        return
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    archive = ROOT / "dist" / f"OpenCoreHelper-{version}-macOS-x64.zip"
    command(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(args.bundle), str(archive)])
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT / "dist" / "SHA256SUMS-macOS-x64.txt").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    (ROOT / "dist" / "macos-build-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Verified macOS x64 package: {archive.name}; target {MINIMUM_MACOS}+")


if __name__ == "__main__":
    main()
