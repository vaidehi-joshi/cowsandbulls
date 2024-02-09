from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import jwt
import datetime
from functools import wraps

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



if __name__ == '__main__':
    app.run(debug=True, port=8080)
