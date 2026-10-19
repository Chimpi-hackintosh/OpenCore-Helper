from __future__ import annotations

import customtkinter as ctk

from openhelper.core.smbios import apply_identity, generate_identity


class SMBIOSDialog(ctk.CTkToplevel):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.t = editor.t
        self.title("SMBIOS · PlatformInfo/Generic")
        self.geometry("620x630")
        self.minsize(540, 560)
        self.transient(editor.winfo_toplevel())
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=self.t("smbios_note"), wraplength=540, justify="left").grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=20)
        platform = editor.doc.data.get("PlatformInfo", {})
        current = platform.get("Generic", {}) if isinstance(platform, dict) else {}
        if not isinstance(current, dict):
            current = {}
        self.fields = {}
        for index, field in enumerate(("SystemProductName", "SystemSerialNumber", "MLB", "SystemUUID", "ROM"), start=1):
            ctk.CTkLabel(self, text=field, anchor="w").grid(row=index, column=0, padx=24, pady=12, sticky="w")
            entry = ctk.CTkEntry(self)
            entry.grid(row=index, column=1, sticky="ew", padx=(0, 24), pady=12)
            value = current.get(field, "")
            entry.insert(0, value.hex().upper() if isinstance(value, bytes) else str(value))
            self.fields[field] = entry
        ctk.CTkButton(self, text=self.t("generate_identity"), command=self.generate).grid(
            row=6, column=0, columnspan=2, sticky="ew", padx=24, pady=14)
        ctk.CTkButton(self, text=self.t("apply_to_config"), command=self.apply).grid(
            row=7, column=0, columnspan=2, sticky="ew", padx=24, pady=8)
        self.state_label = ctk.CTkLabel(self, text=self.t("smbios_unsaved"), wraplength=540, justify="left")
        self.state_label.grid(row=8, column=0, columnspan=2, sticky="ew", padx=24, pady=14)
        self.after(100, self.grab_set)

    def generate(self):
        model = self.fields["SystemProductName"].get().strip()
        path = self.editor.app.settings.get("macserial_path")
        self.state_label.configure(text=self.t("working"))
        def done(identity):
            if not self.winfo_exists():
                return
            for field, value in identity.items():
                self.fields[field].delete(0, "end")
                self.fields[field].insert(0, value.hex().upper() if isinstance(value, bytes) else value)
            self.state_label.configure(text=self.t("smbios_generated"))
        self.editor.app.run_job(lambda: generate_identity(path, model), done)

    def apply(self):
        from openhelper.errors import AppError

        values = {key: entry.get().strip() for key, entry in self.fields.items()}
        try:
            values["ROM"] = bytes.fromhex(values["ROM"])
        except ValueError as error:
            raise AppError("invalid_smbios", detail="ROM") from error
        result = apply_identity(self.editor.doc.data, values)
        self.editor.doc.checkpoint()
        self.editor.doc.data = result
        self.editor.refresh()
        self.destroy()
