import sqlite3
import os
import uuid  # <-- Import uuid module

DB_NAME = 'game_scores.db'
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), DB_NAME)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # Create game_types table (still integer PK)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS game_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    # Create players table (GUID PK)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    # Create games table (GUID PK)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            game_type_id INTEGER NOT NULL,
            total_score INTEGER,
            max_score INTEGER,
            total_duration_seconds INTEGER,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(game_type_id) REFERENCES game_types(id) ON DELETE CASCADE
        )
    ''')
    # Create score_types table (GUID PK)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS score_types (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            value INTEGER NOT NULL
        )
    ''')
    # Create rounds table (GUID PK)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS rounds (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            joker TEXT,
            winner_player_id TEXT,
            duration_seconds INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
            FOREIGN KEY(winner_player_id) REFERENCES players(id) ON DELETE SET NULL
        )
    ''')
    # Create scores table (GUID PK)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id TEXT PRIMARY KEY,
            round_id TEXT NOT NULL,
            player_id TEXT NOT NULL,
            score_type_id TEXT,
            score INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(round_id) REFERENCES rounds(id) ON DELETE CASCADE,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE,
            FOREIGN KEY(score_type_id) REFERENCES score_types(id) ON DELETE SET NULL
        )
    ''')
    # Create game_players table (GUID PK)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS game_players (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            player_id TEXT NOT NULL,
            eliminated INTEGER DEFAULT 0,
            FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

score_types = [
    (str(uuid.uuid4()), 'Declared', 0),
    (str(uuid.uuid4()), 'Custom', 0),  # Use 0 instead of None
    (str(uuid.uuid4()), 'Scoot', 20),
    (str(uuid.uuid4()), 'Half Scoot', 40),
    (str(uuid.uuid4()), 'Full', 80)
]
