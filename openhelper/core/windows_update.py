"""Stage and verify a published OpenCore Helper installer before opening it."""
from __future__ import annotations

import ctypes
import hashlib
import os
import queue
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path

REPO = "https://github.com/Chimpi-hackintosh/OpenCore-Helper"
MAX_SETUP_BYTES = 256 * 1024**2
MIN_WINDOWS_BUILD = 22000
ASSET_HOSTS = {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}
APP = "OpenCore-Helper"
SETUP_302 = {
    "tag": "v3.0.2",
    "min_build": MIN_WINDOWS_BUILD,
    "digest": "sha256:a010669abb6cce810dab00434c0fd220913241fde3f3f8dd5e2a248972367022",
}
MESSAGES = {
    "en": {
        "required": "Update required. Save your work before closing the app to run Setup.",
        "install": "Prepare update",
        "save": "Save work",
        "exit": "Exit app",
        "preparing": "Downloading and verifying the official installer…",
        "ready": "Installer verified. Close the app and open Setup?",
        "download_error": "The official installer could not be prepared. Keep the current installation and try again from the official release page.",
        "release": "Open official release",
        "launch_error": "Setup did not open. Keep the current installation and try again from the official release page.",
        "retry": "The old version is still running and a verified installer is available. If Setup already finished and updating failed, back up your files. After confirming the installer's requirements, uninstall only OpenCore Helper and run the verified installer again.",
        "folder": "Show verified installer",
    },
    "pt": {
        "required": "Atualização obrigatória. Salve seu trabalho antes de fechar o aplicativo para abrir o instalador.",
        "install": "Preparar atualização",
        "save": "Salvar trabalho",
        "exit": "Sair do app",
        "preparing": "Baixando e conferindo o instalador oficial…",
        "ready": "Instalador conferido. Fechar o aplicativo e abrir o instalador?",
        "download_error": "Não foi possível preparar o instalador oficial. Mantenha a instalação atual e tente novamente pela página oficial do lançamento.",
        "release": "Abrir lançamento oficial",
        "launch_error": "Não foi possível abrir o instalador. Mantenha a instalação atual e tente novamente pela página oficial do lançamento.",
        "retry": "A versão antiga ainda está em execução e há um instalador conferido. Se a instalação já terminou e a atualização falhou, faça backup dos seus arquivos. Depois de confirmar os requisitos do instalador, desinstale apenas o OpenCore Helper e rode o instalador conferido novamente.",
        "folder": "Mostrar instalador conferido",
    },
}


@dataclass(frozen=True)
class Setup:
    name: str
    url: str
    size: int
    digest: str
    build: int


def select_setup(entry, metadata, releases):
    """Require an exact stable release and asset matching the reviewed catalog."""
    if not isinstance(metadata, dict) or not isinstance(releases, list):
        return None
    tag = entry.get("tag")
    if not isinstance(tag, str) or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        return None
    if metadata.get("tag") != tag or entry.get("minimum") != tag[1:]:
        return None
    build = metadata.get("min_build")
    if type(build) is not int or not MIN_WINDOWS_BUILD <= build <= 99999:
        return None
    name = f"OpenCoreHelper-{tag[1:]}-Setup-x64.exe"
    url = f"{REPO}/releases/download/{tag}/{name}"
    for release in releases:
        if (not isinstance(release, dict) or release.get("tag_name") != tag
                or release.get("draft") is not False or release.get("prerelease") is not False
                or not release.get("published_at") or release.get("html_url") != f"{REPO}/releases/tag/{tag}"):
            continue
        assets = release.get("assets")
        for asset in assets if isinstance(assets, list) else ():
            if not isinstance(asset, dict):
                continue
            digest, size = asset.get("digest"), asset.get("size")
            if (asset.get("name") == name and asset.get("browser_download_url") == url
                    and type(size) is int and 0 < size <= MAX_SETUP_BYTES
                    and isinstance(digest, str) and re.fullmatch(r"sha256:[a-f0-9]{64}", digest)
                    and metadata.get("digest") == digest):
                return Setup(name, url, size, digest.removeprefix("sha256:"), build)
    return None


def installed_directory():
    """Match the running EXE with the registered machine install, excluding portable copies."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return None
    import winreg

    try:
        key_name = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\OpenCoreHelper"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_name,
                            access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            directory = Path(winreg.QueryValueEx(key, "InstallLocation")[0]).resolve()
        executable = Path(sys.executable).resolve()
        if executable == directory / "OpenCoreHelper.exe" and (directory / "Uninstall.exe").is_file():
            return directory
    except (OSError, TypeError, ValueError):
        pass
    return None


def compatible(setup, directory, staging):
    """Conservative eligibility check for the reviewed Windows x64 install path."""
    if directory is None or sys.platform != "win32" or sys.getwindowsversion().build < setup.build:
        return False
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.IsWow64Process2.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ushort),
                                          ctypes.POINTER(ctypes.c_ushort))
        process, native = ctypes.c_ushort(), ctypes.c_ushort()
        if not kernel.IsWow64Process2(kernel.GetCurrentProcess(), ctypes.byref(process), ctypes.byref(native)):
            return False
        if native.value != 0x8664 or process.value != 0:  # Native AMD64, not emulated or 32-bit.
            return False
        return min(shutil.disk_usage(directory).free, shutil.disk_usage(staging).free) >= setup.size + 128 * 1024**2
    except (AttributeError, OSError):
        return False


def verified(setup, path):
    try:
        if not path.is_file() or path.stat().st_size != setup.size:
            return False
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest() == setup.digest
    except OSError:
        return False


def attempted(setup, staging):
    marker = staging / (setup.digest + ".attempted")
    return marker.is_file() and verified(setup, staging / setup.name)


def find_update(entry, policy, releases):
    from openhelper.paths import data_root

    directory = installed_directory()
    if directory is None:
        return None
    remote_apps = policy.get("apps") if isinstance(policy, dict) and policy.get("schema") == 1 else None
    remote_entry = remote_apps.get(APP) if isinstance(remote_apps, dict) else None
    metadata = remote_entry.get("windows_setup") if isinstance(remote_entry, dict) and remote_entry.get("repo") == APP else None
    setup = select_setup(entry, metadata, releases) or select_setup(entry, SETUP_302, releases)
    staging = data_root() / "updates"
    if setup is None or not compatible(setup, directory, staging.parent):
        return None
    return setup, staging, attempted(setup, staging)


def trusted_asset_host(url):
    try:
        target = urllib.parse.urlsplit(url)
        return (target.scheme == "https" and target.hostname in ASSET_HOSTS
                and not target.username and not target.password and target.port in (443, None))
    except ValueError:
        return False


class ReleaseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not trusted_asset_host(newurl):
            raise ValueError("Unexpected installer download host")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def stage(setup, staging):
    """Download into the current user's profile and accept only the exact published bytes."""
    staging.mkdir(parents=True, exist_ok=True)
    destination = staging / setup.name
    if verified(setup, destination):
        return destination
    opener = urllib.request.build_opener(ReleaseRedirects())
    request = urllib.request.Request(setup.url, headers={"User-Agent": "OpenCore-Helper-updater"})
    fd, filename = tempfile.mkstemp(suffix=".part", dir=staging)
    temporary = Path(filename)
    try:
        deadline = time.monotonic() + 300
        with os.fdopen(fd, "wb") as output, opener.open(request, timeout=15) as response:
            remaining = setup.size
            while remaining:
                if time.monotonic() > deadline:
                    raise TimeoutError("Installer download exceeded its time limit")
                chunk = response.read(min(remaining, 256 * 1024))
                if not chunk:
                    break
                output.write(chunk)
                remaining -= len(chunk)
            if remaining or response.read(1):
                raise ValueError("Unexpected installer size")
        if not verified(setup, temporary):
            raise ValueError("Installer SHA-256 does not match")
        temporary.replace(destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)


def launch(setup, staging):
    path = staging / setup.name
    if not compatible(setup, installed_directory(), staging.parent) or not verified(setup, path):
        raise ValueError("Installer or local requirements could not be verified")
    os.startfile(str(path))
    try:
        (staging / (setup.digest + ".attempted")).touch()
    except OSError:
        pass  # Setup already opened; an unavailable marker only suppresses reinstall guidance.


def launch_pending(setup, staging, lang, title):
    from tkinter import messagebox

    try:
        launch(setup, staging)
    except (OSError, ValueError):
        messagebox.showerror(title, MESSAGES.get(lang, MESSAGES["en"])["launch_error"])


def bind_dialog(root, window, buttons, item, lang):
    from tkinter import messagebox, ttk

    setup, staging, retry = item["windows_update"]
    tr = MESSAGES.get(lang, MESSAGES["en"])
    status = ttk.Label(window, text=tr["required"] + ("\n\n" + tr["retry"] if retry else ""),
                       wraplength=500, justify="left")
    status.grid(row=3, column=0, padx=22, pady=(0, 20), sticky="w")
    window.wait_visibility()
    window.grab_set()
    window.protocol("WM_DELETE_WINDOW", root.close)

    def install():
        install_button.configure(state="disabled")
        status.configure(text=tr["preparing"])
        result = queue.Queue()

        def prepare():
            try:
                if not compatible(setup, installed_directory(), staging.parent):
                    raise ValueError("Installer requirements could not be verified")
                stage(setup, staging)
            except (OSError, ValueError):
                result.put(False)
            else:
                result.put(True)

        def poll():
            try:
                ready = result.get_nowait()
            except queue.Empty:
                window.after(200, poll)
                return
            install_button.configure(state="normal")
            if not ready:
                status.configure(text=tr["download_error"])
                install_button.configure(text=tr["release"], command=lambda: webbrowser.open(item["url"]))
                window.grab_release()
                window.protocol("WM_DELETE_WINDOW", window.destroy)
                return
            status.configure(text=tr["required"])
            if messagebox.askyesno(item["title"], tr["ready"], parent=window):
                root.request_update_close((setup, staging, lang, item["title"]))

        threading.Thread(target=prepare, daemon=True).start()
        window.after(200, poll)

    ttk.Button(buttons, text=item["texts"]["table"], command=lambda: webbrowser.open(item["table"])).pack(side="left", padx=4)
    ttk.Button(buttons, text=tr["exit"], command=root.close).pack(side="left", padx=4)
    install_button = ttk.Button(buttons, text=tr["install"], command=install)
    install_button.pack(side="left", padx=4)
    install_button.focus_set()
    if retry or root.editor.doc.dirty:
        options = ttk.Frame(window)
        options.grid(row=4, column=0, padx=22, pady=(0, 20), sticky="w")
        if root.editor.doc.dirty:
            ttk.Button(options, text=tr["save"], command=root.editor.save).pack(side="left", padx=4)
        if retry:
            ttk.Button(options, text=tr["folder"], command=lambda: os.startfile(str(staging))).pack(side="left", padx=4)
