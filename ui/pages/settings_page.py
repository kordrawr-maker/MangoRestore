import os
import customtkinter as ctk
from tkinter import filedialog


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Settings", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 16)
        )

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        row = 0

        # --- Appearance ---
        row = self._section(scroll, row, "Appearance")

        row = self._label_row(scroll, row, "Theme", "Controls the app's color scheme")
        self.theme_var = ctk.StringVar(value=app.settings.get("appearance", "dark").capitalize())
        ctk.CTkSegmentedButton(
            scroll, values=["Dark", "Light", "System"],
            variable=self.theme_var,
            command=self._apply_theme,
        ).grid(row=row, column=0, sticky="w", padx=16, pady=(0, 12))
        row += 1

        row = self._label_row(scroll, row, "Accent Color", "Button and highlight color")
        self.accent_var = ctk.StringVar(value=app.settings.get("color_theme", "blue").capitalize())
        ctk.CTkSegmentedButton(
            scroll, values=["Blue", "Green", "Dark-Blue"],
            variable=self.accent_var,
            command=self._apply_accent,
        ).grid(row=row, column=0, sticky="w", padx=16, pady=(0, 12))
        row += 1

        # --- Storage ---
        row = self._section(scroll, row, "Storage")

        row = self._label_row(scroll, row, "Default backup folder", "Where backups are saved")
        dir_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        dir_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 12))
        dir_frame.grid_columnconfigure(0, weight=1)
        self.dir_var = ctk.StringVar(value=app.settings.get("save_dir"))
        ctk.CTkEntry(dir_frame, textvariable=self.dir_var, height=34).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(dir_frame, text="Browse", width=80, height=34, command=self._browse_dir).grid(row=0, column=1, padx=(6, 0))
        row += 1

        row = self._label_row(scroll, row, "Max backups to keep", "Older backups are deleted automatically (0 = keep all)")
        self.max_var = ctk.StringVar(value=str(app.settings.get("max_backups_to_keep", 10)))
        ctk.CTkEntry(scroll, textvariable=self.max_var, width=80, height=34).grid(row=row, column=0, sticky="w", padx=16, pady=(0, 12))
        row += 1

        # --- Auto Backup ---
        row = self._section(scroll, row, "Auto Backup")

        row = self._label_row(scroll, row, "Enable scheduled backups", "Automatically back up on a timer while the app is open")
        self.auto_var = ctk.BooleanVar(value=app.settings.get("auto_backup_enabled", False))
        auto_switch = ctk.CTkSwitch(scroll, text="", variable=self.auto_var, onvalue=True, offvalue=False,
                                     command=self._toggle_auto)
        auto_switch.grid(row=row, column=0, sticky="w", padx=16, pady=(0, 4))
        row += 1

        row = self._label_row(scroll, row, "Backup interval", "How often to run an automatic backup")
        self.interval_var = ctk.StringVar(value=str(app.settings.get("auto_backup_interval_hours", 24)))
        interval_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        interval_frame.grid(row=row, column=0, sticky="w", padx=16, pady=(0, 12))
        ctk.CTkEntry(interval_frame, textvariable=self.interval_var, width=60, height=34).grid(row=0, column=0)
        ctk.CTkLabel(interval_frame, text="hours", text_color="gray").grid(row=0, column=1, padx=(8, 0))
        row += 1

        row = self._label_row(scroll, row, "Server to auto-backup", "")
        self.auto_guild_var = ctk.StringVar(value=app.settings.get("auto_backup_guild_name") or "Select after verifying token")
        self.auto_guild_menu = ctk.CTkOptionMenu(
            scroll, variable=self.auto_guild_var,
            values=["Verify token first"], width=260, dynamic_resizing=False,
        )
        self.auto_guild_menu.grid(row=row, column=0, sticky="w", padx=16, pady=(0, 12))
        row += 1

        # Auto-backup status display
        self.auto_status_label = ctk.CTkLabel(scroll, text="", font=ctk.CTkFont(size=12), text_color="gray")
        self.auto_status_label.grid(row=row, column=0, sticky="w", padx=16, pady=(0, 8))
        row += 1

        # --- Defaults ---
        row = self._section(scroll, row, "Backup Defaults")

        row = self._label_row(scroll, row, "Include messages by default", "Pre-check the message history option")
        self.msg_default_var = ctk.BooleanVar(value=app.settings.get("include_messages_default", False))
        ctk.CTkSwitch(scroll, text="", variable=self.msg_default_var, onvalue=True, offvalue=False).grid(
            row=row, column=0, sticky="w", padx=16, pady=(0, 12)
        )
        row += 1

        # --- Save button ---
        ctk.CTkButton(
            scroll, text="Save Settings", height=40,
            fg_color="#5865F2", hover_color="#4752c4",
            command=self._save,
        ).grid(row=row, column=0, sticky="w", padx=16, pady=(8, 24))

        self._auto_update_status()

    def on_show(self):
        guilds = self.app.guilds
        if guilds:
            names = [g["name"] for g in guilds]
            self.auto_guild_menu.configure(values=names)
            saved = self.app.settings.get("auto_backup_guild_name")
            if saved and saved in names:
                self.auto_guild_var.set(saved)
            else:
                self.auto_guild_var.set(names[0])

    def _section(self, parent, row, title):
        if row > 0:
            ctk.CTkFrame(parent, height=1, fg_color=("gray70", "gray30")).grid(
                row=row, column=0, sticky="ew", padx=16, pady=(8, 0)
            )
            row += 1
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=15, weight="bold"), anchor="w").grid(
            row=row, column=0, sticky="w", padx=16, pady=(12, 4)
        )
        return row + 1

    def _label_row(self, parent, row, title, subtitle):
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=13), anchor="w").grid(
            row=row, column=0, sticky="w", padx=16, pady=(4, 0)
        )
        row += 1
        if subtitle:
            ctk.CTkLabel(parent, text=subtitle, text_color="gray", font=ctk.CTkFont(size=11), anchor="w").grid(
                row=row, column=0, sticky="w", padx=16, pady=(0, 2)
            )
            row += 1
        return row

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get())
        if d:
            self.dir_var.set(d)

    def _apply_theme(self, value):
        ctk.set_appearance_mode(value.lower())

    def _apply_accent(self, value):
        ctk.set_default_color_theme(value.lower())

    def _toggle_auto(self):
        enabled = self.auto_var.get()
        token = self.app.bot_token.get().strip()
        if enabled and token:
            self._save_auto_settings()
            self.app.scheduler.start(token)
        elif not enabled:
            self.app.scheduler.stop()
        self._auto_update_status()

    def _auto_update_status(self):
        if self.app.scheduler.is_running:
            nxt = self.app.scheduler.next_run
            if nxt:
                self.auto_status_label.configure(
                    text=f"✓ Running — next backup at {nxt.strftime('%H:%M:%S')}",
                    text_color="#57f287"
                )
            else:
                self.auto_status_label.configure(text="✓ Scheduler running", text_color="#57f287")
        else:
            self.auto_status_label.configure(text="Scheduler is off", text_color="gray")
        self.after(5000, self._auto_update_status)

    def _save_auto_settings(self):
        guild_name = self.auto_guild_var.get()
        guild = next((g for g in self.app.guilds if g["name"] == guild_name), None)
        self.app.settings.update({
            "auto_backup_guild_id": guild["id"] if guild else None,
            "auto_backup_guild_name": guild_name if guild else None,
            "auto_backup_interval_hours": int(self.interval_var.get() or 24),
        })

    def _save(self):
        try:
            max_keep = int(self.max_var.get())
        except ValueError:
            max_keep = 10
        try:
            interval = int(self.interval_var.get())
        except ValueError:
            interval = 24

        self._save_auto_settings()
        self.app.settings.update({
            "save_dir": self.dir_var.get(),
            "appearance": self.theme_var.get().lower(),
            "color_theme": self.accent_var.get().lower(),
            "auto_backup_enabled": self.auto_var.get(),
            "auto_backup_interval_hours": interval,
            "max_backups_to_keep": max_keep,
            "include_messages_default": self.msg_default_var.get(),
        })

        # Update save dir on backup page
        try:
            self.app.pages["backup"].dir_var.set(self.dir_var.get())
        except Exception:
            pass

        self.auto_status_label.configure(text="✓ Saved!", text_color="#57f287")
        self.after(2000, self._auto_update_status)
