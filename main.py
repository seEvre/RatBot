import os
import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from keep_alive import keep_alive

TOKEN    = os.environ['DISCORD_TOKEN']
GUILD_ID = int(os.environ['GUILD_ID'])

intents = discord.Intents.default()
intents.messages        = True
intents.message_content = True
intents.guilds          = True
intents.invites         = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

conn = sqlite3.connect("messages.db")
cur  = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author TEXT, content TEXT,
  channel TEXT, timestamp TEXT
)
""")
conn.commit()

async def backup_to_db(channel: discord.TextChannel, limit: int = 100):
    msgs = await channel.history(limit=limit).flatten()
    for m in msgs:
        cur.execute(
            "INSERT INTO messages (author, content, channel, timestamp) VALUES (?, ?, ?, ?)",
            (str(m.author), m.content, str(channel), str(m.created_at))
        )
    conn.commit()

async def backup_to_txt(channel: discord.TextChannel, limit: int = 100):
    msgs = await channel.history(limit=limit).flatten()
    path = f"{channel.name}_backup.txt"
    with open(path, "w", encoding="utf-8") as f:
        for m in msgs:
            f.write(f"[{m.created_at}] {m.author}: {m.content}\n")
    return path

@admin_only()
@tree.command(name="backup", description="Backup recent messages to txt or db.")
@app_commands.describe(channel="Which channel to backup", format="txt or db")
async def backup(interaction: discord.Interaction,
                 channel: discord.TextChannel,
                 format: str):
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(
        title="🔄 Backup Started",
        description=f"Channel: {channel.mention}\nFormat: `{format}`",
        color=discord.Color.dark_blue()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

    if format.lower() == "txt":
        path = await backup_to_txt(channel)
        file = discord.File(path, filename=os.path.basename(path))
        embed = discord.Embed(
            title="✅ TXT Backup Complete",
            description=f"Download the file below.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)

    elif format.lower() == "db":
        await backup_to_db(channel)
        embed = discord.Embed(
            title="✅ DB Backup Complete",
            description="All messages saved to SQLite.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    else:
        embed = discord.Embed(
            title="❌ Invalid Format",
            description="Use `txt` or `db`",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

@admin_only()
@tree.command(name="lockdown", description="Delete all invites to lockdown server.")
async def lockdown(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="Administrator only.",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    invites = await interaction.guild.invites()
    deleted = 0
    for inv in invites:
        try:
            await inv.delete(reason="Server lockdown")
            deleted += 1
        except:
            pass

    embed = discord.Embed(
        title="🔒 Server Lockdown Complete",
        description=f"Deleted {deleted} invites.",
        color=discord.Color.dark_grey()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    bot.loop.create_task(tree.sync(guild=discord.Object(id=GUILD_ID)))
    print(f"✅ Logged in as {bot.user}")
    bot.loop.create_task(backup_scheduler())

async def backup_scheduler():
    await bot.wait_until_ready()
    while True:
        for guild in bot.guilds:
            for channel in guild.text_channels:
                try:
                    await backup_to_db(channel, limit=50)
                except:
                    pass
        await asyncio.sleep(1800)  # every 30 minutes

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)