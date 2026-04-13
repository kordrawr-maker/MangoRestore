from core.settings import Settings
import customtkinter as ctk

# Load settings before building the UI so appearance applies immediately
_settings = Settings()
ctk.set_appearance_mode(_settings.get("appearance", "dark"))
ctk.set_default_color_theme(_settings.get("color_theme", "blue"))

from ui.app import DiscordBackupApp

if __name__ == "__main__":
    app = DiscordBackupApp()
    app.mainloop()
