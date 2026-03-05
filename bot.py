import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID", 0))

GUILD_ID = 000000000000000000  # ← Replace with your Discord server ID
GUILD = discord.Object(id=GUILD_ID)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MVP_DATA_PATH      = os.path.join(BASE_DIR, "mvp_data.json")
ACTIVE_TIMERS_PATH = os.path.join(BASE_DIR, "active_timers.json")
KILL_LOG_PATH      = os.path.join(BASE_DIR, "kill_log.json")
ARCHIVE_PATH       = os.path.join(BASE_DIR, "kill_log_archive.json")
CONFIG_PATH        = os.path.join(BASE_DIR, "config.json")

KC_ALLOWED_ROLES = {
    # ← Replace these with your actual role IDs (right-click role → Copy Role ID)
    # 123456789012345678,  # e.g. Officer
    # 123456789012345679,  # e.g. Member
}

MVP_GROUPS = {
    "atroce": ["Atroce1", "Atroce2", "Atroce3", "Atroce4", "Atroce5"],
}

MVP_GROUP_LABELS = {
    "Atroce1": "Atroce — Veins Field 1",
    "Atroce2": "Atroce — Veins Field 2",
    "Atroce3": "Atroce — Rachel Field 2",
    "Atroce4": "Atroce — Rachel Field 3",
    "Atroce5": "Atroce — Rachel Field 4",
}

AUTO_EXPIRE_BUFFER = 20 * 60



# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# ---------------------------------------------------------------------------
# data helpers
# ---------------------------------------------------------------------------

def load_mvp_data() -> dict:
    with open(MVP_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["mvps"]

def load_active_timers() -> dict:
    if not os.path.exists(ACTIVE_TIMERS_PATH):
        return {}
    with open(ACTIVE_TIMERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_active_timers(timers: dict):
    with open(ACTIVE_TIMERS_PATH, "w", encoding="utf-8") as f:
        json.dump(timers, f, indent=2)

def load_kill_log() -> list:
    if not os.path.exists(KILL_LOG_PATH):
        return []
    with open(KILL_LOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_kill_log(log: list):
    with open(KILL_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

def load_archive() -> list:
    if not os.path.exists(ARCHIVE_PATH):
        return []
    with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_archive(log: list):
    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

def now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()

def log_kill(mvp_name: str, killer_name: str, killer_id: int, map_name: str, kill_time: float = None):
    log = load_kill_log()
    log.append({
        "mvp": mvp_name,
        "killer": killer_name,
        "killer_id": killer_id,
        "map": map_name,
        "timestamp": kill_time or now_ts()
    })
    save_kill_log(log)

def format_time_remaining(seconds: float) -> str:
    if seconds <= 0:
        return "NOW / OVERDUE"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"

def find_mvp(name: str, mvp_db: dict) -> tuple[str, dict] | tuple[None, None]:
    name_lower = name.lower()
    for mvp_name, data in mvp_db.items():
        if name_lower == mvp_name.lower():
            return mvp_name, data
    matches = [(n, d) for n, d in mvp_db.items() if name_lower in n.lower()]
    if len(matches) == 1:
        return matches[0]
    return None, None

def get_group_match(name: str) -> list[str] | None:
    return MVP_GROUPS.get(name.lower().strip())

def expire_old_timers(timers: dict) -> dict:
    current = now_ts()
    return {
        name: info for name, info in timers.items()
        if (info["killed_at"] + info["respawn_max"] + AUTO_EXPIRE_BUFFER) > current
    }

def build_leaderboard_embed(log: list, title: str) -> discord.Embed | str:
    if not log:
        return "No kills recorded for this period."

    kill_counts: dict[int, int] = {}
    mvp_counts: dict[int, dict[str, int]] = {}
    id_to_name: dict[int, str] = {}

    for entry in log:
        # support both old entries (no killer_id) and new ones
        kid = entry.get("killer_id")
        kname = entry.get("killer", "Unknown")
        mvp = entry["mvp"]

        if kid is None:
            # legacy entry — use name as key
            kid = kname
        id_to_name[kid] = kname
        kill_counts[kid] = kill_counts.get(kid, 0) + 1
        if kid not in mvp_counts:
            mvp_counts[kid] = {}
        mvp_counts[kid][mvp] = mvp_counts[kid].get(mvp, 0) + 1

    sorted_killers = sorted(kill_counts.items(), key=lambda x: x[1], reverse=True)
    embed = discord.Embed(title=title,
                          description=f"{len(log)} total kills recorded",
                          color=discord.Color.gold())

    for i, (kid, total) in enumerate(sorted_killers[:3]):
        name = id_to_name[kid]
        mention = f"<@{kid}>" if isinstance(kid, int) else f"**{kid}**"
        fav_mvp = max(mvp_counts[kid], key=mvp_counts[kid].get)
        fav_count = mvp_counts[kid][fav_mvp]
        embed.add_field(
            name=f"{i+1}. {name}",
            value=f"{mention} — **{total}** kills | favourite: {fav_mvp} ({fav_count}x)",
            inline=False
        )

    if len(sorted_killers) > 3:
        others = ", ".join(id_to_name[k] for k, _ in sorted_killers[3:])
        embed.set_footer(text=f"Others: {others}")

    return embed

def build_tracker_embed(timers: dict) -> discord.Embed:
    current = now_ts()

    if not timers:
        embed = discord.Embed(
            title="MVP Tracker — Live",
            description="No MVPs are currently being tracked.",
            color=discord.Color.dark_gray()
        )
        embed.set_footer(text="Use /startmvp or /tombmvp to add a timer.")
        return embed

    sorted_timers = sorted(
        timers.items(),
        key=lambda x: x[1]["killed_at"] + x[1]["respawn_min"]
    )

    embed = discord.Embed(
        title="MVP Tracker — Live",
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc)
    )

    for mvp_name, info in sorted_timers:
        min_spawn = info["killed_at"] + info["respawn_min"]
        max_spawn = info["killed_at"] + info["respawn_max"]
        time_to_min = min_spawn - current
        time_to_max = max_spawn - current

        if time_to_max <= 0:
            status, dot = "OVERDUE", "🔴"
        elif time_to_min <= 0:
            status, dot = "IN WINDOW", "🟡"
        elif time_to_min <= 600:
            status, dot = "SOON", "🟠"
        else:
            status, dot = "waiting", "🟢"

        confirmed = info.get("confirmed", True)
        kill_label = f"by **{info['killed_by']}**" if confirmed and info.get("killed_by") else "tomb timer"
        logged_by_id = info.get("started_by_id")
        logged_by = f" | logged by <@{logged_by_id}>" if logged_by_id else ""
        notes = info.get("notes", "")
        notes_line = f"\n> {notes}" if notes else ""

        value = (
            f"{dot} **{status}** — {info['map_name']} (`{info['map']}`)\n"
            f"Killed {kill_label}{logged_by}\n"
            f"Window: <t:{int(min_spawn)}:T> — <t:{int(max_spawn)}:T>\n"
            f"Opens in: **{format_time_remaining(time_to_min)}** | "
            f"Closes in: **{format_time_remaining(time_to_max)}**"
            f"{notes_line}"
        )
        embed.add_field(name=mvp_name, value=value, inline=False)

    embed.set_footer(text=f"Tracking {len(timers)} MVP(s) — updates every 30s")
    return embed


# ---------------------------------------------------------------------------
# confirmation view for destructive admin commands
# ---------------------------------------------------------------------------

class ConfirmView(discord.ui.View):
    def __init__(self, action: str):
        super().__init__(timeout=10)
        self.action = action
        self.confirmed = False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.send_message("Cancelled.", ephemeral=True)

    async def on_timeout(self):
        self.stop()


# ---------------------------------------------------------------------------
# spawn selector view
# ---------------------------------------------------------------------------

class SpawnSelectView(discord.ui.View):
    def __init__(self, keys: list[str], action: str, invoker: discord.Member,
                 killer: discord.Member = None, kill_time: float = None):
        super().__init__(timeout=30)
        self.action = action
        self.invoker = invoker
        self.killer = killer
        self.kill_time = kill_time
        self.mvp_db = load_mvp_data()

        for key in keys:
            label = MVP_GROUP_LABELS.get(key, key)
            button = discord.ui.Button(label=label, custom_id=key, style=discord.ButtonStyle.secondary)
            button.callback = self.make_callback(key)
            self.add_item(button)

    def make_callback(self, key: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.invoker:
                await interaction.response.send_message("This selection isn't for you.", ephemeral=True)
                return
            await interaction.message.delete()
            data = self.mvp_db[key]
            killer = self.killer or self.invoker
            if self.action == "startmvp":
                await _do_startmvp(interaction, key, data, killer)
            elif self.action == "tombmvp":
                await _do_tombmvp(interaction, key, data, self.kill_time or now_ts())
            elif self.action == "kc":
                await _do_kc(interaction, key, data, killer)
            await interaction.response.defer()
        return callback

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
        except Exception:
            pass


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------

async def _send(ctx_or_i, **kwargs):
    if isinstance(ctx_or_i, discord.Interaction):
        if ctx_or_i.response.is_done():
            await ctx_or_i.followup.send(**kwargs)
        else:
            await ctx_or_i.response.send_message(**kwargs)
    else:
        await ctx_or_i.send(**kwargs)

def _author(ctx_or_i) -> discord.Member:
    if isinstance(ctx_or_i, discord.Interaction):
        return ctx_or_i.user
    return ctx_or_i.author


async def _do_startmvp(ctx_or_i, exact: str, data: dict, killer: discord.Member):
    invoker = _author(ctx_or_i)
    kill_time = now_ts()
    respawn_min_sec = data["respawn_min"] * 60
    respawn_max_sec = data["respawn_max"] * 60

    # duplicate timer warning
    timers = load_active_timers()
    if exact in timers:
        existing = timers[exact]
        existing_by = existing.get("killed_by", "someone")
        existing_starter = existing.get("started_by_id")
        starter_mention = f"<@{existing_starter}>" if existing_starter else "someone"
        view = ConfirmView("overwrite")
        warn_msg = await _send(ctx_or_i,
            content=f"**{exact}** already has an active timer (killed by **{existing_by}**, "
                    f"logged by {starter_mention}). Overwrite it?",
            view=view)
        await view.wait()
        if not view.confirmed:
            return

    timers[exact] = {
        "killed_at": kill_time,
        "killed_by": killer.display_name,
        "started_by_id": invoker.id,
        "respawn_min": respawn_min_sec,
        "respawn_max": respawn_max_sec,
        "map": data["map"],
        "map_name": data["map_name"],
        "notes": data.get("notes", ""),
        "confirmed": True,
        "alerted_spawn": False
    }
    save_active_timers(timers)
    log_kill(exact, killer.display_name, killer.id, data["map_name"], kill_time)
    await update_live_tracker()

    respawn_min_ts = kill_time + respawn_min_sec
    respawn_max_ts = kill_time + respawn_max_sec

    embed = discord.Embed(title=f"{exact} — kill confirmed", color=discord.Color.red())
    embed.add_field(name="Map", value=f"{data['map_name']} (`{data['map']}`)", inline=False)
    embed.add_field(name="Killed by", value=killer.mention, inline=True)
    embed.add_field(name="Time of death", value=f"<t:{int(kill_time)}:T>", inline=True)
    embed.add_field(name="Respawn window",
                    value=f"<t:{int(respawn_min_ts)}:T> — <t:{int(respawn_max_ts)}:T>", inline=False)
    if data.get("notes"):
        embed.add_field(name="Notes", value=data["notes"], inline=False)
    embed.set_footer(text=f"Will ping {invoker.display_name} when respawn window opens.")
    await _send(ctx_or_i, embed=embed)


async def _do_tombmvp(ctx_or_i, exact: str, data: dict, kill_time: float):
    invoker = _author(ctx_or_i)
    respawn_min_sec = data["respawn_min"] * 60
    respawn_max_sec = data["respawn_max"] * 60

    # duplicate timer warning
    timers = load_active_timers()
    if exact in timers:
        existing = timers[exact]
        existing_by = existing.get("killed_by", "unknown")
        existing_starter = existing.get("started_by_id")
        starter_mention = f"<@{existing_starter}>" if existing_starter else "someone"
        view = ConfirmView("overwrite")
        await _send(ctx_or_i,
            content=f"**{exact}** already has an active timer (killed by **{existing_by}**, "
                    f"logged by {starter_mention}). Overwrite it?",
            view=view)
        await view.wait()
        if not view.confirmed:
            return

    timers[exact] = {
        "killed_at": kill_time,
        "killed_by": None,
        "started_by_id": invoker.id,
        "respawn_min": respawn_min_sec,
        "respawn_max": respawn_max_sec,
        "map": data["map"],
        "map_name": data["map_name"],
        "notes": data.get("notes", ""),
        "confirmed": False,
        "alerted_spawn": False
    }
    save_active_timers(timers)
    await update_live_tracker()

    respawn_min_ts = kill_time + respawn_min_sec
    respawn_max_ts = kill_time + respawn_max_sec

    embed = discord.Embed(title=f"{exact} — tomb timer", color=discord.Color.orange())
    embed.add_field(name="Map", value=f"{data['map_name']} (`{data['map']}`)", inline=False)
    embed.add_field(name="Time of death", value=f"<t:{int(kill_time)}:T>", inline=True)
    embed.add_field(name="Respawn window",
                    value=f"<t:{int(respawn_min_ts)}:T> — <t:{int(respawn_max_ts)}:T>", inline=False)
    if data.get("notes"):
        embed.add_field(name="Notes", value=data["notes"], inline=False)
    embed.set_footer(text=f"Kill not credited — timer only. Will ping {invoker.display_name}.")
    await _send(ctx_or_i, embed=embed)


async def _do_kc(ctx_or_i, exact: str, data: dict, killer: discord.Member):
    log_kill(exact, killer.display_name, killer.id, data["map_name"], now_ts())
    await _send(ctx_or_i,
        content=f"Kill credited — {killer.mention} killed **{exact}** (bloody branch). Logged to leaderboard.")


# ---------------------------------------------------------------------------
# live tracker + bot status
# ---------------------------------------------------------------------------

async def update_live_tracker():
    cfg = load_config()
    channel_id = cfg.get("tracker_channel_id")
    message_id = cfg.get("tracker_message_id")
    if not channel_id or not message_id:
        return
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return
    try:
        msg = await channel.fetch_message(int(message_id))
        timers = expire_old_timers(load_active_timers())
        save_active_timers(timers)
        await msg.edit(embed=build_tracker_embed(timers))
    except Exception:
        pass

async def update_bot_status():
    timers = load_active_timers()
    timers = expire_old_timers(timers)
    count = len(timers)
    if count == 0:
        activity = discord.Game(name="No MVPs tracked")
    else:
        activity = discord.Game(name=f"Tracking {count} MVP{'s' if count != 1 else ''}")
    await bot.change_presence(activity=activity)


# ---------------------------------------------------------------------------
# autocomplete
# ---------------------------------------------------------------------------

async def mvp_autocomplete(interaction: discord.Interaction, current: str):
    mvp_db = load_mvp_data()
    all_names = list(mvp_db.keys()) + list(MVP_GROUPS.keys())
    matches = [n for n in all_names if current.lower() in n.lower()]
    return [app_commands.Choice(name=n, value=n) for n in sorted(matches)[:25]]


# ---------------------------------------------------------------------------
# on_ready
# ---------------------------------------------------------------------------

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"[SLASH ERROR] /{interaction.command.name if interaction.command else '?'}: {error}")
    try:
        await interaction.response.send_message(f"Error: {error}", ephemeral=True)
    except Exception:
        try:
            await interaction.followup.send(f"Error: {error}", ephemeral=True)
        except Exception:
            pass


@bot.event
async def on_ready():
    cfg = load_config()
    try:
        synced = await bot.tree.sync(guild=GUILD)
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")
        print(f"Synced {len(synced)} slash commands to guild {GUILD_ID}")
    except Exception as e:
        print(f"Sync failed: {e}")
    if not check_respawns.is_running():
        check_respawns.start()
    if not update_tracker_loop.is_running():
        update_tracker_loop.start()


@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def force_sync(ctx):
    """[Admin] Force re-sync slash commands to the guild."""
    try:
        # clear global commands first to avoid conflicts
        bot.tree.clear_commands(guild=None)
        # copy global-registered commands to the guild
        bot.tree.copy_global_to(guild=GUILD)
        synced = await bot.tree.sync(guild=GUILD)
        await ctx.send(f"Synced {len(synced)} slash commands to guild {GUILD_ID}.")
        # list them out so we can verify
        names = [c.name for c in synced]
        await ctx.send("Commands: " + ", ".join(names))
    except Exception as e:
        await ctx.send(f"Sync failed: {e}")


# ---------------------------------------------------------------------------
# /startmvp + !startmvp
# ---------------------------------------------------------------------------

@bot.tree.command(name="startmvp", description="Record a confirmed MVP kill. Timer starts now.",
                  guild=GUILD)
@app_commands.describe(mvp="MVP name (partial names work)",
                       killer="The player who got the kill (defaults to you)")
@app_commands.autocomplete(mvp=mvp_autocomplete)
async def slash_startmvp(interaction: discord.Interaction, mvp: str,
                          killer: discord.Member = None):
    if killer is None:
        killer = interaction.user
    mvp_db = load_mvp_data()
    exact, data = find_mvp(mvp, mvp_db)
    if not exact:
        group_keys = get_group_match(mvp)
        if group_keys:
            view = SpawnSelectView(group_keys, "startmvp", interaction.user, killer=killer)
            await interaction.response.send_message("Which spawn?", view=view, ephemeral=True)
            return
        await interaction.response.send_message(
            f"MVP **{mvp}** not found. Use `/mvplist` to see all.", ephemeral=True)
        return
    await interaction.response.defer()
    await _do_startmvp(interaction, exact, data, killer)

@bot.command(name="startmvp", aliases=["killedmvp", "kill"])
async def prefix_startmvp(ctx, killer: discord.Member = None, *, mvp_name: str):
    if killer is None:
        killer = ctx.author
    mvp_db = load_mvp_data()
    exact, data = find_mvp(mvp_name, mvp_db)
    if not exact:
        group_keys = get_group_match(mvp_name)
        if group_keys:
            view = SpawnSelectView(group_keys, "startmvp", ctx.author, killer=killer)
            await ctx.send("Which spawn?", view=view)
            return
        await ctx.send(f"MVP **{mvp_name}** not found. Use `!mvplist` to see all.")
        return
    await _do_startmvp(ctx, exact, data, killer)


# ---------------------------------------------------------------------------
# /tombmvp + !tombmvp
# ---------------------------------------------------------------------------

@bot.tree.command(name="tombmvp", description="Start a timer from a tomb. No kill credit.",
                  guild=GUILD)
@app_commands.describe(mvp="MVP name (partial names work)",
                       spawns_in="Minutes until it spawns (e.g. 45 if window opens in 45 mins)",
                       minutes_ago="Minutes since you found the tomb (e.g. 5 if you found it 5 mins ago)")
@app_commands.autocomplete(mvp=mvp_autocomplete)
async def slash_tombmvp(interaction: discord.Interaction, mvp: str,
                        spawns_in: int = None, minutes_ago: int = None):
    mvp_db = load_mvp_data()
    exact, data = find_mvp(mvp, mvp_db)
    kill_time = None

    if not exact:
        group_keys = get_group_match(mvp)
        if group_keys:
            view = SpawnSelectView(group_keys, "tombmvp", interaction.user, kill_time=now_ts())
            await interaction.response.send_message("Which spawn?", view=view, ephemeral=True)
            return
        await interaction.response.send_message(
            f"MVP **{mvp}** not found. Use `/mvplist` to see all.", ephemeral=True)
        return

    if spawns_in is not None:
        # spawns_in X minutes means the respawn window opens in X minutes
        # so kill happened (respawn_min - spawns_in) minutes ago
        kill_time = now_ts() - (data["respawn_min"] * 60 - spawns_in * 60)
    elif minutes_ago is not None:
        # tomb was found X minutes ago, so kill happened X minutes ago
        kill_time = now_ts() - (minutes_ago * 60)
    else:
        await interaction.response.send_message(
            "Provide either `spawns_in` (minutes until spawn) or `minutes_ago` (how long ago you found the tomb).",
            ephemeral=True)
        return

    await interaction.response.defer()
    await _do_tombmvp(interaction, exact, data, kill_time)

@bot.command(name="tombmvp", aliases=["tomb", "trackmvp"])
async def prefix_tombmvp(ctx, *, args: str = None):
    """
    Usage: !tombmvp <mvp> spawns:<minutes>   — spawns in X minutes
           !tombmvp <mvp> ago:<minutes>       — found tomb X minutes ago
    """
    if args is None:
        await ctx.send("Usage: `!tombmvp <mvp> spawns:45` or `!tombmvp <mvp> ago:5`")
        return

    mvp_db = load_mvp_data()
    kill_time = None

    # parse "spawns:X" or "ago:X" suffix
    import re
    spawns_match = re.search(r'spawns:(\d+)', args)
    ago_match = re.search(r'ago:(\d+)', args)
    mvp_name = re.sub(r'(spawns|ago):\d+', '', args).strip()

    exact, data = find_mvp(mvp_name, mvp_db)
    if not exact:
        group_keys = get_group_match(mvp_name)
        if group_keys:
            view = SpawnSelectView(group_keys, "tombmvp", ctx.author, kill_time=now_ts())
            await ctx.send("Which spawn?", view=view)
            return
        await ctx.send(f"MVP **{mvp_name}** not found. Use `!mvplist` to see all.")
        return

    if spawns_match:
        spawns_in = int(spawns_match.group(1))
        kill_time = now_ts() - (data["respawn_min"] * 60 - spawns_in * 60)
    elif ago_match:
        minutes_ago = int(ago_match.group(1))
        kill_time = now_ts() - (minutes_ago * 60)
    else:
        await ctx.send("Specify time: `!tombmvp <mvp> spawns:45` or `!tombmvp <mvp> ago:5`")
        return

    await _do_tombmvp(ctx, exact, data, kill_time)


# ---------------------------------------------------------------------------
# /kc + !kc
# ---------------------------------------------------------------------------

@bot.tree.command(name="kc", description="Log a bloody branch kill to the leaderboard. No timer.",
                  guild=GUILD)
@app_commands.describe(mvp="MVP name", killer="The player who got the kill (defaults to you)")
@app_commands.autocomplete(mvp=mvp_autocomplete)
async def slash_kc(interaction: discord.Interaction, mvp: str, killer: discord.Member = None):
    user_role_ids = {role.id for role in interaction.user.roles}
    if not user_role_ids & KC_ALLOWED_ROLES:
        await interaction.response.send_message("You don't have permission to use this command.",
                                                ephemeral=True)
        return
    if killer is None:
        killer = interaction.user
    mvp_db = load_mvp_data()
    exact, data = find_mvp(mvp, mvp_db)
    if not exact:
        group_keys = get_group_match(mvp)
        if group_keys:
            view = SpawnSelectView(group_keys, "kc", interaction.user, killer=killer)
            await interaction.response.send_message("Which spawn?", view=view, ephemeral=True)
            return
        await interaction.response.send_message(
            f"MVP **{mvp}** not found. Use `/mvplist` to see all.", ephemeral=True)
        return
    await interaction.response.defer()
    await _do_kc(interaction, exact, data, killer)

@bot.command(name="kc", aliases=["branchkill", "bc"])
async def prefix_kc(ctx, killer: discord.Member = None, *, mvp_name: str):
    user_role_ids = {role.id for role in ctx.author.roles}
    if not user_role_ids & KC_ALLOWED_ROLES:
        await ctx.send("You don't have permission to use this command.")
        return
    if killer is None:
        killer = ctx.author
    mvp_db = load_mvp_data()
    exact, data = find_mvp(mvp_name, mvp_db)
    if not exact:
        group_keys = get_group_match(mvp_name)
        if group_keys:
            view = SpawnSelectView(group_keys, "kc", ctx.author, killer=killer)
            await ctx.send("Which spawn?", view=view)
            return
        await ctx.send(f"MVP **{mvp_name}** not found.")
        return
    await _do_kc(ctx, exact, data, killer)


# ---------------------------------------------------------------------------
# /endmvp + !endmvp
# ---------------------------------------------------------------------------

@bot.tree.command(name="endmvp", description="Remove an MVP from active tracking.", guild=GUILD)
@app_commands.describe(mvp="MVP name to remove")
@app_commands.autocomplete(mvp=mvp_autocomplete)
async def slash_endmvp(interaction: discord.Interaction, mvp: str):
    mvp_db = load_mvp_data()
    exact, _ = find_mvp(mvp, mvp_db)
    if not exact:
        await interaction.response.send_message(f"MVP **{mvp}** not found.", ephemeral=True)
        return
    timers = load_active_timers()
    if exact not in timers:
        await interaction.response.send_message(f"**{exact}** is not currently being tracked.",
                                                ephemeral=True)
        return
    del timers[exact]
    save_active_timers(timers)
    await update_live_tracker()
    await interaction.response.send_message(f"Removed **{exact}** from active timers.")

@bot.command(name="endmvp", aliases=["removemvp", "clearmvp"])
async def prefix_endmvp(ctx, *, mvp_name: str):
    mvp_db = load_mvp_data()
    exact, _ = find_mvp(mvp_name, mvp_db)
    if not exact:
        await ctx.send(f"MVP **{mvp_name}** not found.")
        return
    timers = load_active_timers()
    if exact not in timers:
        await ctx.send(f"**{exact}** is not currently being tracked.")
        return
    del timers[exact]
    save_active_timers(timers)
    await update_live_tracker()
    await ctx.send(f"Removed **{exact}** from active timers.")


# ---------------------------------------------------------------------------
# /listmvp + !listmvp  — ephemeral
# ---------------------------------------------------------------------------

@bot.tree.command(name="listmvp", description="Show a snapshot of all active MVP timers.",
                  guild=GUILD)
async def slash_listmvp(interaction: discord.Interaction):
    timers = expire_old_timers(load_active_timers())
    save_active_timers(timers)
    await interaction.response.send_message(embed=build_tracker_embed(timers), ephemeral=True)

@bot.command(name="listmvp", aliases=["timers", "mvptimers"])
async def prefix_listmvp(ctx):
    timers = expire_old_timers(load_active_timers())
    save_active_timers(timers)
    await ctx.send(embed=build_tracker_embed(timers))


# ---------------------------------------------------------------------------
# /mvpinfo + !mvpinfo  — ephemeral
# ---------------------------------------------------------------------------

@bot.tree.command(name="mvpinfo", description="Look up an MVP's map and respawn window.",
                  guild=GUILD)
@app_commands.describe(mvp="MVP name")
@app_commands.autocomplete(mvp=mvp_autocomplete)
async def slash_mvpinfo(interaction: discord.Interaction, mvp: str):
    mvp_db = load_mvp_data()
    exact, data = find_mvp(mvp, mvp_db)
    if not exact:
        await interaction.response.send_message(
            f"MVP **{mvp}** not found.", ephemeral=True)
        return
    embed = discord.Embed(title=exact, color=discord.Color.gold())
    embed.add_field(name="Map", value=f"{data['map_name']} (`{data['map']}`)", inline=False)
    embed.add_field(name="Respawn window",
                    value=f"{data['respawn_min']}–{data['respawn_max']} minutes", inline=True)
    if data.get("notes"):
        embed.add_field(name="Notes", value=data["notes"], inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name="mvpinfo", aliases=["info"])
async def prefix_mvpinfo(ctx, *, mvp_name: str):
    mvp_db = load_mvp_data()
    exact, data = find_mvp(mvp_name, mvp_db)
    if not exact:
        await ctx.send(f"MVP **{mvp_name}** not found.")
        return
    embed = discord.Embed(title=exact, color=discord.Color.gold())
    embed.add_field(name="Map", value=f"{data['map_name']} (`{data['map']}`)", inline=False)
    embed.add_field(name="Respawn window",
                    value=f"{data['respawn_min']}–{data['respawn_max']} minutes", inline=True)
    if data.get("notes"):
        embed.add_field(name="Notes", value=data["notes"], inline=False)
    await ctx.send(embed=embed)


# ---------------------------------------------------------------------------
# /mvplist + !mvplist  — ephemeral
# ---------------------------------------------------------------------------

@bot.tree.command(name="mvplist", description="List all MVPs in the database.", guild=GUILD)
async def slash_mvplist(interaction: discord.Interaction):
    mvp_db = load_mvp_data()
    embed = discord.Embed(title="MVP Database",
                          description="Partial names work in all commands.",
                          color=discord.Color.purple())
    names = sorted(mvp_db.keys())
    for i in range(0, len(names), 15):
        chunk = names[i:i + 15]
        embed.add_field(name=f"{i+1}–{i+len(chunk)}", value="\n".join(chunk), inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name="mvplist", aliases=["allmvp", "mvps"])
async def prefix_mvplist(ctx):
    mvp_db = load_mvp_data()
    embed = discord.Embed(title="MVP Database",
                          description="Partial names work in all commands.",
                          color=discord.Color.purple())
    names = sorted(mvp_db.keys())
    for i in range(0, len(names), 15):
        chunk = names[i:i + 15]
        embed.add_field(name=f"{i+1}–{i+len(chunk)}", value="\n".join(chunk), inline=True)
    await ctx.send(embed=embed)


# ---------------------------------------------------------------------------
# /mvptop + !mvptop
# ---------------------------------------------------------------------------

@bot.tree.command(name="mvptop", description="Show the current season kill leaderboard.",
                  guild=GUILD)
async def slash_mvptop(interaction: discord.Interaction):
    log = load_kill_log()
    result = build_leaderboard_embed(log, "MVP Kill Leaderboard — Current Season")
    if isinstance(result, str):
        await interaction.response.send_message(result, ephemeral=True)
    else:
        await interaction.response.send_message(embed=result)

@bot.command(name="mvptop", aliases=["leaderboard", "topmvp"])
async def prefix_mvptop(ctx):
    log = load_kill_log()
    result = build_leaderboard_embed(log, "MVP Kill Leaderboard — Current Season")
    if isinstance(result, str):
        await ctx.send(result)
    else:
        await ctx.send(embed=result)


# ---------------------------------------------------------------------------
# /lastseason + !lastseason
# ---------------------------------------------------------------------------

@bot.tree.command(name="lastseason", description="Show the archived pre-season leaderboard.",
                  guild=GUILD)
async def slash_lastseason(interaction: discord.Interaction):
    log = load_archive()
    result = build_leaderboard_embed(log, "MVP Kill Leaderboard — Pre-Season Archive")
    if isinstance(result, str):
        await interaction.response.send_message(result, ephemeral=True)
    else:
        await interaction.response.send_message(embed=result)

@bot.command(name="lastseason", aliases=["prevseason", "archive"])
async def prefix_lastseason(ctx):
    log = load_archive()
    result = build_leaderboard_embed(log, "MVP Kill Leaderboard — Pre-Season Archive")
    if isinstance(result, str):
        await ctx.send(result)
    else:
        await ctx.send(embed=result)


# ---------------------------------------------------------------------------
# /mvpstats + !mvpstats
# ---------------------------------------------------------------------------

def _build_stats_embed(target: discord.Member) -> discord.Embed | str:
    log = load_kill_log()
    if not log:
        return "No kills recorded yet this season."
    target_name = target.display_name
    player_kills = [e for e in log if e["killer"].lower() == target_name.lower()]
    if not player_kills:
        return f"No kills found for {target.mention} this season."
    mvp_tally: dict[str, int] = {}
    for entry in player_kills:
        mvp_tally[entry["mvp"]] = mvp_tally.get(entry["mvp"], 0) + 1
    sorted_mvps = sorted(mvp_tally.items(), key=lambda x: x[1], reverse=True)
    embed = discord.Embed(title=f"Stats: {target_name}",
                          description=f"**{len(player_kills)}** kills this season",
                          color=discord.Color.orange())
    kill_lines = "\n".join(f"{mvp} — {count}x" for mvp, count in sorted_mvps)
    embed.add_field(name="Kill breakdown", value=kill_lines, inline=False)
    all_counts = {}
    for entry in log:
        all_counts[entry["killer"]] = all_counts.get(entry["killer"], 0) + 1
    rank = sorted(all_counts.items(), key=lambda x: x[1], reverse=True)
    rank_pos = next((i + 1 for i, (p, _) in enumerate(rank)
                     if p.lower() == target_name.lower()), "?")
    embed.set_footer(text=f"Season rank: #{rank_pos} of {len(rank)}")
    return embed

@bot.tree.command(name="mvpstats", description="Show kill stats for a player this season.",
                  guild=GUILD)
@app_commands.describe(player="The player to look up (defaults to you)")
async def slash_mvpstats(interaction: discord.Interaction, player: discord.Member = None):
    target = player or interaction.user
    result = _build_stats_embed(target)
    if isinstance(result, str):
        await interaction.response.send_message(result, ephemeral=True)
    else:
        await interaction.response.send_message(embed=result, ephemeral=True)

@bot.command(name="mvpstats", aliases=["stats", "myscore"])
async def prefix_mvpstats(ctx, member: discord.Member = None):
    target = member or ctx.author
    result = _build_stats_embed(target)
    if isinstance(result, str):
        await ctx.send(result)
    else:
        await ctx.send(embed=result)


# ---------------------------------------------------------------------------
# admin commands
# ---------------------------------------------------------------------------

@bot.tree.command(name="settracker",
                  description="[Admin] Set this channel as the live auto-updating MVP board.",
                  guild=GUILD)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.default_permissions(administrator=True)
async def slash_settracker(interaction: discord.Interaction):
    # Acknowledge immediately, then send the tracker as a followup
    # so we get a real Message object with a reliable ID
    await interaction.response.send_message("Setting up live tracker...", ephemeral=True)
    timers = load_active_timers()
    embed = build_tracker_embed(timers)
    msg = await interaction.channel.send(embed=embed)
    cfg = load_config()
    cfg["tracker_channel_id"] = interaction.channel_id
    cfg["tracker_message_id"] = msg.id
    save_config(cfg)
    await interaction.edit_original_response(
        content="Live tracker set. Pin that message — it updates every 30 seconds.")

@bot.command(name="settracker")
@commands.has_permissions(administrator=True)
async def prefix_settracker(ctx):
    timers = load_active_timers()
    msg = await ctx.send(embed=build_tracker_embed(timers))
    cfg = load_config()
    cfg["tracker_channel_id"] = ctx.channel.id
    cfg["tracker_message_id"] = msg.id
    save_config(cfg)
    await ctx.send("Live tracker set. Pin that message — it updates every 30 seconds.",
                   delete_after=15)




@bot.tree.command(name="cleartimers", description="[Admin] Clear all active timers.", guild=GUILD)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.default_permissions(administrator=True)
async def slash_cleartimers(interaction: discord.Interaction):
    save_active_timers({})
    await update_live_tracker()
    await interaction.response.send_message("All active timers cleared.")

@bot.command(name="cleartimers", aliases=["clearall"])
@commands.has_permissions(administrator=True)
async def prefix_cleartimers(ctx):
    save_active_timers({})
    await update_live_tracker()
    await ctx.send("All active timers cleared.")


@bot.tree.command(name="resetlog",
                  description="[Admin] Archive the kill log and start a fresh season.",
                  guild=GUILD)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.default_permissions(administrator=True)
async def slash_resetlog(interaction: discord.Interaction):
    view = ConfirmView("resetlog")
    await interaction.response.send_message(
        "This will archive the current kill log and wipe the leaderboard. Are you sure?",
        view=view, ephemeral=True)
    await view.wait()
    if not view.confirmed:
        return
    current_log = load_kill_log()
    archive = load_archive()
    archive.extend(current_log)
    save_archive(archive)
    save_kill_log([])
    await interaction.followup.send(
        f"Kill log archived ({len(current_log)} entries saved). Leaderboard reset.",
        ephemeral=True)

@bot.command(name="resetlog")
@commands.has_permissions(administrator=True)
async def prefix_resetlog(ctx):
    view = ConfirmView("resetlog")
    msg = await ctx.send(
        "This will archive the current kill log and wipe the leaderboard. Are you sure?",
        view=view)
    await view.wait()
    if not view.confirmed:
        return
    current_log = load_kill_log()
    archive = load_archive()
    archive.extend(current_log)
    save_archive(archive)
    save_kill_log([])
    await ctx.send(f"Kill log archived ({len(current_log)} entries saved). Leaderboard reset.")


@bot.tree.command(name="resetall",
                  description="[Admin] Archive kill log and wipe all timers.",
                  guild=GUILD)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.default_permissions(administrator=True)
async def slash_resetall(interaction: discord.Interaction):
    view = ConfirmView("resetall")
    await interaction.response.send_message(
        "This will archive the kill log and clear all active timers. Are you sure?",
        view=view, ephemeral=True)
    await view.wait()
    if not view.confirmed:
        return
    current_log = load_kill_log()
    archive = load_archive()
    archive.extend(current_log)
    save_archive(archive)
    save_kill_log([])
    save_active_timers({})
    await update_live_tracker()
    await interaction.followup.send(
        f"Everything wiped. Kill log archived ({len(current_log)} entries). Fresh slate.",
        ephemeral=True)

@bot.command(name="resetall")
@commands.has_permissions(administrator=True)
async def prefix_resetall(ctx):
    view = ConfirmView("resetall")
    msg = await ctx.send(
        "This will archive the kill log and clear all active timers. Are you sure?",
        view=view)
    await view.wait()
    if not view.confirmed:
        return
    current_log = load_kill_log()
    archive = load_archive()
    archive.extend(current_log)
    save_archive(archive)
    save_kill_log([])
    save_active_timers({})
    await update_live_tracker()
    await ctx.send(f"Everything wiped. Kill log archived ({len(current_log)} entries). Fresh slate.")


# ---------------------------------------------------------------------------
# /help + !help  — ephemeral
# ---------------------------------------------------------------------------

def _help_text() -> str:
    return "\n".join([
        "**MVP Timer Bot — Commands**\n",
        "**Timers**",
        "`/startmvp <mvp> [killer]` — confirmed kill, timer from now, logged to leaderboard",
        "`/tombmvp <mvp> spawns_in:<mins>` — tomb found, window opens in X minutes",
        "`/tombmvp <mvp> minutes_ago:<mins>` — found the tomb X minutes ago",
        "`/kc <mvp> [killer]` — log a bloody branch kill (no timer)",
        "`/endmvp <mvp>` — remove an MVP from tracking",
        "",
        "**Info**",
        "`/listmvp` — snapshot of all active timers (only you see this)",
        "`/mvpinfo <mvp>` — map and respawn window for an MVP (only you see this)",
        "`/mvplist` — all MVPs in the database (only you see this)",
        "`/mvptop` — current season kill leaderboard",
        "`/lastseason` — archived pre-season leaderboard",
        "`/mvpstats [player]` — kill breakdown for a player (only you see this)",
        "",
        "**Admin**",
        "`/settracker` — set this channel as the live auto-updating board",
                "`/cleartimers` — wipe all active timers",
        "`/resetlog` — archive kill log and start fresh season",
        "`/resetall` — archive kill log and wipe all timers",
        "",
        "Slash commands have autocomplete — start typing an MVP name and Discord will suggest matches.",
    ])

@bot.tree.command(name="mvphelp", description="Show all bot commands.", guild=GUILD)
async def slash_help(interaction: discord.Interaction):
    await interaction.response.send_message(_help_text(), ephemeral=True)

@bot.command(name="mvphelp", aliases=["help"])
async def prefix_help(ctx):
    await ctx.send(_help_text())


# ---------------------------------------------------------------------------
# background tasks
# ---------------------------------------------------------------------------

@tasks.loop(seconds=30)
async def check_respawns():
    if ALERT_CHANNEL_ID == 0:
        return
    channel = bot.get_channel(ALERT_CHANNEL_ID)
    if not channel:
        return

    timers = load_active_timers()
    timers = expire_old_timers(timers)
    current = now_ts()
    changed = False

    for mvp_name, info in list(timers.items()):
        min_spawn = info["killed_at"] + info["respawn_min"]
        max_spawn = info["killed_at"] + info["respawn_max"]
        time_to_min = min_spawn - current

        if not info["alerted_spawn"] and time_to_min <= 0 and (current - min_spawn) < 60:
            info["alerted_spawn"] = True
            changed = True
            starter_id = info.get("started_by_id")
            ping = f"<@{starter_id}>" if starter_id else ""
            await channel.send(
                f"{ping} **{mvp_name}** is now in spawn window on "
                f"**{info['map_name']}** (`{info['map']}`). "
                f"Window closes <t:{int(max_spawn)}:R>."
            )

    if changed:
        save_active_timers(timers)


@tasks.loop(seconds=30)
async def update_tracker_loop():
    await update_live_tracker()
    await update_bot_status()


@check_respawns.before_loop
@update_tracker_loop.before_loop
async def before_tasks():
    await bot.wait_until_ready()


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN not found. Check your .env file.")
    else:
        bot.run(TOKEN)