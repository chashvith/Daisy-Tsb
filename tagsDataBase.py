import sqlite3
import json

MAX_TAGS = 10        # Max tags a user can have
MAX_TAG_LENGTH = 30  # Max characters per tag

def setupTagsDB():
    connection = sqlite3.connect('userTags.db')
    cursor = connection.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS userTags (
        userID INTEGER PRIMARY KEY,
        tags TEXT DEFAULT '[]'
    )
    ''')

    connection.commit()
    connection.close()


def getUserTags(userID):
    """Returns a list of tags for the given user. Empty list if none."""
    connection = sqlite3.connect('userTags.db')
    cursor = connection.cursor()
    cursor.execute('SELECT tags FROM userTags WHERE userID = ?', (userID,))
    result = cursor.fetchone()
    connection.close()

    if not result:
        return []

    try:
        return json.loads(result[0])
    except json.JSONDecodeError:
        print(f"⚠️ Tag data corruption for user {userID}")
        return []


def addUserTag(userID, tag):
    """
    Adds a tag to the user's tag list.
    Returns:
        'added'     - tag was added successfully
        'duplicate' - tag already exists
        'limit'     - user already has MAX_TAGS tags
    """
    connection = sqlite3.connect('userTags.db')
    cursor = connection.cursor()

    cursor.execute('SELECT tags FROM userTags WHERE userID = ?', (userID,))
    result = cursor.fetchone()

    if result:
        tags = json.loads(result[0])
    else:
        tags = []

    # Normalise before checking (lowercase + stripped)
    tag_normalised = tag.strip().lower()
    existing_normalised = [t.lower() for t in tags]

    if tag_normalised in existing_normalised:
        connection.close()
        return 'duplicate'

    if len(tags) >= MAX_TAGS:
        connection.close()
        return 'limit'

    tags.append(tag.strip())
    tags_json = json.dumps(tags)

    if result:
        cursor.execute('UPDATE userTags SET tags = ? WHERE userID = ?', (tags_json, userID))
    else:
        cursor.execute('INSERT INTO userTags (userID, tags) VALUES (?, ?)', (userID, tags_json))

    connection.commit()
    connection.close()
    return 'added'


def removeUserTag(userID, tag):
    """
    Removes a tag from the user's tag list (case-insensitive match).
    Returns:
        'removed'   - tag was removed successfully
        'not_found' - tag didn't exist
        'empty'     - user has no tags at all
    """
    connection = sqlite3.connect('userTags.db')
    cursor = connection.cursor()

    cursor.execute('SELECT tags FROM userTags WHERE userID = ?', (userID,))
    result = cursor.fetchone()
    connection.close()

    if not result:
        return 'empty'

    tags = json.loads(result[0])

    if not tags:
        return 'empty'

    tag_normalised = tag.strip().lower()
    updated_tags = [t for t in tags if t.lower() != tag_normalised]

    if len(updated_tags) == len(tags):
        return 'not_found'

    # Reconnect to save
    connection = sqlite3.connect('userTags.db')
    cursor = connection.cursor()
    cursor.execute('UPDATE userTags SET tags = ? WHERE userID = ?', (json.dumps(updated_tags), userID))
    connection.commit()
    connection.close()

    return 'removed'

# ==========================================
#  ACTIVE TAG SESSION  (in-memory store)
# ==========================================
# Stores {userID: "TagName"} for users currently in a voice channel.
# This is intentionally in-memory — it resets with the bot, matching
# how voiceTrack works. If the bot restarts, users will be prompted again.
_active_tags: dict[int, str] = {}

def getActiveTag(userID: int) -> str | None:
    """Returns the tag the user is currently studying under, or None."""
    return _active_tags.get(userID)

def setActiveTag(userID: int, tag: str) -> None:
    """Set the user's active study tag."""
    _active_tags[userID] = tag

def clearActiveTag(userID: int) -> None:
    """Remove the user's active study tag (called on voice leave)."""
    _active_tags.pop(userID, None)