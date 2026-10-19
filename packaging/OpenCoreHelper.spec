# Build on Windows x64 with Python 3.12+ and requirements-dev.txt.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=collect_data_files("customtkinter"),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff"],
    noarchive=False,
    optimize=0,  # macrecovery verifies chunklist signatures using assertions.
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz, analysis.scripts, [], exclude_binaries=True, name="OpenCoreHelper",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False, contents_directory="lib",
    version=str(root / "packaging" / "version_info.txt"),
)
distribution = COLLECT(executable, analysis.binaries, analysis.datas,
                       strip=False, upx=False, name="OpenCoreHelper")

