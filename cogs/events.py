# cogs/events.py
import discord
from discord.ext import commands
from .util import set_channel_id, get_channel_id

class EventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_available(self, guild: discord.Guild):
        # Capture channel ids into cfg for quick lookup
        for key, name in self.bot.canonical_channels.items():
            ch = discord.utils.get(guild.text_channels, name=name)
            if ch:
                set_channel_id(guild.id, key, ch.id)

async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))
