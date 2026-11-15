# Build with the python.org framework on an Intel macOS runner.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent
version = (root / "VERSION").read_text(encoding="utf-8").strip()
analysis = Analysis(
    [str(root / "main.py")], pathex=[str(root)], binaries=[],
    datas=collect_data_files("customtkinter") + collect_data_files("certifi") + [
        (str(root / "locales"), "locales"),
        (str(root / "settings.default.json"), "."),
        (str(root / "LICENSE"), "."),
        (str(root / "THIRD_PARTY_NOTICES.md"), "."),
        (str(root / "licenses"), "licenses"),
        (str(root / "docs" / "MACOS.md"), "docs"),
    ],
    hiddenimports=[], hookspath=[], hooksconfig={},
    runtime_hooks=[str(root / "packaging" / "macos_runtime.py")],
    excludes=["pytest", "ruff"], noarchive=False,
    optimize=0,  # macrecovery relies on assertions for signature verification.
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz, analysis.scripts, [], exclude_binaries=True, name="OpenCoreHelper",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False, target_arch="x86_64",
    codesign_identity=None, entitlements_file=None,
)
distribution = COLLECT(executable, analysis.binaries, analysis.datas,
                       strip=False, upx=False, name="OpenCoreHelper")
app = BUNDLE(
    distribution, name="OpenCore Helper.app", bundle_identifier="com.chimpi.opencorehelper",
    info_plist={
        "CFBundleDisplayName": "OpenCore Helper",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "LSMinimumSystemVersion": "10.15",
        "NSHighResolutionCapable": True,
    },
)
