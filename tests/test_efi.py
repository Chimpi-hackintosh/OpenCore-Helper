import json
import plistlib
import stat
import zipfile

import pytest

from openhelper.core.efi import backup_efi, extract_zip, inspect_efi, prepare_workspace
from openhelper.core.validation import contained_path, snapshot_additions, validate_config
from openhelper.errors import AppError


def test_backup_restore_roundtrip_and_tamper_detection(tmp_path):
    source = tmp_path / "EFI"
    (source / "OC").mkdir(parents=True)
    (source / "OC/config.plist").write_bytes(plistlib.dumps({"ACPI": {"Add": []}}))
    (source / "OC/OpenCore.efi").write_bytes(b"bootloader")
    archive = backup_efi(source, tmp_path / "backup.zip")
    restored = extract_zip(archive, tmp_path / "restored", verify_backup=True)
    assert (restored / "EFI/OC/OpenCore.efi").read_bytes() == b"bootloader"
    damaged = tmp_path / "damaged.zip"
    with zipfile.ZipFile(archive) as old, zipfile.ZipFile(damaged, "w") as new:
        for name in old.namelist():
            new.writestr(name, b"modified" if name.endswith("OpenCore.efi") else old.read(name))
    with pytest.raises(AppError, match="checksum_mismatch"):
        extract_zip(damaged, tmp_path / "failed", verify_backup=True)
    assert not (tmp_path / "failed").exists()


def test_backup_rejects_unsafe_destinations(tmp_path):
    source = tmp_path / "EFI"
    source.mkdir()
    with pytest.raises(AppError, match="backup_inside_source"):
        backup_efi(source, source / "recursive.zip")
    destination = tmp_path / "existing.zip"
    destination.write_bytes(b"keep")
    with pytest.raises(AppError, match="destination_exists"):
        backup_efi(source, destination)
    assert destination.read_bytes() == b"keep"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "EFI/../../escape", "EFI/file:stream",
                                  "EFI/CON.txt", "EFI/trailing. ", "\\\\server\\share\\file"])
def test_archive_paths_cannot_escape_or_alias_windows_files(tmp_path, name):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr(name, "payload")
    with pytest.raises(AppError, match="unsafe_archive"):
        extract_zip(archive, tmp_path / "destination")
    assert not (tmp_path / "destination").exists()


def test_archive_symlinks_and_case_collisions_are_rejected(tmp_path):
    archive = tmp_path / "unsafe.zip"
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr(info, "../../target")
    with pytest.raises(AppError, match="unsafe_archive"):
        extract_zip(archive, tmp_path / "symlink")
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("EFI/CONFIG.plist", "first")
        stream.writestr("EFI/config.plist", "second")
    with pytest.raises(AppError, match="unsafe_archive"):
        extract_zip(archive, tmp_path / "collision")


def test_manifest_must_cover_every_restored_file(tmp_path):
    archive = tmp_path / "extra.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("__och_manifest__.json", json.dumps({"files": {}}))
        stream.writestr("extra", "payload")
    with pytest.raises(AppError, match="checksum_mismatch"):
        extract_zip(archive, tmp_path / "restored", verify_backup=True)


def test_prepare_workspace_keeps_original_package_and_does_not_overwrite(tmp_path):
    package = tmp_path / "OpenCore.zip"
    with zipfile.ZipFile(package, "w") as stream:
        stream.writestr("X64/EFI/OC/OpenCore.efi", "boot")
        stream.writestr("X64/EFI/BOOT/BOOTx64.efi", "boot")
        stream.writestr("Docs/Sample.plist", plistlib.dumps({"future": {"key": True}}))
    destination = prepare_workspace(package, tmp_path / "workspace")
    assert plistlib.loads((destination / "EFI/OC/config.plist").read_bytes()) == {"future": {"key": True}}
    assert package.exists()
    with pytest.raises(AppError, match="destination_exists"):
        prepare_workspace(package, destination)


def test_validation_checks_enabled_references_and_type_errors(tmp_path):
    data = {"ACPI": {"Add": [{"Path": "../bad.aml", "Enabled": True},
                              {"Path": "disabled.aml", "Enabled": False}, {"Path": "missing.aml", "Enabled": "yes"}]},
            "Kernel": {"Add": "bad"}, "UEFI": {"Drivers": [{"Path": "OpenRuntime.efi", "Enabled": True}]}}
    issues = validate_config(data, tmp_path)
    assert {issue.code for issue in issues} >= {"unsafe_path", "missing_file", "expected_boolean", "expected_array"}
    assert not any(issue.params.get("file") == "disabled.aml" for issue in issues)
    assert contained_path(tmp_path, "C:\\unsafe") is None


def test_snapshot_preserves_entries_and_orders_new_kext_dependencies(tmp_path):
    oc = tmp_path / "OC"
    (oc / "ACPI").mkdir(parents=True)
    (oc / "ACPI/SSDT.aml").write_bytes(b"table")
    for name, identifier, dependencies in (("APlugin.kext", "plugin", {"lilu": "1"}),
                                             ("Lilu.kext", "lilu", {})):
        contents = oc / "Kexts" / name / "Contents"
        contents.mkdir(parents=True)
        (contents / "Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": identifier,
                                                             "OSBundleLibraries": dependencies}))
    original = {"Kernel": {"Add": [{"BundlePath": "Existing.kext", "Enabled": False, "Comment": "preserve"}]}}
    result, counts = snapshot_additions(original, oc)
    assert counts == {"ACPI": 1, "Kernel": 2, "UEFI": 0}
    assert [item["BundlePath"] for item in result["Kernel"]["Add"]] == ["Existing.kext", "Lilu.kext", "APlugin.kext"]
    assert result["Kernel"]["Add"][0] == original["Kernel"]["Add"][0]
    again, repeated = snapshot_additions(result, oc)
    assert not any(repeated.values())
    assert again == result


def test_inspect_copied_efi_requires_boot_files(tmp_path):
    oc = tmp_path / "EFI/OC"
    oc.mkdir(parents=True)
    (oc / "config.plist").write_bytes(plistlib.dumps({}))
    issues = inspect_efi(tmp_path)
    assert len([issue for issue in issues if issue.code == "missing_file"]) == 2

