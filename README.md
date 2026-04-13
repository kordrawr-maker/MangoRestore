# MangoRestore

Back up and restore your Discord server structure — channels, roles, permissions, emojis, and settings.

## Setup

1. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

2. **Run the app**
   ```
   python main.py
   ```

## How to get a Bot Token

1. Go to https://discord.com/developers/applications
2. Create a **New Application**, then open the **Bot** tab
3. Click **Reset Token** and copy it
4. Under **OAuth2 → URL Generator**, enable:
   - Scopes: `bot`
   - Bot Permissions: `Administrator`
5. Open the generated URL to invite the bot to your server

## Usage

### Backing up
1. Paste your token on the **Bot Token** page and click Verify
2. Go to **Backup**, select your server, and click Start Backup
3. The `.dbak` file is saved to `~/Discord Backups/` by default
![image alt](https://github.com/kordrawr-maker/MangoRestore/blob/30ab6c28012dfe4399d33fa94eff2483995c2109/imgs/Screenshot%202026-04-13%20145046.png)
### Restoring
1. Go to **Restore**, click Browse and select a `.dbak` file
2. Select the target server (must be empty or you can opt to wipe it first)
3. Choose what to restore, then click Start Restore

## What gets saved
- ✅ Server name, icon, and settings
- ✅ All roles (with colors, permissions, hierarchy)
- ✅ All channels and categories (with permission overwrites)
- ✅ Custom emojis
- ✅ Optionally: last 100 messages per channel (read-only log)

## What cannot be restored
- ❌ Server members (Discord doesn't allow this)
- ❌ Message history as original authors
- ❌ Webhooks, integrations, or bots
- ❌ Boost status or nitro perks

## Notes
- The bot needs **Administrator** permission
- Large servers may take a few minutes due to Discord rate limits
- Backups are stored as `.dbak` files (a zip containing `backup.json`)
