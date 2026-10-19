from __future__ import annotations

import argparse
import logging
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="OpenCore Helper 3.0.1")
    parser.add_argument("config", nargs="?")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--smoke-test", action="store_true", help="Open all views and exit for GUI verification")
    parser.add_argument("--recovery-worker", nargs=5, metavar=("BOARD", "MLB", "VARIANT", "DEST", "LOG"),
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.version:
        if sys.stdout:
            from openhelper import __version__

            print(__version__)
        return 0
    if args.recovery_worker:
        from openhelper.core.recovery import recovery_worker

        return recovery_worker(*args.recovery_worker)
    from openhelper.i18n import Translator
    from openhelper.paths import data_root
    from openhelper.storage import Settings

    settings = Settings()
    translate = Translator(settings.get("language"))
    if os.name != "nt" and os.environ.get("OCH_DEV_ALLOW_NON_WINDOWS") != "1":
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("OpenCore Helper", translate("wrong_platform"), parent=root)
        root.destroy()
        return 1
    from logging.handlers import RotatingFileHandler

    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(
        data_root() / "application.log", maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8")])
    from openhelper.ui.app import Application

    app = Application(settings=settings)
    if args.config:
        app.after(150, lambda: app.editor.open(args.config))
    if args.smoke_test:
        def fail_smoke(error):
            app.callback_errors.append(str(error))
            app.after(0, app.destroy)
        app.present_error = fail_smoke
        def verify_views():
            for key in app.pages:
                app.show_page(key)
                app.update_idletasks()
            app.show_page("home")
            app.after(250, app.destroy)
        app.after(250, verify_views)
    app.mainloop()
    return 1 if args.smoke_test and app.callback_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

