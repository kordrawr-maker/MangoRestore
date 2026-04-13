import customtkinter as ctk


class LogBox(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        label = ctk.CTkLabel(self, text="Log", font=ctk.CTkFont(size=12), text_color="gray", anchor="w")
        label.grid(row=0, column=0, sticky="w", padx=8, pady=(4, 0))

        self.textbox = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Courier", size=12),
            fg_color=("#111118", "#111118"),
            text_color="#a0f0a0",
            wrap="word",
            state="disabled",
        )
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))

    def write(self, message: str):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", message + "\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def clear(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")
