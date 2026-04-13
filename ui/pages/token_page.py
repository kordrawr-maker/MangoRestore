import asyncio
import threading
import aiohttp
import customtkinter as ctk


DISCORD_API = "https://discord.com/api/v10"


class TokenPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)

        # Title
        ctk.CTkLabel(self, text="Bot Token", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        ctk.CTkLabel(
            self,
            text="Enter your Discord bot token to get started. The bot must be invited to your server.",
            text_color="gray",
            wraplength=560,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 20))

        # Token input card
        card = ctk.CTkFrame(self, corner_radius=12)
        card.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Bot Token", font=ctk.CTkFont(size=13, weight="bold"), anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 4)
        )

        self.token_entry = ctk.CTkEntry(
            card,
            textvariable=app.bot_token,
            placeholder_text="Paste your bot token here...",
            show="•",
            height=40,
            font=ctk.CTkFont(family="Courier", size=13),
        )
        self.token_entry.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 4))

        self.show_btn = ctk.CTkButton(
            card, text="Show", width=60, height=40,
            fg_color=("#2a2a3e", "#2a2a3e"),
            command=self._toggle_show,
        )
        self.show_btn.grid(row=1, column=1, padx=(4, 16), pady=(0, 4))

        self.verify_btn = ctk.CTkButton(
            card, text="Verify & Connect", height=40,
            fg_color="#5865F2", hover_color="#4752c4",
            command=self._verify,
        )
        self.verify_btn.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 16))

        # Status
        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=13))
        self.status_label.grid(row=3, column=0, sticky="w", pady=(0, 16))

        # Bot info card (hidden until verified)
        self.info_card = ctk.CTkFrame(self, corner_radius=12)
        self.info_card.grid_columnconfigure(1, weight=1)
        self.bot_name_label = ctk.CTkLabel(self.info_card, text="", font=ctk.CTkFont(size=15, weight="bold"))
        self.bot_id_label = ctk.CTkLabel(self.info_card, text="", text_color="gray", font=ctk.CTkFont(size=12))
        self.guild_label = ctk.CTkLabel(self.info_card, text="", text_color="gray", font=ctk.CTkFont(size=12))

        # How to guide
        guide = ctk.CTkFrame(self, corner_radius=12, fg_color=("#1a1a2e", "#1a1a2e"))
        guide.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        guide.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(guide, text="How to get a bot token", font=ctk.CTkFont(size=13, weight="bold"), anchor="w").grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 4)
        )
        steps = [
            "1. Go to discord.com/developers/applications",
            "2. Create a New Application, then go to the Bot tab",
            '3. Click "Reset Token" and copy it',
            "4. Under OAuth2 → URL Generator, select bot + Administrator",
            "5. Open the generated URL to invite the bot to your server",
        ]
        for i, step in enumerate(steps):
            ctk.CTkLabel(guide, text=step, text_color="gray", anchor="w", font=ctk.CTkFont(size=12)).grid(
                row=i + 1, column=0, sticky="w", padx=16, pady=1
            )
        ctk.CTkLabel(guide, text="", height=8).grid(row=99, column=0)

        self._showing = False

    def on_show(self):
        pass

    def _toggle_show(self):
        self._showing = not self._showing
        self.token_entry.configure(show="" if self._showing else "•")
        self.show_btn.configure(text="Hide" if self._showing else "Show")

    def _verify(self):
        token = self.app.bot_token.get().strip()
        if not token:
            self._set_status("Please enter a token.", "red")
            return
        self.verify_btn.configure(state="disabled", text="Verifying...")
        self._set_status("Connecting...", "gray")
        threading.Thread(target=self._do_verify, args=(token,), daemon=True).start()

    def _do_verify(self, token: str):
        async def fetch():
            headers = {"Authorization": f"Bot {token}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{DISCORD_API}/users/@me", headers=headers) as r:
                    if r.status == 200:
                        bot = await r.json()
                        async with session.get(f"{DISCORD_API}/users/@me/guilds", headers=headers) as r2:
                            guilds = await r2.json() if r2.status == 200 else []
                        return bot, guilds
                    else:
                        return None, []

        loop = asyncio.new_event_loop()
        bot, guilds = loop.run_until_complete(fetch())
        loop.close()

        if bot:
            self.app.guilds = guilds
            self.after(0, self._on_verified, bot, guilds)
        else:
            self.after(0, self._on_failed)

    def _on_verified(self, bot: dict, guilds: list):
        name = bot.get("username", "Unknown") + "#" + bot.get("discriminator", "0")
        self._set_status(f"✓ Connected as {name}", "#57f287")
        self.verify_btn.configure(state="normal", text="Verify & Connect")

        # Show info card
        self.bot_name_label.configure(text=f"🤖  {name}")
        self.bot_id_label.configure(text=f"ID: {bot.get('id')}")
        self.guild_label.configure(text=f"In {len(guilds)} server(s)")

        self.info_card.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self.info_card.grid_columnconfigure(0, weight=1)
        self.bot_name_label.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 2))
        self.bot_id_label.grid(row=1, column=0, sticky="w", padx=16, pady=0)
        self.guild_label.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 12))

    def _on_failed(self):
        self._set_status("✗ Invalid token or connection failed.", "#ed4245")
        self.verify_btn.configure(state="normal", text="Verify & Connect")

    def _set_status(self, text: str, color: str):
        self.status_label.configure(text=text, text_color=color)
