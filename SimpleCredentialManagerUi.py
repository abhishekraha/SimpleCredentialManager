import tkinter as tk
import threading
import time
import webbrowser
from pathlib import Path
from secrets import randbelow
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import (
    APP_COPYRIGHT,
    APP_NAME,
    APP_RELEASES_URL,
    APP_REPOSITORY_URL,
    APP_VERSION,
    BUG_REPORT_URL,
    DEFAULT_ENCRYPTED_BACKUP,
    DEFAULT_EXPORT_CSV,
    ENCRYPTED_BACKUP_FILE_EXTENSION,
    SESSION_IDLE_LOCK_SECONDS,
)
from dev.abhishekraha.secretmanager.core.ReleaseUpdateService import (
    ReleaseUpdateError,
    ReleaseUpdateService,
)
from dev.abhishekraha.secretmanager.core.SecretManagerService import (
    SecretManagerService,
)
from dev.abhishekraha.secretmanager.utils.Utils import copy_to_clipboard


class SecretEditorDialog(tk.Toplevel):
    def __init__(self, master, title, secret=None, password_factory=None):
        super().__init__(master)
        self.result = None
        self.password_factory = password_factory
        self.title(title)
        self.transient(master)
        self.resizable(False, False)
        self.columnconfigure(1, weight=1)

        self.name_var = tk.StringVar(value=secret.get_name() if secret else "")
        self.username_var = tk.StringVar(value=secret.get_username() if secret else "")
        self.password_var = tk.StringVar(value=secret.get_password() if secret else "")
        self.url_var = tk.StringVar(value=secret.get_url() if secret else "")
        self.show_password_var = tk.BooleanVar(value=False)

        ttk.Label(self, text="Name").grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")
        ttk.Entry(self, textvariable=self.name_var, width=44).grid(
            row=0, column=1, padx=(0, 16), pady=(16, 8), sticky="ew"
        )

        ttk.Label(self, text="Username").grid(row=1, column=0, padx=16, pady=8, sticky="w")
        ttk.Entry(self, textvariable=self.username_var, width=44).grid(
            row=1, column=1, padx=(0, 16), pady=8, sticky="ew"
        )

        ttk.Label(self, text="Password").grid(row=2, column=0, padx=16, pady=8, sticky="w")
        password_frame = ttk.Frame(self)
        password_frame.grid(row=2, column=1, padx=(0, 16), pady=8, sticky="ew")
        password_frame.columnconfigure(0, weight=1)
        self.password_entry = ttk.Entry(password_frame, textvariable=self.password_var, width=44, show="*")
        self.password_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(password_frame, text="Generate", command=self._generate_password).grid(
            row=0, column=1, padx=(8, 0)
        )
        ttk.Checkbutton(
            self,
            text="Show password",
            variable=self.show_password_var,
            command=self._toggle_password_visibility,
        ).grid(row=3, column=1, padx=(0, 16), pady=(0, 8), sticky="w")

        ttk.Label(self, text="URL").grid(row=4, column=0, padx=16, pady=8, sticky="w")
        ttk.Entry(self, textvariable=self.url_var, width=44).grid(
            row=4, column=1, padx=(0, 16), pady=8, sticky="ew"
        )

        ttk.Label(self, text="Comments").grid(row=5, column=0, padx=16, pady=8, sticky="nw")
        self.comments_text = tk.Text(self, width=44, height=6, wrap="word")
        self.comments_text.grid(row=5, column=1, padx=(0, 16), pady=8, sticky="ew")
        if secret:
            self.comments_text.insert("1.0", secret.get_comments())

        action_frame = ttk.Frame(self)
        action_frame.grid(row=6, column=0, columnspan=2, padx=16, pady=(8, 16), sticky="e")
        ttk.Button(action_frame, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(action_frame, text="Save", command=self._save).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _event: self._save())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()
        self.password_entry.focus_set()

    def _toggle_password_visibility(self):
        self.password_entry.configure(show="" if self.show_password_var.get() else "*")

    def _generate_password(self):
        if self.password_factory is None:
            return
        self.password_var.set(self.password_factory())
        self.show_password_var.set(True)
        self._toggle_password_visibility()

    def _save(self):
        self.result = {
            "name": self.name_var.get().strip(),
            "username": self.username_var.get(),
            "password": self.password_var.get(),
            "url": self.url_var.get(),
            "comments": self.comments_text.get("1.0", "end").rstrip("\n"),
        }
        self.destroy()


class BulkInsertDialog(tk.Toplevel):
    HEADER_TEMPLATE = "name,username,password,url,comments\n"

    def __init__(self, master):
        super().__init__(master)
        self.result = None
        self.title("Bulk insert secrets")
        self.transient(master)
        self.geometry("760x420")
        self.minsize(680, 360)

        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        ttk.Label(container, text="Bulk insert (CSV)", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            container,
            text="Keep the header row. Add one comma-separated secret per line. Quote values that contain commas.",
            wraplength=700,
        ).grid(row=1, column=0, sticky="w", pady=(8, 12))

        self.input_box = tk.Text(container, wrap="none")
        self.input_box.grid(row=2, column=0, sticky="nsew")
        self.input_box.insert("1.0", self.HEADER_TEMPLATE)

        action_frame = ttk.Frame(container)
        action_frame.grid(row=3, column=0, sticky="e", pady=(12, 0))
        ttk.Button(action_frame, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(action_frame, text="Insert", command=self._save).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()
        self.input_box.focus_set()

    def _save(self):
        self.result = self.input_box.get("1.0", "end").rstrip()
        self.destroy()


class MasterPasswordDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.result = None
        self.title("Change master password")
        self.transient(master)
        self.resizable(False, False)
        self.columnconfigure(1, weight=1)

        self.current_password_var = tk.StringVar(value="")
        self.new_password_var = tk.StringVar(value="")
        self.confirm_password_var = tk.StringVar(value="")
        self.show_password_var = tk.BooleanVar(value=False)

        ttk.Label(self, text="Current master password").grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")
        self.current_password_entry = ttk.Entry(self, textvariable=self.current_password_var, width=44, show="*")
        self.current_password_entry.grid(row=0, column=1, padx=(0, 16), pady=(16, 8), sticky="ew")

        ttk.Label(self, text="New master password").grid(row=1, column=0, padx=16, pady=8, sticky="w")
        self.new_password_entry = ttk.Entry(self, textvariable=self.new_password_var, width=44, show="*")
        self.new_password_entry.grid(row=1, column=1, padx=(0, 16), pady=8, sticky="ew")

        ttk.Label(self, text="Confirm new password").grid(row=2, column=0, padx=16, pady=8, sticky="w")
        self.confirm_password_entry = ttk.Entry(self, textvariable=self.confirm_password_var, width=44, show="*")
        self.confirm_password_entry.grid(row=2, column=1, padx=(0, 16), pady=8, sticky="ew")

        ttk.Checkbutton(
            self,
            text="Show passwords",
            variable=self.show_password_var,
            command=self._toggle_password_visibility,
        ).grid(row=3, column=1, padx=(0, 16), pady=(0, 8), sticky="w")

        action_frame = ttk.Frame(self)
        action_frame.grid(row=4, column=0, columnspan=2, padx=16, pady=(8, 16), sticky="e")
        ttk.Button(action_frame, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(action_frame, text="Change", command=self._save).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _event: self._save())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()
        self.current_password_entry.focus_set()

    def _toggle_password_visibility(self):
        show_char = "" if self.show_password_var.get() else "*"
        self.current_password_entry.configure(show=show_char)
        self.new_password_entry.configure(show=show_char)
        self.confirm_password_entry.configure(show=show_char)

    def _save(self):
        self.result = {
            "current_password": self.current_password_var.get(),
            "new_password": self.new_password_var.get(),
            "confirm_password": self.confirm_password_var.get(),
        }
        self.destroy()


class BackupPasswordDialog(tk.Toplevel):
    def __init__(self, master, title, action_label, require_confirmation, allow_generate):
        super().__init__(master)
        self.result = None
        self.require_confirmation = require_confirmation
        self.password_factory = master.service.generate_password if allow_generate else None
        self.title(title)
        self.transient(master)
        self.resizable(False, False)
        self.columnconfigure(1, weight=1)

        self.password_var = tk.StringVar(value="")
        self.confirm_password_var = tk.StringVar(value="")
        self.show_password_var = tk.BooleanVar(value=False)

        ttk.Label(
            self,
            text="This password protects the exported backup separately from your vault password.",
            wraplength=420,
        ).grid(row=0, column=0, columnspan=3, padx=16, pady=(16, 8), sticky="w")
        ttk.Label(self, text="Backup password").grid(row=1, column=0, padx=16, pady=8, sticky="w")
        password_frame = ttk.Frame(self)
        password_frame.grid(row=1, column=1, columnspan=2, padx=(0, 16), pady=8, sticky="ew")
        password_frame.columnconfigure(0, weight=1)
        self.password_entry = ttk.Entry(password_frame, textvariable=self.password_var, width=44, show="*")
        self.password_entry.grid(row=0, column=0, sticky="ew")
        if allow_generate:
            ttk.Button(password_frame, text="Generate", command=self._generate_password).grid(
                row=0, column=1, padx=(8, 0)
            )

        row_index = 2
        if require_confirmation:
            ttk.Label(self, text="Confirm backup password").grid(row=row_index, column=0, padx=16, pady=8, sticky="w")
            self.confirm_password_entry = ttk.Entry(
                self,
                textvariable=self.confirm_password_var,
                width=44,
                show="*",
            )
            self.confirm_password_entry.grid(row=row_index, column=1, columnspan=2, padx=(0, 16), pady=8, sticky="ew")
            row_index += 1
        else:
            self.confirm_password_entry = None

        ttk.Checkbutton(
            self,
            text="Show password",
            variable=self.show_password_var,
            command=self._toggle_password_visibility,
        ).grid(row=row_index, column=1, columnspan=2, padx=(0, 16), pady=(0, 8), sticky="w")
        row_index += 1

        action_frame = ttk.Frame(self)
        action_frame.grid(row=row_index, column=0, columnspan=3, padx=16, pady=(8, 16), sticky="e")
        ttk.Button(action_frame, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(action_frame, text=action_label, command=self._save).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _event: self._save())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()
        self.password_entry.focus_set()

    def _toggle_password_visibility(self):
        show_char = "" if self.show_password_var.get() else "*"
        self.password_entry.configure(show=show_char)
        if self.confirm_password_entry is not None:
            self.confirm_password_entry.configure(show=show_char)

    def _generate_password(self):
        if self.password_factory is None:
            return
        generated_password = self.password_factory()
        self.password_var.set(generated_password)
        self.confirm_password_var.set(generated_password)
        self.show_password_var.set(True)
        self._toggle_password_visibility()

    def _save(self):
        password = self.password_var.get()
        if not password:
            messagebox.showerror(self.title(), "Backup password cannot be empty.", parent=self)
            return
        if self.require_confirmation and password != self.confirm_password_var.get():
            messagebox.showerror(self.title(), "Backup password and confirmation do not match.", parent=self)
            return
        self.result = {"password": password}
        self.destroy()


class SimpleCredentialManagerUi(tk.Tk):
    def __init__(self):
        super().__init__()
        self.release_update_service = ReleaseUpdateService()
        self.service = SecretManagerService(client_name="ui")
        self.status_var = tk.StringVar(value="Starting up...")
        self.search_var = tk.StringVar()
        self.show_password_var = tk.BooleanVar(value=False)
        self.lockout_timer_id = None
        self.idle_check_id = None
        self.idle_monitoring_enabled = False
        self.last_activity_timestamp = time.monotonic()
        self.current_secret_name = None
        self.current_secret_password = ""
        self.current_secret_username = ""
        self.current_password_mask = ""
        self.toast_popup = None
        self.release_status = {}
        self.release_prompt_shown = False
        self.update_install_in_progress = False

        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1160x760")
        self.minsize(980, 640)
        self.protocol("WM_DELETE_WINDOW", self._handle_close)

        self._configure_style()

        self.content = ttk.Frame(self, padding=20)
        self.content.pack(fill="both", expand=True)

        self.footer = ttk.Frame(self, padding=(16, 8))
        self.footer.pack(fill="x", side="bottom")

        self.status_bar = ttk.Label(self.footer, textvariable=self.status_var, anchor="w")
        self.status_bar.pack(side="left")

        footer_right = ttk.Frame(self.footer)
        footer_right.pack(side="right")
        self.version_label = ttk.Label(
            footer_right,
            text=APP_VERSION,
            style="FooterVersion.TLabel",
            cursor="hand2",
        )
        self.version_label.pack(side="left")
        self.version_label.bind("<Button-1>", self._open_release_link)
        ttk.Label(footer_right, text=" | ", style="Footer.TLabel").pack(side="left")
        ttk.Label(
            footer_right,
            text=APP_COPYRIGHT,
            style="Footer.TLabel",
        ).pack(side="left")
        ttk.Label(footer_right, text=" | ", style="Footer.TLabel").pack(side="left")
        self.repo_label = ttk.Label(
            footer_right,
            text="GitHub",
            style="FooterLink.TLabel",
            cursor="hand2",
        )
        self.repo_label.pack(side="left")
        self.repo_label.bind("<Button-1>", lambda _event: webbrowser.open_new_tab(APP_REPOSITORY_URL))
        self.bind_all("<KeyPress>", self._record_user_activity, add="+")
        self.bind_all("<ButtonPress>", self._record_user_activity, add="+")
        self.bind_all("<MouseWheel>", self._record_user_activity, add="+")
        self.bind_all("<Motion>", self._record_user_activity, add="+")

        self.after(50, self._bootstrap)
        self.after(150, self._start_release_check)

    def _configure_style(self):
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 11))
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Footer.TLabel", font=("Segoe UI", 9))
        style.configure("FooterLink.TLabel", font=("Segoe UI", 9, "underline"))
        style.configure("FooterVersion.TLabel", font=("Segoe UI", 9, "bold"))
        style.configure("FooterVersionWarning.TLabel", font=("Segoe UI", 9, "bold"), foreground="#b58900")
        style.configure("FooterVersionStale.TLabel", font=("Segoe UI", 9, "bold"), foreground="#c0392b")

    def _bootstrap(self):
        try:
            initialized = self.service.initialize()
        except (FileNotFoundError, ValueError) as exc:
            self._show_error_screen("Startup failed", str(exc), self.service.get_startup_recovery_instructions(exc))
            return

        if initialized:
            self._show_login_screen()
            return
        self._show_setup_screen()

    def _clear_content(self):
        if self.lockout_timer_id is not None:
            self.after_cancel(self.lockout_timer_id)
            self.lockout_timer_id = None
        for child in self.content.winfo_children():
            child.destroy()

    def _show_setup_screen(self):
        self._clear_content()
        self._stop_idle_monitoring()
        self.status_var.set("")

        ttk.Label(
            self.content,
            text=f"{APP_NAME} {APP_VERSION}",
            style="Title.TLabel",
        ).pack(anchor="w", pady=(0, 20))

        card = ttk.Frame(self.content, padding=20)
        card.pack(anchor="center", expand=True)

        ttk.Label(card, text="Create master password", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        ttk.Label(card, text="Master password").grid(row=1, column=0, sticky="w", pady=8)
        password_entry = ttk.Entry(card, show="*", width=36)
        password_entry.grid(row=1, column=1, sticky="ew", pady=8)

        ttk.Label(card, text="Confirm password").grid(row=2, column=0, sticky="w", pady=8)
        confirm_entry = ttk.Entry(card, show="*", width=36)
        confirm_entry.grid(row=2, column=1, sticky="ew", pady=8)

        def submit_setup():
            try:
                self.service.setup_master_password(password_entry.get(), confirm_entry.get())
                success, message = self.service.authenticate(password_entry.get())
            except Exception as exc:
                messagebox.showerror("Setup failed", str(exc), parent=self)
                return
            if not success:
                messagebox.showerror("Setup failed", message, parent=self)
                return
            self.status_var.set("Vault created successfully.")
            self._show_vault_screen()

        ttk.Button(card, text="Create vault", command=submit_setup).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(16, 0)
        )
        password_entry.focus_set()

    def _show_login_screen(self):
        self._clear_content()
        self._stop_idle_monitoring()
        self.status_var.set("")

        ttk.Label(
            self.content,
            text=f"{APP_NAME} {APP_VERSION}",
            style="Title.TLabel",
        ).pack(anchor="w", pady=(0, 20))

        card = ttk.Frame(self.content, padding=20)
        card.pack(anchor="center", expand=True)

        ttk.Label(card, text="Unlock vault", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        ttk.Label(card, text="Master password").grid(row=1, column=0, sticky="w", pady=8)
        password_entry = ttk.Entry(card, show="*", width=36)
        password_entry.grid(row=1, column=1, sticky="ew", pady=8)

        helper_var = tk.StringVar(value="")
        helper_label = ttk.Label(card, textvariable=helper_var, wraplength=420, foreground="#8a2b2b")
        helper_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))

        unlock_button = ttk.Button(card, text="Unlock")
        unlock_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        def submit_login():
            success, message = self.service.authenticate(password_entry.get())
            if success:
                self.status_var.set("Vault unlocked.")
                self._show_vault_screen()
                return
            helper_var.set(message)
            password_entry.delete(0, "end")
            self._refresh_lockout_state(password_entry, unlock_button, helper_var)

        unlock_button.configure(command=submit_login)
        password_entry.bind("<Return>", lambda _event: submit_login())
        password_entry.focus_set()
        self._refresh_lockout_state(password_entry, unlock_button, helper_var)

    def _refresh_lockout_state(self, password_entry, unlock_button, helper_var):
        status = self.service.get_lockout_status()
        if status["is_locked_out"]:
            helper_var.set(f"Temporary lockout active. Try again in {status['remaining_seconds']} second(s).")
            password_entry.configure(state="disabled")
            unlock_button.configure(state="disabled")
            self.lockout_timer_id = self.after(
                1000, lambda: self._refresh_lockout_state(password_entry, unlock_button, helper_var)
            )
            return
        password_entry.configure(state="normal")
        unlock_button.configure(state="normal")
        if not helper_var.get():
            helper_var.set("Use your master password to unlock the local vault.")

    def _show_vault_screen(self):
        self._clear_content()
        self.status_var.set("")
        self.search_var = tk.StringVar()
        self.show_password_var = tk.BooleanVar(value=False)
        self.search_var.trace_add("write", lambda *_args: self._refresh_secret_tree())

        header = ttk.Frame(self.content)
        header.pack(fill="x", pady=(0, 16))
        ttk.Label(header, text=f"{APP_NAME} {APP_VERSION}", style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="Lock", command=self._lock_and_return_to_login).pack(side="right")

        toolbar = ttk.Frame(self.content)
        toolbar.pack(fill="x", pady=(0, 16))
        ttk.Label(toolbar, text="Search").pack(side="left")
        ttk.Entry(toolbar, textvariable=self.search_var, width=28).pack(side="left", padx=(8, 16))
        for label, command in [
            ("Add", self._add_secret),
            ("Bulk Insert", self._bulk_insert_secrets),
            ("Edit", self._edit_selected_secret),
            ("Delete", self._delete_selected_secret),
            ("Import CSV / Backup", self._import_secrets),
            ("Export CSV", self._export_secrets),
            ("Export Backup", self._export_encrypted_backup),
            ("Change Master Password", self._change_master_password),
        ]:
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=(0, 8))

        paned = ttk.Panedwindow(self.content, orient="horizontal")
        paned.pack(fill="both", expand=True)

        list_frame = ttk.Frame(paned, padding=12)
        detail_frame = ttk.Frame(paned, padding=12)
        paned.add(list_frame, weight=1)
        paned.add(detail_frame, weight=2)

        ttk.Label(list_frame, text="Stored secrets", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        self.secret_tree = ttk.Treeview(
            list_frame,
            columns=("username", "url"),
            show="tree headings",
            selectmode="browse",
        )
        self.secret_tree.heading("#0", text="Name")
        self.secret_tree.heading("username", text="Username")
        self.secret_tree.heading("url", text="URL")
        self.secret_tree.column("#0", width=220, stretch=True)
        self.secret_tree.column("username", width=140, stretch=True)
        self.secret_tree.column("url", width=180, stretch=True)
        self.secret_tree.pack(fill="both", expand=True)
        self.secret_tree.bind("<<TreeviewSelect>>", self._handle_secret_selection)
        self.secret_tree.bind("<Double-1>", lambda _event: self._edit_selected_secret())

        self.name_var = tk.StringVar(value="-")
        self.username_var = tk.StringVar(value="-")
        self.password_var = tk.StringVar(value="-")
        self.url_var = tk.StringVar(value="-")
        self.created_var = tk.StringVar(value="-")
        self.updated_var = tk.StringVar(value="-")
        self.comments_text = tk.Text(detail_frame, width=48, height=12, wrap="word", state="disabled")

        ttk.Label(detail_frame, text="Credential details", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        self._add_detail_row(detail_frame, 1, "Name", self.name_var)
        ttk.Label(detail_frame, text="Username").grid(row=2, column=0, sticky="w", pady=8)
        self.username_entry = ttk.Entry(
            detail_frame,
            textvariable=self.username_var,
            state="readonly",
            cursor="hand2",
        )
        self.username_entry.grid(row=2, column=1, sticky="ew", pady=8)
        self.username_entry.bind("<Button-1>", self._handle_username_click)
        ttk.Label(detail_frame, text="Password").grid(row=3, column=0, sticky="w", pady=8)
        self.password_entry = ttk.Entry(
            detail_frame,
            textvariable=self.password_var,
            state="readonly",
            cursor="hand2",
        )
        self.password_entry.grid(row=3, column=1, sticky="ew", pady=8)
        self.password_entry.bind("<Button-1>", self._handle_password_click)
        ttk.Checkbutton(
            detail_frame,
            text="Show password",
            variable=self.show_password_var,
            command=self._refresh_password_display,
        ).grid(row=4, column=1, sticky="w", pady=(0, 8))
        ttk.Label(detail_frame, text="URL").grid(row=5, column=0, sticky="w", pady=8)
        self.url_entry = ttk.Entry(
            detail_frame,
            textvariable=self.url_var,
            state="readonly",
            cursor="hand2",
        )
        self.url_entry.grid(row=5, column=1, sticky="ew", pady=8)
        self.url_entry.bind("<Button-1>", self._handle_url_click)
        self._add_detail_row(detail_frame, 6, "Created", self.created_var)
        self._add_detail_row(detail_frame, 7, "Updated", self.updated_var)
        ttk.Label(detail_frame, text="Comments").grid(row=8, column=0, sticky="nw", pady=8)
        self.comments_text.grid(row=8, column=1, sticky="nsew", pady=8)
        detail_frame.columnconfigure(1, weight=1)
        detail_frame.rowconfigure(8, weight=1)

        self._start_idle_monitoring()
        self._refresh_secret_tree()

    def _add_detail_row(self, parent, row_index, label_text, variable):
        ttk.Label(parent, text=label_text).grid(row=row_index, column=0, sticky="w", pady=8)
        ttk.Entry(parent, textvariable=variable, state="readonly").grid(
            row=row_index, column=1, sticky="ew", pady=8
        )

    def _refresh_secret_tree(self):
        selected = self.current_secret_name
        for item_id in self.secret_tree.get_children():
            self.secret_tree.delete(item_id)
        records = self.service.get_secret_records(self.search_var.get())
        for secret in records:
            self.secret_tree.insert("", "end", iid=secret.get_name(), text=secret.get_name(), values=(
                secret.get_username(),
                secret.get_url(),
            ))
        if selected and self.secret_tree.exists(selected):
            self.secret_tree.selection_set(selected)
            self.secret_tree.focus(selected)
        elif records:
            first = records[0].get_name()
            self.secret_tree.selection_set(first)
            self.secret_tree.focus(first)
        else:
            self.current_secret_name = None
            self.current_secret_password = ""
            self.current_secret_username = ""
            self.current_password_mask = ""
            self._clear_detail_panel()
        self._render_selected_secret(log_access=False)

    def _handle_secret_selection(self, _event):
        self._render_selected_secret(log_access=True)

    def _render_selected_secret(self, log_access):
        selection = self.secret_tree.selection()
        if not selection:
            self.current_secret_name = None
            self.current_secret_password = ""
            self.current_secret_username = ""
            self.current_password_mask = ""
            self._clear_detail_panel()
            return
        secret = self.service.get_secret(selection[0])
        if secret is None:
            self._clear_detail_panel()
            return
        if log_access:
            self.service.record_secret_view(secret.get_name())
        self.current_secret_name = secret.get_name()
        self.current_secret_password = secret.get_password()
        self.current_secret_username = secret.get_username()
        self.current_password_mask = self._generate_password_mask()
        self.name_var.set(secret.get_name())
        self.username_var.set(secret.get_username() or "-")
        self.url_var.set(secret.get_url() or "-")
        self.created_var.set(self._format_datetime(secret.get_create_date()))
        self.updated_var.set(self._format_datetime(secret.get_update_date()))
        self._set_comments(secret.get_comments() or "")
        self._refresh_password_display()

    def _refresh_password_display(self):
        if not self.current_secret_name:
            self.password_var.set("-")
            return
        if self.show_password_var.get():
            self.password_var.set(self.current_secret_password or "")
            return
        if not self.current_password_mask:
            self.current_password_mask = self._generate_password_mask()
        self.password_var.set(self.current_password_mask)

    def _clear_detail_panel(self):
        for variable in [self.name_var, self.username_var, self.password_var, self.url_var, self.created_var, self.updated_var]:
            variable.set("-")
        self.current_secret_username = ""
        self.current_password_mask = ""
        self._set_comments("")

    def _set_comments(self, value):
        self.comments_text.configure(state="normal")
        self.comments_text.delete("1.0", "end")
        self.comments_text.insert("1.0", value)
        self.comments_text.configure(state="disabled")

    def _add_secret(self):
        dialog = SecretEditorDialog(self, "Add secret", password_factory=self.service.generate_password)
        self.wait_window(dialog)
        if not dialog.result:
            return
        try:
            self.service.add_secret(**dialog.result)
        except Exception as exc:
            messagebox.showerror("Add secret", str(exc), parent=self)
            return
        self.status_var.set(f"Added '{dialog.result['name']}'.")
        self.current_secret_name = dialog.result["name"]
        self._refresh_secret_tree()

    def _bulk_insert_secrets(self):
        dialog = BulkInsertDialog(self)
        self.wait_window(dialog)
        if dialog.result is None:
            return

        try:
            summary = self.service.bulk_insert_secrets(dialog.result)
        except Exception as exc:
            messagebox.showerror("Bulk insert", str(exc), parent=self)
            return

        self.status_var.set(
            f"Bulk insert complete. Added {summary['added']}, skipped blank rows {summary['skipped_blank_rows']}."
        )
        self._refresh_secret_tree()

    def _edit_selected_secret(self):
        secret = self._require_selected_secret()
        if not secret:
            return
        dialog = SecretEditorDialog(
            self,
            "Edit secret",
            secret=secret,
            password_factory=self.service.generate_password,
        )
        self.wait_window(dialog)
        if not dialog.result:
            return
        try:
            self.service.update_secret(
                secret.get_name(),
                dialog.result["name"],
                dialog.result["username"],
                dialog.result["password"],
                dialog.result["url"],
                dialog.result["comments"],
            )
        except Exception as exc:
            messagebox.showerror("Edit secret", str(exc), parent=self)
            return
        self.status_var.set(f"Updated '{dialog.result['name']}'.")
        self.current_secret_name = dialog.result["name"]
        self._refresh_secret_tree()

    def _delete_selected_secret(self):
        secret = self._require_selected_secret()
        if not secret:
            return
        if not messagebox.askyesno(
            "Delete secret",
            f"Delete '{secret.get_name()}' from the local vault?",
            parent=self,
        ):
            return
        self.service.delete_secret(secret.get_name())
        self.status_var.set(f"Deleted '{secret.get_name()}'.")
        self.current_secret_name = None
        self._refresh_secret_tree()

    def _copy_selected_password(self):
        secret = self._require_selected_secret()
        if not secret:
            return
        if not self._copy_text_to_clipboard(secret.get_password()):
            messagebox.showerror(
                "Clipboard unavailable",
                "Clipboard copy is not available on this system.",
                parent=self,
            )
            return
        self.service.record_secret_copy(secret.get_name())
        self.status_var.set(f"Copied password for '{secret.get_name()}' to the clipboard.")
        self._show_transient_popup(f"Password for '{secret.get_name()}' copied to clipboard.")

    def _copy_selected_username(self):
        secret = self._require_selected_secret()
        if not secret:
            return
        if not secret.get_username():
            self.status_var.set(f"'{secret.get_name()}' does not have a username to copy.")
            return
        if not self._copy_text_to_clipboard(secret.get_username()):
            messagebox.showerror(
                "Clipboard unavailable",
                "Clipboard copy is not available on this system.",
                parent=self,
            )
            return
        self.service.record_secret_copy(secret.get_name(), field_name="username")
        self.status_var.set(f"Copied username for '{secret.get_name()}' to the clipboard.")
        self._show_transient_popup(f"Username for '{secret.get_name()}' copied to clipboard.")

    def _handle_password_click(self, _event):
        if self.current_secret_name and self.current_secret_password:
            self._copy_selected_password()
        return "break"

    def _handle_username_click(self, _event):
        if self.current_secret_name and self.current_secret_username:
            self._copy_selected_username()
        return "break"

    def _handle_url_click(self, _event):
        if not self.current_secret_name:
            return "break"
        secret = self._require_selected_secret()
        if not secret or not secret.get_url():
            return "break"
        target_url = self._normalize_url(secret.get_url())
        try:
            webbrowser.open_new_tab(target_url)
        except Exception as exc:
            messagebox.showerror("Open URL", f"Could not open the URL: {exc}", parent=self)
            return "break"
        self.status_var.set(f"Opened URL for '{secret.get_name()}'.")
        return "break"

    def _import_secrets(self):
        source = filedialog.askopenfilename(
            title="Import secrets from CSV or encrypted backup",
            initialdir=str(DEFAULT_EXPORT_CSV.parent),
            filetypes=[
                ("Supported files", "*.csv *.scmbackup"),
                ("CSV files", "*.csv"),
                ("Encrypted backups", "*.scmbackup"),
                ("All files", "*.*"),
            ],
        )
        if not source:
            return
        choice = messagebox.askyesnocancel(
            "Import duplicates",
            "Click Yes to overwrite duplicate names, No to skip duplicates, or Cancel to abort.",
            parent=self,
        )
        if choice is None:
            return
        strategy = "overwrite" if choice else "skip"
        try:
            import_format = self.service.detect_import_format(source)
            if import_format == "encrypted_backup":
                password_dialog = BackupPasswordDialog(
                    self,
                    "Import encrypted backup",
                    action_label="Import",
                    require_confirmation=False,
                    allow_generate=False,
                )
                self.wait_window(password_dialog)
                if not password_dialog.result:
                    return
                summary = self.service.import_encrypted_backup(
                    source,
                    password_dialog.result["password"],
                    conflict_strategy=strategy,
                )
            else:
                summary = self.service.import_secrets(source, conflict_strategy=strategy)
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc), parent=self)
            return
        self.status_var.set(
            f"Import complete. Added {summary['imported']}, overwritten {summary['overwritten']}, skipped {summary['skipped']}."
        )
        self._refresh_secret_tree()

    def _export_secrets(self):
        target = filedialog.asksaveasfilename(
            title="Export secrets to CSV",
            initialdir=str(DEFAULT_EXPORT_CSV.parent),
            initialfile=DEFAULT_EXPORT_CSV.name,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not target:
            return
        if not messagebox.askyesno(
            "Plaintext export warning",
            "This will write plaintext secrets to disk. Continue?",
            parent=self,
        ):
            return
        try:
            self.service.export_secrets(Path(target), overwrite=True)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        self.status_var.set(f"Exported secrets to {target}.")

    def _export_encrypted_backup(self):
        target = filedialog.asksaveasfilename(
            title="Export encrypted backup",
            initialdir=str(DEFAULT_ENCRYPTED_BACKUP.parent),
            initialfile=DEFAULT_ENCRYPTED_BACKUP.name,
            defaultextension=ENCRYPTED_BACKUP_FILE_EXTENSION,
            filetypes=[
                ("Encrypted backups", f"*{ENCRYPTED_BACKUP_FILE_EXTENSION}"),
                ("All files", "*.*"),
            ],
        )
        if not target:
            return

        password_dialog = BackupPasswordDialog(
            self,
            "Export encrypted backup",
            action_label="Export",
            require_confirmation=True,
            allow_generate=True,
        )
        self.wait_window(password_dialog)
        if not password_dialog.result:
            return

        try:
            self.service.export_encrypted_backup(
                Path(target),
                password_dialog.result["password"],
                overwrite=True,
            )
        except Exception as exc:
            messagebox.showerror("Backup export failed", str(exc), parent=self)
            return
        self.status_var.set(f"Exported encrypted backup to {target}.")

    def _change_master_password(self):
        dialog = MasterPasswordDialog(self)
        self.wait_window(dialog)
        if not dialog.result:
            return
        try:
            self.service.change_master_password(
                dialog.result["current_password"],
                dialog.result["new_password"],
                dialog.result["confirm_password"],
            )
        except Exception as exc:
            messagebox.showerror("Change master password", str(exc), parent=self)
            return
        messagebox.showinfo(
            "Master password changed",
            "Your master password has been updated successfully.",
            parent=self,
        )
        self.status_var.set("Master password changed successfully.")

    def _lock_and_return_to_login(self):
        self._stop_idle_monitoring()
        self.service.lock_vault()
        self.current_secret_name = None
        self.current_secret_password = ""
        self.current_secret_username = ""
        self._show_login_screen()

    def _require_selected_secret(self):
        if not self.current_secret_name:
            messagebox.showinfo("Select a secret", "Choose a secret first.", parent=self)
            return None
        return self.service.get_secret(self.current_secret_name)

    def _show_error_screen(self, title, message, details):
        self._clear_content()
        self._stop_idle_monitoring()
        self.status_var.set("")
        ttk.Label(self.content, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.content, text=message, style="Subtitle.TLabel", wraplength=900).pack(anchor="w", pady=(8, 16))
        if details:
            detail_box = tk.Text(self.content, height=12, wrap="word")
            detail_box.pack(fill="both", expand=True)
            detail_box.insert("1.0", "\n".join(f"{index}. {line}" for index, line in enumerate(details, start=1)))
            detail_box.configure(state="disabled")
        ttk.Label(
            self.content,
            text=f"If this looks wrong, raise it with the developer at {BUG_REPORT_URL}.",
            wraplength=900,
        ).pack(anchor="w", pady=(16, 0))
        ttk.Button(self.content, text="Quit", command=self.destroy).pack(anchor="e", pady=(16, 0))

    def _format_datetime(self, value):
        if not value:
            return "-"
        return value.strftime("%Y-%m-%d %H:%M:%S")

    def _show_transient_popup(self, message):
        if self.toast_popup is not None and self.toast_popup.winfo_exists():
            self.toast_popup.destroy()

        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        try:
            popup.attributes("-topmost", True)
        except tk.TclError:
            pass

        label = ttk.Label(popup, text=message, padding=(14, 10))
        label.pack()

        popup.update_idletasks()
        x_position = self.winfo_rootx() + self.winfo_width() - popup.winfo_width() - 24
        y_position = self.winfo_rooty() + 24
        popup.geometry(f"+{x_position}+{y_position}")
        popup.after(1600, popup.destroy)
        self.toast_popup = popup

    def _copy_text_to_clipboard(self, value):
        clipboard_text = "" if value is None else str(value)
        try:
            self.clipboard_clear()
            self.clipboard_append(clipboard_text)
            return True
        except tk.TclError:
            return copy_to_clipboard(clipboard_text)

    def _start_release_check(self):
        threading.Thread(target=self._load_release_status, daemon=True).start()

    def _load_release_status(self):
        release_status = self.release_update_service.check_for_updates()
        try:
            self.after(0, lambda: self._apply_release_status(release_status))
        except tk.TclError:
            return

    def _apply_release_status(self, release_status):
        self.release_status = release_status
        indicator = self.release_update_service.get_release_indicator(release_status)
        style_name = {
            "normal": "FooterVersion.TLabel",
            "update": "FooterVersionWarning.TLabel",
            "stale": "FooterVersionStale.TLabel",
        }[indicator]
        self.version_label.configure(style=style_name)

        if release_status.get("update_available") and not self.release_prompt_shown:
            self.release_prompt_shown = True
            latest_version = release_status.get("latest_version_label") or "A newer version"
            if messagebox.askyesno(
                "Update available",
                (
                    f"{latest_version} is available.\n\n"
                    "Do you want to download and install it now?"
                ),
                parent=self,
            ):
                self._start_update_install()

    def _open_release_link(self, _event=None, download_preferred=False):
        target_url = None
        if download_preferred:
            target_url = self.release_status.get("download_url")
        if not target_url:
            target_url = self.release_status.get("release_url") or APP_RELEASES_URL
        webbrowser.open_new_tab(target_url)

    def _start_update_install(self):
        if self.update_install_in_progress:
            return
        latest_version = self.release_status.get("latest_version_label") or "the latest version"
        self.update_install_in_progress = True
        self.status_var.set(f"Installing {latest_version}...")
        threading.Thread(target=self._install_update, name="release-update-install").start()

    def _install_update(self):
        try:
            result = self.release_update_service.install_update(self.release_status)
        except ReleaseUpdateError as exc:
            error_message = str(exc)
            self._queue_ui_callback(
                lambda error_message=error_message: self._handle_update_install_failure(error_message)
            )
            return
        except Exception as exc:
            error_message = str(exc)
            self._queue_ui_callback(
                lambda error_message=error_message: self._handle_update_install_failure(error_message)
            )
            return

        self._queue_ui_callback(lambda: self._handle_update_install_success(result))

    def _handle_update_install_success(self, result):
        self.update_install_in_progress = False
        latest_version = result.get("latest_version_label") or "the latest version"
        self.release_status = dict(self.release_status, update_available=False)
        self.version_label.configure(style="FooterVersion.TLabel")
        self.status_var.set(f"Installed {latest_version}. Restart the app to use the updated version.")
        messagebox.showinfo(
            "Update installed",
            (
                f"{latest_version} has been installed in place.\n\n"
                "Restart the application to start using the updated version."
            ),
            parent=self,
        )

    def _handle_update_install_failure(self, error_message):
        self.update_install_in_progress = False
        self.status_var.set("Automatic update failed.")
        if messagebox.askyesno(
            "Update failed",
            (
                "The application could not install the update automatically.\n\n"
                f"{error_message}\n\n"
                "Do you want to open the GitHub download page instead?"
            ),
            parent=self,
        ):
            self._open_release_link(download_preferred=True)

    def _queue_ui_callback(self, callback):
        try:
            self.after(0, callback)
        except tk.TclError:
            return

    def _start_idle_monitoring(self):
        self.idle_monitoring_enabled = True
        self.last_activity_timestamp = time.monotonic()
        self._schedule_idle_check()

    def _stop_idle_monitoring(self):
        self.idle_monitoring_enabled = False
        if self.idle_check_id is not None:
            self.after_cancel(self.idle_check_id)
            self.idle_check_id = None

    def _schedule_idle_check(self):
        if self.idle_check_id is not None:
            self.after_cancel(self.idle_check_id)
        self.idle_check_id = self.after(1000, self._check_idle_timeout)

    def _record_user_activity(self, _event=None):
        if not self.idle_monitoring_enabled or not self.service.is_unlocked():
            return
        self.last_activity_timestamp = time.monotonic()

    def _check_idle_timeout(self):
        self.idle_check_id = None
        if not self.idle_monitoring_enabled:
            return
        if not self.service.is_unlocked():
            self._stop_idle_monitoring()
            return
        if time.monotonic() - self.last_activity_timestamp >= SESSION_IDLE_LOCK_SECONDS:
            self._lock_due_to_inactivity()
            return
        self._schedule_idle_check()

    def _lock_due_to_inactivity(self):
        self._stop_idle_monitoring()
        self._close_auxiliary_windows()
        self.service.lock_vault()
        self.current_secret_name = None
        self.current_secret_password = ""
        self.current_secret_username = ""
        self.current_password_mask = ""
        self._show_login_screen()
        self.status_var.set("Vault locked after 1 minute of inactivity.")
        messagebox.showinfo(
            "Vault locked",
            "The vault was locked after 1 minute of inactivity.",
            parent=self,
        )

    def _close_auxiliary_windows(self):
        for child in self.winfo_children():
            if isinstance(child, tk.Toplevel):
                try:
                    child.destroy()
                except tk.TclError:
                    pass
        self.toast_popup = None

    def _normalize_url(self, value):
        url = (value or "").strip()
        if not url:
            return ""
        parsed = urlparse(url)
        if parsed.scheme:
            return url
        return f"https://{url}"

    def _generate_password_mask(self):
        if not self.current_secret_password:
            return ""
        return "*" * (12 + randbelow(9))

    def _handle_close(self):
        if self.update_install_in_progress:
            messagebox.showinfo(
                "Update in progress",
                "Please wait for the automatic update to finish before closing the application.",
                parent=self,
            )
            return
        self._stop_idle_monitoring()
        self.service.lock_vault()
        self.destroy()


def main():
    app = SimpleCredentialManagerUi()
    app.mainloop()


if __name__ == "__main__":
    main()
