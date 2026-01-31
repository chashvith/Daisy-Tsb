from email.mime import base
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io

# Coordinates based on your request
POSITIONS = {
    1: (390, 129),
    
    # --- LEFT COLUMN (Moved Right slightly for padding) ---
    2: (100, 398),
    
    # --- RIGHT COLUMN (Moved Right significantly for symmetry) ---
    3: (650, 398),
    
    # --- REST OF CENTER COLUMN (Aligned with Rank 1) ---
    4: (320, 643),
    5: (320, 643 + 1*135),
    6: (320, 643 + 2*135),
    7: (320, 643 + 3*135),
    8: (320, 643 + 4*135),
    9: (320, 643 + 5*135),
    10:(320, 643 + 6*135)
}

AVATAR_SIZE_LG = 120
AVATAR_SIZE_SM = 80
NAME_COLUMN_WIDTH = 150  # Fixed space for names in Ranks 4-10

def circular_avatar(img, size):
    img = img.resize(size, Image.Resampling.LANCZOS).convert("RGBA")
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)
    output = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
    output.putalpha(mask)
    return output

def draw_leaderboard(users_data):
    try:
        base = Image.open("leaderboard_template.png").convert("RGBA")
    except FileNotFoundError:
        base = Image.new("RGBA", (900, 1900), (44, 47, 51, 255))

    draw = ImageDraw.Draw(base)
    
    try:
        # Large Fonts (Top 3)
        font_name_lg = ImageFont.truetype("arial.ttf", 40)
        font_time_lg = ImageFont.truetype("arial.ttf", 30)
        
        # Small Fonts (Ranks 4-10)
        font_rank_sm = ImageFont.truetype("arial.ttf", 40)
        font_name_sm = ImageFont.truetype("arial.ttf", 30)
        font_time_sm = ImageFont.truetype("arial.ttf", 25)
    except IOError:
        font_name_lg = ImageFont.load_default()
        font_time_lg = ImageFont.load_default()
        font_rank_sm = ImageFont.load_default()
        font_name_sm = ImageFont.load_default()
        font_time_sm = ImageFont.load_default()

    for rank, user in enumerate(users_data, start=1):
        if rank > 10: break
        if rank not in POSITIONS: continue

        x, y = POSITIONS[rank]

        # ==========================================
        # LAYOUT A: TOP 3 (Vertical Stack)
        # ==========================================
        if rank <= 3:
            # Avatar
            if user['avatar_bytes']:
                try:
                    avatar_img = Image.open(io.BytesIO(user['avatar_bytes']))
                    avatar_img = circular_avatar(avatar_img, (AVATAR_SIZE_LG, AVATAR_SIZE_LG))
                    base.paste(avatar_img, (int(x), y), avatar_img)
                except: pass

            # Centering Helper
            def get_centered_x(text, font):
                text_width = draw.textlength(text, font=font)
                return (x + (AVATAR_SIZE_LG / 2)) - (text_width / 2)

            text_y = y + 125
            
            # Name
            name_str = user['name'][:15]
            draw.text((get_centered_x(name_str, font_name_lg), text_y), 
                      name_str, font=font_name_lg, fill="white")
            
            # Time
            draw.text((get_centered_x(user['time'], font_time_lg), text_y + 45), 
                      user['time'], font=font_time_lg, fill="gold")

        # ==========================================
        # LAYOUT B: RANKS 4-10 (Fixed Column Matrix)
        # ==========================================
        else:
            # 1. Avatar (80px)
            avatar_y = y + 10 
            if user['avatar_bytes']:
                try:
                    avatar_img = Image.open(io.BytesIO(user['avatar_bytes']))
                    avatar_img = circular_avatar(avatar_img, (AVATAR_SIZE_SM, AVATAR_SIZE_SM))
                    base.paste(avatar_img, (int(x), avatar_y), avatar_img)
                except: pass

            text_y_center = avatar_y + 25

            # 2. RANK (Left of Avatar)
            rank_str = f"{rank}."
            rank_width = draw.textlength(rank_str, font=font_rank_sm)
            rank_x = x - 20 - rank_width
            draw.text((rank_x, text_y_center), rank_str, font=font_rank_sm, fill="white")

            # 3. NAME (Column 1 - Starts after Avatar)
            name_x = x + AVATAR_SIZE_SM + 20
            
            # Truncate logic: Ensure name doesn't bleed into Time column
            display_name = user['name']
            while draw.textlength(display_name, font=font_name_sm) > (NAME_COLUMN_WIDTH - 10) and len(display_name) > 0:
                display_name = display_name[:-1]
            
            draw.text((name_x, text_y_center), display_name, font=font_name_sm, fill="white")

            # 4. TIME (Column 2 - FIXED START POSITION)
            # This creates the perfect alignment you wanted
            time_x = name_x + NAME_COLUMN_WIDTH
            
            draw.text((time_x, text_y_center + 2), user['time'], font=font_time_sm, fill="gold")

    buffer = io.BytesIO()
    base.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


STREAK_Y_COORDS = {
    1: 80,
    2: 140,
    3: 200,
    4: 260,
    5: 320,
    6: 380,
    7: 440,
    8: 500,
    9: 560,
    10:620
}

NAME_X = 20
STREAK_X = 280

def draw_streak_leaderboard(users_data):
    """
    Draws the Streak Leaderboard based on specific coordinates.
    users_data: list of dicts -> [{'name': 'User', 'streak': '5'}]
    """
    try:
        # distinct background for streaks
        base = Image.open("streak_template.png").convert("RGBA")
    except FileNotFoundError:
        # Fallback to dark gray if file missing
        base = Image.new("RGBA", (900, 1900), (40, 40, 40, 255))

    draw = ImageDraw.Draw(base)

    try:
        # Using a large font since these rows are tall (153px gap)
        font_name = ImageFont.truetype("arial.ttf", 20)
        font_streak = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font_name = ImageFont.load_default()
        font_streak = ImageFont.load_default()

    visual_slot = 1

    for user in users_data:
            if visual_slot > 10: break
            
            # This is the real rank (e.g., 1, 2, 3... 50, 51, 52)
            actual_rank = user['rank']
            
            x, y = POSITIONS[visual_slot]

            # ==========================================
            # TOP 3 (Visual Slots 1, 2, 3)
            # ==========================================
            if visual_slot <= 3:
                if user['avatar_bytes']:
                    try:
                        avatar_img = Image.open(io.BytesIO(user['avatar_bytes']))
                        avatar_img = circular_avatar(avatar_img, (AVATAR_SIZE_LG, AVATAR_SIZE_LG))
                        base.paste(avatar_img, (int(x), y), avatar_img)
                    except: pass

                def get_centered_x(text, font):
                    text_width = draw.textlength(text, font=font)
                    return (x + (AVATAR_SIZE_LG / 2)) - (text_width / 2)

                text_y = y + 125
                
                name_str = user['name'][:15]
                draw.text((get_centered_x(name_str, font_name_lg), text_y), 
                        name_str, font=font_name_lg, fill="white")
                
                draw.text((get_centered_x(user['time'], font_time_lg), text_y + 45), 
                        user['time'], font=font_time_lg, fill="gold")

            # ==========================================
            # LIST VIEW (Visual Slots 4-10)
            # ==========================================
            else:
                # 1. Avatar
                avatar_y = y + 10 
                if user['avatar_bytes']:
                    try:
                        avatar_img = Image.open(io.BytesIO(user['avatar_bytes']))
                        avatar_img = circular_avatar(avatar_img, (AVATAR_SIZE_SM, AVATAR_SIZE_SM))
                        base.paste(avatar_img, (int(x), avatar_y), avatar_img)
                    except: pass

                text_y_center = avatar_y + 25

                # 2. ACTUAL RANK NUMBER (e.g., "50.")
                # This places the rank index strictly to the left of the avatar/name
                rank_str = f"{actual_rank}."
                rank_width = draw.textlength(rank_str, font=font_rank_sm)
                rank_x = x - 20 - rank_width
                
                # Highlight user in Gold, others in White
                rank_color = "gold" if user.get('is_target') else "white"
                draw.text((rank_x, text_y_center), rank_str, font=font_rank_sm, fill=rank_color)

                # 3. Name
                name_x = x + AVATAR_SIZE_SM + 20
                display_name = user['name']
                
                # Truncate
                while draw.textlength(display_name, font=font_name_sm) > (NAME_COLUMN_WIDTH - 10) and len(display_name) > 0:
                    display_name = display_name[:-1]
                
                name_color = "gold" if user.get('is_target') else "white"
                draw.text((name_x, text_y_center), display_name, font=font_name_sm, fill=name_color)

                # 4. Time
                time_x = name_x + NAME_COLUMN_WIDTH
                draw.text((time_x, text_y_center + 2), user['time'], font=font_time_sm, fill="gold")

            visual_slot += 1

    buffer = io.BytesIO()
    base.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer