from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import jwt
import datetime
from functools import wraps
from enums import RolesEnum,GameStatusEnum,GameTypeEnum
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import attributes


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Timestamp of creation

    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(128))  # Storing password in plaintext
    role = db.Column(db.String(50), default='user')
    
    def serialize(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role
            # Add other user attributes as needed
        }

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Timestamp of creation

    game_type = db.Column(db.String(20))  # multiplayer, single, vs_computer
    status = db.Column(db.String(20))  # started, finished, waiting
    turn = db.Column(db.String(20), default=RolesEnum.MASTERMIND.value) #turn flag
    guesser_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # ID of the guesser
    mastermind_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # ID of the mastermind
    guesses = db.relationship('Guess', backref='game', lazy=True)
    code = db.Column(db.String(4))  # Assuming the code is a 4-digit string
    guesser = db.relationship('User', foreign_keys=[guesser_id], lazy='joined', uselist=False)
    mastermind = db.relationship('User', foreign_keys=[mastermind_id], lazy='joined', uselist=False)


class Guess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Timestamp of creation

    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    guess = db.Column(db.String(4))  # The guessed number
    cows = db.Column(db.Integer)  # Number of cows
    bulls = db.Column(db.Integer)  # Number of bulls
    
    def serialize(self):
        return {
            'id': self.id,
            'game_id': self.game_id,
            'guess': self.guess,
            'cows': self.cows,
            'bulls': self.bulls
        }



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

    token = jwt.encode({'user': user.username, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=500)}, app.config['SECRET_KEY'])
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
    if game_type not in [game_type.value for game_type in GameTypeEnum]:
        return jsonify({'message': 'Invalid game type'}), 400
     
    role = data.get('role')  # guesser or mastermind
    if role == RolesEnum.GUESSER.value:
        new_game = Game(guesser_id=current_user.id, game_type=game_type, status=GameStatusEnum.WAITING.value)
    elif role == RolesEnum.MASTERMIND.value:
        new_game = Game(mastermind_id=current_user.id, game_type=game_type, status=GameStatusEnum.WAITING.value)
    else:
        return jsonify({'message': 'Invalid role'}), 400
    
    
    db.session.add(new_game)
    db.session.commit()

    return jsonify({'message': 'Game started successfully', 'game_id': new_game.id}), 201


@app.route('/game/stop/<int:game_id>', methods=['PUT'])
@token_required
def stop_game(current_user, game_id):
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'message': 'Game not found'}), 404
    
    if current_user.id not in [game.guesser_id, game.mastermind_id]:
        return jsonify({'message': 'Unauthorized. This is not your game'}), 401
    
    game.status = GameStatusEnum.FINISHED.value
    db.session.commit()
    
    return jsonify({'message': 'Game stopped successfully'}), 200

@app.route('/game/<int:game_id>', methods=['GET'])
@token_required
def get_game(game_id):
    game = Game.query.options(joinedload(Game.guesser), joinedload(Game.mastermind)).get(game_id)
    return jsonify(get_game_data(game)), 200

def get_game_data(game):
    
    guesses_list = [guess.serialize() for guess in game.guesses]

    game_data = {
        'id': game.id,
        'game_type': game.game_type,
        'status': game.status,
        'guesser': game.guesser.serialize() if game.guesser else None,
        'mastermind': game.mastermind.serialize() if game.mastermind else None,
        'guesses': guesses_list
    }
    return game_data



@app.route('/game/guess/<int:game_id>', methods=['POST'])
@token_required
def make_guess(current_user, game_id):
    game = Game.query.options(joinedload(Game.guesser), joinedload(Game.mastermind)).get(game_id)


    # game = Game.query.options(joinedload(Game.guesser), joinedload(Game.mastermind)).get(game_id)
    # print(get_game_data(game),"guesser:",Game.guesser)
    if not game:
        return jsonify({'message': 'Game not found'}), 404
    
    if game.status != GameStatusEnum.STARTED.value:
        return jsonify({'message': 'Game is not active'}), 400
    
    if game.game_type == 'multiplayer' and game.user_id != current_user.id:
        return jsonify({'message': 'Unauthorized. This is not your game'}), 401
    
    data = request.json
    guess = data.get('guess')
    if not guess or len(guess) != 4 or not guess.isdigit():
        return jsonify({'message': 'Invalid guess. It should be a 4-digit number'}), 400
    
    cows, bulls = calculate_cows_bulls(guess, game.code)  
    
    new_guess = Guess(game_id=game.id, guess=guess, cows=cows, bulls=bulls)
    db.session.add(new_guess)

    if bulls == 4:
        game.status = GameStatusEnum.FINISHED.value
        db.session.commit()
        return jsonify({'message': 'Guessed code successfully', 'game': get_game_data(game)}), 201    
    
    db.session.commit()

    return jsonify({'message': 'Guess registered', 'game': get_game_data(game)}), 201

# Function to calculate cows and bulls, replace it with actual logic
def calculate_cows_bulls(guess, code):
    cows = 0
    bulls = 0
    for i in range(len(code)):
        if guess[i] == code[i]:
            bulls += 1
        elif guess[i] in code:
            cows += 1
    return cows, bulls

# Define an API endpoint for the mastermind to set the code
@app.route('/game/set-code/<int:game_id>', methods=['PUT'])
@token_required
def set_code(current_user, game_id):
    data = request.json
    code = data.get('code')

    game = Game.query.get(game_id)
    if not game:
        return jsonify({'message': 'Game not found'}), 404

    if game.mastermind_id != current_user.id:
        return jsonify({'message': 'Unauthorized'}), 403

    # Validate the code (e.g., check if it's a valid 4-digit string)
    if len(code) != 4 or not code.isdigit():
        return jsonify({'message': 'Invalid code. Please provide a 4-digit number'}), 400

    # Set the code
    game.code = code
    game.turn = RolesEnum.GUESSER.value
    db.session.commit()

    return jsonify({'message': 'Code set successfully'}), 200

# Define the join game endpoint
@app.route('/game/join/<int:game_id>', methods=['PUT'])
@token_required
def join_game(current_user, game_id):
    data = request.json
    role = data.get('role')

    if role not in [RolesEnum.GUESSER.value, RolesEnum.MASTERMIND.value]:
        return jsonify({'message': 'Invalid role'}), 400

    game = Game.query.get(game_id)

    if not game:
        return jsonify({'message': 'Game not found'}), 404
    if game.status == GameStatusEnum.FINISHED.value:
        return jsonify({'message': 'Game has finished'}), 400

    # Assign user ID based on the chosen role
    if role == RolesEnum.GUESSER.value:
        game.guesser_id = current_user.id
    else:
        game.mastermind_id = current_user.id

    game.status = GameStatusEnum.STARTED.value
    db.session.commit()

    return jsonify({'message': f'User joined game as {role} successfully'}), 200

if __name__ == '__main__':
    app.run(debug=True, port=8080)
