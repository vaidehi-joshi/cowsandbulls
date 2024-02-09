from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import jwt
import datetime
from functools import wraps
import random

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://vaidehi@localhost/cowsandbulls'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(128))  # Storing password in plaintext
    role = db.Column(db.String(50), default='user')

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_type = db.Column(db.String(20))  # multiplayer, single, vs_computer
    status = db.Column(db.String(20))  # started, finished
    guesses = db.relationship('Guess', backref='game', lazy=True)

class Guess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    guess = db.Column(db.String(4))  # The guessed number
    cows = db.Column(db.Integer)  # Number of cows
    bulls = db.Column(db.Integer)  # Number of bulls

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.replace('Bearer ', '', 1)
        if not token:
            return jsonify({'message': 'Token is missing or invalid!'}), 403
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(username=data['user']).first()
        except:
            return jsonify({'message': 'Token is invalid!'}), 403
        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/login', methods=['POST'])
def login():
    auth = request.json
    if not auth or not auth.get('username') or not auth.get('password'):
        return jsonify({'message': 'Could not verify'}), 401

    user = User.query.filter_by(username=auth.get('username')).first()
    if not user or user.password != auth.get('password'):
        return jsonify({'message': 'Invalid credentials'}), 401

    token = jwt.encode({'user': user.username, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)}, app.config['SECRET_KEY'])
    return jsonify({'token': token})

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'User already exists'}), 400
    
    new_user = User(username=username, password=password)  # Directly storing plaintext password
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/hello')
@token_required
def hello(current_user):
    return jsonify({'message': 'Hello, world!'})

@app.route('/dashboard')
@token_required
def dashboard(current_user):
    if current_user.role == 'admin':
        return jsonify({'message': 'Welcome to the admin dashboard!'})
    else:
        return jsonify({'message': 'Unauthorized'}), 401

@app.route('/user/delete/<username>', methods=['DELETE'])
@token_required
def delete_user(current_user, username):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized. Admin access required.'}), 401
    
    user_to_delete = User.query.filter_by(username=username).first()
    if not user_to_delete:
        return jsonify({'message': 'User not found'}), 404
    
    db.session.delete(user_to_delete)
    db.session.commit()
    
    return jsonify({'message': 'User deleted successfully'}), 200

@app.route('/users', methods=['GET'])
@token_required
def list_users(current_user):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized. Admin access required.'}), 401

    users = User.query.all()
    users_list = []
    for user in users:
        user_data = {'username': user.username, 'role': user.role}
        users_list.append(user_data)

    return jsonify({'users': users_list}), 200

@app.route('/game/start', methods=['POST'])
@token_required
def start_game(current_user):
    data = request.json
    game_type = data.get('game_type')  # multiplayer, single, vs_computer
    role = data.get('role')  # guesser or mastermind
    if game_type != 'vs_computer' or role not in ['guesser', 'mastermind']:
        return jsonify({'message': 'Invalid game type or role'}), 400
    
    new_game = Game(user_id=current_user.id, game_type=game_type, status='started', role=role)
    db.session.add(new_game)
    db.session.commit()

    return jsonify({'message': 'Game started successfully', 'game_id': new_game.id}), 201

@app.route('/game/stop/<int:game_id>', methods=['PUT'])
@token_required
def stop_game(current_user, game_id):
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'message': 'Game not found'}), 404
    
    if game.user_id != current_user.id:
        return jsonify({'message': 'Unauthorized. This is not your game'}), 401
    
    game.status = 'finished'
    db.session.commit()
    
    return jsonify({'message': 'Game stopped successfully'}), 200

@app.route('/game/guess/<int:game_id>', methods=['POST'])
@token_required
def make_guess(current_user, game_id):
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'message': 'Game not found'}), 404
    
    if game.status != 'started':
        return jsonify({'message': 'Game is not active'}), 400
    
    if game.game_type == 'multiplayer' and game.user_id != current_user.id:
        return jsonify({'message': 'Unauthorized. This is not your game'}), 401
    
    data = request.json
    guess = data.get('guess')
    if not guess or len(guess) != 4 or not guess.isdigit():
        return jsonify({'message': 'Invalid guess. It should be a 4-digit number'}), 400
    
    # Let's assume cows and bulls are calculated here, replace it with actual logic
    cows, bulls = calculate_cows_bulls(guess)  # Implement this function
    
    new_guess = Guess(game_id=game.id, guess=guess, cows=cows, bulls=bulls)
    db.session.add(new_guess)
    db.session.commit()
    
    return jsonify({'message': 'Guess made successfully'}), 201

# Function to calculate cows and bulls, replace it with actual logic
def calculate_cows_bulls(guess):
    secret_number = "1234"  # Replace with the actual secret number
    cows = 0
    bulls = 0
    for i in range(len(secret_number)):
        if guess[i] == secret_number[i]:
            bulls += 1
        elif guess[i] in secret_number:
            cows += 1
    return cows, bulls



if __name__ == '__main__':
    app.run(debug=True, port=8080)
