import customtkinter as ctk
from core.settings import Settings
from core.scheduler import AutoBackupScheduler
from ui.sidebar import Sidebar
from ui.pages.token_page import TokenPage
from ui.pages.backup_page import BackupPage
from ui.pages.restore_page import RestorePage
from ui.pages.archives_page import ArchivesPage
from ui.pages.settings_page import SettingsPage
from ui.pages.diff_page import DiffPage


class DiscordBackupApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MangoRestore")
        self.geometry("940x660")
        self.minsize(820, 580)

        # Load settings first
        self.settings = Settings()

        # Apply saved appearance
        ctk.set_appearance_mode(self.settings.get("appearance", "dark"))
        ctk.set_default_color_theme(self.settings.get("color_theme", "blue"))

        # Shared state
        self.bot_token = ctk.StringVar(value=self.settings.get("token", ""))
        self.guilds = []

        # Auto-backup scheduler
        self.scheduler = AutoBackupScheduler(
            self.settings,
            log_callback=self._scheduler_log,
        )

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(self, self._show_page)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Pages
        self.pages = {
            "token":    TokenPage(self.content_frame, self),
            "backup":   BackupPage(self.content_frame, self),
            "restore":  RestorePage(self.content_frame, self),
            "archives": ArchivesPage(self.content_frame, self),
            "diff":     DiffPage(self.content_frame, self),
            "settings": SettingsPage(self.content_frame, self),
        }

        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        # Restore saved backup dir default
        saved_dir = self.settings.get("save_dir")
        if saved_dir:
            try:
                self.pages["backup"].dir_var.set(saved_dir)
            except Exception:
                pass

        if self.settings.get("include_messages_default"):
            try:
                self.pages["backup"].opt_messages.select()
            except Exception:
                pass

        self._show_page("token")

        # Auto-restart scheduler if it was enabled
        if self.settings.get("auto_backup_enabled") and self.bot_token.get().strip():
            self.after(2000, self._maybe_restart_scheduler)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _show_page(self, name: str):
        for page in self.pages.values():
            page.grid_remove()
        self.pages[name].grid()
        self.pages[name].on_show()
        self.sidebar.set_active(name)

    def _scheduler_log(self, msg: str):
        try:
            self.pages["backup"].log_box.write(msg)
        except Exception:
            pass

    def _maybe_restart_scheduler(self):
        token = self.bot_token.get().strip()
        if token and self.settings.get("auto_backup_enabled"):
            self.scheduler.start(token)

    def _on_close(self):
        self.settings.set("token", self.bot_token.get().strip())
        self.scheduler.stop()
        self.destroy()
