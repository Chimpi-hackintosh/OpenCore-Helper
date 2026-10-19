"""Exercise real widgets on Windows (or a development X display); no network or hardware mutation."""
from __future__ import annotations

import argparse
import plistlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openhelper.storage import Settings  # noqa: E402
from openhelper.ui.app import Application  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    for language in ("en", "pt-BR"):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            settings = Settings(directory / "settings.json")
            settings.save(language=language, appearance="Dark")
            app = Application(settings)
            # Make GUI failures fail CI instead of waiting for a modal error dialog.
            errors = []
            app.present_error = lambda error: errors.append(error)
            fixture = directory / "config.plist"
            fixture.write_bytes(plistlib.dumps({"ACPI": {"Add": []}, "NVRAM": {"Add": {"test": {
                "boot-args": "-v", "csr-active-config": bytes.fromhex("00000000")}}},
                "Kernel": {"Add": []}, "PlatformInfo": {"Generic": {"SystemProductName": "Test"}}}))
            app.editor.open(fixture)
            app.update()
            assert app.winfo_rootx() + app.winfo_width() <= app.winfo_screenwidth()
            assert app.winfo_rooty() + app.winfo_height() <= app.winfo_screenheight()
            for page in app.pages:
                app.show_page(page)
                app.update()
                if args.screenshots:
                    from PIL import ImageGrab

                    args.screenshots.mkdir(parents=True, exist_ok=True)
                    # xdisplay avoids platform-specific screenshot helpers on Linux.
                    import os
                    options = {"xdisplay": os.environ["DISPLAY"]} if os.name != "nt" else {}
                    x, y = app.winfo_rootx(), app.winfo_rooty()
                    image = ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height()), **options)
                    image.save(args.screenshots / f"{language}-{page}.png")
            app.show_page("editor")
            editor = app.editor
            editor.selected = ("NVRAM", "Add", "test", "boot-args")
            editor.refresh()
            app.update()
            editor.value.delete("1.0", "end")
            editor.value.insert("1.0", "-v keepsyms=1")
            editor.apply()
            assert editor.doc.get(editor.selected) == "-v keepsyms=1"
            editor.undo()
            assert editor.doc.data["NVRAM"]["Add"]["test"]["boot-args"] == "-v"
            editor.redo()
            editor.save()
            assert plistlib.loads(fixture.read_bytes())["NVRAM"]["Add"]["test"]["boot-args"] == "-v keepsyms=1"
            for appearance in ("Light", "Dark"):
                import customtkinter as ctk

                ctk.set_appearance_mode(appearance)
                app.style_tree()
                app.update()
            assert not errors, errors
            assert not app.callback_errors, app.callback_errors
            app.executor.shutdown(wait=True)
            app.destroy()
    print("GUI verified: both languages, all 8 pages, typed edit, undo/redo, save and both themes")


if __name__ == "__main__":
    main()
