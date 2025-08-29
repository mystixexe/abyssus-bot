# Abyssus Bot (Heroku-ready)

Single-file Discord bot using `discord.py 2.x` with slash commands.

## Quick Deploy (Heroku)

1. Create the app and set config vars:
   - `DISCORD_TOKEN` = your bot token
   - (optional) `GUILD_LIMIT` = a single guild ID for faster dev sync
   - (optional) `SEASON_DAYS` = default 7

2. Deploy:
   - Drag & drop this folder in Heroku (or push via Git).
   - Ensure the **worker** dyno is enabled: `worker: python bot.py`.

3. First-time setup in your server:
   - Invite the bot with the `applications.commands` scope.
   - Run `/abyssus-setup`.
   - Use `/submit-wr` to submit runs.
   - View with `/leaderboard`, `/wr`, `/history`.
   - Admin tools: `/config-*`, `/admin-*`, `/export-data`.

Data is stored in `wr_data/*.json` and is preserved across restarts in Heroku's dyno ephemeral FS only if using a persistent storage add-on. For durable storage across dyno restarts, consider an external store. Otherwise, export with `/export-data`.
