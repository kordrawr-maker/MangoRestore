import asyncio
import os
import threading
import zipfile
import json
import customtkinter as ctk
from tkinter import filedialog, messagebox
from core.restore import RestoreEngine
from ui.log_box import LogBox


class RestorePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        self._running = False
        self._archive_path = None

        # Title
        ctk.CTkLabel(self, text="Restore Backup", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 12))

        # ── Archive picker ─────────────────────────────────────────────
        pick_card = ctk.CTkFrame(self, corner_radius=12)
        pick_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        pick_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(pick_card, text="Backup file", font=ctk.CTkFont(size=13), anchor="w").grid(
            row=0, column=0, padx=16, pady=(14, 4), sticky="w")
        file_row = ctk.CTkFrame(pick_card, fg_color="transparent")
        file_row.grid(row=0, column=1, padx=16, pady=(14, 4), sticky="ew")
        file_row.grid_columnconfigure(0, weight=1)
        self.file_var = ctk.StringVar(value="No file selected")
        ctk.CTkEntry(file_row, textvariable=self.file_var, height=34, state="disabled").grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(file_row, text="Browse", width=76, height=34, command=self._browse).grid(row=0, column=1, padx=(6, 0))

        # Backup info strip (hidden until file loaded)
        self.info_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=("#16213e", "#16213e"))
        self.info_frame.grid_columnconfigure(0, weight=1)
        self._info_labels = {}
        for i, key in enumerate(["name", "date", "stats"]):
            lbl = ctk.CTkLabel(self.info_frame, text="", anchor="w",
                               font=ctk.CTkFont(size=14 if key == "name" else 12,
                                                weight="bold" if key == "name" else "normal"))
            lbl.grid(row=i, column=0, sticky="w", padx=16,
                     pady=(12 if key == "name" else 1, 10 if key == "stats" else 0))
            self._info_labels[key] = lbl

        # ── Restore options ────────────────────────────────────────────
        opts_card = ctk.CTkFrame(self, corner_radius=12)
        opts_card.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        opts_card.grid_columnconfigure(1, weight=1)

        # Target server
        ctk.CTkLabel(opts_card, text="Restore to", font=ctk.CTkFont(size=13), anchor="w").grid(
            row=0, column=0, padx=16, pady=(14, 4), sticky="w")
        self.target_var = ctk.StringVar(value="Verify token first…")
        self.target_menu = ctk.CTkOptionMenu(
            opts_card, variable=self.target_var, values=["Verify token first"], width=280, dynamic_resizing=False)
        self.target_menu.grid(row=0, column=1, padx=16, pady=(14, 4), sticky="w")

        # What to restore
        sep = ctk.CTkFrame(opts_card, height=1, fg_color=("gray70", "gray30"))
        sep.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 0))
        ctk.CTkLabel(opts_card, text="What to restore", font=ctk.CTkFont(size=13, weight="bold"), anchor="w").grid(
            row=2, column=0, columnspan=2, padx=16, pady=(8, 4), sticky="w")

        chk_frame = ctk.CTkFrame(opts_card, fg_color="transparent")
        chk_frame.grid(row=3, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="w")

        def chk(text, row, col, default=True):
            cb = ctk.CTkCheckBox(chk_frame, text=text)
            if default:
                cb.select()
            cb.grid(row=row, column=col, sticky="w", padx=(0, 24), pady=3)
            return cb

        self.r_settings  = chk("Server name & settings",    0, 0)
        self.r_roles     = chk("Roles & permissions",        0, 1)
        self.r_channels  = chk("Channels & categories",      1, 0)
        self.r_emojis    = chk("Custom emojis",              1, 1)
        self.r_stickers  = chk("Stickers",                   2, 0)
        self.r_events    = chk("Scheduled events",           2, 1)
        self.r_webhooks  = chk("Webhooks",                   3, 0)

        # Wipe options (danger zone)
        sep2 = ctk.CTkFrame(opts_card, height=1, fg_color=("gray70", "gray30"))
        sep2.grid(row=4, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 0))
        ctk.CTkLabel(opts_card, text="⚠  Clean slate options",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#faa61a", anchor="w").grid(
            row=5, column=0, columnspan=2, padx=16, pady=(8, 4), sticky="w")
        ctk.CTkLabel(opts_card, text="Delete existing content before restoring. Cannot be undone.",
                     text_color="gray", font=ctk.CTkFont(size=11), anchor="w").grid(
            row=6, column=0, columnspan=2, padx=16, pady=(0, 4), sticky="w")

        wipe_frame = ctk.CTkFrame(opts_card, fg_color="transparent")
        wipe_frame.grid(row=7, column=0, columnspan=2, padx=16, pady=(0, 14), sticky="w")
        self.w_channels = ctk.CTkCheckBox(wipe_frame, text="Delete existing channels first", text_color="#faa61a")
        self.w_channels.grid(row=0, column=0, sticky="w", padx=(0, 24), pady=3)
        self.w_roles = ctk.CTkCheckBox(wipe_frame, text="Delete existing roles first", text_color="#faa61a")
        self.w_roles.grid(row=0, column=1, sticky="w", pady=3)

        # ── Restore button ─────────────────────────────────────────────
        self.restore_btn = ctk.CTkButton(
            self, text="♻  Start Full Restore", height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#57f287", hover_color="#3ba864", text_color="#000000",
            command=self._confirm)
        self.restore_btn.grid(row=4, column=0, sticky="ew", pady=(0, 6))

        self.progress = ctk.CTkProgressBar(self, mode="indeterminate")
        self.progress.grid(row=4, column=0, sticky="ew", pady=(52, 0))
        self.progress.grid_remove()

        # Log
        self.log_box = LogBox(self, corner_radius=10)
        self.log_box.grid(row=5, column=0, sticky="nsew")
        self.grid_rowconfigure(5, weight=1)

    def on_show(self):
        guilds = self.app.guilds
        if guilds:
            names = [g["name"] for g in guilds]
            self.target_menu.configure(values=names)
            if self.target_var.get() not in names:
                self.target_var.set(names[0])

    def _browse(self):
        initial = self.app.settings.get("save_dir", os.path.expanduser("~")) if hasattr(self.app, "settings") else os.path.expanduser("~")
        path = filedialog.askopenfilename(
            title="Select backup archive",
            filetypes=[("Discord Backup", "*.dbak"), ("All files", "*.*")],
            initialdir=initial)
        if path:
            self._load_info(path)

    def _load_info(self, path):
        try:
            with zipfile.ZipFile(path, "r") as zf:
                with zf.open("backup.json") as f:
                    data = json.loads(f.read())

            self._archive_path = path
            self.file_var.set(os.path.basename(path))
            meta = data.get("meta", {})
            ch = data.get("channels", [])
            roles = [r for r in data.get("roles", []) if not r.get("everyone")]
            emojis = data.get("emojis", [])
            stickers = data.get("stickers", [])
            webhooks = data.get("webhooks", [])
            events = data.get("scheduled_events", [])

            self._info_labels["name"].configure(text=f"📦  {meta.get('name', 'Unknown')}")
            self._info_labels["date"].configure(
                text=f"Backed up: {meta.get('backed_up_at', '')[:19].replace('T', ' ')}   |   Tool v{meta.get('tool_version', '?')}")
            self._info_labels["stats"].configure(
                text=f"{len(ch)} channels  ·  {len(roles)} roles  ·  {len(emojis)} emojis  ·  {len(stickers)} stickers  ·  {len(webhooks)} webhooks  ·  {len(events)} events")

            self.info_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        except Exception as e:
            messagebox.showerror("Invalid archive", str(e))

    def _confirm(self):
        if not self._archive_path:
            self.log_box.write("Select a backup file first.")
            return
        warns = []
        if self.w_channels.get():
            warns.append("• Delete ALL existing channels")
        if self.w_roles.get():
            warns.append("• Delete ALL existing roles")
        if warns:
            if not messagebox.askyesno("⚠ Confirm", "\n".join(warns) + "\n\nThis CANNOT be undone. Continue?", icon="warning"):
                return
        self._start_restore()

    def _start_restore(self):
        token = self.app.bot_token.get().strip()
        if not token:
            self.log_box.write("No bot token.")
            return
        guild_name = self.target_var.get()
        guild = next((g for g in self.app.guilds if g["name"] == guild_name), None)
        if not guild:
            self.log_box.write("Select a valid server.")
            return

        options = {
            "settings":     self.r_settings.get() == 1,
            "roles":        self.r_roles.get() == 1,
            "channels":     self.r_channels.get() == 1,
            "emojis":       self.r_emojis.get() == 1,
            "stickers":     self.r_stickers.get() == 1,
            "events":       self.r_events.get() == 1,
            "webhooks":     self.r_webhooks.get() == 1,
            "wipe_channels": self.w_channels.get() == 1,
            "wipe_roles":   self.w_roles.get() == 1,
        }

        self._running = True
        self.restore_btn.configure(state="disabled", text="Restoring…")
        self.progress.grid()
        self.progress.start()
        self.log_box.clear()

        threading.Thread(target=self._run, args=(token, guild["id"], self._archive_path, options), daemon=True).start()

    def _run(self, token, guild_id, path, options):
        async def go():
            engine = RestoreEngine(token, lambda m: self.after(0, self.log_box.write, m))
            await engine.restore_guild(guild_id, path, options)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(go())
            self.after(0, self._done, "\n✅ Restore finished!")
        except Exception as e:
            self.after(0, self._done, f"\n❌ Error: {e}")
        finally:
            loop.close()

    def _done(self, msg):
        self.log_box.write(msg)
        self.progress.stop()
        self.progress.grid_remove()
        self.restore_btn.configure(state="normal", text="♻  Start Full Restore")
        self._running = False
