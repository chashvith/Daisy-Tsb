import sqlite3
import json

def setupTaskDB():
    #creating a database for tasks and naming it userTaskList
    connection = sqlite3.connect('userTaskList.db')

    #creating a cursor to navigate
    cursor = connection.cursor()

    #creating a table to store user id and their task data
    taskcreate = '''
    CREATE TABLE IF NOT EXISTS
    userTasks(userID INTEGER PRIMARY KEY, tasks TEXT)
    '''
    cursor.execute(taskcreate)
    connection.commit()
    connection.close()
    

def getUserData(userID):
    connection = sqlite3.connect('userTaskList.db')
    cursor = connection.cursor()
    cursor.execute('SELECT tasks FROM userTasks WHERE userID = ?', (userID,))
    result = cursor.fetchone()
    connection.close()

    default_structure = {"journal": [], "daily": []}

    if not result:
        return default_structure

    try:
        loaded_data = json.loads(result[0])
        
        # Migration: Convert flat list to dict if needed
        if isinstance(loaded_data, list):
            loaded_data = {"journal": loaded_data, "daily": []}
        
        # Validation: Ensure keys exist
        if "journal" not in loaded_data: loaded_data["journal"] = []
        if "daily" not in loaded_data: loaded_data["daily"] = []

        return loaded_data

    except json.JSONDecodeError:
        print(f"⚠️ DATA CORRUPTION WARNING: User {userID} has broken JSON.")
        # Return default to avoid crash, BUT we should ideally backup the bad data
        return default_structure

def SaveUserTasks(userID, journal_tasks, daily_tasks):
    connection = sqlite3.connect('userTaskList.db')
    cursor = connection.cursor()
    
    # Combine them back into the dictionary format for storage
    tasks_dict = {
        "journal": journal_tasks,
        "daily": daily_tasks
    }
    
    tasks_json = json.dumps(tasks_dict)
    
    cursor.execute('''
        INSERT INTO userTasks (userID, tasks) VALUES (?, ?)
        ON CONFLICT(userID) DO UPDATE SET tasks = excluded.tasks
    ''', (userID, tasks_json))
    
    connection.commit()
    connection.close()
