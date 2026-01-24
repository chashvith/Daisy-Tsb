import random
import discord
import re

# --- CONFIGURATION 1: EMOJI REACTIONS ---
# Format: 'keyword': 'emoji_symbol'
REACTION_TRIGGERS = {
    # Good Luck
    "good luck": "🍀",
    "all the best": "🤞",
    "best of luck": "🍀",
    "atb": "👍",
    
    # Gratitude
    "thank": "🤝",
    "dhananyavadalu": "🙏",
    
    # Progress
    "done": "✅",
    "completed": "✅",
    "aipoyindi": "🔥", 
    
    
}

# --- CONFIGURATION 2: TEXT REPLIES ---
# Format: 'keyword': ['reply1', 'reply2', ...]
TEXT_REPLIES = {
    # Good Night / Sleep
    "good night": [
        "Rest is the fuel for tomorrow's conquest. Sleep well.",
        "Disconnect to reconnect stronger tomorrow. Subharatri.",
        "The syllabus will be there tomorrow, but your energy needs to be replenished. Good night."
    ],
    "gn": [
        "Rest well. The grind continues tomorrow."
    ],
    "padukuntunna": [ # "I am sleeping"
        "Nidra (Sleep) is essential for memory consolidation. Sleep well.",
        "Subharatri. Wake up with a purpose."
    ],

    # Good Morning / Wake up
    "good morning": [
        "A new day, a new chapter. Seize the opportunity. Subhodayam!",
        "The best time to start is now. Good morning."
    ],
    "gm": [
        "Rise and grind. The goal hasn't changed."
    ],
    
    # Motivation (Retained from previous version)
    "give up": [
        "You did not come this far to only come this far. Push through.",
        "Pain is temporary. Quitting lasts forever."
    ]
}


async def check_humor(message: discord.Message):
    """
    Checks for keywords to either React (Emoji) or Reply (Text).
    """
    content = message.content.lower()
    triggered = False

    # 1. CHECK FOR REACTIONS (Silent Interactions)
    for keyword, emoji in REACTION_TRIGGERS.items():
        if re.search(rf"\b{re.escape(keyword)}\b", content):
            try:
                await message.add_reaction(emoji)
                triggered = True
            except discord.Forbidden:
                print("❌ Missing permissions to add reaction!")
            except Exception as e:
                print(f"Error adding reaction: {e}")

# 2. CHECK FOR REPLIES (Conversation)
    for keyword, replies in TEXT_REPLIES.items():
        if re.search(rf"\b{re.escape(keyword)}\b", content):
            
            embed = discord.Embed(
                description=f"**{random.choice(replies)}**",
                color=discord.Color.dark_teal()
            )
            await message.channel.send(embed=embed)
            triggered = True
            break 

    return triggered