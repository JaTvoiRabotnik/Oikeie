import os
from flask import Flask, render_template, request, jsonify, url_for, redirect, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
from postmarker.core import PostmarkClient
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY") or "a secret key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    verified = db.Column(db.Boolean, default=False)
    token = db.Column(db.String(255))
    token_expiry = db.Column(db.DateTime)

    def __repr__(self):
        return f'<Member {self.email}>'

with app.app_context():
    db.create_all()

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
                return redirect(url_for('chat'))
            else:
                return "Verification link has expired. Please try logging in again to receive a new verification email."
        return "Invalid verification link"
    except:
        return "Invalid verification link"

@app.route('/chat')
def chat():
    email = session.get('email')
    member = Member.query.filter_by(email=email).first()
    if not member or not member.verified:
        return redirect(url_for('index'))
    return render_template('chat.html', email=email)

@socketio.on('join')
def on_join(data):
    email = session.get('email')
    room = data['room']
    member = Member.query.filter_by(email=email).first()
    if member and member.verified:
        join_room(room)
        emit('status', {'msg': f'{email} has entered the room.'}, to=room)
    else:
        emit('status', {'msg': 'You are not verified. Please verify your email to join the chat.'})

@socketio.on('leave')
def on_leave(data):
    email = session.get('email')
    room = data['room']
    leave_room(room)
    emit('status', {'msg': f'{email} has left the room.'}, to=room)

@socketio.on('chat_message')
def handle_message(data):
    email = session.get('email')
    member = Member.query.filter_by(email=email).first()
    if member and member.verified:
        emit('message', {'email': email, 'message': data['message']}, to=data['room'])
    else:
        emit('status', {'msg': 'You are not verified. Please verify your email to send messages.'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
