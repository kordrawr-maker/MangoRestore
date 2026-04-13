import json
import os

SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".discord_backup_settings.json")

DEFAULTS = {
    "save_dir": os.path.join(os.path.expanduser("~"), "Discord Backups"),
    "appearance": "dark",
    "color_theme": "blue",
    "auto_backup_enabled": False,
    "auto_backup_interval_hours": 24,
    "auto_backup_guild_id": None,
    "auto_backup_guild_name": None,
    "max_backups_to_keep": 10,
    "notify_on_complete": True,
    "include_messages_default": False,
    "token": "",
}


class Settings:
    def __init__(self):
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            if os.path.exists(SETTINGS_PATH):
                with open(SETTINGS_PATH, "r") as f:
                    saved = json.load(f)
                self._data.update(saved)
        except Exception:
            pass

    def save(self):
        try:
            with open(SETTINGS_PATH, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    def get(self, key, default=None):
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def update(self, d: dict):
        self._data.update(d)
        self.save()
