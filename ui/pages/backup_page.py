import asyncio
import os
import threading
import customtkinter as ctk
from tkinter import filedialog
from core.backup import BackupEngine
from ui.log_box import LogBox

DEFAULT_SAVE_DIR = os.path.join(os.path.expanduser("~"), "Discord Backups")


class BackupPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._running = False

        # Title
        ctk.CTkLabel(self, text="Create Backup", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 12))

        # ── Settings card ──────────────────────────────────────────────
        card = ctk.CTkFrame(self, corner_radius=12)
        card.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        card.grid_columnconfigure(1, weight=1)

        # Server selector
        ctk.CTkLabel(card, text="Server", font=ctk.CTkFont(size=13), anchor="w").grid(
            row=0, column=0, padx=16, pady=(14, 4), sticky="w")
        self.server_var = ctk.StringVar(value="Verify token first…")
        self.server_menu = ctk.CTkOptionMenu(
            card, variable=self.server_var,
            values=["Verify token first"], width=300, dynamic_resizing=False)
        self.server_menu.grid(row=0, column=1, padx=16, pady=(14, 4), sticky="w")

        # Save dir
        ctk.CTkLabel(card, text="Save to", font=ctk.CTkFont(size=13), anchor="w").grid(
            row=1, column=0, padx=16, pady=4, sticky="w")
        dir_row = ctk.CTkFrame(card, fg_color="transparent")
        dir_row.grid(row=1, column=1, padx=16, pady=4, sticky="ew")
        dir_row.grid_columnconfigure(0, weight=1)
        self.dir_var = ctk.StringVar(value=DEFAULT_SAVE_DIR)
        ctk.CTkEntry(dir_row, textvariable=self.dir_var, height=34).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(dir_row, text="Browse", width=76, height=34, command=self._browse).grid(row=0, column=1, padx=(6, 0))

        # ── What to back up ────────────────────────────────────────────
        sep = ctk.CTkFrame(card, height=1, fg_color=("gray70", "gray30"))
        sep.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(10, 0))

        ctk.CTkLabel(card, text="What to back up", font=ctk.CTkFont(size=13, weight="bold"), anchor="w").grid(
            row=3, column=0, columnspan=2, padx=16, pady=(8, 4), sticky="w")

        opts = ctk.CTkFrame(card, fg_color="transparent")
        opts.grid(row=4, column=0, columnspan=2, padx=16, pady=(0, 14), sticky="w")

        def chk(parent, text, row, col, default=True):
            var = ctk.CTkCheckBox(parent, text=text)
            if default:
                var.select()
            var.grid(row=row, column=col, sticky="w", padx=(0, 24), pady=3)
            return var

        self.opt_roles    = chk(opts, "Roles & permissions",      0, 0)
        self.opt_channels = chk(opts, "Channels & categories",    0, 1)
        self.opt_settings = chk(opts, "Server settings & images", 1, 0)
        self.opt_emojis   = chk(opts, "Custom emojis",            1, 1)
        self.opt_stickers = chk(opts, "Stickers",                 2, 0)
        self.opt_events   = chk(opts, "Scheduled events",         2, 1)
        self.opt_webhooks = chk(opts, "Webhooks",                 3, 0)
        self.opt_soundboard = chk(opts, "Soundboard sounds",      3, 1)

        # Messages (off by default, has limit field)
        msg_row = ctk.CTkFrame(opts, fg_color="transparent")
        msg_row.grid(row=4, column=0, columnspan=2, sticky="w", pady=3)
        self.opt_messages = ctk.CTkCheckBox(msg_row, text="Message history (last")
        self.opt_messages.grid(row=0, column=0, sticky="w")
        self.msg_limit_var = ctk.StringVar(value="100")
        ctk.CTkEntry(msg_row, textvariable=self.msg_limit_var, width=52, height=26).grid(
            row=0, column=1, padx=6)
        ctk.CTkLabel(msg_row, text="per channel)", text_color="gray").grid(row=0, column=2)

        # ── Start button ───────────────────────────────────────────────
        self.backup_btn = ctk.CTkButton(
            self, text="▶  Start Full Backup", height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#5865F2", hover_color="#4752c4",
            command=self._start)
        self.backup_btn.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        self.progress = ctk.CTkProgressBar(self, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(52, 0))
        self.progress.grid_remove()

        # Log
        self.log_box = LogBox(self, corner_radius=10)
        self.log_box.grid(row=3, column=0, sticky="nsew")

    def on_show(self):
        guilds = self.app.guilds
        if guilds:
            names = [g["name"] for g in guilds]
            self.server_menu.configure(values=names)
            if self.server_var.get() not in names:
                self.server_var.set(names[0])
        else:
            self.server_menu.configure(values=["Verify token first"])
            self.server_var.set("Verify token first")

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get())
        if d:
            self.dir_var.set(d)

    def _start(self):
        if self._running:
            return
        token = self.app.bot_token.get().strip()
        if not token:
            self.log_box.write("No bot token — go to Token page first.")
            return
        guild_name = self.server_var.get()
        guild = next((g for g in self.app.guilds if g["name"] == guild_name), None)
        if not guild:
            self.log_box.write("Select a valid server first.")
            return

        save_dir = self.dir_var.get()
        os.makedirs(save_dir, exist_ok=True)

        try:
            msg_limit = int(self.msg_limit_var.get())
        except ValueError:
            msg_limit = 100

        options = {
            "roles":       self.opt_roles.get() == 1,
            "channels":    self.opt_channels.get() == 1,
            "settings":    self.opt_settings.get() == 1,
            "emojis":      self.opt_emojis.get() == 1,
            "stickers":    self.opt_stickers.get() == 1,
            "events":      self.opt_events.get() == 1,
            "webhooks":    self.opt_webhooks.get() == 1,
            "soundboard":  self.opt_soundboard.get() == 1,
            "messages":    self.opt_messages.get() == 1,
            "message_limit": msg_limit,
        }

        self._running = True
        self.backup_btn.configure(state="disabled", text="Backing up…")
        self.progress.grid()
        self.progress.start()
        self.log_box.clear()

        threading.Thread(target=self._run, args=(token, guild["id"], save_dir, options), daemon=True).start()

    def _run(self, token, guild_id, save_dir, options):
        async def go():
            engine = BackupEngine(token, lambda m: self.after(0, self.log_box.write, m))
            return await engine.backup_guild(guild_id, save_dir, options)
        loop = asyncio.new_event_loop()
        try:
            path = loop.run_until_complete(go())
            self.after(0, self._done, f"\n✅ Saved to: {path}")
        except Exception as e:
            self.after(0, self._done, f"\n❌ Error: {e}")
        finally:
            loop.close()

    def _done(self, msg):
        self.log_box.write(msg)
        self.progress.stop()
        self.progress.grid_remove()
        self.backup_btn.configure(state="normal", text="▶  Start Full Backup")
        self._running = False
