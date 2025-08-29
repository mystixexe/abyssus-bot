# cogs/submission.py
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from .util import subs, save_subs

class SubmissionView(discord.ui.View):
    def __init__(self, cog: "SubmissionCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Submit Run (Solo)", style=discord.ButtonStyle.primary, custom_id="wr_submit_solo")
    async def solo(self, i: discord.Interaction, b: discord.ui.Button):
        await self.cog.start_solo_flow(i)

    @discord.ui.button(label="Submit Run (Team)", style=discord.ButtonStyle.secondary, custom_id="wr_submit_team")
    async def team(self, i: discord.Interaction, b: discord.ui.Button):
        await self.cog.start_team_flow(i)

class TeamSizeSelect(discord.ui.Select):
    def __init__(self, cog: "SubmissionCog"):
        options = [
            discord.SelectOption(label="2 Players", value="2"),
            discord.SelectOption(label="3 Players", value="3"),
            discord.SelectOption(label="4 Players", value="4"),
        ]
        super().__init__(placeholder="Team size", min_values=1, max_values=1, options=options, custom_id="wr_team_size")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cog.collect_team_players(interaction, int(self.values[0]))

class SubmissionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def box_embed(self):
        e = discord.Embed(
            title="[WR SUBMISSION BOX]",
            description=("Use the buttons to submit a run.\n"
                         "• **Solo**: pick runner (auto-fills you), choose **Time** or **Damage**, enter value, optional **Notes**.\n"
                         "• **Team**: choose 2p/3p/4p, pick players, choose **Time**/**Damage**, enter value, optional **Notes**."),
            color=self.bot.theme_color
        )
        e.set_footer(text="WR Bot · Submissions")
        return e

    async def post_or_update_submission_box(self, guild: discord.Guild):
        ch = discord.utils.get(guild.text_channels, name="wr-submissions")
        if not ch:
            return
        marker = "[WR SUBMISSION BOX]"
        async for m in ch.history(limit=50):
            if m.author == guild.me and m.embeds and m.embeds[0].title == marker:
                await m.edit(embed=self.box_embed(), view=SubmissionView(self))
                return
        await ch.send(embed=self.box_embed(), view=SubmissionView(self))

    async def _prompt(self, interaction: discord.Interaction, prompt: str, timeout=120) -> Optional[str]:
        await interaction.followup.send(f"{self.bot.brand_prefix} {prompt}", ephemeral=True)
        def check(m: discord.Message):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=timeout)
            content = msg.content.strip()
            try: await msg.delete()
            except: pass
            return content
        except asyncio.TimeoutError:
            await interaction.followup.send(f"{self.bot.brand_prefix} Timed out.", ephemeral=True)
            return None

    async def _choose_metric(self, interaction: discord.Interaction) -> Optional[str]:
        class Metric(discord.ui.Select):
            def __init__(self):
                opts = [
                    discord.SelectOption(label="Time", value="time", emoji="⏱️"),
                    discord.SelectOption(label="Damage", value="damage", emoji="💥"),
                ]
                super().__init__(placeholder="Time or Damage?", options=opts, min_values=1, max_values=1, custom_id="wr_metric")
                self.choice = None

            async def callback(self, i: discord.Interaction):
                self.choice = self.values[0]
                await i.response.edit_message(
                    content=f"{i.client.brand_prefix} ✅ Selected **{'Time' if self.choice=='time' else 'Damage'}**.",
                    view=None
                )
                self.view.stop()

        v = discord.ui.View(timeout=60); msel = Metric(); v.add_item(msel)
        await interaction.followup.send(f"{self.bot.brand_prefix} Choose **Time** or **Damage**.", view=v, ephemeral=True)
        await v.wait()
        return msel.choice

    async def _choose_user(self, interaction: discord.Interaction, default: discord.Member) -> Optional[int]:
        class One(discord.ui.UserSelect):
            def __init__(self):
                super().__init__(
                    placeholder=f"Select runner (default: {default.display_name})",
                    min_values=1,
                    max_values=1,
                    custom_id="wr_one_user"
                )
                self.chosen: Optional[int] = None

            async def callback(self, i: discord.Interaction):
                self.chosen = self.values[0].id
                await i.response.edit_message(
                    content=f"{i.client.brand_prefix} ✅ Selected runner: {self.values[0].display_name}",
                    view=None
                )
                self.view.stop()

        v = discord.ui.View(timeout=60); sel = One(); v.add_item(sel)
        await interaction.followup.send(f"{self.bot.brand_prefix} Choose the **runner**.", view=v, ephemeral=True)
        await v.wait()
        return sel.chosen or default.id

    async def _choose_users(self, interaction: discord.Interaction, size: int) -> Optional[List[int]]:
        class Many(discord.ui.UserSelect):
            def __init__(self):
                super().__init__(
                    placeholder=f"Pick exactly {size} players",
                    min_values=size,
                    max_values=size,
                    custom_id="wr_many_users"
                )
                self.chosen: Optional[List[int]] = None

            async def callback(self, i: discord.Interaction):
                self.chosen = [u.id for u in self.values]
                await i.response.edit_message(
                    content=f"{i.client.brand_prefix} ✅ Selected team: {', '.join(u.display_name for u in self.values)}",
                    view=None
                )
                self.view.stop()

        v = discord.ui.View(timeout=120); sel = Many(); v.add_item(sel)
        await interaction.followup.send(f"{self.bot.brand_prefix} Pick **{size} players** for the team.", view=v, ephemeral=True)
        await v.wait()
        if sel.chosen and len(sel.chosen) == size:
            return sel.chosen
        await interaction.followup.send(f"{self.bot.brand_prefix} You must select exactly {size}.", ephemeral=True)
        return None

    async def start_solo_flow(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        runner = await self._choose_user(interaction, interaction.user)
        if not runner: return
        metric = await self._choose_metric(interaction)
        if not metric: return
        val = await self._prompt(interaction, "Enter your **run time** (e.g., 12:34.56)." if metric=="time" else "Enter your **damage** (number).")
        if not val: return
        notes = await self._prompt(interaction, "Add **notes** (optional). Type `skip` to leave blank.")
        if notes and notes.lower() == "skip": notes = None
        record = {
            "guild_id": interaction.guild_id,
            "submitter_id": interaction.user.id,
            "mode": "Solo",
            "size": 1,
            "players": [runner],
            "metric": metric,
            "value": val,
            "notes": notes,
        }
        await self.enqueue(interaction, record)

    async def start_team_flow(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"{self.bot.brand_prefix} Choose **team size**.", view=self._team_size_view(), ephemeral=True)

    def _team_size_view(self):
        v = discord.ui.View(timeout=60); v.add_item(TeamSizeSelect(self)); return v

    async def collect_team_players(self, interaction: discord.Interaction, size: int):
        players = await self._choose_users(interaction, size)
        if not players: return
        metric = await self._choose_metric(interaction)
        if not metric: return
        val = await self._prompt(interaction, "Enter your **team time** (e.g., 12:34.56)." if metric=="time" else "Enter your **team damage** (number).")
        if not val: return
        notes = await self._prompt(interaction, "Add **notes** (optional). Type `skip` to leave blank.")
        if notes and notes.lower() == "skip": notes = None
        record = {
            "guild_id": interaction.guild_id,
            "submitter_id": interaction.user.id,
            "mode": "Team",
            "size": size,
            "players": players,
            "metric": metric,
            "value": val,
            "notes": notes,
        }
        await self.enqueue(interaction, record)

    async def enqueue(self, interaction: discord.Interaction, record: dict):
        data = subs()
        data["pending"].append(record)
        save_subs(data)
        ch = discord.utils.get(interaction.guild.text_channels, name=interaction.client.canonical_channels["pending"])
        from .approval import ApprovalView
        embed = self.to_embed(interaction.guild, record, pending=True)
        msg = await ch.send(embed=embed, view=ApprovalView(interaction.client))
        record["pending_message_id"] = msg.id
        save_subs(data)
        await interaction.followup.send(f"{self.bot.brand_prefix} 🏆 Submitted for review.", ephemeral=True)

    def to_embed(self, guild: discord.Guild, rec: dict, pending=False) -> discord.Embed:
        e = discord.Embed(title=("Pending WR" if pending else "Approved WR"), color=self.bot.theme_color)
        e.add_field(name="Mode", value=(rec["mode"] if rec["mode"]=="Solo" else f"{rec['size']}p Team"), inline=True)
        e.add_field(name="Category", value=("Time ⏱️" if rec["metric"]=="time" else "Damage 💥"), inline=True)
        e.add_field(name=("Time" if rec["metric"]=="time" else "Damage"), value=rec["value"], inline=True)
        names = []
        for pid in rec["players"]:
            m = guild.get_member(pid)
            names.append(m.mention if m else f"<@{pid}>")
        e.add_field(name="Players", value=", ".join(names), inline=False)
        if rec.get("notes"):
            e.add_field(name="Notes", value=rec["notes"], inline=False)
        subm = guild.get_member(rec["submitter_id"])
        e.set_footer(text=f"Submitted by {subm.display_name if subm else rec['submitter_id']}")
        return e

    @app_commands.command(name="setup-submission-box", description="Post the WR submission UI in this server")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_submission_box(self, interaction: discord.Interaction):
        await self.post_or_update_submission_box(interaction.guild)
        await interaction.response.send_message("Submission box posted/updated.", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = SubmissionCog(bot)
    await bot.add_cog(cog)
    bot.add_view(SubmissionView(cog))
