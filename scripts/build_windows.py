"""Build a self-contained x64 directory, portable ZIP and optional NSIS setup."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from openhelper import __version__  # noqa: E402


def verify_staging(directory: Path):
    required = ["OpenCoreHelper.exe", "lib", "locales/en.json", "locales/pt-BR.json", "LICENSE.txt",
                "README.txt", "settings.default.json", "licenses/OpenCorePkg-BSD-3-Clause.txt"]
    missing = [name for name in required if not (directory / name).exists()]
    sources = [str(path.relative_to(directory)) for path in directory.rglob("*")
               if path.suffix.lower() in (".py", ".pyw")]
    if missing or sources:
        raise RuntimeError(f"Invalid staging: missing={missing}, exposed_sources={sources}")
    english = json.loads((directory / "locales/en.json").read_text(encoding="utf-8"))
    portuguese = json.loads((directory / "locales/pt-BR.json").read_text(encoding="utf-8"))
    if english.keys() != portuguese.keys():
        raise RuntimeError("Localization keys differ")


def collect_licenses(destination: Path):
    for name in ("customtkinter", "Pillow", "darkdetect", "packaging", "pyinstaller"):
        distribution = importlib.metadata.distribution(name)
        for entry in distribution.files or []:
            if "license" in str(entry).lower() and not str(entry).endswith(".py"):
                path = Path(distribution.locate_file(entry))
                if path.is_file():
                    target = destination / name / path.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-installer", action="store_true")
    parser.add_argument("--verify-only", type=Path)
    args = parser.parse_args()
    if args.verify_only:
        verify_staging(args.verify_only)
        return
    if os.name != "nt" or platform.machine().lower() not in ("amd64", "x86_64"):
        raise SystemExit("Build on Windows x64 with x64 Python")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    str(ROOT / "packaging/OpenCoreHelper.spec")], cwd=ROOT, check=True)
    staging = ROOT / "dist/OpenCoreHelper"
    shutil.copytree(ROOT / "locales", staging / "locales", dirs_exist_ok=True)
    shutil.copytree(ROOT / "licenses", staging / "licenses", dirs_exist_ok=True)
    for source, target in (("LICENSE", "LICENSE.txt"), ("README.md", "README.txt"),
                            ("settings.default.json", "settings.default.json"),
                            ("THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md")):
        shutil.copy2(ROOT / source, staging / target)
    collect_licenses(staging / "licenses")
    verify_staging(staging)
    shutil.make_archive(str(ROOT / f"dist/OpenCoreHelper-{__version__}-Windows-x64"), "zip",
                        root_dir=staging.parent, base_dir=staging.name)
    if not args.skip_installer:
        nsis = shutil.which("makensis.exe") or str(Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
                                                  / "NSIS/makensis.exe")
        subprocess.run([nsis, f"/DVERSION={__version__}", f"/DSTAGING={staging}",
                        str(ROOT / "packaging/installer.nsi")], cwd=ROOT, check=True)
    from openhelper.core.efi import sha256_file

    artifacts = [file for file in (ROOT / "dist").iterdir() if file.is_file() and file.suffix in (".zip", ".exe")]
    (ROOT / "dist/SHA256SUMS.txt").write_text("".join(f"{sha256_file(file)}  {file.name}\n" for file in artifacts),
                                            encoding="utf-8")
    print(f"Verified Windows x64 package: {staging}")


if __name__ == "__main__":
    main()

