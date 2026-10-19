from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from openhelper.core.plist_document import TYPES, PlistDocument, display_value, parse_value, value_type
from openhelper.core.validation import SECTIONS, snapshot_additions, validate_config
from openhelper.errors import AppError


class AddDialog(ctk.CTkToplevel):
    def __init__(self, editor, container):
        super().__init__(editor)
        self.editor = editor
        self.t = editor.t
        self.container = container
        self.title(self.t("add_item"))
        self.geometry("460x440")
        self.resizable(False, False)
        self.transient(editor.winfo_toplevel())
        ctk.CTkLabel(self, text=self.t("key_name")).pack(anchor="w", padx=24, pady=(20, 4))
        self.key = ctk.CTkEntry(self, width=410)
        self.key.pack(padx=24)
        if isinstance(editor.doc.get(container), list):
            self.key.configure(state="disabled", placeholder_text=self.t("array_append"))
        ctk.CTkLabel(self, text=self.t("value_type")).pack(anchor="w", padx=24, pady=(12, 4))
        self.kind = ctk.CTkOptionMenu(self, values=[self.t(f"type_{kind}") for kind in TYPES], width=410)
        self.kind.pack(padx=24)
        self.value = ctk.CTkTextbox(self, width=410, height=130)
        self.value.pack(padx=24, pady=16)
        ctk.CTkButton(self, text=self.t("add_item"), command=self.submit).pack(pady=8)
        self.after(100, self.grab_set)

    def submit(self):
        kind = TYPES[[self.t(f"type_{item}") for item in TYPES].index(self.kind.get())]
        self.editor.doc.add(self.container, self.key.get(), parse_value(kind, self.value.get("1.0", "end-1c")))
        self.editor.refresh()
        self.destroy()


class PlistEditor(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.t = app.t
        self.doc = PlistDocument()
        self.paths = {}
        self.selected = ()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for label, callback in (("new", self.new), ("open", self.open), ("save", self.save),
                                ("save_as", self.save_as), ("undo", self.undo), ("redo", self.redo)):
            ctk.CTkButton(top, text=self.t(label), width=95, command=callback).pack(side="left", padx=(0, 6))
        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for label, callback in (("validate", self.validate), ("snapshot", self.snapshot),
                                ("run_ocvalidate", self.ocvalidate), ("smbios", self.smbios),
                                ("launch_ocat", app.open_ocat)):
            ctk.CTkButton(tools, text=self.t(label), width=140, fg_color=("#dce8f6", "#24364e"),
                          text_color=("#163b66", "#dbeafe"), command=callback).pack(side="left", padx=(0, 6))
        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.section = ctk.CTkOptionMenu(filters, width=180, values=[self.t("all_sections"), *SECTIONS],
                                        command=lambda _: self.refresh())
        self.section.pack(side="left", padx=(0, 12))
        self.search = tk.StringVar()
        ctk.CTkEntry(filters, placeholder_text=self.t("search_keys"), textvariable=self.search,
                     width=290).pack(side="left", fill="x", expand=True)
        self.search.trace_add("write", lambda *_: self.refresh())
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2, minsize=275)
        body.grid_rowconfigure(0, weight=1)
        tree_frame = ctk.CTkFrame(body)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, columns=("type", "value"), selectmode="browse", style="OCH.Treeview")
        self.tree.heading("#0", text=self.t("key_name"))
        self.tree.heading("type", text=self.t("value_type"))
        self.tree.heading("value", text=self.t("value"))
        self.tree.column("#0", width=215, minwidth=110)
        self.tree.column("type", width=90, minwidth=65, stretch=False)
        self.tree.column("value", width=190, minwidth=90)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ctk.CTkScrollbar(tree_frame, command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        horizontal = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(xscrollcommand=horizontal.set)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        self.tree.bind("<Double-1>", lambda _: self.value.focus_set())
        form = ctk.CTkScrollableFrame(body)
        form.grid(row=0, column=1, sticky="nsew")
        form.grid_columnconfigure(0, weight=1)
        self.path_label = ctk.CTkLabel(form, text="/", anchor="w", wraplength=245)
        self.path_label.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.key = ctk.CTkEntry(form, placeholder_text=self.t("key_name"))
        self.key.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        ctk.CTkButton(form, text=self.t("rename"), command=self.rename).grid(
            row=2, column=0, sticky="ew", padx=10, pady=(4, 12))
        self.kind = ctk.CTkOptionMenu(form, values=[self.t(f"type_{kind}") for kind in TYPES])
        self.kind.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        self.value = ctk.CTkTextbox(form, height=150, wrap="word")
        self.value.grid(row=4, column=0, sticky="ew", padx=10, pady=8)
        ctk.CTkLabel(form, text=self.t("value_hint"), wraplength=240, justify="left").grid(
            row=5, column=0, sticky="ew", padx=10, pady=4)
        for row, (label, callback) in enumerate((("apply", self.apply), ("add_item", self.add),
                                                ("delete", self.delete)), start=6):
            ctk.CTkButton(form, text=self.t(label), command=callback).grid(
                row=row, column=0, sticky="ew", padx=10, pady=4)
        order = ctk.CTkFrame(form, fg_color="transparent")
        order.grid(row=9, column=0, sticky="ew", padx=10, pady=8)
        ctk.CTkButton(order, text=self.t("move_up"), width=105, command=lambda: self.move(-1)).pack(side="left")
        ctk.CTkButton(order, text=self.t("move_down"), width=105, command=lambda: self.move(1)).pack(side="right")
        self.file_label = ctk.CTkLabel(self, text=self.t("no_file"), anchor="w", wraplength=800)
        self.file_label.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        self.refresh()

    def confirm_discard(self):
        return not self.doc.dirty or messagebox.askyesno(self.t("unsaved"), self.t("discard_prompt"), parent=self)

    def new(self):
        if self.confirm_discard():
            self.doc = PlistDocument()
            self.doc.dirty = True
            self.selected = ()
            self.refresh()
            self.app.set_status(self.t("new_config_note"))

    def open(self, path=None):
        if not self.confirm_discard():
            return
        path = path or filedialog.askopenfilename(parent=self, filetypes=[("Property List", "*.plist"),
                                                                         (self.t("all_files"), "*.*")])
        if path:
            document = PlistDocument()
            document.load(Path(path))
            self.doc = document
            self.app.settings.save(last_config=str(self.doc.path))
            self.selected = ()
            self.section.set(self.t("all_sections"))
            self.search.set("")
            self.refresh()

    def save(self):
        if self.doc.path is None:
            return self.save_as()
        self.doc.save()
        self.refresh()
        self.app.set_status(self.t("saved_with_backup"))
        return True

    def save_as(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".plist", initialfile="config.plist",
                                           filetypes=[("Property List", "*.plist")])
        if path:
            self.doc.save(Path(path))
            self.refresh()
            self.app.set_status(self.t("saved_with_backup"))
            return True
        return False

    def refresh(self):
        open_paths = {self.paths[item] for item in self.paths if self.tree.exists(item) and self.tree.item(item, "open")}
        self.tree.delete(*self.tree.get_children())
        self.paths.clear()
        query = self.search.get().strip().casefold()
        section = self.section.get()

        def matches(key, value):
            if query in str(key).casefold() or query in display_value(value).casefold():
                return True
            children = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else []
            return any(matches(k, v) for k, v in children)

        def insert(parent, key, value, path):
            if query and path and not matches(key, value):
                return
            item = self.tree.insert(parent, "end", text=str(key),
                                    values=(self.t(f"type_{value_type(value)}"), display_value(value)[:350]),
                                    open=not path or path in open_paths or bool(query))
            self.paths[item] = path
            if isinstance(value, dict):
                for child_key, child in value.items():
                    if not path and section != self.t("all_sections") and child_key != section:
                        continue
                    insert(item, child_key, child, (*path, child_key))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    insert(item, index, child, (*path, index))

        insert("", "config.plist", self.doc.data, ())
        for item, path in self.paths.items():
            if path == self.selected:
                self.tree.selection_set(item)
                break
        self.file_label.configure(text=f"{'* ' if self.doc.dirty else ''}{self.doc.path or self.t('no_file')}")
        self.app.title(f"{'* ' if self.doc.dirty else ''}OpenCore Helper 3.0.1")

    def select(self, _=None):
        selection = self.tree.selection()
        if not selection:
            return
        self.selected = self.paths[selection[0]]
        value = self.doc.get(self.selected)
        self.path_label.configure(text="/" + "/".join(map(str, self.selected)))
        self.key.delete(0, "end")
        self.key.insert(0, str(self.selected[-1]) if self.selected else "")
        self.kind.set(self.t(f"type_{value_type(value)}"))
        self.value.delete("1.0", "end")
        if not isinstance(value, (dict, list)):
            self.value.insert("1.0", display_value(value))

    def apply(self):
        if not self.selected:
            raise AppError("root_edit")
        value = self.doc.get(self.selected)
        kind = TYPES[[self.t(f"type_{item}") for item in TYPES].index(self.kind.get())]
        if isinstance(value, (dict, list)):
            if kind == value_type(value):
                return
            if not messagebox.askyesno(self.t("confirm"), self.t("replace_container"), parent=self):
                return
        self.doc.set(self.selected, parse_value(kind, self.value.get("1.0", "end-1c")))
        self.refresh()

    def rename(self):
        old = self.selected
        self.doc.rename(old, self.key.get())
        self.selected = (*old[:-1], self.key.get())
        self.refresh()

    def add(self):
        path = self.selected
        if not isinstance(self.doc.get(path), (dict, list)):
            path = path[:-1]
        AddDialog(self, path)

    def delete(self):
        if not self.selected:
            raise AppError("root_edit")
        if messagebox.askyesno(self.t("confirm"), self.t("delete_prompt"), parent=self):
            self.doc.delete(self.selected)
            self.selected = self.selected[:-1]
            self.refresh()

    def move(self, offset):
        self.doc.move(self.selected, offset)
        target = self.selected[-1] + offset
        if 0 <= target < len(self.doc.get(self.selected[:-1])):
            self.selected = (*self.selected[:-1], target)
        self.refresh()

    def undo(self):
        self.doc.undo()
        self.selected = ()
        self.refresh()

    def redo(self):
        self.doc.redo()
        self.selected = ()
        self.refresh()

    def validate(self):
        self.app.efi_issues = validate_config(self.doc.data, self.doc.path.parent if self.doc.path else None)
        self.app.show_issues(self.app.efi_output, self.app.efi_issues)
        self.app.show_page("efi")

    def snapshot(self):
        if self.doc.path is None:
            raise AppError("no_config")
        if not messagebox.askyesno(self.t("snapshot"), self.t("snapshot_prompt"), parent=self):
            return
        data, counts = snapshot_additions(self.doc.data, self.doc.path.parent)
        if any(counts.values()):
            self.doc.checkpoint()
            self.doc.data = data
            self.refresh()
        self.app.set_status(self.t("snapshot_result", **counts))

    def ocvalidate(self):
        from openhelper.core.process import run_tool

        if self.doc.path is None:
            raise AppError("no_config")
        if self.doc.dirty:
            raise AppError("save_before_tool")
        path = self.doc.path
        self.app.run_job(lambda: run_tool(self.app.settings.get("ocvalidate_path"), [str(path)]),
                         lambda result: self.app.show_tool_result(result))

    def smbios(self):
        from openhelper.ui.smbios import SMBIOSDialog

        SMBIOSDialog(self)

