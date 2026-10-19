import plistlib
from datetime import datetime
from pathlib import Path

import pytest

from openhelper.core.plist_document import PlistDocument, display_value, parse_value
from openhelper.errors import AppError


@pytest.mark.parametrize("kind,text,expected", [
    ("String", "  -v  ", "  -v  "), ("Boolean", "true", True), ("Boolean", "false", False),
    ("Integer", "08", 8), ("Integer", "0xFF", 255), ("Integer", "-0x10", -16),
    ("Real", "2.5", 2.5), ("Data", "<01 AB 00>", b"\x01\xab\0"),
    ("Data", "", b""), ("Date", "2026-10-19T10:00:00+02:00", datetime(2026, 10, 19, 8)),
    ("Dictionary", "", {}), ("Array", "", []),
])
def test_typed_values(kind, text, expected):
    assert parse_value(kind, text) == expected


@pytest.mark.parametrize("kind,text", [("Boolean", "yes"), ("Integer", "1.5"), ("Data", "0"),
                                        ("Date", "tomorrow"), ("Real", "NaN"), ("Real", "Infinity")])
def test_invalid_typed_values(kind, text):
    with pytest.raises(AppError):
        parse_value(kind, text)


@pytest.mark.parametrize("fmt", [plistlib.FMT_XML, plistlib.FMT_BINARY])
def test_save_preserves_types_unknown_keys_and_creates_backup(tmp_path, fmt):
    path = tmp_path / "config.plist"
    original = plistlib.dumps({"FutureSection": {"bytes": b"\0\1", "flag": True, "integer": 4,
                                                "date": datetime(2026, 1, 2)}, "NVRAM": {"boot-args": "-v"}}, fmt=fmt)
    path.write_bytes(original)
    doc = PlistDocument()
    doc.load(path)
    doc.set(("NVRAM", "boot-args"), "-v keepsyms=1")
    backup = doc.save()
    assert backup.read_bytes() == original
    assert doc.dirty is False
    assert path.read_bytes().startswith(b"bplist") == (fmt == plistlib.FMT_BINARY)
    assert plistlib.loads(path.read_bytes())["FutureSection"] == plistlib.loads(original)["FutureSection"]


def test_external_edits_are_not_overwritten(tmp_path):
    path = tmp_path / "config.plist"
    path.write_bytes(plistlib.dumps({"Key": "before"}))
    doc = PlistDocument()
    doc.load(path)
    doc.set(("Key",), "mine")
    path.write_bytes(plistlib.dumps({"Key": "external"}))
    with pytest.raises(AppError, match="external_change"):
        doc.save()
    assert plistlib.loads(path.read_bytes())["Key"] == "external"


def test_add_rename_move_delete_and_history():
    doc = PlistDocument()
    doc.add((), "Kernel", {"Add": ["Lilu", "WhateverGreen"]})
    doc.rename(("Kernel",), "K")
    doc.move(("K", "Add", 1), -1)
    assert doc.get(("K", "Add")) == ["WhateverGreen", "Lilu"]
    doc.delete(("K", "Add", 0))
    doc.undo()
    assert len(doc.get(("K", "Add"))) == 2
    doc.redo()
    assert doc.get(("K", "Add")) == ["Lilu"]
    with pytest.raises(AppError, match="duplicate_key"):
        doc.add((), "K", {})
    with pytest.raises(AppError, match="root_edit"):
        doc.delete(())


def test_failed_load_preserves_current_document(tmp_path):
    doc = PlistDocument()
    doc.data = {"keep": True}
    path = tmp_path / "broken.plist"
    path.write_text("broken")
    with pytest.raises(AppError):
        doc.load(path)
    assert doc.data == {"keep": True}


def test_save_as_requires_a_target_and_handles_existing_file(tmp_path):
    doc = PlistDocument()
    with pytest.raises(AppError, match="no_config"):
        doc.save()
    path = tmp_path / "copy.plist"
    path.write_bytes(plistlib.dumps({"previous": True}))
    backup = doc.save(path)
    assert plistlib.loads(backup.read_bytes()) == {"previous": True}
    assert display_value(parse_value("Data", "00ff")) == "00FF"
    assert isinstance(doc.path, Path)

