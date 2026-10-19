import hashlib
import io
import json
import subprocess
import uuid
from pathlib import Path
from threading import Event

import pytest

from openhelper.core import downloads, recovery, smbios
from openhelper.core.downloads import Asset, download_asset
from openhelper.core.hardware import compatibility_findings
from openhelper.core.process import convert_recovery
from openhelper.core.reports import export_report, make_report
from openhelper.errors import AppError
from openhelper.i18n import Translator, resolve_language
from openhelper.storage import Settings


@pytest.mark.parametrize("override,candidates,result", [
    ("auto", ["pt_BR", "en"], "pt-BR"), ("auto", ["fr-FR", "en-US"], "en"),
    ("auto", ["pt-PT"], "pt-BR"), ("en", ["pt-BR"], "en"), ("auto", ["ja-JP"], "en"),
])
def test_windows_language_priority(override, candidates, result):
    assert resolve_language(override, candidates) == result


def test_translation_keys_and_interpolation_are_complete():
    import ast
    import string

    root = Path(__file__).resolve().parent.parent
    en = json.loads((root / "locales/en.json").read_text(encoding="utf-8"))
    pt = json.loads((root / "locales/pt-BR.json").read_text(encoding="utf-8"))
    assert en.keys() == pt.keys()
    def fields(text):
        return {field for _, field, _, _ in string.Formatter().parse(text) if field}
    for key in en:
        assert fields(en[key]) == fields(pt[key]), key
    literal_keys = set()
    for path in (root / "openhelper").rglob("*.py"):
        if "vendor" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            index = 0
            if isinstance(node.func, ast.Attribute) and node.func.attr == "t":
                pass
            elif isinstance(node.func, ast.Name) and node.func.id in ("AppError", "Issue"):
                index = 1 if node.func.id == "Issue" else 0
            else:
                continue
            if len(node.args) > index and isinstance(node.args[index], ast.Constant):
                literal_keys.add(node.args[index].value)
    assert not literal_keys - en.keys()
    assert "test" in Translator("en")("duplicate_key", key="test")


def test_settings_persist_and_recover_corrupt_json(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings(path)
    settings.save(language="pt-BR", ocat_path="C:/Tools/OCAT.exe")
    assert Settings(path).get("ocat_path") == "C:/Tools/OCAT.exe"
    path.write_text("{broken", encoding="utf-8")
    restored = Settings(path)
    assert restored.get("language") == "auto"
    assert list(tmp_path.glob("settings.corrupt-*.json"))


class Response(io.BytesIO):
    url = "https://release-assets.githubusercontent.com/official.zip"


def test_verified_download_and_failed_digest_cleanup(tmp_path, monkeypatch):
    content = b"release asset"
    digest = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(downloads.urllib.request, "urlopen", lambda *a, **k: Response(content))
    asset = Asset("OpenCore.zip", "https://github.com/acidanthera/OpenCorePkg/releases/download/1.0/OpenCore.zip",
                  len(content), "sha256:" + digest)
    path, computed, verified = download_asset(asset, tmp_path / "ok.zip")
    assert path.read_bytes() == content and computed == digest and verified
    bad = Asset(asset.name, asset.url, len(content), "sha256:" + "0" * 64)
    with pytest.raises(AppError, match="checksum_mismatch"):
        download_asset(bad, tmp_path / "bad.zip")
    assert not (tmp_path / "bad.zip").exists()
    assert not list(tmp_path.glob("*.part"))


def test_download_without_published_digest_does_not_claim_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(downloads.urllib.request, "urlopen", lambda *a, **k: Response(b"data"))
    asset = Asset("file.zip", "https://github.com/ic005k/OCAuxiliaryTools/releases/download/tag/file.zip", 4, None)
    assert download_asset(asset, tmp_path / "file.zip")[2] is False
    with pytest.raises(AppError, match="untrusted_download"):
        download_asset(Asset("bad.zip", "https://example.com/bad.zip", 0, None), tmp_path / "bad.zip")


def test_recovery_parameters_are_validated_before_starting_a_child(tmp_path):
    with pytest.raises(AppError, match="invalid_recovery_parameters"):
        recovery.download_recovery("invalid", "0" * 17, "latest", tmp_path / "new", Event())
    assert not (tmp_path / "new").exists()


def test_conversion_failure_discards_partial_output(tmp_path, monkeypatch):
    source, target = tmp_path / "image.dmg", tmp_path / "image.vmdk"
    source.write_bytes(b"dmg")
    def failing_tool(*args, **kwargs):
        target.write_bytes(b"partial")
        return subprocess.CompletedProcess([], 1, "", "conversion failed")
    monkeypatch.setattr("openhelper.core.process.run_tool", failing_tool)
    with pytest.raises(AppError, match="tool_failed"):
        convert_recovery("qemu-img.exe", source, target)
    assert not target.exists()
    assert source.read_bytes() == b"dmg"


def test_ohv_reports_uncertainty_and_html_report_escapes_data(tmp_path):
    hardware = {"system": {"architecture": "AMD64"}, "cpu": [{"Name": "AMD Ryzen"}],
                "gpu": [{"Name": "NVIDIA <script>alert(1)</script>"}], "memory": [{"Capacity": str(4 * 1024**3)}]}
    findings = compatibility_findings(hardware)
    assert {issue.code for issue in findings} >= {"ohv_scope", "ohv_amd", "ohv_nvidia", "ohv_memory"}
    report = make_report(hardware=hardware, findings=findings, translate=Translator("en"))
    assert "score" not in json.dumps(report).lower()
    file = tmp_path / "report.html"
    export_report(report, file)
    assert "<script>" not in file.read_text(encoding="utf-8")
    assert "&lt;script&gt;" in file.read_text(encoding="utf-8")


def test_macserial_values_are_generated_and_require_explicit_application(monkeypatch):
    monkeypatch.setattr(smbios, "run_tool", lambda *a, **k: subprocess.CompletedProcess(
        [], 0, "C02ABCDEFGH1 | C0200000000000000\n", ""))
    identity = smbios.generate_identity("macserial.exe", "iMac19,1")
    uuid.UUID(identity["SystemUUID"])
    assert len(identity["ROM"]) == 6
    data = {"PlatformInfo": {"Generic": {"SpoofVendor": True}}, "Unknown": True}
    result = smbios.apply_identity(data, identity)
    assert result["PlatformInfo"]["Generic"]["SpoofVendor"] is True
    assert result["Unknown"] is True
    assert "SystemSerialNumber" not in data["PlatformInfo"]["Generic"]


def test_bad_smbios_is_rejected():
    with pytest.raises(AppError):
        smbios.apply_identity({}, {"SystemUUID": "bad"})


def test_vendored_macrecovery_matches_pinned_upstream():
    root = Path(__file__).resolve().parent.parent / "openhelper/vendor/macrecovery"
    origin = json.loads((root / "ORIGIN.json").read_text(encoding="utf-8"))
    assert hashlib.sha256((root / "upstream.py").read_bytes()).hexdigest() == origin["sha256"]


def test_release_versions_match():
    import tomllib

    from openhelper import __version__

    root = Path(__file__).resolve().parent.parent
    assert (root / "VERSION").read_text().strip() == __version__
    assert tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"] == __version__
