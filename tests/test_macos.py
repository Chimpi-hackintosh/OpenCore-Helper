import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from openhelper import i18n, paths
from openhelper.core import macos_hardware, process
from openhelper.errors import AppError
from scripts.build_macos import minimum_versions, verify_bundle, version_tuple


def test_frozen_mac_resources_and_user_data_are_independent_of_cwd(tmp_path, monkeypatch):
    executable = tmp_path / "My App.app/Contents/MacOS/OpenCoreHelper"
    monkeypatch.setattr(paths, "sys", SimpleNamespace(platform="darwin", frozen=True, executable=str(executable)))
    monkeypatch.setattr(paths, "os", SimpleNamespace(name="posix", environ={}))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    assert paths.resource_root() == executable.parent.parent / "Resources"
    target = paths.data_root()
    assert target == tmp_path / "home/Library/Application Support/SnoopyOS Company/OpenCore Helper"
    assert target.is_dir()


def test_mac_language_order_and_failure_fallback(monkeypatch):
    monkeypatch.setattr(i18n, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(i18n, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(i18n.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        [], 0, '(\n    "pt-BR",\n    "en-US"\n)\n', ""))
    assert i18n.preferred_languages() == ["pt-BR", "en-US"]
    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 5)
    monkeypatch.setattr(i18n.subprocess, "run", fail)
    monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("en_US", "UTF-8"))
    assert i18n.preferred_languages() == ["en_US"]


def test_launch_mac_ocat_bundle_preserves_spaces_and_document(tmp_path, monkeypatch):
    app = tmp_path / "Official OCAT.app"
    (app / "Contents").mkdir(parents=True)
    (app / "Contents/Info.plist").write_text("plist")
    document = tmp_path / "My EFI/config.plist"
    calls = []
    monkeypatch.setattr(process, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(process.subprocess, "Popen", lambda args, **kwargs: calls.append(args))
    process.launch_ocat(str(app), document)
    assert calls == [["/usr/bin/open", "-a", str(app.resolve()), str(document.resolve())]]
    (app / "Contents/Info.plist").unlink()
    with pytest.raises(AppError, match="tool_not_found"):
        process.launch_ocat(str(app), document)


def test_mac_inventory_whitelists_fields_and_reports_unavailable_devices():
    profile = {"SPHardwareDataType": [{"machine_model": "Macmini8,1", "serial_number": "PRIVATE-SERIAL",
               "platform_UUID": "PRIVATE-UUID", "boot_rom_version": "1"}],
               "SPDisplaysDataType": [{"sppci_model": "Intel UHD 630", "serial_number": "PRIVATE-GPU"}],
               "SPNetworkDataType": [{"_name": "Ethernet", "ip_address": "PRIVATE-IP"}]}
    result = macos_hardware.normalize_inventory(profile, "Intel Core i5", 16 * 1024**3)
    assert result["cpu"][0]["Name"] == "Intel Core i5"
    assert result["gpu"] == [{"Name": "Intel UHD 630"}]
    assert result["memory"][0]["Capacity"] == 16 * 1024**3
    assert set(result["unavailable"]) == {"audio", "storage"}
    assert "PRIVATE" not in json.dumps(result)


def test_invalid_system_profiler_json_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(macos_hardware.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        [], 0, "invalid", ""))
    with pytest.raises(AppError, match="tool_failed"):
        macos_hardware.scan_macos_hardware()


def test_macho_minimum_parser_ignores_dylib_versions():
    commands = """Load command 0
          cmd LC_ID_DYLIB
        current version 50.0.0
    Load command 1
          cmd LC_BUILD_VERSION
        minos 10.15
          sdk 15.0
    Load command 2
          cmd LC_VERSION_MIN_MACOSX
      version 10.13
    """
    assert minimum_versions(commands) == ["10.15", "10.13"]
    assert version_tuple("10.15") < version_tuple("11")


@pytest.mark.parametrize("architecture,minos", [("arm64", "10.15"), ("x86_64", "11.0")])
def test_macos_verifier_rejects_wrong_architecture_or_newer_dependency(tmp_path, monkeypatch, architecture, minos):
    app = tmp_path / "Test.app"
    binary = app / "Contents/MacOS/OpenCoreHelper"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(bytes.fromhex("cffaedfe"))
    binary.chmod(0o755)
    def command(args):
        if args[0].endswith("lipo"):
            return architecture
        if args[0].endswith("otool"):
            return f"Load command 1\ncmd LC_BUILD_VERSION\nminos {minos}\n"
        return ""
    monkeypatch.setattr("scripts.build_macos.command", command)
    with pytest.raises(RuntimeError):
        verify_bundle(app)
