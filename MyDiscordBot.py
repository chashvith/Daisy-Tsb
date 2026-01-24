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
from flask import flask
token = os.getenv('DISCORD_TOKEN')
from timeDataBase import setupTimeDB, getUserTime, SaveUserTime, get_leaderboard_data, get_streak_leaderboard # Added get_streak_leaderboard
from lb_image_gen import draw_leaderboard, draw_streak_leaderboard # Added draw_streak_leaderboard
from repDataBase import setupRepDB, add_rep
from lb_image_gen import draw_leaderboard
from fun_replies import check_humor
from tasksDataBase import setupTaskDB,getUserData,SaveUserTasks
from discord.ext import commands,tasks
from timeDataBase import setupTimeDB,getUserTime,SaveUserTime,get_leaderboard_data,getUserDailyTime,get_streak_info
from excludedChannels import setupExChannelDB, getExChannel,addChannel
from discord import app_commands

bot = commands.Bot(command_prefix = "!", intents = discord.Intents.all())

SESSION_FILE = "active_sessions.json"

def load_voice_sessions():
    if not os.path.exists(SESSION_FILE):
        return {}
    try:
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
            # Convert ISO strings back to datetime objects
            return {int(uid): datetime.fromisoformat(ts) for uid, ts in data.items()}
    except Exception as e:
        return {}
    
def save_voice_sessions(sessions):
    try:
        # Convert datetime objects to ISO strings for JSON
        data = {str(uid): ts.isoformat() for uid, ts in sessions.items()}
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving sessions: {e}")
        
voiceTrack = load_voice_sessions()

bot.report_channel_id = None

##Reporting Code
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
    
    # Person on whom report is logged
    embed.add_field(
        name="Reported for", 
        value=f"{message.author.mention}\nID: `{message.author.id}`", 
        inline=True
    )
    
    # Reporter Info (The person who clicked report)
    embed.add_field(
        name="Reporter", 
        value=f"{interaction.user.mention}\nID: `{interaction.user.id}`", 
        inline=True
    )

    # The text
    embed.add_field(name="Message", value=f'"{safe_content}"', inline=False)

    # Check if this was a reply to Tom
    if message.reference and message.reference.resolved:
        original_msg = message.reference.resolved
        embed.add_field(
            name="Replying To (Tom)", 
            value=f"{original_msg.author.mention}: \"{original_msg.content}\"\nID: `{original_msg.author.id}`", 
            inline=False
        )

    await target_channel.send(content="Attention Staff!", embed=embed)
    await interaction.response.send_message("Report sent to Staff. Take a sip of Coffee and get back to Work!", ephemeral=True)
    
report_menu = app_commands.ContextMenu(
    name="Report a User",
    callback=report_context_menu
)

        
@bot.tree.command(name="invite_members", description="Send DMs to specific users mentioned in the command")
@app_commands.describe(mentions="Mention the users you want to invite (e.g. @User1 @User2)")
async def invite_mentions(interaction: discord.Interaction, mentions: str):
    await interaction.response.defer(ephemeral=True)

    # 1. Use Regex to find all User IDs in the string (Format: <@123...> or <@!123...>)
    user_ids = re.findall(r'<@!?(\d+)>', mentions)
    
    if not user_ids:
        return await interaction.followup.send("You didn't mention any valid users!", ephemeral=True)

    # Remove duplicates
    user_ids = list(set(user_ids))

    # 2. Create the Embed
    embed = discord.Embed(
        title="📬 You've been invited!",
        description=f"**{interaction.user.display_name}** has sent you an invitation from **{interaction.guild.name}**.",
        color=discord.Color.blue(),
        timestamp=interaction.created_at
    )
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.add_field(name="Action", value=f"{interaction.user.display_name} is waiting for you in <#{interaction.channel_id}> to join them!")

    # 3. Loop and Send
    success_count = 0
    for u_id in user_ids:
        try:
            user = await bot.fetch_user(int(u_id))
            if user.bot: continue
            
            await user.send(embed=embed)
            success_count += 1
        except (discord.Forbidden, discord.NotFound, ValueError):
            # Forbidden happens if DMs are closed
            continue

    await interaction.followup.send(f"Attempted to notify {len(user_ids)} users. Successfully delivered to {success_count}.", ephemeral=True)

#profile command
@bot.tree.command(name="profile", description="View Your Profile")
async def Profile(interaction: discord.Interaction):
    userID = interaction.user.id
    lvl = level(interaction.user.id)
    time = getUserTime(userID)
    solid_square = '\u25a0'
    hollow_square = '\u25a1'
    print(lvl)
    pAch = int(lvl[2]/lvl[1]*10)
    print(pAch)
    desp= f'''```
Username    = {interaction.user.name}
Level = {lvl[0]}
Daily Rank  = {get_user_rank(lbtype="daily",userID=interaction.user.id)}
Server Rank = {get_user_rank(lbtype="all time",userID=interaction.user.id)}

```'''
    profileEmbed = discord.Embed(
        title=f"{interaction.user.name}'s Profile",
        color= discord.Color.red(),
        description= desp
    )
    profileEmbed.set_thumbnail(url=interaction.user.avatar)
    profileEmbed.add_field(name="XP",value=f"{pAch*solid_square+((10-pAch)*hollow_square)}",inline=False)
    profileEmbed.add_field(name="Today Study Time",value=f"Total Time: {str(timedelta(seconds=int(getUserDailyTime(interaction.user.id))))}",inline=False)
    profileEmbed.add_field(name="Total Study Time",value=f"Total Time: {str(timedelta(seconds=int(getUserTime(interaction.user.id))))}",inline=False)
    profileEmbed.set_footer(
        text="Thanks for using our server. Keep Studying!",
        icon_url= interaction.guild.icon
                            )
    await interaction.response.send_message(embed = profileEmbed)
    
    

@bot.event
async def on_voice_state_update(member, before, after):
    userID = member.id
    guild_id = member.guild.id
    exChannels = getExChannel(guild_id)
    
    # Determine if the user was previously tracking time
    was_tracking = userID in voiceTrack
    
    # Determine if the new state is "tracking worthy"
    # (Must be in a channel, and that channel must NOT be excluded)
    is_now_tracking = (after.channel is not None) and (after.channel.id not in exChannels)

    # --- HANDLE LEAVING or SWITCHING AWAY ---
    # If they were tracking, and now they are NOT (or switched), save the time.
    if was_tracking and (not is_now_tracking or before.channel.id != after.channel.id):
        joinTime = voiceTrack.pop(userID)
        leaveTime = datetime.now(timezone.utc)
        duration = (leaveTime - joinTime).total_seconds()
        
        SaveUserTime(userID, duration)
        save_voice_sessions(voiceTrack) # Save to file immediately

    # --- HANDLE JOINING or SWITCHING TO ---
    # If they are now in a valid state, start the timer.
    # We check 'userID not in voiceTrack' to ensure we don't double-start on a switch 
    # (though the pop() above handles that, this is a safety net).
    if is_now_tracking and userID not in voiceTrack:
        voiceTrack[userID] = datetime.now(timezone.utc)
        save_voice_sessions(voiceTrack) # Save to file immediately


@bot.tree.command(name="leaderboard", description="View a visual leaderboard")
@app_commands.choices(lb_type=[
    app_commands.Choice(name="Daily", value="daily"),
    app_commands.Choice(name="All Time", value="all time")
])
async def img_leaderboard(interaction: discord.Interaction, lb_type: app_commands.Choice[str]):
    await interaction.response.defer() # Image generation takes time, so we defer first
    
    lb_mode = lb_type.value
    # 1. Fetch Data from DB
    raw_data = get_leaderboard_data(lb_mode, offset=0) # Reuse your existing function
    
    if not raw_data:
        return await interaction.followup.send("No data available yet!")

    processed_users = []
    
    # 2. Gather Avatar & Name Data Asynchronously
    # We use aiohttp to fetch avatars quickly without blocking
    async with aiohttp.ClientSession() as session:
        for user_id, seconds in raw_data:
            user = bot.get_user(user_id)
            if not user:
                try:
                    user = await bot.fetch_user(user_id)
                except:
                    user = None
            
            # Prepare user details
            username = user.display_name if user else "Unknown"
            
            # Calculate Time String
            m, s = divmod(int(seconds), 60)
            h, m = divmod(m, 60)
            time_str = f"{h}h {m}m"

            # Download Avatar Bytes
            avatar_bytes = None
            if user and user.avatar:
                try:
                    async with session.get(user.avatar.url) as resp:
                        if resp.status == 200:
                            avatar_bytes = await resp.read()
                except:
                    pass # Keep avatar_bytes as None if fetch fails
            
            processed_users.append({
                'name': username,
                'time': time_str,
                'avatar_bytes': avatar_bytes
            })

    # 3. Generate Image in a Separate Thread (Crucial for performance)
    # This runs the PIL code on a separate thread so the bot doesn't freeze
    final_buffer = await bot.loop.run_in_executor(None, draw_leaderboard, processed_users)

    # 4. Send Image
    file = discord.File(fp=final_buffer, filename="leaderboard.png")
    await interaction.followup.send(file=file)

@bot.tree.command(name="exclude_channel", description="Exclude a channel from tracking (Mods Only)")
@app_commands.describe(channel="Select the channel to exclude")
@app_commands.checks.has_permissions(manage_guild=True) 
async def exclude_channels(interaction: discord.Interaction, channel: discord.TextChannel):
    addChannel(interaction.guild.id, channel.id)
    
    await interaction.response.send_message(f"{channel.mention} has been added to excluded channels.")

  
##leaderboard
async def get_leaderboard_users(lbData, bot):
    """Helper to efficiently fetch users for the leaderboard."""
    users = []
    for user_id, total_seconds in lbData:
        # Try to get from cache first (Instant)
        user = bot.get_user(user_id)
        if not user:
            try:
                # Only fetch from API if not in cache (Slower)
                user = await bot.fetch_user(user_id)
            except discord.NotFound:
                user = None
        
        username = user.name if user else f"Unknown User ({user_id})"
        users.append((username, total_seconds))
    return users

@bot.command(aliases=('lb','rank'))
async def leaderboard(ctx, page : int = 1):
    offset = (page - 1) * 10
    lbData = get_leaderboard_data('all time', offset=offset)
    
    if not lbData:
        return await ctx.send("No data found for this page.")

    # Optimized user fetching (Done ONCE per command)
    user_list = await get_leaderboard_users(lbData, bot)

    lbEmbed = discord.Embed(
        title='🏆 All Time Study Leaderboard',
        color=discord.Color.gold()
    )
    if ctx.guild.icon:
        lbEmbed.set_thumbnail(url=ctx.guild.icon.url)

    # Calculate padding dynamic based on names we just fetched
    longest_name = max((len(u[0]) for u in user_list), default=0)

    start_rank = offset + 1
    
    for rank, (username, total_seconds) in enumerate(user_list, start=start_rank):
        # Format the time
        minutes, seconds = divmod(int(total_seconds), 60)
        hours, minutes = divmod(minutes, 60)
        time_str = f"{hours}h {minutes}m {seconds}s"
        
        # Add to Embed
        lbEmbed.add_field(
            name=f"#{rank} - {username.ljust(longest_name)}",
            value=f"⏱️ {time_str}",
            inline=False 
        )

    await ctx.send(embed=lbEmbed)

@bot.command(aliases=('dlb','daily'))
async def daily_leaderboard(ctx, page : int = 1):
    offset = (page - 1) * 10
    lbData = get_leaderboard_data('daily', offset=offset)

    if not lbData:
        return await ctx.send("No data found for this page.")

    # Optimized user fetching
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



def get_user_rank(userID, lbtype):
    connection = sqlite3.connect('userTimeUsage.db')
    cursor = connection.cursor()
    if lbtype == 'all time':
        cursor.execute('''
            SELECT COUNT(*) FROM userTime 
            WHERE time > (SELECT time FROM userTime WHERE userID = ?)
        ''',(userID,))
        users_ahead = cursor.fetchone()[0]
    
    if lbtype == 'daily':
        cursor.execute('''
            SELECT COUNT(*) FROM userTime 
            WHERE daily_time > (SELECT daily_time FROM userTime WHERE userID = ?)
        ''',(userID,))
        users_ahead = cursor.fetchone()[0]

    
    connection.close()
    user_rank = users_ahead + 1
    return user_rank

def level(userID):
    td = timedelta(seconds=int(getUserDailyTime(userID)))
    study_hours = td.total_seconds()/3600
    if study_hours < 5:
        return ("Iron",5,study_hours)
    elif study_hours < 10:
        return ("Bronze",10,study_hours)
    elif study_hours < 15:
        return ("Silver",15,study_hours)
    elif study_hours < 30:
        return ("Gold",30,study_hours)
    elif study_hours < 50:
        return ("Platinum",50,study_hours)
    elif study_hours < 75:
        return ("Diamond",75,study_hours)
    elif study_hours < 110:
        return ("Master",110,study_hours)
    elif study_hours < 150:
        return ("Grandmaster",150,study_hours)
    elif study_hours < 200:
        return ("Immortal",200,study_hours)
    elif study_hours < 300:
        return ("Conqueror",300,study_hours)
    else:
        return ("God",1000,study_hours)

#streak system

@bot.tree.command(name="add_task", description="Add a Journal or Daily task")
@app_commands.choices(task_type=[
    app_commands.Choice(name="Journal", value="journal"),
    app_commands.Choice(name="Daily", value="daily")
])
async def add_task(interaction: discord.Interaction, task_name: str, task_type: app_commands.Choice[str]):
    # .value gets the string "journal" or "daily" from the choice
    type_val = task_type.value 
    
    data = getUserData(interaction.user.id)
    new_task = {"name": task_name, "completed": False}
    
    # This will now work because getUserData returns a dict
    data[type_val].append(new_task)
        
    SaveUserTasks(interaction.user.id, data["journal"], data["daily"])
    await interaction.response.send_message(f"✅ Added {type_val} task: **{task_name}**", ephemeral=True)

    
class TaskSelect(discord.ui.Select):
    def __init__(self, user_id, journal_tasks, daily_tasks):
        options = []
        
        # Add Journal Tasks to dropdown (if not already done)
        for i, t in enumerate(journal_tasks):
            if not t['completed']:
                options.append(discord.SelectOption(
                    label=f"Journal: {t['name']}", 
                    value=f"journal_{i}",
                    emoji="📝"
                ))
        
        # Add Daily Tasks to dropdown (if not already done)
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
        data = getUserData(user_id) # Uses your JSON loader
        
        # Parse the value (e.g., "journal_0")
        task_type, index = self.values[0].split("_")
        index = int(index)
        
        # Mark as completed
        data[task_type][index]['completed'] = True
        
        # Save back to DB
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
    
    # Check if they even have tasks
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
    info = get_streak_info(user_id) # From your timeDataBase
    
    embed = discord.Embed(
        title=f"📋 {interaction.user.name}'s Task List", 
        color=discord.Color.blue()
    )
    
    # Streak Header
    status_emoji = "🔥" if info['streak'] > 0 else "❄️"
    embed.description = f"Current Streak: **{info['streak']} Days** {status_emoji}\nStatus: `{info['status']}`"

    # Format Journal List
    j_list = "\n".join([f"{'✅' if t['completed'] else '❌'} {t['name']}" for t in data['journal']]) or "None"
    embed.add_field(name="Journal Tasks (Recurring)", value=j_list, inline=False)

    # Format Daily List
    d_list = "\n".join([f"{'✅' if t['completed'] else '❌'} {t['name']}" for t in data['daily']]) or "None"
    embed.add_field(name="Daily Tasks (Today Only)", value=d_list, inline=False)

    await interaction.response.send_message(embed=embed)



def check_streak_eligibility(userID):
    data = getUserData(userID)
    
    all_journal_done = all(task['completed'] for task in data['journal'])
    all_daily_done = all(task['completed'] for task in data['daily'])
    
    if all_journal_done and all_daily_done:
        return True
    return False  


MAINTENANCE_TIME = time(hour=23, minute=25, tzinfo=timezone.utc)

@tasks.loop(time=MAINTENANCE_TIME)
async def midnight_maintenance():
    print("🕛 4:55 AM IST: RUNNING MAINTENANCE & STREAK UPDATES")
    
    # --- PART 1: STREAK & TASK CLEANUP ---
    task_conn = sqlite3.connect('userTaskList.db')
    time_conn = sqlite3.connect('userTimeUsage.db')
    
    task_cursor = task_conn.cursor()
    time_cursor = time_conn.cursor()

    task_cursor.execute("SELECT userID, tasks FROM userTasks")
    all_users = task_cursor.fetchall()

    # Determine "Yesterday" based on IST logic (since we run at 5AM IST, yesterday was the study day)
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')

    for userID, tasks_json in all_users:
        try:
            data = json.loads(tasks_json)
            journal_tasks = data.get("journal", [])
            daily_tasks = data.get("daily", [])

            # --- STREAK CHECK ---
            if not journal_tasks and not daily_tasks:
                is_eligible = False
            else:
                journal_done = all(t.get('completed', False) for t in journal_tasks)
                daily_done = all(t.get('completed', False) for t in daily_tasks)
                is_eligible = journal_done and daily_done

            if is_eligible:
                # Update Streak (Active)
                time_cursor.execute('''
                    UPDATE userTime 
                    SET current_streak = current_streak + 1, 
                        streak_status = 'ACTIVE',
                        last_completion_date = ?
                    WHERE userID = ?
                ''', (yesterday_str, userID))
            else:
                # Break Streak (Inactive)
                time_cursor.execute('''
                    UPDATE userTime 
                    SET current_streak = 0, 
                        streak_status = 'INACTIVE'
                    WHERE userID = ?
                ''', (userID,))

            # --- TASK RESET ---
            for t in journal_tasks: t['completed'] = False
            
            # WIPE Daily Tasks
            new_tasks_data = json.dumps({"journal": journal_tasks, "daily": []})
            task_cursor.execute("UPDATE userTasks SET tasks = ? WHERE userID = ?", (new_tasks_data, userID))
            
        except Exception as e:
            print(f"Error processing user {userID}: {e}")

    task_conn.commit()
    time_conn.commit()
    task_conn.close()
    time_conn.close()


    # --- PART 2: LEADERBOARD RESET ---
    # Split active sessions & Wipe Daily Time
    current_time = datetime.now(timezone.utc)
    
    # Handle active voice sessions
    for userID, start_time in list(voiceTrack.items()):
        duration = (current_time - start_time).total_seconds()
        SaveUserTime(userID, duration)
        voiceTrack[userID] = current_time # Restart timer
    save_voice_sessions(voiceTrack)

    # Wipe the Daily Column
    conn_lb = sqlite3.connect('userTimeUsage.db')
    cursor_lb = conn_lb.cursor()
    cursor_lb.execute('UPDATE userTime SET daily_time = 0')
    conn_lb.commit()
    conn_lb.close()
    print("✅ Daily leaderboard reset.")


    # --- PART 2: LEADERBOARD RESET ---
    # (From your previous logic: Split sessions & Wipe Daily Time)
    
    # A. Split active sessions (midnight crossover)
    current_time = datetime.now(timezone.utc)
    for userID, start_time in list(voiceTrack.items()):
        duration = (current_time - start_time).total_seconds()
        SaveUserTime(userID, duration)
        voiceTrack[userID] = current_time # Restart timer for new day
    save_voice_sessions(voiceTrack)

    # B. Wipe the Daily Column
    conn_lb = sqlite3.connect('userTimeUsage.db')
    cursor_lb = conn_lb.cursor()
    cursor_lb.execute('UPDATE userTime SET daily_time = 0')
    conn_lb.commit()
    conn_lb.close()
    print("✅ Daily leaderboard reset.")
    
@bot.tree.command(name="streak_leaderboard", description="View the Top 10 Active Streaks")
async def streak_img_lb(interaction: discord.Interaction):
    await interaction.response.defer()

    # 1. Fetch Data
    raw_data = get_streak_leaderboard()
    
    if not raw_data:
        return await interaction.followup.send("No active streaks found! Start studying to get on the board.")

    processed_users = []
    
    # 2. Process Data (No avatars needed for this specific layout request, just names)
    for user_id, streak in raw_data:
        # Get User Name
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

    # 3. Generate Image
    final_buffer = await bot.loop.run_in_executor(None, draw_streak_leaderboard, processed_users)

    # 4. Send
    file = discord.File(fp=final_buffer, filename="streak_leaderboard.png")
    await interaction.followup.send(file=file)
    
# ==========================================
#  DAILY STREAK TASK CONFIGURATION
# ==========================================
STREAK_CHANNEL_ID = 1464650405278515444

# 2. Set the time you want it to post (24-hour format, e.g., 9:00 AM)
# This uses UTC time by default. If you are in India (UTC+5:30), 
# 03:30 UTC = 09:00 AM IST.
DAILY_TIME = time(hour=23, minute=30, tzinfo=timezone.utc)

@tasks.loop(time=DAILY_TIME)
async def post_daily_streak():
    channel = bot.get_channel(STREAK_CHANNEL_ID)
    
    if not channel:
        print(f"❌ Error: Could not find channel with ID {STREAK_CHANNEL_ID}")
        return

    # --- STEP 1: REMOVE OLD LEADERBOARD TEXT ---
    # We search the last 20 messages to find one sent by the bot 
    # that contains the specific header text.
    try:
        async for message in channel.history(limit=20):
            if message.author == bot.user and "Daily Streak Leaderboard" in message.content:
                await message.delete()
                break 
    except Exception as e:
        print(f"Error deleting old message: {e}")

    # --- STEP 2: GENERATE NEW LEADERBOARD ---
    try:
        # Fetch Data
        raw_data = get_streak_leaderboard()
        
        if not raw_data:
            await channel.send("Daily Streak Leaderboard: No active streaks today!")
            return

        processed_users = []
        for user_id, streak in raw_data:
            # Get User Name
            user = bot.get_user(user_id)
            if not user:
                try:
                    user = await bot.fetch_user(user_id)
                except:
                    user = None
            
            username = user.display_name if user else "Unknown User"
            processed_users.append({'name': username, 'streak': str(streak)})

        # Generate Image
        final_buffer = await bot.loop.run_in_executor(None, draw_streak_leaderboard, processed_users)
        file = discord.File(fp=final_buffer, filename="daily_streak.png")

        # --- STEP 3: POST NEW LEADERBOARD ---
        await channel.send("🔥 **Daily Streak Leaderboard** 🔥\nKeep the grind going!", file=file)
        
    except Exception as e:
        print(f"Error generating daily streak: {e}")


    
@bot.event
async def on_message(message):
# --- REP SYSTEM LOGIC ---
    msg_content = message.content.lower()
    thank_keywords = ["thanks", "thank you", "thx", "tysm"]
    if any(word in msg_content for word in thank_keywords):
        thanked_user = None

        # PRIORITY 1: Check if it is a Reply
        if message.reference:
            try:
                original_msg = message.reference.resolved
                if not original_msg:
                    original_msg = await message.channel.fetch_message(message.reference.message_id)
                thanked_user = original_msg.author
            except Exception:
                pass

        # PRIORITY 2: Check if it uses Mentions (if no reply was found)
        # We check 'not thanked_user' so we don't overwrite the reply target if both exist
        if not thanked_user and message.mentions:
            # Loop to find the first user who is NOT the author
            for user in message.mentions:
                if user.id != message.author.id:
                    thanked_user = user
                    break
                
            if not thanked_user:
                thanked_user = message.mentions[0]

        # If we found a target user (via Reply OR Mention), process the Rep
        if thanked_user:
            try:
                # ANTI-ABUSE CHECKS:
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

    # Check for humor/fun replies
    replied = await check_humor(message)
    await bot.process_commands(message)
    
 
@exclude_channels.error
async def exclude_channels_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You do not have permission to use this command, nice try diddy!", ephemeral=True)   
    
@bot.event
async def on_ready():
    setupTimeDB()
    setupTaskDB()
    setupExChannelDB()
    setupRepDB()
    
    if not midnight_maintenance.is_running():
        midnight_maintenance.start()

    bot.tree.add_command(report_menu)
    try:    
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    print("Bot ready!")
    

    
async def setup_hook(self):
        self.tree.add_command(report_context_menu)
        await self.tree.sync()

token = os.getenv('DISCORD_TOKEN')
bot.run(token)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

Thread(target=run_web).start()

# Ensure your existing bot.run is the last line
token = os.getenv('DISCORD_TOKEN')
bot.run(token)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

Thread(target=run_web).start()

# Ensure your existing bot.run is the last line
token = os.getenv('DISCORD_TOKEN')
bot.run(token)
# --- KEEP-ALIVE SERVER CONFIG ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    # Render provides the PORT variable automatically
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# We start the web server in a background thread FIRST
if __name__ == "__main__":
    t = Thread(target=run_web)
    t.start()

    # NOW we start the bot. This must be the very last thing that happens.
    token = os.getenv('DISCORD_TOKEN')
    if token:
        bot.run(token)
    else:
        print("ERROR: DISCORD_TOKEN not found in Environment Variables!")