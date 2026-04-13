import os
import customtkinter as ctk
from tkinter import filedialog
from core.diff import compare_backups, DiffItem


CHANGE_COLORS = {
    "added":    ("#57f287", "#57f287"),
    "removed":  ("#ed4245", "#ed4245"),
    "modified": ("#faa61a", "#faa61a"),
}

CHANGE_ICONS = {
    "added": "+",
    "removed": "−",
    "modified": "~",
}

CATEGORY_ICONS = {
    "channels": "💬",
    "roles": "🎭",
    "emojis": "😀",
    "settings": "⚙",
}


class DiffPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(self, text="Compare Backups", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        ctk.CTkLabel(
            self, text="Select two backup files to see what changed between them.",
            text_color="gray", font=ctk.CTkFont(size=13),
        ).grid(row=1, column=0, sticky="w", pady=(0, 12))

        # File selectors
        sel_card = ctk.CTkFrame(self, corner_radius=12)
        sel_card.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        sel_card.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(sel_card, text="Older backup", font=ctk.CTkFont(size=13), anchor="w").grid(
            row=0, column=0, padx=16, pady=(14, 2), sticky="w"
        )
        self.file_a_var = ctk.StringVar(value="Not selected")
        ctk.CTkEntry(sel_card, textvariable=self.file_a_var, height=32, state="disabled").grid(
            row=1, column=0, columnspan=2, padx=16, pady=(0, 4), sticky="ew"
        )
        ctk.CTkButton(sel_card, text="Browse", width=80, height=32, command=lambda: self._browse("a")).grid(
            row=1, column=2, padx=(0, 8), pady=(0, 4)
        )

        ctk.CTkLabel(sel_card, text="Newer backup", font=ctk.CTkFont(size=13), anchor="w").grid(
            row=2, column=0, padx=16, pady=(8, 2), sticky="w"
        )
        self.file_b_var = ctk.StringVar(value="Not selected")
        ctk.CTkEntry(sel_card, textvariable=self.file_b_var, height=32, state="disabled").grid(
            row=3, column=0, columnspan=2, padx=16, pady=(0, 4), sticky="ew"
        )
        ctk.CTkButton(sel_card, text="Browse", width=80, height=32, command=lambda: self._browse("b")).grid(
            row=3, column=2, padx=(0, 8), pady=(0, 4)
        )

        ctk.CTkButton(
            sel_card, text="Compare →", height=38,
            fg_color="#5865F2", hover_color="#4752c4",
            command=self._compare,
        ).grid(row=4, column=0, columnspan=3, sticky="ew", padx=16, pady=(8, 14))

        # Results area
        self.results_scroll = ctk.CTkScrollableFrame(self, corner_radius=12)
        self.results_scroll.grid(row=3, column=0, sticky="nsew")
        self.results_scroll.grid_columnconfigure(0, weight=1)

        self._path_a = None
        self._path_b = None
        self._result_widgets = []

    def on_show(self):
        pass

    def _browse(self, which: str):
        initial = self.app.settings.get("save_dir", os.path.expanduser("~"))
        path = filedialog.askopenfilename(
            title="Select backup archive",
            filetypes=[("Discord Backup", "*.dbak"), ("All files", "*.*")],
            initialdir=initial,
        )
        if not path:
            return
        name = os.path.basename(path)
        if which == "a":
            self._path_a = path
            self.file_a_var.set(name)
        else:
            self._path_b = path
            self.file_b_var.set(name)

    def _compare(self):
        if not self._path_a or not self._path_b:
            self._show_message("Please select both backup files.", "gray")
            return

        for w in self._result_widgets:
            w.destroy()
        self._result_widgets = []

        try:
            diffs = compare_backups(self._path_a, self._path_b)
        except Exception as e:
            self._show_message(f"Error comparing backups: {e}", "#ed4245")
            return

        if not diffs:
            self._show_message("✓ No differences found — the two backups are identical!", "#57f287")
            return

        # Summary bar
        added = sum(1 for d in diffs if d.change_type == "added")
        removed = sum(1 for d in diffs if d.change_type == "removed")
        modified = sum(1 for d in diffs if d.change_type == "modified")

        summary = ctk.CTkFrame(self.results_scroll, corner_radius=8, fg_color=("#1a1a2e", "#1a1a2e"))
        summary.grid(row=0, column=0, sticky="ew", pady=(0, 12), padx=2)
        summary.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(summary, text=f"+ {added} added", text_color="#57f287", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, pady=10)
        ctk.CTkLabel(summary, text=f"− {removed} removed", text_color="#ed4245", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=1, pady=10)
        ctk.CTkLabel(summary, text=f"~ {modified} modified", text_color="#faa61a", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=2, pady=10)
        self._result_widgets.append(summary)

        # Group by category
        categories = {}
        for d in diffs:
            categories.setdefault(d.category, []).append(d)

        widget_row = 1
        for category, items in categories.items():
            icon = CATEGORY_ICONS.get(category, "•")

            # Category header
            hdr = ctk.CTkLabel(
                self.results_scroll,
                text=f"{icon}  {category.capitalize()}  ({len(items)})",
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w",
            )
            hdr.grid(row=widget_row, column=0, sticky="w", padx=4, pady=(8, 4))
            self._result_widgets.append(hdr)
            widget_row += 1

            for item in sorted(items, key=lambda x: (x.change_type, x.name)):
                row_frame = ctk.CTkFrame(self.results_scroll, corner_radius=6, height=36)
                row_frame.grid(row=widget_row, column=0, sticky="ew", padx=2, pady=2)
                row_frame.grid_columnconfigure(2, weight=1)
                row_frame.grid_propagate(False)

                color = CHANGE_COLORS[item.change_type]
                icon_lbl = ctk.CTkLabel(
                    row_frame,
                    text=f" {CHANGE_ICONS[item.change_type]} ",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=color,
                    width=28,
                )
                icon_lbl.grid(row=0, column=0, padx=(8, 0))

                name_lbl = ctk.CTkLabel(
                    row_frame,
                    text=item.name,
                    font=ctk.CTkFont(size=13),
                    anchor="w",
                )
                name_lbl.grid(row=0, column=1, padx=(4, 0), sticky="w")

                if item.detail:
                    detail_lbl = ctk.CTkLabel(
                        row_frame,
                        text=item.detail,
                        font=ctk.CTkFont(size=11),
                        text_color="gray",
                        anchor="w",
                    )
                    detail_lbl.grid(row=0, column=2, padx=(8, 8), sticky="w")

                self._result_widgets.append(row_frame)
                widget_row += 1

    def _show_message(self, text: str, color: str):
        for w in self._result_widgets:
            w.destroy()
        self._result_widgets = []
        lbl = ctk.CTkLabel(self.results_scroll, text=text, text_color=color, font=ctk.CTkFont(size=14))
        lbl.grid(row=0, column=0, pady=40)
        self._result_widgets.append(lbl)
