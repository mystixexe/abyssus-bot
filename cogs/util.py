# cogs/util.py
import os, json, discord
from typing import Dict, Any, List, Tuple

DATA_DIR = "wr_data"
FP_CFG = os.path.join(DATA_DIR, "config.json")
FP_SUB = os.path.join(DATA_DIR, "submissions.json")
FP_PIN = os.path.join(DATA_DIR, "pins.json")

os.makedirs(DATA_DIR, exist_ok=True)

def _load(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _save(path: str, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def cfg() -> Dict[str, Any]:
    return _load(FP_CFG, {"guilds": {}})

def set_channel_id(guild_id: int, key: str, value: int):
    c = cfg()
    g = c["guilds"].setdefault(str(guild_id), {"channels": {}, "roles": {}})
    g["channels"][key] = value
    _save(FP_CFG, c)

def get_channel_id(guild_id: int, key: str) -> int:
    return cfg().get("guilds", {}).get(str(guild_id), {}).get("channels", {}).get(key, 0)

def set_role_id(guild_id: int, name: str, rid: int):
    c = cfg()
    g = c["guilds"].setdefault(str(guild_id), {"channels": {}, "roles": {}})
    g["roles"][name] = rid
    _save(FP_CFG, c)

def get_role_id(guild_id: int, name: str) -> int:
    return cfg().get("guilds", {}).get(str(guild_id), {}).get("roles", {}).get(name, 0)

def subs() -> Dict[str, Any]:
    return _load(FP_SUB, {"pending": [], "approved": [], "records": []})

def save_subs(data: Dict[str, Any]):
    _save(FP_SUB, data)

def pins() -> Dict[str, Any]:
    return _load(FP_PIN, {})

def save_pins(data: Dict[str, Any]):
    _save(FP_PIN, data)

def time_to_sort_key(s: str) -> float:
    try:
        parts = [p.strip() for p in str(s).split(":")]
        total = 0.0
        for p in parts:
            total = total*60 + float(p)
        return total
    except:
        return 9e9

def damage_to_sort_key(s: str) -> float:
    try:
        return float(str(s).replace(",", ""))
    except:
        return 0.0

def leaderboard_slice(guild_id: int, metric: str, mode: str, size: int, season: str = "current"):
    data = subs()
    # simple season model: max season present, else 1
    seasons = [r.get("season", 1) for r in data["records"] if r.get("guild_id")==guild_id]
    cur = max(seasons) if seasons else 1
    sel = cur if season == "current" else int(season)
    rs = [r for r in data["records"] if r.get("guild_id")==guild_id and r.get("metric")==metric and r.get("mode")==mode and int(r.get("size",1))==size and r.get("season",1)==sel]
    if metric == "time":
        rs.sort(key=lambda r: time_to_sort_key(r.get("value")))
    else:
        rs.sort(key=lambda r: damage_to_sort_key(r.get("value")), reverse=True)
    return rs

async def find_or_create_channel(guild: discord.Guild, name: str) -> discord.TextChannel:
    ch = discord.utils.get(guild.text_channels, name=name)
    return ch
