import sqlite3
import os

# Path to the database file (change as needed)
DB_PATH = os.getenv("DB_PATH", "word_mine_bot.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    conn = get_connection()
    c = conn.cursor()
    # Create table for global scores
    c.execute('''
        CREATE TABLE IF NOT EXISTS global_scores (
            user_id INTEGER PRIMARY KEY,
            score INTEGER NOT NULL DEFAULT 0
        )
    ''')
    # Create table for chat scores
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_scores (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
    ''')
    conn.commit()
    conn.close()

def update_global_score(user_id, points=1):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO global_scores (user_id, score) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET score = score + ?
    """, (user_id, points, points))
    conn.commit()
    conn.close()

def update_chat_score(chat_id, user_id, points=1):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO chat_scores (chat_id, user_id, score) VALUES (?, ?, ?)
        ON CONFLICT(chat_id, user_id) DO UPDATE SET score = score + ?
    """, (chat_id, user_id, points, points))
    conn.commit()
    conn.close()

def get_global_leaderboard(limit=10):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, score FROM global_scores ORDER BY score DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [(row["user_id"], row["score"]) for row in rows]

def get_chat_leaderboard(chat_id, limit=10):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, score FROM chat_scores WHERE chat_id=? ORDER BY score DESC LIMIT ?", (chat_id, limit))
    rows = c.fetchall()
    conn.close()
    return [(row["user_id"], row["score"]) for row in rows]

if __name__ == "database":
    initialize_db()
    print("Database initialized.")



