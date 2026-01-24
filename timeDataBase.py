import sqlite3
import json

def setupTimeDB():
    connection = sqlite3.connect('userTimeUsage.db')

    cursor = connection.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS
    userTime(userID INTEGER PRIMARY KEY, time REAL DEFAULT 0, daily_time REAL DEFAULT 0)
    ''')
    
    

    # Add new Streak and Season columns safely
    new_columns = [
        ("current_streak", "INTEGER DEFAULT 0"),
        ("streak_status", "TEXT DEFAULT 'INACTIVE'"),
        ("last_completion_date", "TEXT"), # Stores YYYY-MM-DD
        ("season_id", "INTEGER DEFAULT 1")
    ]
    
    for col_name, col_type in new_columns:
        try:
            cursor.execute(f'ALTER TABLE userTime ADD COLUMN {col_name} {col_type}')
        except sqlite3.OperationalError:
            pass

    # Add the daily_time column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE userTime ADD COLUMN daily_time REAL DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    connection.commit()
    connection.close()

def getUserTime(userID):
    connection = sqlite3.connect('userTimeUsage.db')
    cursor = connection.cursor()
    cursor.execute('SELECT time FROM userTime WHERE userID = ?', (userID,))
    result = cursor.fetchone()
    connection.close()

    if result == None:
        return 0
    else:
        return result[0]
    
def getUserDailyTime(userID):
    connection = sqlite3.connect('userTimeUsage.db')
    cursor = connection.cursor()
    cursor.execute('SELECT daily_time FROM userTime WHERE userID = ?', (userID,))
    result = cursor.fetchone()
    connection.close()

    if result == None:
        return 0
    else:
        return result[0]


def SaveUserTime(userID, duration):
    connection = sqlite3.connect('userTimeUsage.db')
    cursor = connection.cursor()

    # 1. Update (or Insert) TOTAL Time
    # We try to update first. If no row exists, we insert.
    cursor.execute('UPDATE userTime SET time = time + ? WHERE userID = ?', (duration, userID))
    
    # If the row didn't exist (changes == 0), we create it
    if cursor.rowcount == 0:
        cursor.execute('INSERT INTO userTime (userID, time, daily_time) VALUES (?, ?, ?)', (userID, duration, duration))
    else:
        # 2. Update DAILY Time
        # We only need to run this if the user already existed (because the INSERT above handles both)
        cursor.execute('UPDATE userTime SET daily_time = daily_time + ? WHERE userID = ?', (duration, userID))

    connection.commit()
    connection.close()

def get_leaderboard_data(lbtype,offset=0):
    """Fetches 10 users from the database, starting after the offset."""
    connection = sqlite3.connect('userTimeUsage.db')
    cursor = connection.cursor()
    
    # The '?' is a placeholder for the offset value
    if lbtype == "daily":
        cursor.execute('SELECT userID, daily_time FROM userTime ORDER BY daily_time DESC LIMIT 10 OFFSET ?', (offset,))
        result = cursor.fetchall()
    elif lbtype == "all time":
        cursor.execute('SELECT userID, time FROM userTime ORDER BY time DESC LIMIT 10 OFFSET ?', (offset,))
        result = cursor.fetchall()
    
    connection.close()
    return result

def get_streak_info(userID):
    connection = sqlite3.connect('userTimeUsage.db')
    cursor = connection.cursor()
    cursor.execute('SELECT current_streak, streak_status, last_completion_date FROM userTime WHERE userID = ?', (userID,))
    result = cursor.fetchone()
    connection.close()
    
    if result:
        return {"streak": result[0], "status": result[1], "last_date": result[2]}
    return {"streak": 0, "status": 'INACTIVE', "last_date": None}

def get_streak_leaderboard():
    connection = sqlite3.connect('userTimeUsage.db')
    cursor = connection.cursor()
    # Filter for active streaks and sort by the highest number
    cursor.execute('''
        SELECT userID, current_streak 
        FROM userTime 
        WHERE current_streak > 0 
        ORDER BY current_streak DESC
    ''')
    result = cursor.fetchall()
    connection.close()
    return result

def reset_seasonal_streaks():
    connection = sqlite3.connect('userTimeUsage.db')
    cursor = connection.cursor()
    
    # 1. Reset all streaks to 0
    # 2. Set all statuses to INACTIVE so they can redefine tasks
    cursor.execute('''
        UPDATE userTime 
        SET current_streak = 0, 
            streak_status = 'INACTIVE', 
            last_completion_date = NULL
    ''')
    
    connection.commit()
    connection.close()
    print("Season has been reset. All streaks are now 0.")