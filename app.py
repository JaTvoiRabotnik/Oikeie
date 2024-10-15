import os
from flask import Flask, render_template, request, jsonify, url_for, redirect, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
from postmarker.core import PostmarkClient
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY") or "a secret key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    verified = db.Column(db.Boolean, default=False)
    token = db.Column(db.String(255))
    token_expiry = db.Column(db.DateTime)
    handle = db.Column(db.String(50), unique=True)

    __table_args__ = (
        db.UniqueConstraint('handle', name='uq_member_handle'),
    )

    def __repr__(self):
        return f'<Member {self.email}>'

def generate_verification_token(email):
    return serializer.dumps(email, salt='email-verify')

def send_verification_email(email, token):
    postmark = PostmarkClient(server_token=os.environ.get('POSTMARK_API_TOKEN'))
    verify_url = url_for('verify_email', token=token, _external=True)
    postmark.emails.send(
        From=os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@yourdomain.com'),
        To=email,
        Subject='Verify your email',
        TextBody=f'Click the following link to verify your email: {verify_url}'
    )

@app.route('/')
def index():
    if 'email' in session:
        member = Member.query.filter_by(email=session['email']).first()
        if member and member.verified:
            return redirect(url_for('chat'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    
    member = Member.query.filter_by(email=email).first()
    if not member:
        # New user, create an account
        token = generate_verification_token(email)
        new_member = Member(email=email, token=token, token_expiry=datetime.utcnow() + timedelta(hours=24))
        db.session.add(new_member)
        db.session.commit()
        try:
            send_verification_email(email, token)
            return jsonify({'success': True, 'message': 'Registration successful. Please check your email to verify your account.'})
        except Exception as e:
            print(f"Error sending verification email: {str(e)}")
            return jsonify({'success': False, 'message': 'An error occurred while sending the verification email. Please try again later.'})
    
    if not member.verified:
        return jsonify({'success': False, 'message': 'Please verify your email before logging in.'})
    
    session['email'] = email
    return jsonify({'success': True, 'message': 'Login successful', 'redirect': url_for('chat')})

@app.route('/verify/<token>')
def verify_email(token):
    try:
        email = serializer.loads(token, salt='email-verify', max_age=86400)  # 24 hours
        member = Member.query.filter_by(email=email).first()
        if member and member.token == token:
            if datetime.utcnow() <= member.token_expiry:
                member.verified = True
                db.session.commit()
                session['email'] = email
                return redirect(url_for('set_handle'))
            else:
                return "Verification link has expired. Please try logging in again to receive a new verification email."
        return "Invalid verification link"
    except:
        return "Invalid verification link"

@app.route('/set_handle', methods=['GET', 'POST'])
def set_handle():
    if 'email' not in session:
        return redirect(url_for('index'))
    
    email = session['email']
    member = Member.query.filter_by(email=email).first()
    if not member or not member.verified:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        handle = request.form.get('handle')
        if handle:
            existing_member = Member.query.filter_by(handle=handle).first()
            if existing_member:
                return render_template('set_handle.html', error="This handle is already taken. Please choose another.")
            member.handle = handle
            db.session.commit()
            return redirect(url_for('chat'))
    
    return render_template('set_handle.html')

@app.route('/chat')
def chat():
    if 'email' not in session:
        return redirect(url_for('index'))
    
    email = session['email']
    member = Member.query.filter_by(email=email).first()
    if not member or not member.verified:
        return redirect(url_for('index'))
    if not member.handle:
        return redirect(url_for('set_handle'))
    return render_template('chat.html', email=email, handle=member.handle)

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('index'))

@socketio.on('join')
def on_join(data):
    email = session.get('email')
    room = data['room']
    member = Member.query.filter_by(email=email).first()
    if member and member.verified and member.handle:
        join_room(room)
        emit('status', {'msg': f'{member.handle} has entered the room.'}, to=room)
    else:
        emit('status', {'msg': 'You are not verified or haven\'t set a handle. Please verify your email and set a handle to join the chat.'})

@socketio.on('leave')
def on_leave(data):
    email = session.get('email')
    room = data['room']
    member = Member.query.filter_by(email=email).first()
    leave_room(room)
    emit('status', {'msg': f'{member.handle} has left the room.'}, to=room)

@socketio.on('chat_message')
def handle_message(data):
    email = session.get('email')
    member = Member.query.filter_by(email=email).first()
    if member and member.verified and member.handle:
        emit('message', {'handle': member.handle, 'message': data['message']}, to=data['room'])
    else:
        emit('status', {'msg': 'You are not verified or haven\'t set a handle. Please verify your email and set a handle to send messages.'})

@app.route('/check_db_structure')
def check_db_structure():
    conn = sqlite3.connect('instance/chat_app.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='member'")
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return f"Structure of 'member' table:<br><pre>{result[0]}</pre>"
    else:
        return "Table 'member' not found in the database."

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
