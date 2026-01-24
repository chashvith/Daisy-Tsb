import io
import re
import os
import discord
import json
import random
from datetime import datetime, timedelta, timezone, time
from threading import Thread
import asyncio
import sqlite3
import aiohttp
from flask import Flask
from discord.ext import commands, tasks
from discord import app_commands

# ==========================
# ✅ IMPORT YOUR MODULES
# ==========================
from timeDataBase import (
    setupTimeDB, getUserTime, SaveUserTime,
    get_leaderboard_data, getUserDailyTime,
    get_streak_info, get_streak_leaderboard
)

from lb_image_gen import draw_leaderboard, draw_streak_leaderboard
from repDataBase import setupRepDB, add_rep
from fun_replies import check_humor
from tasksDataBase import setupTaskDB, getUserData, SaveUserTasks
from excludedChannels import setupExChannelDB, getExChannel, addChannel

# ==========================
# ✅ DISCORD BOT SETUP
# ==========================
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

SESSION_FILE = "active_sessions.json"

# ==========================
# ✅ LOAD/SAVE VOICE TRACKING
# ==========================
def load_voice_sessions():
    if not os.path.exists(SESSION_FILE):
        return {}
    try:
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
            return {int(uid): datetime.fromisoformat(ts) for uid, ts in data.items()}
    except:
        return {}

def save_voice_sessions(sessions):
    try:
        data = {str(uid): ts.isoformat() for uid, ts in sessions.items()}
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print("Error saving sessions:", e)

voiceTrack = load_voice_sessions()

# ==========================
# ✅ REPORT SYSTEM
# ==========================
bot.report_channel_id = None

@bot.tree.command(name="set_report_channel", description="MODS ONLY: Set the channel for forwarded reports")
@app_commands.checks.has_permissions(manage_channels=True)
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    bot.report_channel_id = channel.id
    await interaction.response.send_message(f"Reports will now be sent to {channel.mention}", ephemeral=True)

async def report_context_menu(interaction: discord.Interaction, message: discord.Message):
    target_channel = bot.get_channel(bot.report_channel_id)

    if not target_channel:
        return await interaction.response.send_message(
            "Staff needs to setup report channel.",
            ephemeral=True
        )

    safe_content = message.content.replace("\n", " ")[:1024]

    embed = discord.Embed(
        title="**Report**",
        color=discord.Color.dark_gold(),
        timestamp=interaction.created_at
    )

    embed.add_field(
        name="Reported for",
        value=f"{message.author.mention}\nID: `{message.author.id}`",
        inline=True
    )

    embed.add_field(
        name="Reporter",
        value=f"{interaction.user.mention}\nID: `{interaction.user.id}`",
        inline=True
    )

    embed.add_field(name="Message", value=f'"{safe_content}"', inline=False)

    await target_channel.send(content="Attention Staff!", embed=embed)
    await interaction.response.send_message("✅ Report sent!", ephemeral=True)

report_menu = app_commands.ContextMenu(
    name="Report a User",
    callback=report_context_menu
)

# ==========================
# ✅ VOICE TIME TRACKING
# ==========================
@bot.event
async def on_voice_state_update(member, before, after):

    userID = member.id
    guild_id = member.guild.id
    exChannels = getExChannel(guild_id)

    was_tracking = userID in voiceTrack
    is_now_tracking = (
        after.channel is not None and
        after.channel.id not in exChannels
    )

    # Leaving
    if was_tracking and (not is_now_tracking or before.channel.id != after.channel.id):
        joinTime = voiceTrack.pop(userID)
        leaveTime = datetime.now(timezone.utc)

        duration = (leaveTime - joinTime).total_seconds()
        SaveUserTime(userID, duration)

        save_voice_sessions(voiceTrack)

    # Joining
    if is_now_tracking and userID not in voiceTrack:
        voiceTrack[userID] = datetime.now(timezone.utc)
        save_voice_sessions(voiceTrack)

# ==========================
# ✅ ON MESSAGE REP SYSTEM
# ==========================
@bot.event
async def on_message(message):

    msg_content = message.content.lower()

    thank_keywords = ["thanks", "thank you", "thx", "tysm"]

    if any(word in msg_content for word in thank_keywords):
        thanked_user = None

        # Reply rep
        if message.reference:
            try:
                original_msg = message.reference.resolved
                if not original_msg:
                    original_msg = await message.channel.fetch_message(message.reference.message_id)
                thanked_user = original_msg.author
            except:
                pass

        # Mention rep
        if not thanked_user and message.mentions:
            for user in message.mentions:
                if user.id != message.author.id:
                    thanked_user = user
                    break

        if thanked_user and not thanked_user.bot:
            total_reps = add_rep(thanked_user.id)

            embed = discord.Embed(
                description=f"🎉 {thanked_user.mention} got a rep!\nTotal reps: `{total_reps}`",
                color=discord.Color.blue()
            )
            await message.channel.send(embed=embed)

    await check_humor(message)
    await bot.process_commands(message)

# ==========================
# ✅ BOT READY EVENT
# ==========================
@bot.event
async def on_ready():
    setupTimeDB()
    setupTaskDB()
    setupExChannelDB()
    setupRepDB()

    bot.tree.add_command(report_menu)

    try:
        synced = await bot.tree.sync()
        print("✅ Synced", len(synced), "commands")
    except Exception as e:
        print("Sync error:", e)

    print("✅ BOT IS ONLINE!")

# ==========================
# ✅ FLASK KEEP-ALIVE (RENDER)
# ==========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==========================
# ✅ MAIN START (ONLY ONCE)
# ==========================
if __name__ == "__main__":

    Thread(target=run_web).start()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ ERROR: DISCORD_TOKEN missing!")
    else:
        bot.run(token)
