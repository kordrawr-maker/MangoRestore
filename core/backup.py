"""
Full Discord Server Backup Engine
Captures every piece of server data the Discord API exposes to bots.
"""

import asyncio
import aiohttp
import base64
import json
import os
import zipfile
from datetime import datetime
from typing import Callable, Optional

DISCORD_API = "https://discord.com/api/v10"
CDN = "https://cdn.discordapp.com"


class BackupEngine:
    def __init__(self, token: str, log: Callable[[str], None]):
        self.token = token
        self.log = log
        self.headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }

    async def _get(self, session, path):
        url = f"{DISCORD_API}{path}"
        while True:
            async with session.get(url, headers=self.headers) as r:
                if r.status == 200:
                    return await r.json()
                if r.status == 429:
                    data = await r.json()
                    wait = float(data.get("retry_after", 1.0))
                    self.log(f"    Rate limited — waiting {wait:.1f}s")
                    await asyncio.sleep(wait)
                    continue
                if r.status in (403, 404):
                    return None
                self.log(f"    Warning: GET {path} -> {r.status}")
                return None

    async def _fetch_image(self, session, url):
        try:
            async with session.get(url) as r:
                if r.status == 200:
                    return base64.b64encode(await r.read()).decode()
        except Exception:
            pass
        return None

    async def get_guilds(self):
        async with aiohttp.ClientSession() as s:
            return await self._get(s, "/users/@me/guilds") or []

    async def backup_guild(self, guild_id, output_dir, options):
        self.log("=" * 48)
        self.log("  FULL SERVER BACKUP STARTING")
        self.log("=" * 48)

        backup = {
            "meta": {}, "settings": {}, "roles": [], "channels": [],
            "emojis": [], "stickers": [], "scheduled_events": [],
            "soundboard": [], "webhooks": [], "messages": {}
        }

        async with aiohttp.ClientSession() as s:

            # 1. Guild base info
            self.log("\n[1/10] Fetching server info...")
            guild = await self._get(s, f"/guilds/{guild_id}?with_counts=true")
            if not guild:
                raise ValueError("Cannot fetch guild. Bot must be in the server with Administrator.")

            backup["meta"] = {
                "guild_id": guild_id,
                "name": guild["name"],
                "backed_up_at": datetime.utcnow().isoformat(),
                "tool_version": "2.1",
            }

            backup["settings"] = {
                "name":                             guild["name"],
                "description":                      guild.get("description"),
                "verification_level":               guild.get("verification_level", 0),
                "default_message_notifications":    guild.get("default_message_notifications", 0),
                "explicit_content_filter":          guild.get("explicit_content_filter", 0),
                "afk_timeout":                      guild.get("afk_timeout", 300),
                "preferred_locale":                 guild.get("preferred_locale", "en-US"),
                "system_channel_flags":             guild.get("system_channel_flags", 0),
                "premium_progress_bar_enabled":     guild.get("premium_progress_bar_enabled", False),
                "nsfw_level":                       guild.get("nsfw_level", 0),
                "features":                         guild.get("features", []),
                # These will be resolved to names below
                "_afk_channel_name":                None,
                "_system_channel_name":             None,
                "_rules_channel_name":              None,
                "_public_updates_channel_name":     None,
            }
            self.log(f"    Server: {guild['name']}")

            # 2. Images
            self.log("\n[2/10] Downloading server images...")

            async def grab_image(hash_val, url, key):
                if hash_val:
                    data = await self._fetch_image(s, url)
                    if data:
                        backup["settings"][key] = data
                        ext = "gif" if hash_val.startswith("a_") else "png"
                        backup["settings"][key + "_ext"] = ext
                        self.log(f"    Saved {key} ({ext})")

            if guild.get("icon"):
                ext = "gif" if guild["icon"].startswith("a_") else "png"
                await grab_image(guild["icon"], f"{CDN}/icons/{guild_id}/{guild['icon']}.{ext}?size=1024", "icon")
            if guild.get("banner"):
                ext = "gif" if guild["banner"].startswith("a_") else "png"
                await grab_image(guild["banner"], f"{CDN}/banners/{guild_id}/{guild['banner']}.{ext}?size=1024", "banner")
            if guild.get("splash"):
                await grab_image(guild["splash"], f"{CDN}/splashes/{guild_id}/{guild['splash']}.png?size=1024", "splash")
            if guild.get("discovery_splash"):
                await grab_image(guild["discovery_splash"], f"{CDN}/discovery-splashes/{guild_id}/{guild['discovery_splash']}.png?size=1024", "discovery_splash")

            # 3. Roles
            self.log("\n[3/10] Fetching roles...")
            raw_roles = await self._get(s, f"/guilds/{guild_id}/roles") or []
            raw_roles.sort(key=lambda r: r["position"])
            role_id_to_name = {r["id"]: r["name"] for r in raw_roles}

            for role in raw_roles:
                entry = {
                    "name":          role["name"],
                    "color":         role["color"],
                    "hoist":         role["hoist"],
                    "mentionable":   role["mentionable"],
                    "permissions":   role["permissions"],
                    "position":      role["position"],
                    "managed":       role.get("managed", False),
                    "everyone":      role["name"] == "@everyone",
                    "unicode_emoji": role.get("unicode_emoji"),
                    "icon":          None,
                }
                if role.get("icon"):
                    img = await self._fetch_image(s, f"{CDN}/role-icons/{role['id']}/{role['icon']}.png")
                    if img:
                        entry["icon"] = img
                backup["roles"].append(entry)
                self.log(f"    Role: {role['name']}")

            self.log(f"    Total: {len(backup['roles'])} roles")

            # 4. Channels — full data
            self.log("\n[4/10] Fetching channels...")
            raw_channels = await self._get(s, f"/guilds/{guild_id}/channels") or []
            id_to_ch = {c["id"]: c for c in raw_channels}
            cat_id_to_name = {c["id"]: c["name"] for c in raw_channels if c["type"] == 4}

            # Resolve special channel names from IDs
            for key, field in [
                ("_afk_channel_name",            "afk_channel_id"),
                ("_system_channel_name",          "system_channel_id"),
                ("_rules_channel_name",           "rules_channel_id"),
                ("_public_updates_channel_name",  "public_updates_channel_id"),
            ]:
                cid = guild.get(field)
                if cid and cid in id_to_ch:
                    backup["settings"][key] = id_to_ch[cid]["name"]

            for ch in sorted(raw_channels, key=lambda c: c.get("position", 0)):
                overwrites = []
                for ow in ch.get("permission_overwrites", []):
                    if ow["type"] == 0:
                        label = role_id_to_name.get(ow["id"], ow["id"])
                    else:
                        label = ow["id"]  # member overwrites — ID only
                    overwrites.append({
                        "type":  ow["type"],
                        "label": label,
                        "allow": ow["allow"],
                        "deny":  ow["deny"],
                    })

                # Forum/thread tag objects
                available_tags = []
                for tag in ch.get("available_tags", []):
                    available_tags.append({
                        "name":       tag["name"],
                        "moderated":  tag.get("moderated", False),
                        "emoji_name": tag.get("emoji_name"),
                    })

                backup["channels"].append({
                    "_original_id":          ch["id"],
                    "name":                  ch["name"],
                    "type":                  ch["type"],
                    "position":              ch.get("position", 0),
                    "topic":                 ch.get("topic"),
                    "nsfw":                  ch.get("nsfw", False),
                    "slowmode":              ch.get("rate_limit_per_user", 0),
                    "bitrate":               ch.get("bitrate"),
                    "user_limit":            ch.get("user_limit"),
                    "video_quality_mode":    ch.get("video_quality_mode", 1),
                    "default_auto_archive":  ch.get("default_auto_archive_duration"),
                    "default_sort_order":    ch.get("default_sort_order"),
                    "default_forum_layout":  ch.get("default_forum_layout"),
                    "rtc_region":            ch.get("rtc_region"),
                    "parent_id":             ch.get("parent_id"),
                    "parent_name":           cat_id_to_name.get(ch.get("parent_id")),
                    "available_tags":        available_tags,
                    "permission_overwrites": overwrites,
                })
                t = {0:"text",2:"voice",4:"category",5:"announcement",13:"stage",15:"forum"}.get(ch["type"], str(ch["type"]))
                self.log(f"    [{t}] #{ch['name']}")

            self.log(f"    Total: {len(backup['channels'])} channels")

            # 5. Emojis
            self.log("\n[5/10] Downloading custom emojis...")
            raw_emojis = await self._get(s, f"/guilds/{guild_id}/emojis") or []
            for emoji in raw_emojis:
                ext = "gif" if emoji.get("animated") else "png"
                img = await self._fetch_image(s, f"{CDN}/emojis/{emoji['id']}.{ext}")
                if img:
                    backup["emojis"].append({
                        "name":     emoji["name"],
                        "animated": emoji.get("animated", False),
                        "ext":      ext,
                        "data":     img,
                        "roles":    [role_id_to_name.get(r, r) for r in emoji.get("roles", [])],
                    })
                    self.log(f"    :{emoji['name']}:")
                await asyncio.sleep(0.15)
            self.log(f"    Total: {len(backup['emojis'])} emojis")

            # 6. Stickers
            self.log("\n[6/10] Downloading stickers...")
            raw_stickers = await self._get(s, f"/guilds/{guild_id}/stickers") or []
            for sticker in raw_stickers:
                fmt_map = {1: "png", 2: "apng", 3: "lottie", 4: "gif"}
                fmt = fmt_map.get(sticker.get("format_type", 1), "png")
                img = None
                if fmt != "lottie":
                    img = await self._fetch_image(s, f"{CDN}/stickers/{sticker['id']}.{fmt}")
                backup["stickers"].append({
                    "name":        sticker["name"],
                    "description": sticker.get("description", ""),
                    "tags":        sticker.get("tags", ""),
                    "format":      fmt,
                    "data":        img,
                })
                self.log(f"    {sticker['name']}")
                await asyncio.sleep(0.15)
            self.log(f"    Total: {len(backup['stickers'])} stickers")

            # 7. Scheduled events
            self.log("\n[7/10] Fetching scheduled events...")
            raw_events = await self._get(s, f"/guilds/{guild_id}/scheduled-events") or []
            for ev in raw_events:
                backup["scheduled_events"].append({
                    "name":                 ev["name"],
                    "description":          ev.get("description"),
                    "scheduled_start_time": ev["scheduled_start_time"],
                    "scheduled_end_time":   ev.get("scheduled_end_time"),
                    "privacy_level":        ev.get("privacy_level", 2),
                    "entity_type":          ev.get("entity_type", 3),
                    "entity_metadata":      ev.get("entity_metadata"),
                    "_channel_name":        id_to_ch.get(ev.get("channel_id", ""), {}).get("name"),
                })
                self.log(f"    {ev['name']}")
            self.log(f"    Total: {len(backup['scheduled_events'])} events")

            # 8. Soundboard
            if options.get("soundboard", True):
                self.log("\n[8/10] Fetching soundboard sounds...")
                raw = await self._get(s, f"/guilds/{guild_id}/soundboard-sounds")
                sounds_list = []
                if isinstance(raw, dict):
                    sounds_list = raw.get("items", [])
                elif isinstance(raw, list):
                    sounds_list = raw
                for sound in sounds_list:
                    sid = sound.get("sound_id") or sound.get("id", "")
                    snd_data = await self._fetch_image(s, f"{CDN}/soundboard-sounds/{sid}")
                    backup["soundboard"].append({
                        "name":   sound["name"],
                        "volume": sound.get("volume", 1.0),
                        "emoji":  sound.get("emoji_name"),
                        "data":   snd_data,
                    })
                    self.log(f"    {sound['name']}")
                    await asyncio.sleep(0.2)
                self.log(f"    Total: {len(backup['soundboard'])} sounds")
            else:
                self.log("\n[8/10] Soundboard — skipped")

            # 9. Webhooks
            if options.get("webhooks", True):
                self.log("\n[9/10] Fetching webhooks...")
                raw_hooks = await self._get(s, f"/guilds/{guild_id}/webhooks") or []
                for hook in raw_hooks:
                    ch_name = id_to_ch.get(hook.get("channel_id", ""), {}).get("name")
                    avatar_data = None
                    if hook.get("avatar"):
                        avatar_data = await self._fetch_image(
                            s, f"{CDN}/avatars/{hook['id']}/{hook['avatar']}.png")
                    backup["webhooks"].append({
                        "name":         hook["name"],
                        "channel_name": ch_name,
                        "avatar":       avatar_data,
                    })
                    self.log(f"    {hook['name']} -> #{ch_name}")
                self.log(f"    Total: {len(backup['webhooks'])} webhooks")
            else:
                self.log("\n[9/10] Webhooks — skipped")

            # 10. Messages
            if options.get("messages", False):
                msg_limit = min(options.get("message_limit", 100), 100)
                self.log(f"\n[10/10] Fetching messages (up to {msg_limit}/channel)...")
                text_chs = [c for c in raw_channels if c["type"] in (0, 5)]
                for ch in text_chs:
                    self.log(f"    #{ch['name']}...")
                    msgs = await self._get(s, f"/channels/{ch['id']}/messages?limit={msg_limit}")
                    if msgs:
                        backup["messages"][ch["name"]] = [
                            {
                                "author":      m["author"]["username"],
                                "content":     m.get("content", ""),
                                "timestamp":   m["timestamp"],
                                "pinned":      m.get("pinned", False),
                                "attachments": [a["url"] for a in m.get("attachments", [])],
                            }
                            for m in reversed(msgs)
                        ]
                    await asyncio.sleep(0.5)
                total_msgs = sum(len(v) for v in backup["messages"].values())
                self.log(f"    Total: {total_msgs} messages")
            else:
                self.log("\n[10/10] Messages — skipped")

        # Write zip
        self.log("\nWriting archive...")
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c for c in guild["name"] if c.isalnum() or c in " _-").strip().replace(" ", "_")
        filename = f"{safe}_{ts}.dbak"
        filepath = os.path.join(output_dir, filename)

        with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("backup.json", json.dumps(backup, indent=2, ensure_ascii=False))

        size = os.path.getsize(filepath)
        size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.2f} MB"
        self.log(f"\n{'='*48}")
        self.log(f"  BACKUP COMPLETE — {filename}")
        self.log(f"  Size: {size_str}")
        self.log(f"{'='*48}")
        return filepath
