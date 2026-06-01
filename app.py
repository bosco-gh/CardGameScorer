from flask import Flask, render_template, request, redirect, url_for, flash
from model.db import init_db
from model import game_model

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # For flash messages

# Initialize DB and score types on startup
init_db()
game_model.init_score_types()

@app.route('/')
def index():
    games = game_model.get_games()
    # Annotate each game with status and winner
    games_with_status = []
    for g in games:
        is_over = game_model.is_game_over(g['id'])
        winner = game_model.get_game_winner(g['id']) if is_over else None
        games_with_status.append({
            **g,
            'status': 'Finished' if is_over else 'Open',
            'winner': winner['name'] if winner else '-' if is_over else '-',
            'is_over': is_over
        })
    return render_template('index.html', games=games_with_status)

@app.route('/players/add', methods=['GET', 'POST'])
def add_player():
    if request.method == 'POST':
        name = request.form.get('name')
        try:
            game_model.add_player(name)
            flash('Player added!', 'success')
            return redirect(url_for('add_player'))
        except game_model.PlayerExistsError:
            flash('Player already exists.', 'danger')
        except Exception as e:
            flash(str(e), 'danger')
    return render_template('add_player.html')

@app.route('/game_types/add', methods=['GET', 'POST'])
def add_game_type():
    if request.method == 'POST':
        name = request.form.get('name')
        try:
            game_model.add_game_type(name)
            flash('Game type added!', 'success')
            return redirect(url_for('add_game_type'))
        except game_model.GameTypeExistsError:
            flash('Game type already exists.', 'danger')
        except Exception as e:
            flash(str(e), 'danger')
    return render_template('add_game_type.html')

@app.route('/games/add', methods=['GET', 'POST'])
def add_game():
    game_types = game_model.get_game_types()
    if request.method == 'POST':
        game_type_id = request.form.get('game_type_id')
        name = request.form.get('name')
        total_score = request.form.get('total_score')
        try:
            total_score = int(total_score) if total_score else None
            game_model.add_game(game_type_id, name, total_score)
            flash('Game added!', 'success')
            return redirect(url_for('add_game'))
        except Exception as e:
            flash(str(e), 'danger')
    return render_template('add_game.html', game_types=game_types)

@app.route('/games/<game_id>/scores')
def game_scores(game_id):
    game = None
    for g in game_model.get_games():
        if g['id'] == game_id:
            game = g
            break
    if not game:
        flash('Game not found.', 'danger')
        return redirect(url_for('index'))
    rounds = game_model.get_rounds_for_game(game_id)
    round_scores = []
    for rnd in rounds:
        scores = game_model.get_scores_for_round(rnd['id'])
        round_scores.append({'round': rnd, 'scores': scores})
    players = game_model.get_all_players_for_game(game_id)
    game_over = game_model.is_game_over(game_id)
    winner = game_model.get_game_winner(game_id) if game_over else None
    return render_template('game_scores.html', game=game, players=players, round_scores=round_scores, game_over=game_over, winner=winner)

@app.route('/rounds/add', methods=['GET', 'POST'])
def add_round():
    games = game_model.get_games()
    game_id = request.args.get('game_id')
    # Calculate next round number
    round_number = None
    if game_id:
        rounds = game_model.get_rounds_for_game(game_id)
        round_number = len(rounds) + 1
    players = game_model.get_non_eliminated_players_for_game(game_id) if game_id else []
    score_types = game_model.get_score_types()
    declared_type = game_model.get_score_type_by_name('Declared')
    custom_type = game_model.get_score_type_by_name('Custom')
    if request.method == 'POST':
        game_id = request.form.get('game_id')
        round_number = request.form.get('round_number')
        joker = request.form.get('joker')
        winner_player_id = request.form.get('winner_player_id')
        duration_minutes = request.form.get('duration_minutes')
        duration_seconds = request.form.get('duration_seconds')
        total_seconds = 0
        try:
            total_seconds = int(duration_minutes or 0) * 60 + int(duration_seconds or 0)
        except Exception:
            total_seconds = None
        players = game_model.get_non_eliminated_players_for_game(game_id)
        # Prevent duplicate round number
        existing_rounds = game_model.get_rounds_for_game(game_id)
        if any(int(r['round_number']) == int(round_number) for r in existing_rounds):
            flash('This round number already exists for this game.', 'danger')
            return render_template('add_round.html', games=games, players=players, score_types=score_types, game_id=game_id, round_number=round_number, winner_player_id=winner_player_id)
        scores_dict = {}
        missing_score = False
        for player in players:
            if winner_player_id and player['id'] == winner_player_id:
                scores_dict[player["id"]] = (declared_type['id'], 0)
                continue
            score_type_id = request.form.get(f'score_type_{player["id"]}')
            score_val = request.form.get(f'score_{player["id"]}')
            if not score_type_id or score_val is None or score_val == '':
                missing_score = True
                flash(f"Score and score type are required for {player['name']}", 'danger')
            else:
                try:
                    scores_dict[player["id"]] = (score_type_id, int(score_val))
                except ValueError:
                    flash(f"Score for {player['name']} must be a number.", 'danger')
                    return render_template('add_round.html', games=games, players=players, score_types=score_types, game_id=game_id, round_number=round_number, winner_player_id=winner_player_id)
        if missing_score:
            return render_template('add_round.html', games=games, players=players, score_types=score_types, game_id=game_id, round_number=round_number, winner_player_id=winner_player_id)
        try:
            round_id = game_model.add_round(game_id, int(round_number), joker, winner_player_id, total_seconds)
            game_model.add_scores_for_round(round_id, scores_dict)
            game_model.eliminate_players_if_needed(game_id)
            if game_model.is_game_over(game_id):
                game_model.set_game_total_duration(game_id)
            flash('Round and scores added!', 'success')
            return redirect(url_for('game_scores', game_id=game_id))
        except Exception as e:
            flash(str(e), 'danger')
    return render_template('add_round.html', games=games, players=players, score_types=score_types, game_id=game_id, round_number=round_number)

@app.route('/leaderboard')
def leaderboard():
    game_types = game_model.get_game_types()
    game_type_id = request.args.get('game_type_id', type=int)
    leaderboard = game_model.get_leaderboard(game_type_id)
    return render_template('leaderboard.html', leaderboard=leaderboard, game_types=game_types, selected_game_type=game_type_id)

@app.route('/winner')
def winner():
    winner = game_model.get_winner()
    return render_template('leaderboard.html', leaderboard=[winner] if winner else [], winner=True)

@app.route('/games/start', methods=['GET', 'POST'])
def start_game():
    game_types = game_model.get_game_types()
    all_games = game_model.get_games()
    players = game_model.get_players()
    selected_game_type_id = request.form.get('game_type_id') if request.method == 'POST' else request.args.get('game_type_id')
    selected_game_pattern_id = request.form.get('game_pattern_id') if request.method == 'POST' else None
    # Filter games by selected type for pattern selection
    game_patterns = [g for g in all_games if selected_game_type_id and str(g['game_type_id']) == str(selected_game_type_id)]
    if request.method == 'POST' and 'start_game' in request.form:
        game_type_id = request.form.get('game_type_id')
        game_pattern_id = request.form.get('game_pattern_id')
        instance_name = request.form.get('instance_name')
        total_score = request.form.get('total_score')
        selected_players = request.form.getlist('player_ids')
        if not game_type_id or not game_pattern_id or not selected_players:
            flash('Please select a game type, game pattern, and at least one player.', 'danger')
            return render_template('start_game.html', game_types=game_types, game_patterns=game_patterns, players=players, selected_game_type_id=selected_game_type_id, selected_game_pattern_id=selected_game_pattern_id)
        # Get pattern details
        pattern_game = next((g for g in all_games if g['id'] == game_pattern_id), None)
        if not pattern_game:
            flash('Invalid game pattern selected.', 'danger')
            return render_template('start_game.html', game_types=game_types, game_patterns=game_patterns, players=players, selected_game_type_id=selected_game_type_id, selected_game_pattern_id=selected_game_pattern_id)
        try:
            # Create a new game instance based on the pattern
            game_name = instance_name or f"{pattern_game['name']} Instance"
            total_score = int(total_score) if total_score else pattern_game['total_score']
            new_game_id = game_model.add_game(game_type_id, game_name, total_score)
            game_model.add_players_to_game(new_game_id, selected_players)
            flash('New game instance started!', 'success')
            return redirect(url_for('game_scores', game_id=new_game_id))
        except Exception as e:
            flash(str(e), 'danger')
    return render_template('start_game.html', game_types=game_types, game_patterns=game_patterns, players=players, selected_game_type_id=selected_game_type_id, selected_game_pattern_id=selected_game_pattern_id)

@app.route('/games/open')
def open_games():
    all_games = game_model.get_games()
    open_games = [g for g in all_games if not game_model.is_game_over(g['id'])]
    return render_template('open_games.html', games=open_games)

@app.route('/game_types')
def view_game_types():
    game_types = game_model.get_game_types()
    games = game_model.get_games()
    # Group games by game_type_id
    games_by_type = {}
    for gt in game_types:
        games_by_type[gt['id']] = [g for g in games if g['game_type_id'] == gt['id']]
    return render_template('game_types.html', game_types=game_types, games_by_type=games_by_type)

def get_score_for_player(scores, player_id):
    for s in scores:
        if str(s['player_id']) == str(player_id):
            return s['score']
    return '-'

app.jinja_env.filters['get_score_for_player'] = get_score_for_player

def total_score_for_player(round_scores, player_id):
    total = 0
    for entry in round_scores:
        for s in entry['scores']:
            if str(s['player_id']) == str(player_id):
                total += s['score']
    return total

app.jinja_env.filters['total_score_for_player'] = total_score_for_player

if __name__ == '__main__':
    app.run(debug=True)
