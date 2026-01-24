import sqlite3

def setupRepDB():
    connection = sqlite3.connect('userReps.db')
    cursor = connection.cursor()
    
    # Create table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS userReps (
        userID INTEGER PRIMARY KEY, 
        reps INTEGER DEFAULT 0
    )
    ''')
    
    connection.commit()
    connection.close()

def get_reps(userID):
    connection = sqlite3.connect('userReps.db')
    cursor = connection.cursor()
    cursor.execute('SELECT reps FROM userReps WHERE userID = ?', (userID,))
    result = cursor.fetchone()
    connection.close()
    
    if result:
        return result[0]
    return 0

def add_rep(userID):
    """Increments rep by 1 and returns the new total."""
    connection = sqlite3.connect('userReps.db')
    cursor = connection.cursor()
    
    # Check if user exists
    cursor.execute('SELECT reps FROM userReps WHERE userID = ?', (userID,))
    result = cursor.fetchone()
    
    new_reps = 1
    
    if result:
        new_reps = result[0] + 1
        cursor.execute('UPDATE userReps SET reps = ? WHERE userID = ?', (new_reps, userID))
    else:
        cursor.execute('INSERT INTO userReps (userID, reps) VALUES (?, ?)', (userID, new_reps))
        
    connection.commit()
    connection.close()
    
    return new_reps