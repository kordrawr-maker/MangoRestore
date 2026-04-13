import asyncio
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional
from core.backup import BackupEngine


class AutoBackupScheduler:
    def __init__(self, settings, log_callback: Callable[[str], None]):
        self.settings = settings
        self.log = log_callback
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._next_run: Optional[datetime] = None
        self._running = False

    @property
    def next_run(self) -> Optional[datetime]:
        return self._next_run

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, token: str):
        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._loop, args=(token,), daemon=True)
        self._thread.start()
        self.log("Auto-backup scheduler started.")

    def stop(self):
        self._stop_event.set()
        self._running = False
        self._next_run = None
        self.log("Auto-backup scheduler stopped.")

    def _loop(self, token: str):
        while not self._stop_event.is_set():
            interval_h = self.settings.get("auto_backup_interval_hours", 24)
            self._next_run = datetime.now() + timedelta(hours=interval_h)

            # Wait in small increments so we can check stop_event
            total_secs = interval_h * 3600
            elapsed = 0
            while elapsed < total_secs and not self._stop_event.is_set():
                time.sleep(5)
                elapsed += 5

            if self._stop_event.is_set():
                break

            guild_id = self.settings.get("auto_backup_guild_id")
            guild_name = self.settings.get("auto_backup_guild_name", "Unknown")
            save_dir = self.settings.get("save_dir")

            if not guild_id or not token:
                continue

            self.log(f"[Auto] Starting scheduled backup of {guild_name}...")
            self._do_backup(token, guild_id, save_dir)

        self._running = False
        self._next_run = None

    def _do_backup(self, token: str, guild_id: str, save_dir: str):
        async def go():
            engine = BackupEngine(token, self.log)
            path = await engine.backup_guild(guild_id, save_dir)
            self.log(f"[Auto] Backup saved: {os.path.basename(path)}")
            self._prune_old_backups(save_dir)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(go())
        except Exception as e:
            self.log(f"[Auto] Backup failed: {e}")
        finally:
            loop.close()

    def _prune_old_backups(self, save_dir: str):
        max_keep = self.settings.get("max_backups_to_keep", 10)
        if max_keep <= 0:
            return
        try:
            files = sorted(
                [f for f in os.listdir(save_dir) if f.endswith(".dbak")],
                reverse=True,
            )
            to_delete = files[max_keep:]
            for f in to_delete:
                os.remove(os.path.join(save_dir, f))
                self.log(f"[Auto] Pruned old backup: {f}")
        except Exception as e:
            self.log(f"[Auto] Prune error: {e}")
