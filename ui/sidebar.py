import customtkinter as ctk


NAV_ITEMS = [
    ("token",    "🔑", "Bot Token"),
    ("backup",   "💾", "Backup"),
    ("restore",  "♻️",  "Restore"),
    ("archives", "📁", "Archives"),
    ("diff",     "🔍", "Compare"),
    ("settings", "⚙️",  "Settings"),
]


class Sidebar(ctk.CTkFrame):
    def __init__(self, parent, on_navigate):
        super().__init__(parent, width=190, corner_radius=0, fg_color=("#1e1e2e", "#1e1e2e"))
        self.on_navigate = on_navigate
        self.buttons = {}
        self.grid_propagate(False)
        self.grid_rowconfigure(len(NAV_ITEMS) + 2, weight=1)

        # Logo / title
        title = ctk.CTkLabel(
            self, text="Mango\nRestore",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#5865F2",
        )
        title.grid(row=0, column=0, padx=20, pady=(24, 20), sticky="w")

        for i, (page_id, icon, label) in enumerate(NAV_ITEMS):
            # Separator before Settings
            if page_id == "settings":
                sep = ctk.CTkFrame(self, height=1, fg_color=("#2a2a3e", "#2a2a3e"))
                sep.grid(row=i + 1, column=0, sticky="ew", padx=12, pady=4)

            btn = ctk.CTkButton(
                self,
                text=f"  {icon}  {label}",
                anchor="w",
                width=170,
                height=42,
                corner_radius=8,
                font=ctk.CTkFont(size=14),
                fg_color="transparent",
                text_color=("#e0e0e0", "#e0e0e0"),
                hover_color=("#2a2a3e", "#2a2a3e"),
                command=lambda p=page_id: self.on_navigate(p),
            )
            btn.grid(row=i + 2, column=0, padx=10, pady=2, sticky="ew")
            self.buttons[page_id] = btn

        # Version at bottom
        ver = ctk.CTkLabel(self, text="v2.0.0", font=ctk.CTkFont(size=11), text_color="gray")
        ver.grid(row=99, column=0, padx=20, pady=12, sticky="sw")

    def set_active(self, page_id: str):
        for pid, btn in self.buttons.items():
            if pid == page_id:
                btn.configure(fg_color=("#2a2a4a", "#2a2a4a"), text_color="#5865F2")
            else:
                btn.configure(fg_color="transparent", text_color=("#e0e0e0", "#e0e0e0"))
