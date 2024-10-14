import os
from flask import Flask, render_template, request, jsonify, url_for, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
from postmarker.core import PostmarkClient

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY") or "a secret key"

socketio = SocketIO(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# In-memory storage for users (replace with a database in production)
users = {}

def generate_verification_token(email):
    return serializer.dumps(email, salt='email-verify')

def send_verification_email(email, token):
    postmark = PostmarkClient(server_token=os.environ.get('POSTMARK_API_TOKEN'))
    verify_url = url_for('verify_email', token=token, _external=True)
    postmark.emails.send(
        From=os.environ.get('MAIL_DEFAULT_SENDER'),
        To=email,
        Subject='Verify your email',
        TextBody=f'Click the following link to verify your email: {verify_url}'
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    email = request.form.get('email')
    
    if username in users:
        return jsonify({'success': False, 'message': 'Username already exists'})
    
    token = generate_verification_token(email)
    users[username] = {
        'email': email,
        'verified': False,
        'token': token,
        'token_expiry': datetime.utcnow() + timedelta(hours=24)
    }
    
    send_verification_email(email, token)
    
    return jsonify({'success': True, 'message': 'Registration successful. Please check your email to verify your account.'})

@app.route('/verify/<token>')
def verify_email(token):
    try:
        email = serializer.loads(token, salt='email-verify', max_age=86400)  # 24 hours
        for username, user in users.items():
            if user['email'] == email and user['token'] == token:
                if datetime.utcnow() <= user['token_expiry']:
                    user['verified'] = True
                    return redirect(url_for('chat', username=username))
                else:
                    return "Verification link has expired. Please register again."
        return "Invalid verification link"
    except:
        return "Invalid verification link"

@app.route('/chat')
def chat():
    username = request.args.get('username')
    if username not in users or not users[username]['verified']:
        return redirect(url_for('index'))
    return render_template('chat.html', username=username)

@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    if username in users and users[username]['verified']:
        join_room(room)
        emit('status', {'msg': username + ' has entered the room.'}, to=room)
    else:
        emit('status', {'msg': 'You are not verified. Please verify your email to join the chat.'}, to=request.sid)

@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    emit('status', {'msg': username + ' has left the room.'}, to=room)

@socketio.on('message')
def handle_message(data):
    if data['username'] in users and users[data['username']]['verified']:
        emit('message', data, to=data['room'])
    else:
        emit('status', {'msg': 'You are not verified. Please verify your email to send messages.'}, to=request.sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
