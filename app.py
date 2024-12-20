from flask import Flask, jsonify, request, session, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Gerakl2288@localhost/messenger_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['PROFILE_PIC_FOLDER'] = 'static/profile_pics'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

# Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    phone_number = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(100), nullable=True)
    profile_pic = db.Column(db.String(100), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)

    def __init__(self, username, password, is_admin=False):
        self.username = username
        self.password_hash = generate_password_hash(password)
        self.is_admin = is_admin

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    attachment = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        return render_template('index.html', user=user)
    return redirect(url_for('welcome'))

@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'User already exists'}), 400

        new_user = User(username, password)
        db.session.add(new_user)
        db.session.commit()

        return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('welcome.html')

    if request.method == 'POST':
        if request.headers.get('Content-Type') != 'application/json':
            return jsonify({'error': 'Unsupported Media Type'}), 415

        data = request.json
        username = data.get('username')
        password = data.get('password')

        user = User.query.filter_by(username=username).first()
        if not user or not user.verify_password(password):
            return jsonify({'error': 'Invalid credentials'}), 401

        session['user_id'] = user.id
        session['is_admin'] = user.is_admin
        return jsonify({'message': 'Login successful'}), 200

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('welcome'))

@app.route('/users', methods=['GET'])
def list_users():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    users = User.query.filter(User.id != session['user_id']).all()
    print(f"Loaded users: {users}")  # Логирование
    return jsonify([{'id': u.id, 'username': u.username, 'profile_pic': u.profile_pic} for u in users])

@app.route('/messages', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.form
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    file = request.files.get('attachment')

    receiver = User.query.get(receiver_id)
    if not receiver:
        return jsonify({'error': 'Receiver does not exist'}), 400

    new_message = Message(sender_id=session['user_id'], receiver_id=receiver_id, content=content)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        new_message.attachment = filename

    db.session.add(new_message)
    db.session.commit()

    return jsonify({'message': 'Message sent successfully', 'message_id': new_message.id}), 201

@app.route('/messages/<int:receiver_id>', methods=['GET'])
def get_chat_messages(receiver_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    messages = Message.query.filter(
        ((Message.sender_id == session['user_id']) & (Message.receiver_id == receiver_id)) |
        ((Message.sender_id == receiver_id) & (Message.receiver_id == session['user_id']))
    ).order_by(Message.timestamp).all()

    formatted_messages = [
        {
            'id': m.id,
            'sender': 'You' if m.sender_id == session['user_id'] else m.sender.username,
            'content': m.content,
            'attachment': m.attachment,
            'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }
        for m in messages
    ]

    return jsonify(formatted_messages), 200

@app.route('/messages/<int:message_id>', methods=['DELETE'])
def delete_message(message_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    message = Message.query.get(message_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404

    if message.sender_id != session['user_id'] and not session.get('is_admin'):
        return jsonify({'error': 'Permission denied'}), 403

    db.session.delete(message)
    db.session.commit()

    return jsonify({'message': 'Message deleted successfully'}), 200

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        username = request.form.get('username')
        phone_number = request.form.get('phone_number')
        status = request.form.get('status')
        file = request.files.get('profile_pic')

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['PROFILE_PIC_FOLDER'], filename)
            file.save(file_path)
            user.profile_pic = filename

        user.username = username
        user.phone_number = phone_number
        user.status = status
        db.session.commit()

        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)

@app.route('/admin/users', methods=['GET'])
def admin_list_users():
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    users = User.query.all()
    return render_template('admin.html', users=users)

@app.route('/admin/users/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Удаляем все сообщения, связанные с этим пользователем
    messages_sent = Message.query.filter_by(sender_id=user_id).all()
    messages_received = Message.query.filter_by(receiver_id=user_id).all()

    for message in messages_sent + messages_received:
        db.session.delete(message)

    # Удаляем пользователя
    db.session.delete(user)
    db.session.commit()

    return jsonify({'message': 'User and associated messages deleted successfully'}), 200

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
def admin_edit_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if request.method == 'POST':
        username = request.form.get('username')
        phone_number = request.form.get('phone_number')
        status = request.form.get('status')
        file = request.files.get('profile_pic')

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['PROFILE_PIC_FOLDER'], filename)
            file.save(file_path)
            user.profile_pic = filename

        user.username = username
        user.phone_number = phone_number
        user.status = status
        db.session.commit()

        flash('User profile updated successfully', 'success')
        return redirect(url_for('admin_list_users'))

    return render_template('edit_user.html', user=user)

@app.route('/user/<int:user_id>', methods=['GET'])
def user_profile(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return render_template('user_profile.html', user=user)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)