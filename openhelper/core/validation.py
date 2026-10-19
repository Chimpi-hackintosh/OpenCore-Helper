from __future__ import annotations

import plistlib
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath

SECTIONS = ("ACPI", "Booter", "DeviceProperties", "Kernel", "Misc", "NVRAM", "PlatformInfo", "UEFI")


@dataclass
class Issue:
    severity: str
    code: str
    path: str = ""
    params: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def contained_path(root: Path, relative: str) -> Path | None:
    normalized = relative.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if not normalized or pure.is_absolute() or ":" in normalized or ".." in pure.parts:
        return None
    target = root.joinpath(*pure.parts).resolve()
    return target if target.is_relative_to(root.resolve()) else None


def validate_config(data: dict, oc_directory: Path | None = None) -> list[Issue]:
    issues: list[Issue] = []
    for section in SECTIONS:
        if section not in data:
            issues.append(Issue("warning", "missing_section", section))
        elif not isinstance(data[section], dict):
            issues.append(Issue("error", "expected_dictionary", section))
    for section, collection, folder, field_name in (
        ("ACPI", "Add", "ACPI", "Path"), ("Kernel", "Add", "Kexts", "BundlePath"),
        ("UEFI", "Drivers", "Drivers", "Path"), ("Misc", "Tools", "Tools", "Path"),
    ):
        block = data.get(section, {})
        if not isinstance(block, dict):
            continue
        entries = block.get(collection, [])
        label = f"{section}/{collection}"
        if not isinstance(entries, list):
            issues.append(Issue("error", "expected_array", label))
            continue
        seen = set()
        for index, entry in enumerate(entries):
            node = f"{label}/{index}"
            if not isinstance(entry, dict):
                issues.append(Issue("error", "expected_dictionary", node))
                continue
            enabled = entry.get("Enabled", True)
            if not isinstance(enabled, bool):
                issues.append(Issue("error", "expected_boolean", f"{node}/Enabled"))
            reference = entry.get(field_name)
            if not isinstance(reference, str) or not reference:
                issues.append(Issue("error", "missing_path", f"{node}/{field_name}"))
                continue
            folded = reference.replace("\\", "/").casefold()
            if folded in seen:
                issues.append(Issue("warning", "duplicate_entry", node, {"file": reference}))
            seen.add(folded)
            if not enabled or oc_directory is None:
                continue
            target = contained_path(oc_directory / folder, reference)
            if target is None:
                issues.append(Issue("error", "unsafe_path", node, {"file": reference}))
            elif not target.exists():
                issues.append(Issue("error", "missing_file", node, {"file": reference}))
            elif section == "Kernel":
                for member in ("PlistPath", "ExecutablePath"):
                    suffix = entry.get(member, "")
                    if not isinstance(suffix, str):
                        issues.append(Issue("error", "expected_string", f"{node}/{member}"))
                    elif suffix:
                        child = contained_path(target, suffix)
                        if child is None or not child.is_file():
                            issues.append(Issue("error", "missing_file", f"{node}/{member}", {"file": suffix}))
    platform = data.get("PlatformInfo", {})
    generic = platform.get("Generic", {}) if isinstance(platform, dict) else {}
    if isinstance(generic, dict):
        for key in ("SystemProductName", "SystemSerialNumber", "MLB", "SystemUUID"):
            value = generic.get(key)
            if not isinstance(value, str) or not value or value.lower() in ("string", "default"):
                issues.append(Issue("warning", "identity_unconfigured", f"PlatformInfo/Generic/{key}"))
    # Structural checks intentionally do not claim schema/boot compatibility.
    issues.append(Issue("info", "validation_scope"))
    return issues


def snapshot_additions(data: dict, oc_directory: Path) -> tuple[dict, dict[str, int]]:
    """Append discovered files without deleting or rewriting existing configuration."""
    import copy

    result = copy.deepcopy(data)
    counts = {"ACPI": 0, "Kernel": 0, "UEFI": 0}
    for section, collection, folder, glob, key in (
        ("ACPI", "Add", "ACPI", "*.aml", "Path"),
        ("UEFI", "Drivers", "Drivers", "*.efi", "Path"),
    ):
        block = result.setdefault(section, {})
        if not isinstance(block, dict) or not isinstance(block.setdefault(collection, []), list):
            raise ValueError(f"{section}/{collection}")
        existing = block[collection]
        names = {str(item.get(key, "")).casefold() for item in existing if isinstance(item, dict)}
        for file in sorted((oc_directory / folder).rglob(glob)):
            if file.is_symlink() or not file.is_file():
                continue
            name = file.relative_to(oc_directory / folder).as_posix()
            if contained_path(oc_directory / folder, name) is None:
                continue
            if name.casefold() not in names:
                entry = {"Comment": "", "Enabled": True, "Path": name}
                if section == "UEFI":
                    entry.update(Arguments="", LoadEarly=False)
                existing.append(entry)
                names.add(name.casefold())
                counts[section] += 1
    block = result.setdefault("Kernel", {})
    if not isinstance(block, dict) or not isinstance(block.setdefault("Add", []), list):
        raise ValueError("Kernel/Add")
    entries = block["Add"]
    known = {str(item.get("BundlePath", "")).casefold() for item in entries if isinstance(item, dict)}
    candidates = {}
    for info in sorted((oc_directory / "Kexts").rglob("*.kext/Contents/Info.plist")):
        bundle = info.parent.parent
        relative = bundle.relative_to(oc_directory / "Kexts").as_posix()
        if relative.casefold() in known or contained_path(oc_directory / "Kexts", relative) is None:
            continue
        metadata = plistlib.loads(info.read_bytes())
        executable = metadata.get("CFBundleExecutable", "")
        candidates[relative] = (metadata, {
            "Arch": "Any", "BundlePath": relative, "Comment": "", "Enabled": True,
            "ExecutablePath": f"Contents/MacOS/{executable}" if executable else "",
            "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist",
        })
    # Topologically order new bundles. Existing order is left for the user to review.
    providers = {meta.get("CFBundleIdentifier"): name for name, (meta, _) in candidates.items()}
    visited, visiting = set(), set()

    def append_bundle(name):
        if name in visited:
            return
        if name in visiting:
            raise ValueError("cyclic OSBundleLibraries")
        visiting.add(name)
        meta, entry = candidates[name]
        for dependency in meta.get("OSBundleLibraries", {}):
            provider = providers.get(dependency)
            if provider and provider != name:
                append_bundle(provider)
        visiting.remove(name)
        visited.add(name)
        entries.append(entry)
        counts["Kernel"] += 1

    for candidate in candidates:
        append_bundle(candidate)
    return result, counts

