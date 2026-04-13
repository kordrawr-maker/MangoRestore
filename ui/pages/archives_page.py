import os
import json
import zipfile
import customtkinter as ctk
from tkinter import filedialog, messagebox


DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Discord Backups")


class ArchivesPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._current_dir = DEFAULT_DIR

        # Title row
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        title_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(title_row, text="Archives", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkButton(
            title_row, text="📂  Change Folder", width=140, height=34,
            fg_color=("#2a2a3e", "#2a2a3e"),
            command=self._change_dir,
        ).grid(row=0, column=1, sticky="e")

        # Current dir label
        self.dir_label = ctk.CTkLabel(self, text=self._current_dir, text_color="gray", font=ctk.CTkFont(size=11), anchor="w")
        self.dir_label.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        # Scrollable list
        self.scroll = ctk.CTkScrollableFrame(self, corner_radius=12)
        self.scroll.grid(row=2, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        self._cards = []

    def on_show(self):
        self._refresh()

    def _change_dir(self):
        d = filedialog.askdirectory(initialdir=self._current_dir)
        if d:
            self._current_dir = d
            self.dir_label.configure(text=d)
            self._refresh()

    def _refresh(self):
        for card in self._cards:
            card.destroy()
        self._cards = []

        os.makedirs(self._current_dir, exist_ok=True)
        files = [f for f in os.listdir(self._current_dir) if f.endswith(".dbak")]
        files.sort(reverse=True)

        if not files:
            empty = ctk.CTkLabel(
                self.scroll,
                text="No backups found in this folder.\nCreate one from the Backup page!",
                text_color="gray",
                font=ctk.CTkFont(size=14),
                justify="center",
            )
            empty.grid(row=0, column=0, pady=60)
            self._cards.append(empty)
            return

        for i, filename in enumerate(files):
            filepath = os.path.join(self._current_dir, filename)
            card = self._make_card(filepath, filename, i)
            card.grid(row=i, column=0, sticky="ew", padx=4, pady=4)
            self._cards.append(card)

    def _read_meta(self, filepath: str) -> dict:
        try:
            with zipfile.ZipFile(filepath, "r") as zf:
                with zf.open("backup.json") as f:
                    data = json.loads(f.read())
            meta = data.get("meta", {})
            channels = data.get("channels", [])
            roles = [r for r in data.get("roles", []) if not r.get("everyone")]
            emojis = data.get("emojis", [])
            has_messages = "messages" in data
            return {
                "name": meta.get("name", "Unknown"),
                "date": meta.get("backed_up_at", "")[:16].replace("T", " "),
                "channels": len(channels),
                "roles": len(roles),
                "emojis": len(emojis),
                "has_messages": has_messages,
                "size": os.path.getsize(filepath),
            }
        except Exception:
            return {"name": "Corrupted?", "date": "", "channels": 0, "roles": 0, "emojis": 0, "has_messages": False, "size": 0}

    def _make_card(self, filepath: str, filename: str, index: int) -> ctk.CTkFrame:
        meta = self._read_meta(filepath)
        size_str = f"{meta['size'] / 1024:.1f} KB" if meta['size'] < 1024 * 1024 else f"{meta['size'] / 1024 / 1024:.1f} MB"

        card = ctk.CTkFrame(self.scroll, corner_radius=10)
        card.grid_columnconfigure(0, weight=1)

        # Top row: server name + date
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text=f"📦  {meta['name']}", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(top, text=meta["date"], text_color="gray", font=ctk.CTkFont(size=11)).grid(row=0, column=1, sticky="e")

        # Stats row
        tags = f"{meta['channels']} channels  ·  {meta['roles']} roles  ·  {meta['emojis']} emojis  ·  {size_str}"
        if meta["has_messages"]:
            tags += "  ·  📜 includes messages"
        ctk.CTkLabel(card, text=tags, text_color="gray", font=ctk.CTkFont(size=11), anchor="w").grid(
            row=1, column=0, sticky="w", padx=14, pady=(0, 4)
        )

        # Filename
        ctk.CTkLabel(card, text=filename, text_color=("#555", "#666"), font=ctk.CTkFont(size=10), anchor="w").grid(
            row=2, column=0, sticky="w", padx=14, pady=(0, 8)
        )

        # Buttons
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

        ctk.CTkButton(
            btn_row, text="Open folder", width=100, height=30,
            fg_color=("#2a2a3e", "#2a2a3e"),
            command=lambda p=filepath: self._open_folder(p),
        ).grid(row=0, column=0, padx=4)

        ctk.CTkButton(
            btn_row, text="🗑 Delete", width=90, height=30,
            fg_color=("#3a1a1a", "#3a1a1a"), text_color="#ed4245",
            hover_color=("#4a2a2a", "#4a2a2a"),
            command=lambda p=filepath, fn=filename: self._delete(p, fn),
        ).grid(row=0, column=1, padx=4)

        return card

    def _open_folder(self, filepath: str):
        folder = os.path.dirname(filepath)
        import subprocess, sys
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", filepath])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", filepath])
        else:
            subprocess.Popen(["xdg-open", folder])

    def _delete(self, filepath: str, filename: str):
        if messagebox.askyesno("Delete Backup", f"Permanently delete:\n{filename}?", icon="warning"):
            os.remove(filepath)
            self._refresh()
