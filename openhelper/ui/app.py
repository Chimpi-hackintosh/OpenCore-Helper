from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import sys
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from openhelper import __version__
from openhelper.core.downloads import REPOSITORIES, download_asset, latest_release
from openhelper.core.efi import backup_efi, extract_zip, inspect_efi, prepare_workspace, sha256_file
from openhelper.core.hardware import compatibility_findings, scan_hardware
from openhelper.core.process import convert_recovery, launch_ocat
from openhelper.core.recovery import download_recovery
from openhelper.core.reports import export_report, make_report
from openhelper.errors import AppError
from openhelper.i18n import Translator
from openhelper.paths import data_root
from openhelper.storage import Settings
from openhelper.ui.editor import PlistEditor


class Application(ctk.CTk):
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.t = Translator(self.settings.get("language"))
        ctk.set_appearance_mode(self.settings.get("appearance"))
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.title(f"OpenCore Helper {__version__}")
        scale = self._get_window_scaling()
        screen_width, screen_height = self.winfo_screenwidth(), self.winfo_screenheight()
        width = min(1280, int((screen_width - 32) / scale))
        height = min(800, int((screen_height - 100) / scale))
        x = max(0, (screen_width - round(width * scale)) // 2)
        self.geometry(f"{width}x{height}+{x}+24")
        self.minsize(min(980, width), min(620, height))
        self.configure(fg_color=("#f2f5fa", "#0d1524"))
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.pages = {}
        self.nav = {}
        self.wrap_labels = []
        self.wrap_width = max(480, width - 280)
        self.hardware = None
        self.findings = []
        self.efi_issues = []
        self.release = None
        self.busy = False
        self.cancelled = threading.Event()
        self.messages = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="OpenCoreHelper")
        self.callback_errors = []
        self._build_sidebar()
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=26, pady=22)
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self.main_area, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        self.heading = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=27, weight="bold"), anchor="w")
        self.heading.pack(side="left")
        ctk.CTkLabel(header, text=f"  v{__version__}  ", corner_radius=8,
                     fg_color=("#dbeafe", "#1a3152"), text_color=("#1e40af", "#93c5fd")).pack(side="right")
        self.content = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self._build_home()
        self._build_efi()
        self._build_hardware()
        self._build_downloads()
        self._build_recovery()
        self._build_reports()
        self._build_settings()
        self.editor = PlistEditor(self.content, self)
        self.pages["editor"] = self.editor
        footer = ctk.CTkFrame(self.main_area, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        footer.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(footer, text=self.t("ready"), anchor="w", wraplength=770)
        self.status.grid(row=0, column=0, sticky="ew")
        self.cancel_button = ctk.CTkButton(footer, text=self.t("cancel"), width=100,
                                          command=self.cancelled.set, state="disabled")
        self.cancel_button.grid(row=0, column=1, padx=(8, 0))
        self.progress = ctk.CTkProgressBar(footer, height=4)
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.progress.set(0)
        self.style_tree()
        self.show_page("home")
        self.protocol("WM_DELETE_WINDOW", self.close)
        modifier = "Command" if sys.platform == "darwin" else "Control"
        self.bind(f"<{modifier}-o>", lambda _: self.editor.open())
        self.bind(f"<{modifier}-s>", lambda _: self.editor.save())
        self.bind("<Configure>", self.resize_notes, add="+")
        self.after(100, self.poll_messages)

    def _build_sidebar(self):
        side = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=("#e5ecf6", "#131e30"))
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="OC", font=ctk.CTkFont(size=39, weight="bold"),
                     text_color=("#1d4ed8", "#60a5fa")).pack(pady=(30, 0))
        ctk.CTkLabel(side, text="OpenCore Helper", font=ctk.CTkFont(size=17, weight="bold")).pack(pady=(0, 4))
        ctk.CTkLabel(side, text=self.t("workspace_label"), text_color=("#53647b", "#99abc5")).pack(pady=(0, 28))
        for key in ("home", "editor", "efi", "hardware", "downloads", "recovery", "reports", "settings"):
            button = ctk.CTkButton(side, text=self.t(f"nav_{key}"), anchor="w", width=174, height=40,
                                   fg_color="transparent", text_color=("#223956", "#c9d8ef"),
                                   hover_color=("#d4e1f2", "#203450"),
                                   command=lambda page=key: self.show_page(page))
            button.pack(padx=12, pady=3)
            self.nav[key] = button
        ctk.CTkLabel(side, text=self.t("independent_app"), justify="left", wraplength=165,
                     text_color=("#53647b", "#8fa3c2"), font=ctk.CTkFont(size=11)).pack(
                         side="bottom", padx=16, pady=24)

    def page(self, name, *, scroll=False):
        frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent") if scroll else ctk.CTkFrame(
            self.content, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        self.pages[name] = frame
        return frame

    def note(self, parent, key, row, **params):
        label = ctk.CTkLabel(parent, text=self.t(key, **params), wraplength=self.wrap_width, anchor="w", justify="left",
                              text_color=("#52637b", "#b2c2da"))
        label.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        self.wrap_labels.append((label, 0))
        return label

    def button_row(self, parent, row, actions):
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        for key, callback in actions:
            ctk.CTkButton(bar, text=self.t(key), command=callback, width=165).pack(side="left", padx=(0, 10))
        return bar

    def output(self, parent, row):
        parent.grid_rowconfigure(row, weight=1)
        box = ctk.CTkTextbox(parent, font=ctk.CTkFont(
            family="Menlo" if sys.platform == "darwin" else "Consolas", size=13), wrap="word")
        box.grid(row=row, column=0, sticky="nsew")
        box.configure(state="disabled")
        return box

    @staticmethod
    def write(box, text):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def _build_home(self):
        frame = self.page("home", scroll=True)
        hero = ctk.CTkFrame(frame, corner_radius=18, fg_color=("#dceafa", "#192e4a"))
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        for key, size, padding in (("hero_title", 30, (28, 12)), ("hero_body", 13, (0, 26))):
            label = ctk.CTkLabel(hero, text=self.t(key), font=ctk.CTkFont(size=size,
                                weight="bold" if key == "hero_title" else "normal"),
                                wraplength=min(760, self.wrap_width - 56), justify="left", anchor="w")
            label.pack(fill="x", padx=28, pady=padding)
            self.wrap_labels.append((label, 56))
        self.button_row(frame, 1, [("open_config", self.open_config), ("scan_hardware", self.scan),
                                    ("open_downloads", lambda: self.show_page("downloads"))])
        cards = ctk.CTkFrame(frame, fg_color="transparent")
        cards.grid(row=2, column=0, sticky="ew", pady=12)
        for index, key in enumerate(("editor", "efi", "hardware")):
            cards.grid_columnconfigure(index, weight=1, uniform="cards")
            card = ctk.CTkFrame(cards, corner_radius=14)
            card.grid(row=0, column=index, sticky="nsew", padx=(0, 10))
            ctk.CTkLabel(card, text=self.t(f"nav_{key}"), font=ctk.CTkFont(size=18, weight="bold"),
                         anchor="w").pack(fill="x", padx=18, pady=(20, 8))
            ctk.CTkLabel(card, text=self.t(f"card_{key}"), justify="left", wraplength=215,
                         anchor="nw").pack(fill="both", expand=True, padx=18, pady=(0, 22))
        self.note(frame, "home_scope", 3)
        self.button_row(frame, 4, [("official_guide", lambda: webbrowser.open(
            "https://dortania.github.io/OpenCore-Install-Guide/")), ("project_github", lambda: webbrowser.open(
                "https://github.com/Chimpi-hackintosh/OpenCore-Helper"))])

    def _build_efi(self):
        frame = self.page("efi")
        self.note(frame, "efi_note", 0)
        self.button_row(frame, 1, [("inspect_efi", self.inspect), ("backup_efi", self.backup),
                                    ("restore_backup", self.restore)])
        self.button_row(frame, 2, [("prepare_workspace", self.prepare), ("open_config", self.open_config)])
        self.efi_output = self.output(frame, 3)
        self.write(self.efi_output, self.t("efi_empty"))

    def _build_hardware(self):
        frame = self.page("hardware")
        self.note(frame, "hardware_note", 0)
        self.button_row(frame, 1, [("scan_hardware", self.scan), ("export_report", self.export)])
        self.hardware_output = self.output(frame, 2)
        self.write(self.hardware_output, self.t("hardware_empty"))

    def _build_downloads(self):
        frame = self.page("downloads")
        self.note(frame, "downloads_note", 0)
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self.project = ctk.CTkOptionMenu(row, values=list(REPOSITORIES), width=210)
        self.project.pack(side="left", padx=(0, 12))
        ctk.CTkButton(row, text=self.t("check_release"), command=self.check_release).pack(side="left")
        self.assets = ctk.CTkOptionMenu(frame, values=[self.t("check_release_first")], width=600)
        self.assets.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        self.button_row(frame, 3, [("download_zip", self.download), ("extract_zip", self.extract),
                                    ("open_release_page", self.open_release)])
        self.download_output = self.output(frame, 4)
        self.write(self.download_output, self.t("downloads_empty"))

    def _build_recovery(self):
        frame = self.page("recovery")
        self.note(frame, "recovery_note", 0)
        fields = ctk.CTkFrame(frame)
        fields.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        fields.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(fields, text="Board ID").grid(row=0, column=0, padx=16, pady=10, sticky="w")
        self.board = ctk.CTkEntry(fields)
        self.board.insert(0, "Mac-27AD2F918AE68F61")
        self.board.grid(row=0, column=1, padx=16, pady=10, sticky="ew")
        ctk.CTkLabel(fields, text="MLB").grid(row=1, column=0, padx=16, pady=10, sticky="w")
        self.mlb = ctk.CTkEntry(fields)
        self.mlb.insert(0, "00000000000000000")
        self.mlb.grid(row=1, column=1, padx=16, pady=10, sticky="ew")
        self.recovery_variant = ctk.CTkOptionMenu(fields, values=[self.t("recovery_latest"), self.t("recovery_default")])
        self.recovery_variant.grid(row=2, column=1, padx=16, pady=10, sticky="ew")
        self.button_row(frame, 2, [("download_recovery", self.recovery_download), ("inspect_image", self.inspect_image),
                                    ("convert_vmdk", self.convert_image)])
        self.button_row(frame, 3, [("macos_catalog", lambda: webbrowser.open("https://support.apple.com/109033")),
                                   ("recovery_guide", lambda: webbrowser.open(
                                       "https://dortania.github.io/OpenCore-Install-Guide/installer-guide/windows-install.html"))])
        self.recovery_output = self.output(frame, 4)
        self.write(self.recovery_output, self.t("recovery_empty"))

    def _build_reports(self):
        frame = self.page("reports")
        self.note(frame, "reports_note", 0)
        self.button_row(frame, 1, [("refresh_report", self.refresh_report), ("export_report", self.export),
                                    ("open_data_folder", lambda: self.open_folder(data_root()))])
        self.report_output = self.output(frame, 2)
        self.refresh_report()

    def _build_settings(self):
        frame = self.page("settings", scroll=True)
        self.note(frame, "settings_note", 0)
        ctk.CTkLabel(frame, text=self.t("language"), anchor="w").grid(row=1, column=0, sticky="ew")
        self.language_values = {self.t("automatic_language"): "auto", "Português (Brasil)": "pt-BR", "English": "en"}
        self.language = ctk.CTkOptionMenu(frame, values=list(self.language_values))
        self.language.set(next(key for key, value in self.language_values.items() if value == self.settings.get("language")))
        self.language.grid(row=2, column=0, sticky="ew", pady=(4, 16))
        ctk.CTkLabel(frame, text=self.t("appearance"), anchor="w").grid(row=3, column=0, sticky="ew")
        self.appearance_values = {self.t("appearance_system"): "System", self.t("appearance_light"): "Light",
                                  self.t("appearance_dark"): "Dark"}
        self.appearance = ctk.CTkOptionMenu(frame, values=list(self.appearance_values))
        self.appearance.set(next(key for key, value in self.appearance_values.items()
                                 if value == self.settings.get("appearance")))
        self.appearance.grid(row=4, column=0, sticky="ew", pady=(4, 18))
        self.tool_entries = {}
        for row, (name, label) in enumerate((("ocat_path", "tool_ocat"), ("ocvalidate_path", "tool_ocvalidate"),
                                            ("qemu_img_path", "tool_qemu"),
                                            ("macserial_path", "tool_macserial")), start=5):
            card = ctk.CTkFrame(frame)
            card.grid(row=row, column=0, sticky="ew", pady=(0, 12))
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(card, text=self.t(label), anchor="w").grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
            entry = ctk.CTkEntry(card)
            entry.insert(0, self.settings.get(name))
            entry.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
            ctk.CTkButton(card, text=self.t("browse"), width=100,
                          command=lambda target=entry: self.choose_executable(target)).grid(
                              row=1, column=1, padx=(0, 14), pady=(0, 14))
            self.tool_entries[name] = entry
        self.button_row(frame, 9, [("save_settings", self.save_settings), ("launch_ocat", self.open_ocat)])
        self.note(frame, "ocat_note", 10)

    def show_page(self, name):
        for key, frame in self.pages.items():
            frame.grid_forget()
            self.nav[key].configure(fg_color="transparent")
        self.pages[name].grid(row=0, column=0, sticky="nsew")
        self.nav[name].configure(fg_color=("#c7dbf6", "#263e5f"))
        self.heading.configure(text=self.t(f"nav_{name}"))

    def style_tree(self):
        dark = ctk.get_appearance_mode() == "Dark"
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("OCH.Treeview", background="#162338" if dark else "#ffffff",
                        fieldbackground="#162338" if dark else "#ffffff",
                        foreground="#dfeaff" if dark else "#1e293b", rowheight=28, borderwidth=0,
                        font=("Segoe UI", 10))
        style.configure("OCH.Treeview.Heading", background="#213652" if dark else "#e5edf8",
                        foreground="#dfeaff" if dark else "#1e293b", font=("Segoe UI", 10, "bold"))
        style.map("OCH.Treeview", background=[("selected", "#2563eb")], foreground=[("selected", "#ffffff")])

    def set_status(self, text):
        self.status.configure(text=text)

    def resize_notes(self, event):
        # A toplevel binding also receives child events; handle only actual window changes.
        if event.widget is not self:
            return
        logical_width = round(event.width / self._get_window_scaling())
        if getattr(self, "_wrapped_for", None) == logical_width:
            return
        self._wrapped_for = logical_width
        for label, padding in self.wrap_labels:
            label.configure(wraplength=min(810, max(180, logical_width - 280 - padding)))

    def report_callback_exception(self, exc_type, exc_value, traceback):
        self.callback_errors.append(str(exc_value))
        logging.error("UI callback failed", exc_info=(exc_type, exc_value, traceback))
        self.present_error(exc_value)

    def present_error(self, error):
        text = self.t(error.key, **error.params) if isinstance(error, AppError) else self.t("unexpected_error", detail=str(error))
        messagebox.showerror(self.t("error"), text, parent=self)
        if hasattr(self, "status"):
            self.set_status(self.t("task_failed"))

    def run_job(self, task, success, *, cancellable=False):
        if self.busy:
            raise AppError("task_running")
        self.busy = True
        self.cancelled.clear()
        self.cancel_button.configure(state="normal" if cancellable else "disabled")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.set_status(self.t("working"))

        def worker():
            try:
                self.messages.put(("result", success, task(), None))
            except Exception as error:
                logging.exception("Background task failed")
                self.messages.put(("result", None, None, error))

        self.executor.submit(worker)

    def poll_messages(self):
        try:
            while True:
                message = self.messages.get_nowait()
                if message[0] == "progress":
                    received, total = message[1:]
                    self.set_status(self.t("download_progress", received=round(received / 1024**2, 1),
                                            total=round(total / 1024**2, 1)))
                    continue
                _, callback, result, error = message
                self.busy = False
                self.progress.stop()
                self.progress.configure(mode="determinate")
                self.progress.set(0)
                self.cancel_button.configure(state="disabled")
                if error:
                    self.present_error(error)
                else:
                    self.set_status(self.t("complete"))
                    try:
                        callback(result)
                    except Exception as failure:
                        self.present_error(failure)
        except queue.Empty:
            pass
        self.after(100, self.poll_messages)

    def show_issues(self, target, issues):
        self.write(target, "\n\n".join(f"[{self.t(issue.severity).upper()}] {issue.path}\n"
                                        f"{self.t(issue.code, **issue.params)}" for issue in issues))

    def show_tool_result(self, result):
        self.show_page("efi")
        self.write(self.efi_output, self.t("tool_exit", code=result.returncode) + "\n\n" + result.stdout + result.stderr)

    def open_config(self):
        self.show_page("editor")
        self.editor.open()

    def open_ocat(self):
        if self.editor.doc.dirty:
            raise AppError("save_before_tool")
        launch_ocat(self.settings.get("ocat_path"), self.editor.doc.path)
        self.set_status(self.t("ocat_launched"))

    def inspect(self):
        folder = filedialog.askdirectory(parent=self, title=self.t("choose_efi"))
        if folder:
            def done(issues):
                self.efi_issues = issues
                self.show_issues(self.efi_output, issues)
            self.run_job(lambda: inspect_efi(Path(folder)), done)

    def backup(self):
        folder = filedialog.askdirectory(parent=self, title=self.t("choose_efi"))
        if not folder:
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        destination = filedialog.asksaveasfilename(parent=self, defaultextension=".zip",
                                                  initialfile=f"EFI-backup-{stamp}.zip", filetypes=[("ZIP", "*.zip")])
        if destination:
            self.run_job(lambda: backup_efi(Path(folder), Path(destination)),
                         lambda path: self.write(self.efi_output, self.t("backup_complete", file=path)))

    def new_directory(self, label):
        # Save-as provides a new directory name rather than choosing an existing directory.
        path = filedialog.asksaveasfilename(parent=self, title=self.t("choose_new_folder"), initialfile=label,
                                           confirmoverwrite=False)
        if path and Path(path).exists():
            raise AppError("destination_exists")
        return Path(path) if path else None

    def restore(self):
        archive = filedialog.askopenfilename(parent=self, filetypes=[("ZIP", "*.zip")])
        if not archive:
            return
        target = self.new_directory("EFI-restored")
        if target:
            self.run_job(lambda: extract_zip(Path(archive), target, verify_backup=True),
                         lambda path: self.write(self.efi_output, self.t("restore_complete", file=path)))

    def prepare(self):
        archive = filedialog.askopenfilename(parent=self, title=self.t("choose_oc_zip"), filetypes=[("ZIP", "*.zip")])
        if not archive:
            return
        target = self.new_directory("OpenCore-workspace")
        if target:
            self.run_job(lambda: prepare_workspace(Path(archive), target),
                         lambda path: self.write(self.efi_output, self.t("workspace_complete", file=path)))

    def scan(self):
        self.show_page("hardware")
        def done(result):
            self.hardware = result
            self.findings = compatibility_findings(result)
            lines = "\n\n".join(f"[{self.t(issue.severity).upper()}] {issue.path}\n"
                                  f"{self.t(issue.code, **issue.params)}" for issue in self.findings)
            self.write(self.hardware_output, lines + "\n\n" + json.dumps(result, indent=2, ensure_ascii=False))
        self.run_job(scan_hardware, done)

    def check_release(self):
        project = self.project.get()
        def done(release):
            self.release = release
            names = [asset.name for asset in release.assets] or [self.t("no_assets")]
            self.assets.configure(values=names)
            self.assets.set(names[0])
            self.write(self.download_output, f"{release.repository}\n{release.tag}\n{release.url}\n\n" + self.t("zip_only"))
        self.run_job(lambda: latest_release(project), done)

    def download(self):
        if self.release is None:
            raise AppError("check_release_first")
        asset = next((asset for asset in self.release.assets if asset.name == self.assets.get()), None)
        if asset is None:
            raise AppError("no_assets")
        path = filedialog.asksaveasfilename(parent=self, initialfile=asset.name, defaultextension=".zip",
                                           filetypes=[("ZIP", "*.zip")])
        if not path:
            return
        def progress(received, total):
            if self.cancelled.is_set():
                raise AppError("cancelled")
            self.messages.put(("progress", received, total))
        def done(result):
            file, digest, verified = result
            self.write(self.download_output, self.t("download_complete", file=file, digest=digest) + "\n\n" +
                       self.t("digest_verified" if verified else "digest_unavailable"))
        self.run_job(lambda: download_asset(asset, Path(path), progress), done, cancellable=True)

    def extract(self):
        archive = filedialog.askopenfilename(parent=self, filetypes=[("ZIP", "*.zip")])
        if not archive:
            return
        target = self.new_directory(Path(archive).stem)
        if target:
            self.run_job(lambda: extract_zip(Path(archive), target),
                         lambda path: self.write(self.download_output, self.t("extract_complete", file=path)))

    def open_release(self):
        if self.release:
            webbrowser.open(self.release.url)
        else:
            webbrowser.open(f"https://github.com/{REPOSITORIES[self.project.get()]}/releases")

    def recovery_download(self):
        board, mlb = self.board.get().strip(), self.mlb.get().strip()
        variant = "latest" if self.recovery_variant.get() == self.t("recovery_latest") else "default"
        target = self.new_directory("com.apple.recovery.boot")
        if target:
            self.run_job(lambda: download_recovery(board, mlb, variant, target, self.cancelled),
                         lambda result: self.write(self.recovery_output, self.t("recovery_complete", **result)),
                         cancellable=True)

    def inspect_image(self):
        source = filedialog.askopenfilename(parent=self, filetypes=[("DMG / VMDK", "*.dmg *.vmdk"),
                                                                  (self.t("all_files"), "*.*")])
        if source:
            path = Path(source)
            self.run_job(lambda: (path.stat().st_size, sha256_file(path)),
                         lambda result: self.write(self.recovery_output, self.t("image_info", file=path,
                                                                                size=result[0], digest=result[1])))

    def convert_image(self):
        source = filedialog.askopenfilename(parent=self, filetypes=[("DMG", "*.dmg")])
        if not source:
            return
        target = filedialog.asksaveasfilename(parent=self, initialfile=Path(source).stem + ".vmdk",
                                             defaultextension=".vmdk", filetypes=[("VMDK", "*.vmdk")])
        if target:
            executable = self.settings.get("qemu_img_path")
            self.run_job(lambda: convert_recovery(executable, Path(source), Path(target)),
                         lambda path: self.write(self.recovery_output, self.t("conversion_complete", file=path)))

    def current_report(self):
        return make_report(hardware=self.hardware, findings=self.findings, efi=self.efi_issues, translate=self.t)

    def refresh_report(self):
        self.write(self.report_output, json.dumps(self.current_report(), indent=2, ensure_ascii=False))

    def export(self):
        path = filedialog.asksaveasfilename(parent=self, initialfile="OpenCore-Helper-report.json",
                                           defaultextension=".json", filetypes=[("JSON", "*.json"),
                                                                               ("HTML", "*.html"), ("Text", "*.txt")])
        if path:
            report = self.current_report()
            self.run_job(lambda: export_report(report, Path(path)),
                         lambda _: self.set_status(self.t("report_saved", file=path)))

    def choose_executable(self, entry):
        filetypes = [(self.t("executable"), "*.exe"), (self.t("all_files"), "*.*")]
        if sys.platform == "darwin":
            filetypes = [(self.t("macos_application"), "*.app"), (self.t("all_files"), "*")]
        path = filedialog.askopenfilename(parent=self, filetypes=filetypes)
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def save_settings(self):
        language = self.language_values[self.language.get()]
        appearance = self.appearance_values[self.appearance.get()]
        tools = {key: entry.get().strip().strip('"') for key, entry in self.tool_entries.items()}
        for key, path in tools.items():
            binary = Path(path).expanduser()
            app_bundle = (sys.platform == "darwin" and key == "ocat_path" and
                          binary.suffix.lower() == ".app" and (binary / "Contents" / "Info.plist").is_file())
            if path and not binary.is_file() and not app_bundle:
                raise AppError("tool_not_found", file=path)
        self.settings.save(language=language, appearance=appearance, **tools)
        ctk.set_appearance_mode(appearance)
        self.style_tree()
        self.set_status(self.t("settings_saved"))

    @staticmethod
    def open_folder(path):
        if os.name == "nt":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["/usr/bin/open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def close(self):
        if self.busy:
            self.present_error(AppError("task_running_close"))
            return
        if self.editor.confirm_discard():
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.destroy()

    def destroy(self):
        # Cancel Tcl timers before destroying their callbacks, including CTk animations.
        for timer in self.tk.call("after", "info"):
            # Keep callback ownership with each widget; after_cancel would also delete
            # child-owned Tcl commands and make their later destruction fail.
            self.tk.call("after", "cancel", timer)
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()
