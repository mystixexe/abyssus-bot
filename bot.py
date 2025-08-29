# bot.py
# Abyssal WR Bot — cog-based rewrite (keeps wr_data/ persistence)
# Python 3.11+, discord.py 2.x

import os
import logging
import discord
from discord.ext import commands

logging.basicConfig(level=logging.INFO)

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True

APPROVAL_ROLE = "Abyssal Warden"
BRAND_PREFIX = "[WR BOT]"
THEME_COLOR = 0x7B68EE

# Canonical channel names
CHAN_PENDING = "pending-submissions"
CHAN_WORLD = "world-records"
CHAN_LEADER = "wr-leaderboard"
CHAN_INFO = "bot-commands-info"
CHAN_SCREEN = "wr-screenshots"

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", help_command=None, intents=INTENTS)
        self.theme_color = THEME_COLOR
        self.brand_prefix = BRAND_PREFIX
        self.approval_role_name = APPROVAL_ROLE
        self.canonical_channels = {
            "pending": CHAN_PENDING,
            "records": CHAN_WORLD,
            "leaderboard": CHAN_LEADER,
            "info": CHAN_INFO,
            "screens": CHAN_SCREEN,
        }

    async def setup_hook(self):
        # Load cogs
        for ext in ("cogs.events", "cogs.info", "cogs.submission", "cogs.approval", "cogs.leaderboard"):
            try:
                await self.load_extension(ext)
                logging.info(f"Loaded {ext}")
            except Exception as e:
                logging.exception(f"Failed to load {ext}: {e}")
        await self.tree.sync()
        logging.info("Application commands synced.")

    async def ensure_role_and_channels(self, guild: discord.Guild):
        # Role
        role = discord.utils.get(guild.roles, name=self.approval_role_name)
        if not role:
            try:
                role = await guild.create_role(
                    name=self.approval_role_name,
                    reason="WR Bot auto-create approver role"
                )
                logging.info(f"Created role {self.approval_role_name} in {guild.name}")
            except discord.Forbidden:
                logging.warning(f"[{guild.name}] Missing permissions to create role {self.approval_role_name}")
            except Exception as e:
                logging.error(f"[{guild.name}] Failed to create role: {e}")

        # Helper: Locked channel (readonly)
        async def get_or_create_locked(name: str):
            ch = discord.utils.get(guild.text_channels, name=name)
            if ch: return ch
            try:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True),
                }
                return await guild.create_text_channel(name, overwrites=overwrites, reason="WR Bot setup")
            except discord.Forbidden:
                logging.warning(f"[{guild.name}] Missing permissions to create locked channel {name}")
            except Exception as e:
                logging.error(f"[{guild.name}] Failed to create locked channel {name}: {e}")

        # Helper: Pending channel (private for wardens/admins)
        async def get_or_create_pending(name: str):
            ch = discord.utils.get(guild.text_channels, name=name)
            if ch: return ch
            try:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True),
                }
                role = discord.utils.get(guild.roles, name=self.approval_role_name)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True,
                        read_message_history=True, add_reactions=True
                    )
                return await guild.create_text_channel(name, overwrites=overwrites, reason="WR Bot setup")
            except discord.Forbidden:
                logging.warning(f"[{guild.name}] Missing permissions to create pending channel {name}")
            except Exception as e:
                logging.error(f"[{guild.name}] Failed to create pending channel {name}: {e}")

        # Helper: Open channel (screenshots)
        async def get_or_create_open(name: str):
            ch = discord.utils.get(guild.text_channels, name=name)
            if ch: return ch
            try:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True),
                }
                return await guild.create_text_channel(name, overwrites=overwrites, reason="WR Bot setup")
            except discord.Forbidden:
                logging.warning(f"[{guild.name}] Missing permissions to create open channel {name}")
            except Exception as e:
                logging.error(f"[{guild.name}] Failed to create open channel {name}: {e}")

        # Ensure channels
        await get_or_create_locked(CHAN_INFO)
        await get_or_create_locked(CHAN_WORLD)
        await get_or_create_locked(CHAN_LEADER)
        await get_or_create_pending(CHAN_PENDING)
        await get_or_create_open(CHAN_SCREEN)

bot = Bot()

@bot.event
async def on_ready():
    # Ensure resources in all guilds
    for g in bot.guilds:
        await bot.ensure_role_and_channels(g)
        try:
            await bot.get_cog("InfoCog").post_or_update_help(g)
            await bot.get_cog("SubmissionCog").post_or_update_submission_box(g)
            await bot.get_cog("LeaderboardCog").post_or_update_leaderboard_box(g)
        except Exception as e:
            logging.exception(f"Startup posting in {g.name} failed: {e}")
    logging.info(f"Logged in as: {bot.user} (ID: {bot.user.id})")

def main():
    token = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN")
    if not token:
        print("Set DISCORD_TOKEN env var.")
        return
    bot.run(token)

if __name__ == "__main__":
    main()
