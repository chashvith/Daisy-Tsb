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

# Import your custom modules
from timeDataBase import (setupTimeDB, getUserTime, SaveUserTime, get_leaderboard_data, 
                          get_streak_leaderboard, getUserDailyTime, get_streak_info)
from lb_image_gen import draw_leaderboard, draw_streak_leaderboard
from repDataBase import setupRepDB, add_rep
from fun_replies import check_humor
from tasksDataBase import setupTaskDB, getUserData, SaveUserTasks
from excludedChannels import setupExChannelDB, getExChannel, addChannel

# Bot setup
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
bot.report_channel_id = None

SESSION_FILE = "active_sessions.json"

# Session management functions
def load_voice_sessions():
    if not os.path.exists(SESSION_FILE):
        return {}
    try:
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
            return {int(uid): datetime.fromisoformat(ts) for uid, ts in data.items()}
    except Exception as e:
        print(f"Error loading sessions: {e}")
        return {}

def save_voice_sessions(sessions):
    try:
        data = {str(uid): ts.isoformat() for uid, ts in sessions.items()}
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving sessions: {e}")

voiceTrack = load_voice_sessions()

# ==========================================
#  REPORTING SYSTEM
# ==========================================
@bot.tree.command(name="set_report_channel", description="MODS ONLY: Set the channel for forwarded reports")
@app_commands.checks.has_permissions(manage_channels=True)
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    bot.report_channel_id = channel.id
    await interaction.response.send_message(f"Reports will now be sent to {channel.mention}", ephemeral=True)

async def report_context_menu(interaction: discord.Interaction, message: discord.Message):
    target_channel = bot.get_channel(bot.report_channel_id)
    if not target_channel:
        return await interaction.response.send_message("Staff needs to setup report channel. Please contact any Staff member for help.", ephemeral=True)

    safe_content = message.content.replace('\n', ' ')[:1024]
    
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

    if message.reference and message.reference.resolved:
        original_msg = message.reference.resolved
        embed.add_field(
            name="Replying To", 
            value=f"{original_msg.author.mention}: \"{original_msg.content[:100]}\"\nID: `{original_msg.author.id}`", 
            inline=False
        )

    await target_channel.send(content="Attention Staff!", embed=embed)
    await interaction.response.send_message("Report sent to Staff. Take a sip of Coffee and get back to Work!", ephemeral=True)

report_menu = app_commands.ContextMenu(
    name="Report a User",
    callback=report_context_menu
)

# ==========================================
#  INVITE SYSTEM
# ==========================================
@bot.tree.command(name="invite_members", description="Send DMs to specific users mentioned in the command")
@app_commands.describe(mentions="Mention the users you want to invite (e.g. @User1 @User2)")
async def invite_mentions(interaction: discord.Interaction, mentions: str):
    await interaction.response.defer(ephemeral=True)

    user_ids = re.findall(r'<@!?(\d+)>', mentions)
    
    if not user_ids:
        return await interaction.followup.send("You didn't mention any valid users!", ephemeral=True)

    user_ids = list(set(user_ids))

    embed = discord.Embed(
        title="📬 You've been invited!",
        description=f"**{interaction.user.display_name}** has sent you an invitation from **{interaction.guild.name}**.",
        color=discord.Color.blue(),
        timestamp=interaction.created_at
    )
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.add_field(name="Action", value=f"{interaction.user.display_name} is waiting for you in <#{interaction.channel_id}> to join them!")

    success_count = 0
    for u_id in user_ids:
        try:
            user = await bot.fetch_user(int(u_id))
            if user.bot:
                continue
            
            await user.send(embed=embed)
            success_count += 1
        except (discord.Forbidden, discord.NotFound, ValueError):
            continue

    await interaction.followup.send(f"Attempted to notify {len(user_ids)} users. Successfully delivered to {success_count}.", ephemeral=True)

# ==========================================
#  HELPER FUNCTIONS
# ==========================================
def level(userID):
    td = timedelta(seconds=int(getUserDailyTime(userID)))
    study_hours = td.total_seconds() / 3600
    if study_hours < 5:
        return ("Iron", 5, study_hours)
    elif study_hours < 10:
        return ("Bronze", 10, study_hours)
    elif study_hours < 15:
        return ("Silver", 15, study_hours)
    elif study_hours < 30:
        return ("Gold", 30, study_hours)
    elif study_hours < 50:
        return ("Platinum", 50, study_hours)
    elif study_hours < 75:
        return ("Diamond", 75, study_hours)
    elif study_hours < 110:
        return ("Master", 110, study_hours)
    elif study_hours < 150:
        return ("Grandmaster", 150, study_hours)
    elif study_hours < 200:
        return ("Immortal", 200, study_hours)
    elif study_hours < 300:
        return ("Conqueror", 300, study_hours)
    else:
        return ("God", 1000, study_hours)
def flush_active_voice_time():
    current_time = datetime.now(timezone.utc)

    for user_id, start_time in voiceTrack.items():
        duration = (current_time - start_time).total_seconds()

        if duration > 0:
            SaveUserTime(user_id, duration) 
            voiceTrack[user_id] = current_time
    save_voice_sessions(voiceTrack)    

def get_user_rank(userID, lbtype):
    connection = sqlite3.connect('userTimeUsage.db')
    cursor = connection.cursor()
    if lbtype == 'all time':
        cursor.execute('''
            SELECT COUNT(*) FROM userTime 
            WHERE time > (SELECT time FROM userTime WHERE userID = ?)
        ''', (userID,))
        users_ahead = cursor.fetchone()[0]
    
    if lbtype == 'daily':
        cursor.execute('''
            SELECT COUNT(*) FROM userTime 
            WHERE daily_time > (SELECT daily_time FROM userTime WHERE userID = ?)
        ''', (userID,))
        users_ahead = cursor.fetchone()[0]

    connection.close()
    user_rank = users_ahead + 1
    return user_rank

async def get_leaderboard_users(lbData, bot):
    users = []
    for user_id, total_seconds in lbData:
        user = bot.get_user(user_id)
        if not user:
            try:
                user = await bot.fetch_user(user_id)
            except discord.NotFound:
                user = None
        
        username = user.name if user else f"Unknown User ({user_id})"
        users.append((username, total_seconds))
    return users

# ==========================================
#  PROFILE COMMAND
# ==========================================
@bot.tree.command(name="profile", description="View Your Profile")
async def Profile(interaction: discord.Interaction):
    userID = interaction.user.id
    lvl = level(interaction.user.id)
    solid_square = '\u25a0'
    hollow_square = '\u25a1'
    pAch = int(lvl[2] / lvl[1] * 10)
    
    desp = f'''```
Username    = {interaction.user.name}
Level       = {lvl[0]}
Daily Rank  = {get_user_rank(lbtype="daily", userID=interaction.user.id)}
Server Rank = {get_user_rank(lbtype="all time", userID=interaction.user.id)}
```'''
    
    profileEmbed = discord.Embed(
        title=f"{interaction.user.name}'s Profile",
        color=discord.Color.red(),
        description=desp
    )
    profileEmbed.set_thumbnail(url=interaction.user.avatar)
    profileEmbed.add_field(name="XP", value=f"{pAch*solid_square+((10-pAch)*hollow_square)}", inline=False)
    profileEmbed.add_field(name="Today Study Time", value=f"Total Time: {str(timedelta(seconds=int(getUserDailyTime(interaction.user.id))))}", inline=False)
    profileEmbed.add_field(name="Total Study Time", value=f"Total Time: {str(timedelta(seconds=int(getUserTime(interaction.user.id))))}", inline=False)
    profileEmbed.set_footer(
        text="Thanks for using our server. Keep Studying!",
        icon_url=interaction.guild.icon
    )
    await interaction.response.send_message(embed=profileEmbed)

# ==========================================
#  VOICE TRACKING
# ==========================================
@bot.event
async def on_voice_state_update(member, before, after):
    userID = member.id
    guild_id = member.guild.id
    exChannels = getExChannel(guild_id)
    
    was_tracking = userID in voiceTrack
    is_now_tracking = (after.channel is not None) and (after.channel.id not in exChannels)

    if was_tracking and (not is_now_tracking or before.channel.id != after.channel.id):
        joinTime = voiceTrack.pop(userID)
        leaveTime = datetime.now(timezone.utc)
        duration = (leaveTime - joinTime).total_seconds()
        
        SaveUserTime(userID, duration)
        save_voice_sessions(voiceTrack)

    if is_now_tracking and userID not in voiceTrack:
        voiceTrack[userID] = datetime.now(timezone.utc)
        save_voice_sessions(voiceTrack)

# ==========================================
#  LEADERBOARD COMMANDS
# ==========================================
@bot.tree.command(name="leaderboard", description="View a visual leaderboard")
@app_commands.choices(lb_type=[
    app_commands.Choice(name="Daily", value="daily"),
    app_commands.Choice(name="All Time", value="all time")
])
async def img_leaderboard(interaction: discord.Interaction, lb_type: app_commands.Choice[str]):
    await interaction.response.defer()
    
    lb_mode = lb_type.value
    raw_data = get_leaderboard_data(lb_mode, offset=0)
    
    if not raw_data:
        return await interaction.followup.send("No data available yet!")

    processed_users = []
    
    async with aiohttp.ClientSession() as session:
        for user_id, seconds in raw_data:
            user = bot.get_user(user_id)
            if not user:
                try:
                    user = await bot.fetch_user(user_id)
                except:
                    user = None
            
            if user:
                username = getattr(user, "display_name", None) or getattr(user, "name", f"Unknown ({user_id})")
            else:
                username = f"Unknown ({user_id})"

            m, s = divmod(int(seconds), 60)
            h, m = divmod(m, 60)
            time_str = f"{h}h {m}m"

            avatar_bytes = None
            if user:
                try:
                    avatar_url = user.display_avatar.url
                    async with session.get(avatar_url) as resp:
                        if resp.status == 200:
                            avatar_bytes = await resp.read()
                except:
                    pass

            processed_users.append({
                'name': username,
                'time': time_str,
                'avatar_bytes': avatar_bytes
            })

    final_buffer = await bot.loop.run_in_executor(None, draw_leaderboard, processed_users)
    file = discord.File(fp=final_buffer, filename="leaderboard.png")
    await interaction.followup.send(file=file)

@bot.tree.command(name="exclude_channel", description="Exclude a channel from tracking (Mods Only)")
@app_commands.describe(channel="Select the channel to exclude")
@app_commands.checks.has_permissions(manage_guild=True)
async def exclude_channels(interaction: discord.Interaction, channel: discord.VoiceChannel):
    addChannel(interaction.guild.id, channel.id)
    await interaction.response.send_message(f"{channel.mention} has been added to excluded channels.")

@exclude_channels.error
async def exclude_channels_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You do not have permission to use this command, nice try diddy!", ephemeral=False)
@set_channel.error
async def set_channel_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You do not have permission to use this command, nice try diddy!", ephemeral=False)
@bot.command(aliases=('lb', 'rank'))
async def leaderboard(ctx, page: int = 1):
    offset = (page - 1) * 10
    lbData = get_leaderboard_data('all time', offset=offset)
    
    if not lbData:
        return await ctx.send("No data found for this page.")

    user_list = await get_leaderboard_users(lbData, bot)

    lbEmbed = discord.Embed(
        title='🏆 All Time Study Leaderboard',
        color=discord.Color.gold()
    )
    if ctx.guild.icon:
        lbEmbed.set_thumbnail(url=ctx.guild.icon.url)

    longest_name = max((len(u[0]) for u in user_list), default=0)
    start_rank = offset + 1
    
    for rank, (username, total_seconds) in enumerate(user_list, start=start_rank):
        minutes, seconds = divmod(int(total_seconds), 60)
        hours, minutes = divmod(minutes, 60)
        time_str = f"{hours}h {minutes}m {seconds}s"
        
        lbEmbed.add_field(
            name=f"#{rank} - {username.ljust(longest_name)}",
            value=f"⏱️ {time_str}",
            inline=False
        )

    await ctx.send(embed=lbEmbed)

@bot.command(aliases=('dlb', 'daily'))
async def daily_leaderboard(ctx, page: int = 1):
    offset = (page - 1) * 10
    lbData = get_leaderboard_data('daily', offset=offset)

    if not lbData:
        return await ctx.send("No data found for this page.")

    user_list = await get_leaderboard_users(lbData, bot)

    lbEmbed = discord.Embed(
        title='☀️ Daily Study Leaderboard',
        color=discord.Color.blue()
    )
    if ctx.guild.icon:
        lbEmbed.set_thumbnail(url=ctx.guild.icon.url)

    longest_name = max((len(u[0]) for u in user_list), default=0)
    start_rank = offset + 1

    for rank, (username, total_seconds) in enumerate(user_list, start=start_rank):
        minutes, seconds = divmod(int(total_seconds), 60)
        hours, minutes = divmod(minutes, 60)
        time_str = f"{hours}h {minutes}m {seconds}s"
        
        lbEmbed.add_field(
            name=f"#{rank} - {username.ljust(longest_name)}",
            value=f"⏱️ {time_str}",
            inline=False
        )

    await ctx.send(embed=lbEmbed)

# ==========================================
#  TASK SYSTEM
# ==========================================
@bot.tree.command(name="add_task", description="Add a Journal or Daily task")
@app_commands.choices(task_type=[
    app_commands.Choice(name="Journal", value="journal"),
    app_commands.Choice(name="Daily", value="daily")
])
async def add_task(interaction: discord.Interaction, task_name: str, task_type: app_commands.Choice[str]):
    type_val = task_type.value
    
    data = getUserData(interaction.user.id)
    new_task = {"name": task_name, "completed": False}
    
    data[type_val].append(new_task)
        
    SaveUserTasks(interaction.user.id, data["journal"], data["daily"])
    await interaction.response.send_message(f"✅ Added {type_val} task: **{task_name}**", ephemeral=True)

class TaskSelect(discord.ui.Select):
    def __init__(self, user_id, journal_tasks, daily_tasks):
        options = []
        
        for i, t in enumerate(journal_tasks):
            if not t['completed']:
                options.append(discord.SelectOption(
                    label=f"Journal: {t['name']}", 
                    value=f"journal_{i}",
                    emoji="📝"
                ))
        
        for i, t in enumerate(daily_tasks):
            if not t['completed']:
                options.append(discord.SelectOption(
                    label=f"Daily: {t['name']}", 
                    value=f"daily_{i}",
                    emoji="☀️"
                ))

        if not options:
            options.append(discord.SelectOption(label="All tasks completed!", value="none"))
            super().__init__(placeholder="Nothing left to do!", options=options, disabled=True)
        else:
            super().__init__(placeholder="Select a task to complete...", options=options)

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        data = getUserData(user_id)
        
        task_type, index = self.values[0].split("_")
        index = int(index)
        
        data[task_type][index]['completed'] = True
        
        SaveUserTasks(user_id, data['journal'], data['daily'])
        
        await interaction.response.send_message(
            f"✅ Marked **{data[task_type][index]['name']}** as completed!", 
            ephemeral=True
        )

class TaskView(discord.ui.View):
    def __init__(self, user_id, journal, daily):
        super().__init__()
        self.add_item(TaskSelect(user_id, journal, daily))

@bot.tree.command(name="complete", description="Check off your study tasks for the day")
async def complete(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = getUserData(user_id)
    
    if not data['journal'] and not data['daily']:
        return await interaction.response.send_message(
            "You don't have any tasks set! Use `/add_task` first.", 
            ephemeral=True
        )
    
    view = TaskView(user_id, data['journal'], data['daily'])
    await interaction.response.send_message("Select a task to mark it as finished:", view=view, ephemeral=True)

@bot.tree.command(name="tasks", description="View your current task list and streak status")
async def view_tasks(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = getUserData(user_id)
    info = get_streak_info(user_id)
    
    embed = discord.Embed(
        title=f"📋 {interaction.user.name}'s Task List", 
        color=discord.Color.blue()
    )
    
    status_emoji = "🔥" if info['streak'] > 0 else "❄️"
    embed.description = f"Current Streak: **{info['streak']} Days** {status_emoji}\nStatus: `{info['status']}`"

    j_list = "\n".join([f"{'✅' if t['completed'] else '❌'} {t['name']}" for t in data['journal']]) or "None"
    embed.add_field(name="Journal Tasks (Recurring)", value=j_list, inline=False)

    d_list = "\n".join([f"{'✅' if t['completed'] else '❌'} {t['name']}" for t in data['daily']]) or "None"
    embed.add_field(name="Daily Tasks (Today Only)", value=d_list, inline=False)

    await interaction.response.send_message(embed=embed)

# ==========================================
#  STREAK LEADERBOARD
# ==========================================
@bot.tree.command(name="streak_leaderboard", description="View the Top 10 Active Streaks")
async def streak_img_lb(interaction: discord.Interaction):
    await interaction.response.defer()

    raw_data = get_streak_leaderboard()
    
    if not raw_data:
        return await interaction.followup.send("No active streaks found! Start studying to get on the board.")

    processed_users = []
    
    for user_id, streak in raw_data:
        user = bot.get_user(user_id)
        if not user:
            try:
                user = await bot.fetch_user(user_id)
            except:
                user = None
        
        username = user.display_name if user else "Unknown User"
        
        processed_users.append({
            'name': username,
            'streak': str(streak)
        })

    final_buffer = await bot.loop.run_in_executor(None, draw_streak_leaderboard, processed_users)
    file = discord.File(fp=final_buffer, filename="streak_leaderboard.png")
    await interaction.followup.send(file=file)

# ==========================================
#  SCHEDULED TASKS
# ==========================================
MAINTENANCE_TIME = time(hour=23, minute=25, tzinfo=timezone.utc)
STREAK_CHANNEL_ID = 1464650405278515444
DAILY_TIME = time(hour=23, minute=30, tzinfo=timezone.utc)

@tasks.loop(time=MAINTENANCE_TIME)
async def midnight_maintenance():
    print("🕛 4:55 AM IST: RUNNING MAINTENANCE & STREAK UPDATES")
    
    task_conn = sqlite3.connect('userTaskList.db')
    time_conn = sqlite3.connect('userTimeUsage.db')
    
    task_cursor = task_conn.cursor()
    time_cursor = time_conn.cursor()

    task_cursor.execute("SELECT userID, tasks FROM userTasks")
    all_users = task_cursor.fetchall()

    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')

    for userID, tasks_json in all_users:
        try:
            data = json.loads(tasks_json)
            journal_tasks = data.get("journal", [])
            daily_tasks = data.get("daily", [])

            if not journal_tasks and not daily_tasks:
                is_eligible = False
            else:
                journal_done = all(t.get('completed', False) for t in journal_tasks)
                daily_done = all(t.get('completed', False) for t in daily_tasks)
                is_eligible = journal_done and daily_done

            if is_eligible:
                time_cursor.execute('''
                    UPDATE userTime 
                    SET current_streak = current_streak + 1, 
                        streak_status = 'ACTIVE',
                        last_completion_date = ?
                    WHERE userID = ?
                ''', (yesterday_str, userID))
            else:
                time_cursor.execute('''
                    UPDATE userTime 
                    SET current_streak = 0, 
                        streak_status = 'INACTIVE'
                    WHERE userID = ?
                ''', (userID,))

            for t in journal_tasks:
                t['completed'] = False
            
            new_tasks_data = json.dumps({"journal": journal_tasks, "daily": []})
            task_cursor.execute("UPDATE userTasks SET tasks = ? WHERE userID = ?", (new_tasks_data, userID))
            
        except Exception as e:
            print(f"Error processing user {userID}: {e}")

    task_conn.commit()
    time_conn.commit()
    task_conn.close()
    time_conn.close()

    current_time = datetime.now(timezone.utc)
    
    for userID, start_time in list(voiceTrack.items()):
        duration = (current_time - start_time).total_seconds()
        SaveUserTime(userID, duration)
        voiceTrack[userID] = current_time
    save_voice_sessions(voiceTrack)

    conn_lb = sqlite3.connect('userTimeUsage.db')
    cursor_lb = conn_lb.cursor()
    cursor_lb.execute('UPDATE userTime SET daily_time = 0')
    conn_lb.commit()
    conn_lb.close()
    print("✅ Daily leaderboard reset.")

@tasks.loop(time=DAILY_TIME)
async def post_daily_streak():
    channel = bot.get_channel(STREAK_CHANNEL_ID)
    
    if not channel:
        print(f"❌ Error: Could not find channel with ID {STREAK_CHANNEL_ID}")
        return

    try:
        async for message in channel.history(limit=20):
            if message.author == bot.user and "Daily Streak Leaderboard" in message.content:
                await message.delete()
                break
    except Exception as e:
        print(f"Error deleting old message: {e}")

    try:
        raw_data = get_streak_leaderboard()
        
        if not raw_data:
            await channel.send("Daily Streak Leaderboard: No active streaks today!")
            return

        processed_users = []
        for user_id, streak in raw_data:
            user = bot.get_user(user_id)
            if not user:
                try:
                    user = await bot.fetch_user(user_id)
                except:
                    user = None
            
            username = user.display_name if user else "Unknown User"
            processed_users.append({'name': username, 'streak': str(streak)})

        final_buffer = await bot.loop.run_in_executor(None, draw_streak_leaderboard, processed_users)
        file = discord.File(fp=final_buffer, filename="daily_streak.png")

        await channel.send("🔥 **Daily Streak Leaderboard** 🔥\nKeep the grind going!", file=file)
        
    except Exception as e:
        print(f"Error generating daily streak: {e}")

# ==========================================
#  MESSAGE HANDLER (REP SYSTEM)
# ==========================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return
        
    msg_content = message.content.lower()
    thank_keywords = ["thanks", "thank you", "thx", "tysm"]
    
    if any(word in msg_content for word in thank_keywords):
        thanked_user = None

        if message.reference:
            try:
                original_msg = message.reference.resolved
                if not original_msg:
                    original_msg = await message.channel.fetch_message(message.reference.message_id)
                thanked_user = original_msg.author
            except Exception:
                pass

        if not thanked_user and message.mentions:
            for user in message.mentions:
                if user.id != message.author.id:
                    thanked_user = user
                    break
                
            if not thanked_user and message.mentions:
                thanked_user = message.mentions[0]

        if thanked_user:
            try:
                if thanked_user.id == message.author.id:
                    await message.channel.send(f"{message.author.mention}, you can't rep yourself! Nice try though. 😉")
                elif thanked_user.bot:
                    await message.channel.send(f"I appreciate it, {message.author.mention}, but I don't need reps! 🤖")
                else:
                    total_reps = add_rep(thanked_user.id)
                    
                    embed = discord.Embed(
                        description=f"**Thanks {thanked_user.mention} for helping {message.author.mention}!**\n\n🎉 You gained a rep!\n📈 **Your Total Reps:** `{total_reps}`",
                        color=discord.Color.blue()
                    )
                    
                    embed.set_thumbnail(url=thanked_user.display_avatar.url)

                    embed.set_footer(
                        text="Thanks for the Good Work! Keep it up.",
                        icon_url=message.guild.icon.url if message.guild.icon else None
                    )
                    
                    await message.channel.send(embed=embed)
                    
            except Exception as e:
                print(f"Error in rep system: {e}")

    await check_humor(message)
    await bot.process_commands(message)

# ==========================================
#  BOT READY EVENT - MUST BE AFTER ALL COMMANDS
# ==========================================
@bot.event
async def on_ready():
    print("🤖 Bot is starting up...")
    
    # Setup databases
    setupTimeDB()
    setupTaskDB()
    setupExChannelDB()
    setupRepDB()
    
    # Start scheduled tasks
    if not midnight_maintenance.is_running():
        midnight_maintenance.start()
        print("✅ Midnight maintenance task started")
    
    if not post_daily_streak.is_running():
        post_daily_streak.start()
        print("✅ Daily streak post task started")

    # Add context menu
    bot.tree.add_command(report_menu)
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")
    
    print(f"✅ Bot is ready! Logged in as {bot.user}")

# ==========================================
#  FLASK WEB SERVER (RENDER KEEP-ALIVE)
# ==========================================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive and running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ==========================================
#  MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    # Start Flask in background thread
    web_thread = Thread(target=run_web, daemon=True)
    web_thread.start()
    print("✅ Flask web server started")

    # Start Discord bot (THIS MUST BE LAST)
    token = os.getenv('DISCORD_TOKEN')
    if token:
        print("🚀 Starting Discord bot...")
        bot.run(token)
    else:
        print("❌ ERROR: DISCORD_TOKEN not found in Environment Variables!")


#