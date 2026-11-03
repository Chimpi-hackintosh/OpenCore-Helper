"""Read-only macOS inventory with the same field names used by the OHV report.

Only named device fields are retained; system_profiler serial numbers, UUIDs,
user names, IP addresses and other personal fields are not exported.
"""
from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone

from openhelper.errors import AppError


def normalize_inventory(profile: dict, cpu_name: str, memory_bytes: int) -> dict:
    hardware = next(iter(profile.get("SPHardwareDataType", [])), {})
    groups = {
        "gpu": ("SPDisplaysDataType", "sppci_model", "Name"),
        "storage": ("SPStorageDataType", "_name", "Model"),
        "network": ("SPNetworkDataType", "_name", "Name"),
        "audio": ("SPAudioDataType", "_name", "Name"),
    }
    inventory = {
        "cpu": [{"Name": cpu_name or hardware.get("cpu_type", ""),
                 "NumberOfCores": hardware.get("number_processors", "")}],
        "memory": [{"Capacity": memory_bytes}] if memory_bytes > 0 else [],
        "motherboard": [{"Manufacturer": "Apple", "Product": hardware.get("machine_model", "")}],
        "bios": [{"SMBIOSBIOSVersion": hardware.get("boot_rom_version", "")}],
        "unavailable": [],
    }
    for group, (source, field, target) in groups.items():
        inventory[group] = [{target: item.get(field) or item.get("_name", "")}
                            for item in profile.get(source, [])]
        if not inventory[group]:
            inventory["unavailable"].append(group)
    if not inventory["memory"]:
        inventory["unavailable"].append("memory")
    if not hardware:
        inventory["unavailable"].extend(["motherboard", "bios"])
    return inventory


def _sysctl(name: str) -> str:
    result = subprocess.run(["/usr/sbin/sysctl", "-n", name], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=10, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def scan_macos_hardware() -> dict:
    result = subprocess.run([
        "/usr/sbin/system_profiler", "-json", "-detailLevel", "mini",
        "SPHardwareDataType", "SPDisplaysDataType", "SPStorageDataType",
        "SPNetworkDataType", "SPAudioDataType",
    ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, check=False)
    if result.returncode:
        raise AppError("tool_failed", detail=result.stderr[:1000])
    try:
        profile = json.loads(result.stdout)
        if not isinstance(profile, dict):
            raise ValueError("Expected a system_profiler object")
    except ValueError as error:
        raise AppError("tool_failed", detail="Invalid system_profiler JSON") from error
    memory = _sysctl("hw.memsize")
    inventory = normalize_inventory(profile, _sysctl("machdep.cpu.brand_string"),
                                    int(memory) if memory.isdigit() else 0)
    inventory["system"] = {"os": platform.platform(), "architecture": platform.machine()}
    inventory["scanned_utc"] = datetime.now(timezone.utc).isoformat()
    return inventory
