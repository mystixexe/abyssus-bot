# cogs/info.py
import discord
from discord.ext import commands
from discord import app_commands

HELP_MARKER = "[WR COMMANDS]"

class InfoCog(commands.Cog, name="InfoCog"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def post_or_update_help(self, guild: discord.Guild):
        ch = discord.utils.get(guild.text_channels, name=self.bot.canonical_channels["info"])
        if not ch: return
        embed = discord.Embed(
            title=HELP_MARKER,
            description=(
                "### Commands & UI\n"
                "• `/setup-submission-box` — Post the submission UI.\n"
                "• `/setup-leaderboard-box` — Post the leaderboard UI.\n\n"
                "### Flow\n"
                "1) Submit via **Submission Box** (Solo/Team).\n"
                "2) Reviewed by **Abyssal Warden** in **#pending-submissions**.\n"
                "3) Approved → **#world-records** + leaderboard update.\n"
                "4) Post screenshots in **#wr-screenshots** (optional)."
            ),
            color=self.bot.theme_color
        )
        embed.set_footer(text="WR Bot — Command Index")
        async for m in ch.history(limit=50):
            if m.author == guild.me and m.embeds and m.embeds[0].title == HELP_MARKER:
                await m.edit(embed=embed)
                return
        await ch.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(InfoCog(bot))
