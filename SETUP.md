# 🗡️ RO MVP Timer Bot — Setup Guide

## 📁 Project File Structure

These are the only files you need to set up manually. Everything else is created automatically when the bot runs.

```
your-project-folder/
│
├── bot.py                ← Main bot file
├── mvp_data.json         ← MVP database
├── requirements.txt      ← Python dependencies
├── .env                  ← Your secret tokens (NEVER share this)
├── .env.example          ← Safe blank template (fine to share/commit)
└── .gitignore            ← Tells Git to ignore .env and runtime files
```

### 🤖 Auto-Created at Runtime

The bot will create these files on its own the first time it runs — **you do not need to create or include them**:

| File | Created when | Purpose |
|---|---|---|
| `active_timers.json` | Bot starts | Stores live MVP timers, survives restarts |
| `kill_log.json` | First kill is logged | Tracks all confirmed kills for the leaderboard |
| `kill_log_archive.json` | First `/resetlog` is run | Stores previous season data |
| `config.json` | `/settracker` is run | Saves the live tracker channel and message ID |

> 📊 **How kill tracking works:** Every time `/startmvp` or `/kc` is used, the kill is appended to `kill_log.json` with the killer's name, Discord ID, MVP name, map, and timestamp. This powers the `/mvptop` leaderboard and `/mvpstats` per-player breakdowns. When a new season starts, an admin runs `/resetlog` — this moves all current entries into `kill_log_archive.json` (so history is never lost) and starts a fresh `kill_log.json`. The `/lastseason` command reads from the archive so previous season standings are always accessible.

---

## ✅ Step 1 — Install Dependencies

Open a terminal in your project folder (in PyCharm: **Terminal** tab at the bottom) and run:

```bash
pip install -r requirements.txt
```

---

## ✅ Step 2 — Create the `.env` File

Copy `.env.example`, rename it to `.env`, and fill in your values:

```
DISCORD_TOKEN=your_bot_token_here
ALERT_CHANNEL_ID=your_alert_channel_id_here
```

**How to get your bot token:**
- Go to https://discord.com/developers/applications
- Select your app → **Bot** → **Reset Token** → Copy it
- Paste it after `DISCORD_TOKEN=` (no quotes needed)

**How to get your channel ID:**
- In Discord, enable Developer Mode: Settings → Advanced → Developer Mode ON
- Right-click the channel you want spawn alerts posted in → **Copy Channel ID**
- Paste it after `ALERT_CHANNEL_ID=`

> ⚠️ **NEVER share your `.env` file or paste your token in chat, GitHub, etc.**
> The `.env.example` file has no real values and is safe to share.

---

## ✅ Step 3 — Fill In the Bot Config (`bot.py`)

Open `bot.py` and update the two sections near the top:

### Server ID
```python
GUILD_ID = 000000000000000000  # ← Replace with your Discord server ID
```
**How to get your server ID:** Right-click your server icon in Discord → **Copy Server ID** (requires Developer Mode)

### KC Role Restriction
The `/kc` (bloody branch kill) command is role-gated. Add the IDs of roles allowed to use it:

```python
KC_ALLOWED_ROLES = {
    123456789012345678,   # e.g. Officer role
    123456789012345679,   # e.g. Member role
}
```
**How to get a role ID:** Server Settings → Roles → right-click a role → **Copy Role ID**

> ℹ️ If you want `/kc` open to everyone, you can either clear this set or skip setting it up — users without matching roles will just get a permission denied message.

---

## ✅ Step 4 — Create the Virtual Environment in PyCharm

1. Go to **File → Settings → Project → Python Interpreter**
2. Click ⚙️ → **Add Interpreter → Add Local Interpreter**
3. Choose **Virtualenv Environment** → **New environment** → click **OK**
4. Open the **Terminal** tab — you should see `(.venv)` at the start of the line
5. Run: `pip install -r requirements.txt`

---

## ✅ Step 5 — Discord Bot Permissions

Make sure your bot has these permissions when inviting it to a server:
- **Read Messages / View Channels**
- **Send Messages**
- **Embed Links**
- **Mention Everyone** (for spawn window alerts)
- **Read Message History**
- **Manage Messages** (to edit the live tracker message)

In the Developer Portal under **Bot**, enable:
- ✅ **Message Content Intent** (required for prefix commands like `!startmvp`)

---

## ✅ Step 6 — Run the Bot

Press the green ▶️ button in PyCharm, or in the terminal:

```bash
python bot.py
```

You should see:
```
Logged in as YourBotName (ID: xxxxxxxxxxxxxxxxxx)
Synced X slash commands to guild xxxxxxxxxxxxxxxxxx
```

---

## ✅ Step 7 — Set Up the Live Tracker

The live tracker is a pinned message the bot auto-edits every 30 seconds with current timer status.

1. Go to the channel you want the tracker in
2. Run `/settracker` or `!settracker` (admin only)
3. **Pin the message** the bot posts so it stays visible
4. The bot will keep it updated automatically — channel and message IDs are saved to `config.json`

---

## 🤖 Commands Reference

All commands support both **slash** (`/command`) and **prefix** (`!command`) versions. Slash commands have autocomplete for MVP names.

### ⚔️ Timers

| Slash | Prefix | Description |
|---|---|---|
| `/startmvp <mvp> [killer]` | `!startmvp [killer] <mvp>` | Confirmed kill — timer starts now, logged to leaderboard |
| `/tombmvp <mvp> spawns_in:<mins>` | `!tombmvp <mvp> spawns:45` | Tomb found — window opens in X minutes, no kill credit |
| `/tombmvp <mvp> minutes_ago:<mins>` | `!tombmvp <mvp> ago:5` | Found tomb X minutes ago, no kill credit |
| `/kc <mvp> [killer]` | `!kc [killer] <mvp>` | Bloody branch kill — leaderboard only, no timer |
| `/endmvp <mvp>` | `!endmvp <mvp>` | Remove an MVP from active tracking |

### 📋 Info

| Slash | Prefix | Description |
|---|---|---|
| `/listmvp` | `!listmvp` | Snapshot of all active timers with countdowns |
| `/mvpinfo <mvp>` | `!mvpinfo <mvp>` | Map and respawn window for an MVP |
| `/mvplist` | `!mvplist` | All MVPs in the database |
| `/mvptop` | `!mvptop` | Current season kill leaderboard |
| `/lastseason` | `!lastseason` | Archived pre-season leaderboard |
| `/mvpstats [player]` | `!mvpstats [player]` | Kill breakdown for a player — defaults to yourself |
| `/mvphelp` | `!mvphelp` | Show command help in Discord |

### 🔒 Admin Only

| Slash | Prefix | Description |
|---|---|---|
| `/settracker` | `!settracker` | Set this channel as the live auto-updating MVP board |
| `/cleartimers` | `!cleartimers` | Wipe all active timers |
| `/resetlog` | `!resetlog` | Archive kill log and start a fresh season |
| `/resetall` | `!resetall` | Archive kill log and wipe all timers — full reset |
| — | `!sync` | Force re-sync slash commands to the guild |

> ⚠️ `resetlog` and `resetall` require a confirmation button before executing.

---

## 🔔 Automatic Alerts

Every 30 seconds the bot:
- **Pings the person who logged the timer** when an MVP enters its spawn window
- **Edits the live tracker message** to stay current

Timer status indicators:
- 🟢 **waiting** — spawn window not open yet
- 🟠 **SOON** — opens within 10 minutes
- 🟡 **IN WINDOW** — MVP is currently spawnable
- 🔴 **OVERDUE** — past the max spawn time

Timers auto-expire 20 minutes after the max respawn time.

---

## 📝 Adding Custom MVPs

Open `mvp_data.json` and add entries in this format:

```json
"MVP Name Here": {
  "map": "map_code",
  "map_name": "Human Readable Map Name",
  "respawn_min": 60,
  "respawn_max": 70,
  "notes": "Any tips or notes here"
}
```

Respawn times are in **minutes**. `notes` is optional and shows up in timer embeds and `/mvpinfo`.

### Group MVPs (multiple spawns)

For MVPs like Atroce with multiple map spawns, add each one individually in `mvp_data.json` then register the group in `bot.py`:

```python
MVP_GROUPS = {
    "atroce": ["Atroce1", "Atroce2", "Atroce3", "Atroce4", "Atroce5"],
}

MVP_GROUP_LABELS = {
    "Atroce1": "Atroce — Veins Field 1",
    "Atroce2": "Atroce — Veins Field 2",
    # etc.
}
```

Typing `/startmvp atroce` will prompt the user with buttons to pick the specific spawn.
