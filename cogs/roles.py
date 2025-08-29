# cogs/roles.py
import discord
from typing import Dict, List, Optional

# ---------- Theme & Tiers ----------
THEME_PREFIX = "Abyssal "  # visible brand

# Lowered thresholds as requested
TIER_THRESHOLDS = {
    1: {"name": f"{THEME_PREFIX}Adept",   "emoji": "🎖️", "color": discord.Colour.from_rgb(88, 101, 242)},   # blurple
    2: {"name": f"{THEME_PREFIX}Champion","emoji": "🏅", "color": discord.Colour.from_rgb(46, 204, 113)},    # green
    3: {"name": f"{THEME_PREFIX}Paragon", "emoji": "💠", "color": discord.Colour.from_rgb(241, 196, 15)},    # gold
    4: {"name": f"{THEME_PREFIX}Sovereign","emoji": "👑","color": discord.Colour.from_rgb(231, 76, 60)},     # red
}

# Badge roles (non-exclusive; stackable). Highest prestige is exclusive.
BADGE_DEFS = {
    "solo":   {"name": f"{THEME_PREFIX}Soloist",       "emoji": "🧍"},
    "team":   {"name": f"{THEME_PREFIX}Team Player",   "emoji": "🧑‍🤝‍🧑"},
    "time":   {"name": f"{THEME_PREFIX}Speedrunner",   "emoji": "⏱️"},
    "damage": {"name": f"{THEME_PREFIX}Damage Dealer", "emoji": "💥"},
}

def _find_role(guild: discord.Guild, name: str) -> Optional[discord.Role]:
    return discord.utils.get(guild.roles, name=name)

async def ensure_roles(guild: discord.Guild) -> Dict[str, discord.Role]:
    """Create prestige tiers + badge roles if missing. Return dict of all roles."""
    created: Dict[str, discord.Role] = {}

    # Create tiers
    for level, meta in TIER_THRESHOLDS.items():
        r = _find_role(guild, meta["name"])
        if not r:
            try:
                r = await guild.create_role(name=meta["name"], colour=meta["color"], mentionable=True, reason="WR prestige auto-setup")
            except Exception:
                # fallback without color if lacking perms
                r = _find_role(guild, meta["name"]) or await guild.create_role(name=meta["name"], reason="WR prestige auto-setup (no color)")
        created[meta["name"]] = r

    # Create badges
    for key, meta in BADGE_DEFS.items():
        r = _find_role(guild, meta["name"])
        if not r:
            r = await guild.create_role(name=meta["name"], mentionable=False, reason="WR badge auto-setup")
        created[meta["name"]] = r

    # Try to place prestige roles near the top (best-effort).
    try:
        tiers = [created[TIER_THRESHOLDS[i]["name"]] for i in sorted(TIER_THRESHOLDS.keys(), reverse=True)]
        top_index = max((role.position for role in guild.me.roles), default=1) - 1
        # Bring tiers just under bot's top role, preserving highest>lowest order
        for offset, role in enumerate(tiers):
            new_pos = max(1, top_index - offset)
            if role.position != new_pos:
                await role.edit(position=new_pos, reason="WR prestige ordering")
    except Exception:
        pass

    return created

def highest_prestige_for(member: discord.Member) -> Optional[discord.Role]:
    """Return the highest prestige role the member currently has (if any)."""
    got = []
    for lvl in sorted(TIER_THRESHOLDS.keys(), reverse=True):
        name = TIER_THRESHOLDS[lvl]["name"]
        r = _find_role(member.guild, name)
        if r and r in member.roles:
            got.append((lvl, r))
    return got[0][1] if got else None

async def sync_member_roles(member: discord.Member, wr_count: int, badges: List[str]) -> None:
    """
    Assign exactly one prestige role based on wr_count (thresholds 1/2/3/4),
    and add/remove badge roles in `badges` (keys from BADGE_DEFS).
    """
    await ensure_roles(member.guild)

    # Determine target prestige level
    target_lvl = 0
    for lvl in sorted(TIER_THRESHOLDS.keys()):
        if wr_count >= lvl:
            target_lvl = lvl

    # Gather roles
    prestige_roles = { TIER_THRESHOLDS[l]["name"]: _find_role(member.guild, TIER_THRESHOLDS[l]["name"]) for l in TIER_THRESHOLDS }
    target_role = prestige_roles[TIER_THRESHOLDS[target_lvl]["name"]] if target_lvl else None

    to_add = []
    to_remove = []

    # Ensure only the target prestige is present
    for name, role in prestige_roles.items():
        if not role: 
            continue
        if role in member.roles and role != target_role:
            to_remove.append(role)
    if target_role and target_role not in member.roles:
        to_add.append(target_role)

    # Badge roles
    for key, meta in BADGE_DEFS.items():
        r = _find_role(member.guild, meta["name"])
        if not r: 
            continue
        should_have = key in badges
        if should_have and r not in member.roles:
            to_add.append(r)
        if (not should_have) and r in member.roles:
            to_remove.append(r)

    # Apply
    if to_remove:
        try: 
            await member.remove_roles(*to_remove, reason="WR prestige/badges update")
        except Exception:
            pass
    if to_add:
        try: 
            await member.add_roles(*to_add, reason="WR prestige/badges update")
        except Exception:
            pass
