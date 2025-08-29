# cogs/leaderboard.py
import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, Tuple, Optional
from .util import subs

# ---- Role Tier Config (lowered thresholds: 1,2,3,4) ----
WR_ROLE_THEME = {
    "name_prefix": "WR",              # All roles prefixed with "WR"
    "tiers": [
        # (display_name, min_wrs, color_int) – highest tier last
        ("WR Novice",      1, 0x7C7C7C),
        ("WR Challenger",  2, 0x3BA55D),
        ("WR Pro",         3, 0x5865F2),
        ("WR Elite",       4, 0xFEE75C),
    ],
}

LEADERBOARD_TITLE = "[WR LEADERBOARD]"
LEADERBOARD_CHANNEL_NAME = "wr-leaderboard"  # uses your canonical mapping if present
MAX_ROWS = 50  # how many lines to show

def tier_for_count(wr_count: int) -> Optional[str]:
    """Return the highest role name for this WR count, or None."""
    name = None
    for role_name, min_wrs, _ in WR_ROLE_THEME["tiers"]:
        if wr_count >= min_wrs:
            name = role_name
    return name

def role_order_map() -> Dict[str, int]:
    """Map role name to its rank (higher number = higher role)."""
    order = {}
    for idx, (role_name, _min, _col) in enumerate(WR_ROLE_THEME["tiers"], start=1):
        order[role_name] = idx
    return order


class LeaderboardRefresh(discord.ui.View):
    def __init__(self, cog: "LeaderboardCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Refresh Leaderboard", style=discord.ButtonStyle.primary, custom_id="wr_lb_refresh")
    async def refresh(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.defer(ephemeral=True, thinking=True)
        await self.cog.post_or_update_leaderboard_box(i.guild)
        await i.followup.send(f"{i.client.brand_prefix} 🔄 Leaderboard refreshed.", ephemeral=True)


class LeaderboardCog(commands.Cog, name="LeaderboardCog"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -------------------------- Setup --------------------------
    async def ensure_wr_roles(self, guild: discord.Guild) -> Dict[str, discord.Role]:
        """
        Ensure all WR roles exist. Returns mapping of role name -> role object.
        Roles are created with the given color; position is near the bot's top manageable spot.
        """
        existing = {r.name: r for r in guild.roles}
        result: Dict[str, discord.Role] = {}
        me: discord.Member = guild.me

        # Find a position we can manage (just under bot's top role)
        manageable_positions = [r.position for r in me.roles if r.name != "@everyone"]
        base_pos = max(manageable_positions) - 1 if manageable_positions else 1
        base_pos = max(base_pos, 1)

        for idx, (role_name, _min, color_int) in enumerate(WR_ROLE_THEME["tiers"]):
            if role_name in existing:
                result[role_name] = existing[role_name]
                continue
            try:
                r = await guild.create_role(
                    name=role_name,
                    colour=discord.Colour(color_int),
                    reason="Auto-create WR role",
                    mentionable=False,
                )
                # Try to move it under bot's top role (best effort)
                try:
                    await r.edit(position=base_pos - (len(WR_ROLE_THEME["tiers"]) - idx), reason="Position WR roles")
                except Exception:
                    pass
                result[role_name] = r
            except Exception as e:
                # If creation fails, skip but keep going
                self.bot.logger.warning(f"[{guild.name}] Failed creating role {role_name}: {e}") if hasattr(self.bot, "logger") else None

        return result

    # ----------------- WR Counting & Display -------------------
    def _guild_wr_counts(self, guild: discord.Guild) -> Dict[int, int]:
        """
        Build a counter of total approved WRs per player (id) for this guild.
        """
        data = subs()
        counts: Dict[int, int] = {}
        for rec in data.get("approved", []):
            if rec.get("guild_id") != guild.id:
                continue
            for pid in rec.get("players", []):
                counts[pid] = counts.get(pid, 0) + 1
        return counts

    def _format_line(self, guild: discord.Guild, user_id: int, wrs: int) -> str:
        m = guild.get_member(user_id)
        display = m.display_name if m else f"<@{user_id}>"
        highest = tier_for_count(wrs)
        if highest:
            return f"**{display}** — {wrs} WRs · *{highest}*"
        return f"**{display}** — {wrs} WRs"

    def leaderboard_embed(self, guild: discord.Guild) -> discord.Embed:
        counts = self._guild_wr_counts(guild)
        # sort by WRs desc then name
        rows: List[Tuple[int, int]] = sorted(
            counts.items(),
            key=lambda kv: (-kv[1], guild.get_member(kv[0]).display_name.lower() if guild.get_member(kv[0]) else str(kv[0]))
        )
        description_lines: List[str] = []
        for idx, (uid, wrs) in enumerate(rows[:MAX_ROWS], start=1):
            description_lines.append(f"{idx}. {self._format_line(guild, uid, wrs)}")

        e = discord.Embed(
            title=LEADERBOARD_TITLE,
            description="\n".join(description_lines) if description_lines else "_No world records yet._",
            color=self.bot.theme_color
        )
        e.set_footer(text="WR Bot · Leaderboard")
        return e

    # ----------------- Role Assignment Logic -------------------
    async def assign_roles_for_member(self, guild: discord.Guild, member_id: int, wr_count: Optional[int] = None):
        """
        Ensure the member has exactly their highest WR role (and none of the lower tiers).
        """
        member = guild.get_member(member_id)
        if not member:
            return

        if wr_count is None:
            wr_count = self._guild_wr_counts(guild).get(member_id, 0)

        # Ensure roles exist
        role_map = await self.ensure_wr_roles(guild)

        target_role_name = tier_for_count(wr_count)
        target_role: Optional[discord.Role] = role_map.get(target_role_name) if target_role_name else None

        # Build sets
        wr_role_names = {name for (name, _min, _c) in WR_ROLE_THEME["tiers"]}
        member_wr_roles = [r for r in member.roles if r.name in wr_role_names]

        # If the member already has only the right one, skip
        if target_role and len(member_wr_roles) == 1 and member_wr_roles[0].id == target_role.id:
            return
        if not target_role and not member_wr_roles:
            return

        # Remove all WR roles first, then add target (if any)
        try:
            if member_wr_roles:
                await member.remove_roles(*member_wr_roles, reason="WR role update")
            if target_role:
                await member.add_roles(target_role, reason="WR role update")
        except discord.Forbidden:
            # Missing perms; best effort
            pass
        except Exception:
            pass

    async def recompute_and_apply_for_member(self, guild: discord.Guild, member_id: int):
        """
        Recompute WRs and adjust roles for this member.
        """
        count = self._guild_wr_counts(guild).get(member_id, 0)
        await self.assign_roles_for_member(guild, member_id, count)

    async def recompute_all_for_guild(self, guild: discord.Guild):
        """
        Recompute WRs and adjust roles for all members present in the data.
        """
        counts = self._guild_wr_counts(guild)
        await self.ensure_wr_roles(guild)
        for uid, c in counts.items():
            await self.assign_roles_for_member(guild, uid, c)

    # ---------------- Leaderboard Posting/Updating --------------
    async def _get_leaderboard_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        # Prefer your canonical channel mapping if the bot defines it
        name = getattr(self.bot, "canonical_channels", {}).get("leaderboard", LEADERBOARD_CHANNEL_NAME)
        ch = discord.utils.get(guild.text_channels, name=name)
        return ch

    async def post_or_update_leaderboard_box(self, guild: discord.Guild):
        """
        Post or update the leaderboard message in the designated channel.
        Also ensures WR roles exist before displaying.
        """
        await self.ensure_wr_roles(guild)

        ch = await self._get_leaderboard_channel(guild)
        if not ch:
            return  # Respect existing setup; your bot may create channels elsewhere

        marker = LEADERBOARD_TITLE
        embed = self.leaderboard_embed(guild)
        view = LeaderboardRefresh(self)

        async for m in ch.history(limit=50):
            if m.author == guild.me and m.embeds and m.embeds[0].title == marker:
                await m.edit(embed=embed, view=view)
                return
        await ch.send(embed=embed, view=view)

    # -------------------- Slash Commands -----------------------
    @app_commands.command(name="setup-leaderboard-box", description="Post or refresh the WR leaderboard panel in this server")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_leaderboard_box(self, interaction: discord.Interaction):
        await self.post_or_update_leaderboard_box(interaction.guild)
        await interaction.response.send_message(f"{self.bot.brand_prefix} Leaderboard panel posted/updated.", ephemeral=True)

    @app_commands.command(name="refresh-leaderboard", description="Recompute WRs, update roles, and refresh the leaderboard")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def refresh_leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.recompute_all_for_guild(interaction.guild)
        await self.post_or_update_leaderboard_box(interaction.guild)
        await interaction.followup.send(f"{self.bot.brand_prefix} ✅ Leaderboard refreshed and roles updated.", ephemeral=True)


async def setup(bot: commands.Bot):
    cog = LeaderboardCog(bot)
    await bot.add_cog(cog)
    # Persistent view for the refresh button
    bot.add_view(LeaderboardRefresh(cog))
