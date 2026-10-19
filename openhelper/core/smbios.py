from __future__ import annotations

import copy
import re
import secrets
import uuid

from openhelper.core.process import run_tool
from openhelper.errors import AppError


def generate_identity(executable: str, model: str) -> dict:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]+\d+,\d+", model):
        raise AppError("invalid_smbios_model")
    result = run_tool(executable, ["-m", model, "-n", "1"])
    if result.returncode:
        raise AppError("tool_failed", detail=result.stderr or result.stdout)
    pair = next((line.strip().split("|") for line in result.stdout.splitlines() if "|" in line), None)
    if not pair or len(pair) != 2:
        raise AppError("invalid_macserial_output")
    serial, mlb = (part.strip() for part in pair)
    if not re.fullmatch(r"[A-Za-z0-9]{10,12}", serial) or not re.fullmatch(r"[A-Za-z0-9]{17}", mlb):
        raise AppError("invalid_macserial_output")
    rom = bytearray(secrets.token_bytes(6))
    rom[0] = (rom[0] | 2) & 0xFE
    return {"SystemProductName": model, "SystemSerialNumber": serial, "MLB": mlb,
            "SystemUUID": str(uuid.uuid4()).upper(), "ROM": bytes(rom)}


def apply_identity(data: dict, values: dict) -> dict:
    try:
        uuid.UUID(values["SystemUUID"])
        if len(values["ROM"]) != 6 or not isinstance(values["ROM"], bytes):
            raise ValueError("ROM")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]+\d+,\d+", values["SystemProductName"]):
            raise ValueError("SystemProductName")
        if not re.fullmatch(r"[A-Za-z0-9]{10,12}", values["SystemSerialNumber"]):
            raise ValueError("SystemSerialNumber")
        if not re.fullmatch(r"[A-Za-z0-9]{17}", values["MLB"]):
            raise ValueError("MLB")
        result = copy.deepcopy(data)
        platform = result.setdefault("PlatformInfo", {})
        if not isinstance(platform, dict) or not isinstance(platform.setdefault("Generic", {}), dict):
            raise ValueError("PlatformInfo/Generic")
        platform["Generic"].update(values)
        return result
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise AppError("invalid_smbios", detail=str(error)) from error

