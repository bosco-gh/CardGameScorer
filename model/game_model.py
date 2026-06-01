from .db import get_connection
import uuid

class PlayerExistsError(Exception):
    pass
class InvalidScoreError(Exception):
    pass
class GameTypeExistsError(Exception):
    pass

def add_game_type(name):
    if not name or not name.strip():
        raise ValueError('Game type name required')
    conn = get_connection()
    try:
        conn.execute('INSERT INTO game_types (name) VALUES (?)', (name.strip(),))
        conn.commit()
    except Exception as e:
        if 'UNIQUE constraint' in str(e):
            raise GameTypeExistsError('Game type already exists')
        raise
    finally:
        conn.close()

def get_game_types():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM game_types ORDER BY name')
    types = cur.fetchall()
    conn.close()
    return types

def add_game(game_type_id, name, total_score=None, played_at=None):
    if not name or not name.strip():
        raise ValueError('Game name required')
    conn = get_connection()
    cur = conn.cursor()
    game_id = str(uuid.uuid4())
    if played_at:
        cur.execute('INSERT INTO games (id, name, game_type_id, total_score, played_at) VALUES (?, ?, ?, ?, ?)', (game_id, name.strip(), game_type_id, total_score, played_at))
    else:
        cur.execute('INSERT INTO games (id, name, game_type_id, total_score) VALUES (?, ?, ?, ?)', (game_id, name.strip(), game_type_id, total_score))
    conn.commit()
    conn.close()
    return game_id

def get_games():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT g.*, gt.name as game_type_name
        FROM games g
        JOIN game_types gt ON g.game_type_id = gt.id
        ORDER BY g.played_at DESC
    ''')
    games = cur.fetchall()
    conn.close()
    return games

def init_score_types():
    conn = get_connection()
    cur = conn.cursor()
    # Remove existing types to avoid duplicates (dev only, safe for re-init)
    cur.execute('DELETE FROM score_types')
    score_types = [
        (str(uuid.uuid4()), 'Declared', 0),
        (str(uuid.uuid4()), 'Custom', 0),  # Use 0 instead of None
        (str(uuid.uuid4()), 'Scoot', 20),
        (str(uuid.uuid4()), 'Half Scoot', 40),
        (str(uuid.uuid4()), 'Full', 80)
    ]
    for st_id, name, value in score_types:
        cur.execute('INSERT INTO score_types (id, name, value) VALUES (?, ?, ?)', (st_id, name, value))
    conn.commit()
    conn.close()

def get_score_types():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM score_types ORDER BY value')
    types = cur.fetchall()
    conn.close()
    return types

def get_score_type_by_name(name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM score_types WHERE name = ?', (name,))
    st = cur.fetchone()
    conn.close()
    return st

def add_round(game_id, round_number, joker=None, winner_player_id=None, duration_seconds=None):
    import datetime
    conn = get_connection()
    cur = conn.cursor()
    # Get previous round's created_at
    cur.execute('SELECT created_at FROM rounds WHERE game_id = ? ORDER BY round_number DESC LIMIT 1', (game_id,))
    prev = cur.fetchone()
    now = datetime.datetime.now()
    if prev:
        prev_time = datetime.datetime.fromisoformat(prev['created_at'])
        duration_seconds = int((now - prev_time).total_seconds())
    else:
        duration_seconds = 0
    round_id = str(uuid.uuid4())
    cur.execute('INSERT INTO rounds (id, game_id, round_number, joker, winner_player_id, duration_seconds, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (round_id, game_id, round_number, joker, winner_player_id, duration_seconds, now.isoformat()))
    conn.commit()
    conn.close()
    return round_id

def set_game_total_duration(game_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT COALESCE(SUM(duration_seconds), 0) as total FROM rounds WHERE game_id = ?', (game_id,))
    total = cur.fetchone()['total']
    cur.execute('UPDATE games SET total_duration_seconds = ? WHERE id = ?', (total, game_id))
    conn.commit()
    conn.close()

def add_scores_for_round(round_id, scores_dict):
    # scores_dict: {player_id: (score_type_id, score), ...}
    conn = get_connection()
    for player_id, (score_type_id, score) in scores_dict.items():
        score_id = str(uuid.uuid4())
        conn.execute('INSERT INTO scores (id, round_id, player_id, score_type_id, score) VALUES (?, ?, ?, ?, ?)', (score_id, round_id, player_id, score_type_id, score))
    conn.commit()
    conn.close()

def update_score(score_id, new_score):
    if not isinstance(new_score, int):
        raise InvalidScoreError('Score must be an integer')
    conn = get_connection()
    conn.execute('UPDATE scores SET score = ? WHERE id = ?', (new_score, score_id))
    conn.commit()
    conn.close()

def get_scores_for_round(round_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT s.*, p.name as player_name
        FROM scores s
        JOIN players p ON s.player_id = p.id
        WHERE s.round_id = ?
        ORDER BY s.score DESC
    ''', (round_id,))
    scores = cur.fetchall()
    # Ensure player_id is always a string
    scores = [dict(row) for row in scores]
    for s in scores:
        s['player_id'] = str(s['player_id'])
    conn.close()
    return scores

def get_leaderboard(game_type_id=None):
    conn = get_connection()
    cur = conn.cursor()
    if game_type_id:
        cur.execute('''
            SELECT p.id, p.name, COALESCE(SUM(s.score), 0) as total_score
            FROM players p
            LEFT JOIN scores s ON p.id = s.player_id
            LEFT JOIN rounds r ON s.round_id = r.id
            LEFT JOIN games g ON r.game_id = g.id
            WHERE g.game_type_id = ?
            GROUP BY p.id
            ORDER BY total_score DESC, p.name
        ''', (game_type_id,))
    else:
        cur.execute('''
            SELECT p.id, p.name, COALESCE(SUM(s.score), 0) as total_score
            FROM players p
            LEFT JOIN scores s ON p.id = s.player_id
            GROUP BY p.id
            ORDER BY total_score DESC, p.name
        ''')
    results = cur.fetchall()
    conn.close()
    return results

def get_winner(game_type_id=None):
    leaderboard = get_leaderboard(game_type_id)
    return leaderboard[0] if leaderboard else None

def get_score_by_id(score_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM scores WHERE id = ?', (score_id,))
    score = cur.fetchone()
    conn.close()
    return score

def add_players_to_game(game_id, player_ids):
    conn = get_connection()
    for player_id in player_ids:
        assoc_id = str(uuid.uuid4())
        conn.execute('INSERT INTO game_players (id, game_id, player_id) VALUES (?, ?, ?)', (assoc_id, game_id, player_id))
    conn.commit()
    conn.close()

def get_players_for_game(game_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT p.* FROM players p
        JOIN game_players gp ON p.id = gp.player_id
        WHERE gp.game_id = ?
        ORDER BY p.name
    ''', (game_id,))
    players = cur.fetchall()
    conn.close()
    return players

def get_non_eliminated_players_for_game(game_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT p.* FROM players p
        JOIN game_players gp ON p.id = gp.player_id
        WHERE gp.game_id = ? AND gp.eliminated = 0
        ORDER BY p.name
    ''', (game_id,))
    players = cur.fetchall()
    conn.close()
    return players

def add_player(name):
    if not name or not name.strip():
        raise ValueError('Player name required')
    conn = get_connection()
    player_id = str(uuid.uuid4())
    try:
        conn.execute('INSERT INTO players (id, name) VALUES (?, ?)', (player_id, name.strip(),))
        conn.commit()
    except Exception as e:
        if 'UNIQUE constraint' in str(e):
            raise PlayerExistsError('Player already exists')
        raise
    finally:
        conn.close()
    return player_id

def get_players():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM players ORDER BY name')
    players = cur.fetchall()
    conn.close()
    return players

def get_game_total_score(game_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT total_score FROM games WHERE id = ?', (game_id,))
    row = cur.fetchone()
    conn.close()
    return row['total_score'] if row else None

def get_player_total_score_for_game(game_id, player_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT COALESCE(SUM(s.score), 0) as total_score
        FROM scores s
        JOIN rounds r ON s.round_id = r.id
        WHERE r.game_id = ? AND s.player_id = ?
    ''', (game_id, player_id))
    row = cur.fetchone()
    conn.close()
    return row['total_score'] if row else 0

def eliminate_players_if_needed(game_id):
    total_score = get_game_total_score(game_id)
    if total_score is None:
        return
    players = get_players_for_game(game_id)
    conn = get_connection()
    for player in players:
        player_total = get_player_total_score_for_game(game_id, player['id'])
        if player_total >= total_score:
            conn.execute('UPDATE game_players SET eliminated = 1 WHERE game_id = ? AND player_id = ?', (game_id, player['id']))
    conn.commit()
    conn.close()

def get_rounds_for_game(game_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM rounds WHERE game_id = ? ORDER BY round_number', (game_id,))
    rounds = cur.fetchall()
    conn.close()
    return rounds

def get_all_players_for_game(game_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT p.*, gp.eliminated FROM players p
        JOIN game_players gp ON p.id = gp.player_id
        WHERE gp.game_id = ?
        ORDER BY p.name
    ''', (game_id,))
    players = cur.fetchall()
    conn.close()
    return players

def get_game_winner(game_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT p.* FROM players p
        JOIN game_players gp ON p.id = gp.player_id
        WHERE gp.game_id = ? AND gp.eliminated = 0
    ''', (game_id,))
    remaining = cur.fetchall()
    if len(remaining) == 1:
        return remaining[0]
    return None

def is_game_over(game_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) as cnt FROM game_players WHERE game_id = ? AND eliminated = 0', (game_id,))
    row = cur.fetchone()
    conn.close()
    return row['cnt'] <= 1
