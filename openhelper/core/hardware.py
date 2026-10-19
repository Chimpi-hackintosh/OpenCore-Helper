from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone

from openhelper.core.validation import Issue
from openhelper.errors import AppError

# Fixed commands only; no user input is interpolated into PowerShell.
HARDWARE_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$result = [ordered]@{}
$queries = [ordered]@{
  cpu = @{ Class='Win32_Processor'; Fields=@('Name','Manufacturer','NumberOfCores','NumberOfLogicalProcessors') }
  gpu = @{ Class='Win32_VideoController'; Fields=@('Name','PNPDeviceID','DriverVersion','AdapterRAM') }
  memory = @{ Class='Win32_PhysicalMemory'; Fields=@('Capacity','Speed','Manufacturer') }
  motherboard = @{ Class='Win32_BaseBoard'; Fields=@('Manufacturer','Product') }
  bios = @{ Class='Win32_BIOS'; Fields=@('Manufacturer','SMBIOSBIOSVersion','ReleaseDate') }
  storage = @{ Class='Win32_DiskDrive'; Fields=@('Model','InterfaceType','Size') }
  network = @{ Class='Win32_NetworkAdapter'; Fields=@('Name','PNPDeviceID','PhysicalAdapter') }
  audio = @{ Class='Win32_SoundDevice'; Fields=@('Name','PNPDeviceID') }
}
$failures = @()
foreach ($key in $queries.Keys) {
  try {
    $query = $queries[$key]
    $result[$key] = @(Get-CimInstance -ClassName $query.Class | Select-Object -Property $query.Fields)
  } catch { $result[$key] = @(); $failures += $key }
}
$result['unavailable'] = $failures
$result | ConvertTo-Json -Depth 6 -Compress
"""


def scan_hardware() -> dict:
    if os.name != "nt":
        raise AppError("windows_scan_only")
    powershell = shutil.which("powershell.exe")
    if not powershell:
        raise AppError("tool_not_found", file="Windows PowerShell")
    import base64

    encoded = base64.b64encode(HARDWARE_SCRIPT.encode("utf-16-le")).decode("ascii")
    result = subprocess.run([powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                            capture_output=True, encoding="utf-8-sig", errors="replace", timeout=120,
                            creationflags=subprocess.CREATE_NO_WINDOW, check=False)
    if result.returncode:
        raise AppError("tool_failed", detail=result.stderr)
    try:
        hardware = json.loads(result.stdout)
    except ValueError as error:
        raise AppError("tool_failed", detail=result.stdout[:500]) from error
    hardware["system"] = {"os": platform.platform(), "architecture": platform.machine()}
    hardware["scanned_utc"] = datetime.now(timezone.utc).isoformat()
    return hardware


def compatibility_findings(hardware: dict) -> list[Issue]:
    """Conservative OHV preflight, never a fabricated percentage or compatibility promise."""
    findings = [Issue("info", "ohv_scope")]
    architecture = hardware.get("system", {}).get("architecture", "").lower()
    if architecture not in ("amd64", "x86_64"):
        findings.append(Issue("error", "ohv_architecture", "system/architecture"))
    cpu_text = " ".join(item.get("Name", "") for item in hardware.get("cpu", []))
    if "amd" in cpu_text.lower() or "ryzen" in cpu_text.lower():
        findings.append(Issue("warning", "ohv_amd", "cpu"))
    if "intel" in cpu_text.lower():
        findings.append(Issue("info", "ohv_intel", "cpu"))
    for gpu in hardware.get("gpu", []):
        name = gpu.get("Name", "")
        if "nvidia" in name.lower():
            findings.append(Issue("warning", "ohv_nvidia", "gpu", {"file": name}))
        else:
            findings.append(Issue("info", "ohv_device_pending", "gpu", {"file": name}))
    memory_bytes = sum(int(item.get("Capacity") or 0) for item in hardware.get("memory", []))
    if 0 < memory_bytes < 8 * 1024**3:
        findings.append(Issue("warning", "ohv_memory", "memory"))
    for group in ("network", "audio", "storage"):
        findings.append(Issue("info", "ohv_group_pending", group))
    for group in hardware.get("unavailable", []):
        findings.append(Issue("warning", "ohv_query_unavailable", group))
    return findings

