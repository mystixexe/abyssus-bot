# cogs/approval.py
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .util import subs, save_subs

APPROVAL_TITLE = "[WR PENDING APPROVAL]"


class ApprovalView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id="wr_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Load record from pending list
        data = subs()
        rec = None
        for r in data.get("pending", []):
            if r.get("pending_message_id") == interaction.message.id:
                rec = r
                break
        if not rec:
            await interaction.followup.send(f"{self.bot.brand_prefix} Could not find the pending record.", ephemeral=True)
            return

        # Move record → approved
        data["pending"].remove(rec)
        data.setdefault("approved", []).append(rec)
        save_subs(data)

        # Update embed
        from .submission import SubmissionCog
        cog: SubmissionCog = self.bot.get_cog("SubmissionCog")
        embed = cog.to_embed(interaction.guild, rec, pending=False)
        await interaction.message.edit(embed=embed, view=None)

        # --- NEW: Update roles & refresh leaderboard ---
        lb = self.bot.get_cog("LeaderboardCog")
        if lb:
            for pid in rec.get("players", []):
                await lb.recompute_and_apply_for_member(interaction.guild, pid)
            await lb.post_or_update_leaderboard_box(interaction.guild)

        await interaction.followup.send(f"{self.bot.brand_prefix} ✅ Approved and roles updated.", ephemeral=True)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.danger, custom_id="wr_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Load record from pending list
        data = subs()
        rec = None
        for r in data.get("pending", []):
            if r.get("pending_message_id") == interaction.message.id:
                rec = r
                break
        if not rec:
            await interaction.followup.send(f"{self.bot.brand_prefix} Could not find the pending record.", ephemeral=True)
            return

        # Remove record
        data["pending"].remove(rec)
        save_subs(data)

        # Update message
        await interaction.message.edit(content=f"{self.bot.brand_prefix} ❌ Rejected.", embed=None, view=None)
        await interaction.followup.send(f"{self.bot.brand_prefix} ❌ Submission rejected.", ephemeral=True)


class ApprovalCog(commands.Cog, name="ApprovalCog"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def post_or_update_pending_box(self, guild: discord.Guild):
        # Placeholder if you want to add a pending-submissions board later
        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ApprovalCog(bot))
    bot.add_view(ApprovalView(bot))  # persistent approval buttons
