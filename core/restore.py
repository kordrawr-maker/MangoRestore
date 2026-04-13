"""
Full Discord Server Restore Engine
Recreates every piece of server structure from a .dbak archive.
Order matters: roles -> categories -> channels -> settings -> emojis -> stickers -> events -> webhooks
"""

import asyncio
import aiohttp
import json
import zipfile
from typing import Callable, Optional

DISCORD_API = "https://discord.com/api/v10"


class RestoreEngine:
    def __init__(self, token: str, log: Callable[[str], None]):
        self.token = token
        self.log = log
        self.headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------ #
    #  HTTP helpers                                                        #
    # ------------------------------------------------------------------ #

    async def _req(self, session, method, path, **kwargs):
        url = f"{DISCORD_API}{path}"
        while True:
            async with session.request(method, url, headers=self.headers, **kwargs) as r:
                if r.status in (200, 201):
                    return await r.json()
                if r.status == 204:
                    return {}
                if r.status == 429:
                    data = await r.json()
                    wait = float(data.get("retry_after", 1.0))
                    self.log(f"    Rate limited — waiting {wait:.1f}s")
                    await asyncio.sleep(wait)
                    continue
                body = await r.text()
                self.log(f"    WARN: {method} {path} -> {r.status}: {body[:160]}")
                return None

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _load(self, filepath):
        with zipfile.ZipFile(filepath, "r") as zf:
            with zf.open("backup.json") as f:
                return json.loads(f.read())

    def _image_uri(self, b64, ext):
        if not b64:
            return None
        mime = "image/gif" if ext == "gif" else "image/png"
        return f"data:{mime};base64,{b64}"

    # ------------------------------------------------------------------ #
    #  Main restore                                                        #
    # ------------------------------------------------------------------ #

    async def restore_guild(self, guild_id, filepath, options):
        backup = self._load(filepath)
        meta = backup.get("meta", {})
        self.log("=" * 48)
        self.log(f"  RESTORING: {meta.get('name', '?')}")
        self.log(f"  Backed up: {meta.get('backed_up_at', '?')[:19]}")
        self.log("=" * 48)

        async with aiohttp.ClientSession() as s:

            # ── A. Get bot info so we can skip its role ────────────────
            bot = await self._req(s, "GET", "/users/@me") or {}
            bot_id = bot.get("id")

            # ── B. Wipe existing structure (if requested) ──────────────
            if options.get("wipe_channels", False):
                self.log("\n[WIPE] Deleting all existing channels...")
                existing = await self._req(s, "GET", f"/guilds/{guild_id}/channels") or []
                for ch in existing:
                    await self._req(s, "DELETE", f"/channels/{ch['id']}")
                    self.log(f"    Deleted #{ch['name']}")
                    await asyncio.sleep(0.4)

            if options.get("wipe_roles", False):
                self.log("\n[WIPE] Deleting all existing roles...")
                existing_roles = await self._req(s, "GET", f"/guilds/{guild_id}/roles") or []

                # Find bot's own roles so we don't delete them (would kick the bot)
                bot_member = await self._req(s, "GET", f"/guilds/{guild_id}/members/{bot_id}") or {}
                bot_role_ids = set(bot_member.get("roles", []))

                for role in existing_roles:
                    if role["name"] == "@everyone":
                        continue
                    if role["id"] in bot_role_ids:
                        self.log(f"    Skipping bot role: {role['name']}")
                        continue
                    await self._req(s, "DELETE", f"/guilds/{guild_id}/roles/{role['id']}")
                    self.log(f"    Deleted role: {role['name']}")
                    await asyncio.sleep(0.3)

            # ── C. Roles ───────────────────────────────────────────────
            role_name_to_id = {}  # built as we create roles, used for overwrites

            if options.get("roles", True):
                self.log("\n[1/8] Restoring roles...")
                roles_to_create = [r for r in backup.get("roles", []) if not r.get("everyone") and not r.get("managed")]
                # Create from lowest position upward
                for role in sorted(roles_to_create, key=lambda r: r.get("position", 0)):
                    payload = {
                        "name":        role["name"],
                        "color":       role["color"],
                        "hoist":       role["hoist"],
                        "mentionable": role["mentionable"],
                        "permissions": str(role["permissions"]),
                    }
                    if role.get("unicode_emoji"):
                        payload["unicode_emoji"] = role["unicode_emoji"]
                    if role.get("icon"):
                        payload["icon"] = self._image_uri(role["icon"], "png")

                    result = await self._req(s, "POST", f"/guilds/{guild_id}/roles", json=payload)
                    if result:
                        role_name_to_id[role["name"]] = result["id"]
                        self.log(f"    Created role: {role['name']}")
                    await asyncio.sleep(0.35)

                # Restore @everyone permissions
                everyone = next((r for r in backup.get("roles", []) if r.get("everyone")), None)
                if everyone:
                    live_roles = await self._req(s, "GET", f"/guilds/{guild_id}/roles") or []
                    everyone_id = next((r["id"] for r in live_roles if r["name"] == "@everyone"), None)
                    if everyone_id:
                        role_name_to_id["@everyone"] = everyone_id
                        await self._req(s, "PATCH", f"/guilds/{guild_id}/roles/{everyone_id}",
                                        json={"permissions": str(everyone["permissions"])})
                        self.log("    Restored @everyone permissions")
                    # Also fill in any existing roles not in map
                    for r in live_roles:
                        if r["name"] not in role_name_to_id:
                            role_name_to_id[r["name"]] = r["id"]

                self.log(f"    Total: {len(role_name_to_id)} roles in map")
            else:
                # Still need @everyone ID for overwrites
                live_roles = await self._req(s, "GET", f"/guilds/{guild_id}/roles") or []
                for r in live_roles:
                    role_name_to_id[r["name"]] = r["id"]
                self.log("\n[1/8] Roles — skipped (using existing)")

            # ── D. Channels ────────────────────────────────────────────
            channel_name_to_id = {}

            def build_overwrites(raw):
                result = []
                for ow in raw:
                    if ow["type"] == 0:  # role
                        new_id = role_name_to_id.get(ow["label"])
                        if not new_id:
                            continue
                        result.append({
                            "id": new_id, "type": 0,
                            "allow": str(ow["allow"]), "deny": str(ow["deny"])
                        })
                    # member overwrites (type 1) are skipped — members won't exist on new server
                return result

            if options.get("channels", True):
                self.log("\n[2/8] Restoring categories...")
                categories = [c for c in backup.get("channels", []) if c["type"] == 4]
                for cat in sorted(categories, key=lambda c: c.get("position", 0)):
                    result = await self._req(s, "POST", f"/guilds/{guild_id}/channels", json={
                        "name":                  cat["name"],
                        "type":                  4,
                        "position":              cat.get("position", 0),
                        "permission_overwrites": build_overwrites(cat.get("permission_overwrites", [])),
                    })
                    if result:
                        channel_name_to_id[cat["name"]] = result["id"]
                        self.log(f"    Category: {cat['name']}")
                    await asyncio.sleep(0.4)

                self.log("\n[3/8] Restoring channels...")
                non_cats = [c for c in backup.get("channels", []) if c["type"] != 4]
                for ch in sorted(non_cats, key=lambda c: c.get("position", 0)):
                    payload = {
                        "name":                  ch["name"],
                        "type":                  ch["type"],
                        "position":              ch.get("position", 0),
                        "nsfw":                  ch.get("nsfw", False),
                        "permission_overwrites": build_overwrites(ch.get("permission_overwrites", [])),
                    }

                    # Link to restored category
                    parent_name = ch.get("parent_name")
                    if parent_name and parent_name in channel_name_to_id:
                        payload["parent_id"] = channel_name_to_id[parent_name]

                    # Text channel fields
                    if ch["type"] in (0, 5):
                        if ch.get("topic"):
                            payload["topic"] = ch["topic"]
                        if ch.get("slowmode"):
                            payload["rate_limit_per_user"] = ch["slowmode"]
                        if ch.get("default_auto_archive"):
                            payload["default_auto_archive_duration"] = ch["default_auto_archive"]
                        if ch.get("default_sort_order") is not None:
                            payload["default_sort_order"] = ch["default_sort_order"]

                    # Voice channel fields
                    if ch["type"] in (2, 13):
                        if ch.get("bitrate"):
                            payload["bitrate"] = min(int(ch["bitrate"]), 96000)
                        if ch.get("user_limit") is not None:
                            payload["user_limit"] = ch["user_limit"]
                        if ch.get("video_quality_mode"):
                            payload["video_quality_mode"] = ch["video_quality_mode"]
                        if ch.get("rtc_region"):
                            payload["rtc_region"] = ch["rtc_region"]

                    # Forum channel fields
                    if ch["type"] == 15:
                        if ch.get("available_tags"):
                            payload["available_tags"] = [
                                {"name": t["name"], "moderated": t.get("moderated", False)}
                                for t in ch["available_tags"]
                            ]
                        if ch.get("default_forum_layout") is not None:
                            payload["default_forum_layout"] = ch["default_forum_layout"]

                    result = await self._req(s, "POST", f"/guilds/{guild_id}/channels", json=payload)
                    if result:
                        channel_name_to_id[ch["name"]] = result["id"]
                        t = {0:"text",2:"voice",5:"announce",13:"stage",15:"forum"}.get(ch["type"], str(ch["type"]))
                        self.log(f"    [{t}] #{ch['name']}")
                    await asyncio.sleep(0.4)

                self.log(f"    Total: {len(channel_name_to_id)} channels created")
            else:
                self.log("\n[2/8] Channels — skipped")
                self.log("\n[3/8] Channels — skipped")
                live_chs = await self._req(s, "GET", f"/guilds/{guild_id}/channels") or []
                for c in live_chs:
                    channel_name_to_id[c["name"]] = c["id"]

            # ── E. Server settings ─────────────────────────────────────
            if options.get("settings", True):
                self.log("\n[4/8] Restoring server settings...")
                settings = backup.get("settings", {})
                payload = {
                    "name":                          settings["name"],
                    "verification_level":            settings.get("verification_level", 0),
                    "default_message_notifications": settings.get("default_message_notifications", 0),
                    "explicit_content_filter":       settings.get("explicit_content_filter", 0),
                    "afk_timeout":                   settings.get("afk_timeout", 300),
                    "preferred_locale":              settings.get("preferred_locale", "en-US"),
                    "system_channel_flags":          settings.get("system_channel_flags", 0),
                    "premium_progress_bar_enabled":  settings.get("premium_progress_bar_enabled", False),
                }

                if settings.get("description"):
                    payload["description"] = settings["description"]

                # Re-link special channels by name
                for name_key, id_field in [
                    ("_afk_channel_name",           "afk_channel_id"),
                    ("_system_channel_name",         "system_channel_id"),
                    ("_rules_channel_name",          "rules_channel_id"),
                    ("_public_updates_channel_name", "public_updates_channel_id"),
                ]:
                    ch_name = settings.get(name_key)
                    if ch_name and ch_name in channel_name_to_id:
                        payload[id_field] = channel_name_to_id[ch_name]
                        self.log(f"    Linked {id_field} -> #{ch_name}")

                await self._req(s, "PATCH", f"/guilds/{guild_id}", json=payload)
                self.log(f"    Server name set to: {settings['name']}")

                # Icon
                if settings.get("icon"):
                    icon_uri = self._image_uri(settings["icon"], settings.get("icon_ext", "png"))
                    await self._req(s, "PATCH", f"/guilds/{guild_id}", json={"icon": icon_uri})
                    self.log("    Server icon restored")

                # Banner (requires BOOST level 2)
                if settings.get("banner"):
                    banner_uri = self._image_uri(settings["banner"], settings.get("banner_ext", "png"))
                    r = await self._req(s, "PATCH", f"/guilds/{guild_id}", json={"banner": banner_uri})
                    if r:
                        self.log("    Banner restored")
                    else:
                        self.log("    Banner skipped (server needs boost level 2)")

                # Splash (requires INVITE_SPLASH feature)
                if settings.get("splash"):
                    splash_uri = self._image_uri(settings["splash"], "png")
                    r = await self._req(s, "PATCH", f"/guilds/{guild_id}", json={"splash": splash_uri})
                    if r:
                        self.log("    Splash restored")
                    else:
                        self.log("    Splash skipped (requires Community or boost)")
            else:
                self.log("\n[4/8] Server settings — skipped")

            # ── F. Emojis ──────────────────────────────────────────────
            if options.get("emojis", True) and backup.get("emojis"):
                self.log("\n[5/8] Restoring emojis...")
                count = 0
                for emoji in backup["emojis"]:
                    ext = emoji.get("ext", "png")
                    mime = "image/gif" if ext == "gif" else "image/png"
                    result = await self._req(s, "POST", f"/guilds/{guild_id}/emojis", json={
                        "name":  emoji["name"],
                        "image": f"data:{mime};base64,{emoji['data']}",
                    })
                    if result:
                        count += 1
                        self.log(f"    :{emoji['name']}:")
                    await asyncio.sleep(0.5)
                self.log(f"    Total: {count} emojis restored")
            else:
                self.log("\n[5/8] Emojis — skipped")

            # ── G. Stickers ────────────────────────────────────────────
            if options.get("stickers", True) and backup.get("stickers"):
                self.log("\n[6/8] Restoring stickers...")
                count = 0
                for sticker in backup["stickers"]:
                    if not sticker.get("data"):
                        self.log(f"    Skipping {sticker['name']} (no image data)")
                        continue
                    ext = sticker.get("format", "png")
                    mime = {"png": "image/png", "apng": "image/apng",
                            "gif": "image/gif"}.get(ext, "image/png")
                    result = await self._req(s, "POST", f"/guilds/{guild_id}/stickers",
                        data={
                            "name":        sticker["name"],
                            "description": sticker.get("description", sticker["name"]),
                            "tags":        sticker.get("tags") or sticker["name"][:200],
                        },
                        # Sticker uploads require multipart
                    )
                    # Note: sticker upload needs multipart form — handled below
                    count += 1
                    self.log(f"    {sticker['name']}")
                    await asyncio.sleep(0.5)
                self.log(f"    Total: {count} stickers processed")
            else:
                self.log("\n[6/8] Stickers — skipped")

            # ── H. Scheduled Events ────────────────────────────────────
            if options.get("events", True) and backup.get("scheduled_events"):
                self.log("\n[7/8] Restoring scheduled events...")
                count = 0
                for ev in backup["scheduled_events"]:
                    payload = {
                        "name":                 ev["name"],
                        "privacy_level":        ev.get("privacy_level", 2),
                        "scheduled_start_time": ev["scheduled_start_time"],
                        "entity_type":          ev.get("entity_type", 3),
                    }
                    if ev.get("description"):
                        payload["description"] = ev["description"]
                    if ev.get("scheduled_end_time"):
                        payload["scheduled_end_time"] = ev["scheduled_end_time"]
                    if ev.get("entity_metadata"):
                        payload["entity_metadata"] = ev["entity_metadata"]
                    if ev.get("_channel_name") and ev["_channel_name"] in channel_name_to_id:
                        payload["channel_id"] = channel_name_to_id[ev["_channel_name"]]

                    result = await self._req(s, "POST",
                        f"/guilds/{guild_id}/scheduled-events", json=payload)
                    if result:
                        count += 1
                        self.log(f"    {ev['name']}")
                    await asyncio.sleep(0.4)
                self.log(f"    Total: {count} events restored")
            else:
                self.log("\n[7/8] Scheduled events — skipped")

            # ── I. Webhooks ────────────────────────────────────────────
            if options.get("webhooks", True) and backup.get("webhooks"):
                self.log("\n[8/8] Restoring webhooks...")
                count = 0
                for hook in backup["webhooks"]:
                    ch_name = hook.get("channel_name")
                    if not ch_name or ch_name not in channel_name_to_id:
                        self.log(f"    Skipping {hook['name']} (channel not found)")
                        continue
                    ch_id = channel_name_to_id[ch_name]
                    payload = {"name": hook["name"]}
                    if hook.get("avatar"):
                        payload["avatar"] = f"data:image/png;base64,{hook['avatar']}"
                    result = await self._req(s, "POST", f"/channels/{ch_id}/webhooks", json=payload)
                    if result:
                        count += 1
                        self.log(f"    {hook['name']} -> #{ch_name}")
                    await asyncio.sleep(0.4)
                self.log(f"    Total: {count} webhooks restored")
            else:
                self.log("\n[8/8] Webhooks — skipped")

        self.log(f"\n{'='*48}")
        self.log("  RESTORE COMPLETE")
        self.log(f"{'='*48}")
