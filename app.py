import eventlet
eventlet.monkey_patch()

import os
import logging
from flask import Flask, render_template, request, jsonify, url_for, redirect, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from datetime import datetime, timedelta, timezone
from postmarker.core import PostmarkClient
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.exceptions import NotFound, InternalServerError, Unauthorized
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash, check_password_hash
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# Temporarily disable Talisman
# Talisman(app, content_security_policy={...}, force_https=False)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

logging.basicConfig(level=logging.DEBUG)
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

with app.app_context():
    class Member(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(120), unique=True, nullable=False)
        verified = db.Column(db.Boolean, default=False)
        token = db.Column(db.String(255))
        token_expiry = db.Column(db.DateTime(timezone=True))
        handle = db.Column(db.String(50), unique=True)

        __table_args__ = (
            db.UniqueConstraint('handle', name='uq_member_handle'),
        )

        def __init__(self, email, verified=False, token=None, token_expiry=None, handle=None):
            self.email = email
            self.verified = verified
            self.token = token
            self.token_expiry = token_expiry
            self.handle = handle

        def __repr__(self):
            return f'<Member {self.email}>'

def generate_magic_link_token():
    return secrets.token_urlsafe(32)

def send_magic_link_email(email, token):
    try:
        postmark = PostmarkClient(server_token=os.environ.get('POSTMARK_API_TOKEN'))
        verify_url = url_for('verify_magic_link', token=token, _external=True, _scheme='https')
        postmark.emails.send(
            From=os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@yourdomain.com'),
            To=email,
            Subject='Your Magic Link',
            TextBody=f'Click the following link to log in: {verify_url}'
        )
        app.logger.info(f"Magic link email sent to {email}")
    except Exception as e:
        app.logger.error(f"Error sending magic link email: {str(e)}")
        raise

@app.route('/')
def index():
    app.logger.debug(f"Accessing index route. Session: {session}")
    if 'email' in session:
        app.logger.debug(f"User is logged in. Redirecting to chat.")
        return redirect(url_for('chat'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    email = request.form.get('email')
    app.logger.debug(f"Login attempt for email: {email}")
    
    try:
        member = Member.query.filter_by(email=email).first()
        if not member:
            app.logger.info(f"Creating new member for email: {email}")
            member = Member(email=email)
            db.session.add(member)
        
        token = generate_magic_link_token()
        member.token = token
        member.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        db.session.commit()
        
        send_magic_link_email(email, token)
        app.logger.debug(f"Magic link sent to: {email}")
        return jsonify({'success': True, 'message': 'A magic link has been sent to your email. Please check your inbox.'})
    except Exception as e:
        app.logger.error(f"Error in login process: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred while processing your request. Please try again later.'})

@app.route('/verify_magic_link/<token>')
@limiter.limit("5 per minute")
def verify_magic_link(token):
    app.logger.debug(f"Verifying magic link with token: {token}")
    try:
        member = Member.query.filter_by(token=token).first()
        if member:
            current_time = datetime.now(timezone.utc)
            app.logger.debug(f"Current time: {current_time}, Token expiry: {member.token_expiry}")
            if member.token_expiry and current_time <= member.token_expiry.replace(tzinfo=timezone.utc):
                member.verified = True
                member.token = None
                member.token_expiry = None
                db.session.commit()
                session.clear()
                session['email'] = member.email
                session.permanent = True
                app.logger.info(f"User {member.email} verified successfully")
                if member.handle:
                    app.logger.debug(f"Redirecting to chat for user: {member.email}")
                    return redirect(url_for('chat'))
                else:
                    app.logger.debug(f"Redirecting to set_handle for user: {member.email}")
                    return redirect(url_for('set_handle'))
            else:
                app.logger.warning(f"Expired magic link used for {member.email}")
                return render_template('error.html', message="Magic link has expired. Please try logging in again to receive a new magic link.")
        app.logger.warning(f"Invalid magic link used")
        return render_template('error.html', message="Invalid magic link")
    except Exception as e:
        app.logger.error(f"Error in verify_magic_link: {str(e)}")
        return render_template('error.html', message="An error occurred while processing your request")

@app.route('/set_handle', methods=['GET', 'POST'])
def set_handle():
    app.logger.debug(f"Accessing set_handle route. Session: {session}")
    if 'email' not in session:
        app.logger.debug("No email in session, redirecting to index")
        return redirect(url_for('index'))
    
    email = session['email']
    member = Member.query.filter_by(email=email).first()
    if not member or not member.verified:
        app.logger.debug(f"Member not found or not verified: {email}")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        handle = request.form.get('handle')
        if handle:
            try:
                existing_member = Member.query.filter_by(handle=handle).first()
                if existing_member:
                    app.logger.debug(f"Handle already taken: {handle}")
                    return render_template('set_handle.html', error="This handle is already taken. Please choose another.")
                member.handle = handle
                db.session.commit()
                app.logger.info(f"Handle set for user {email}: {handle}")
                return redirect(url_for('chat'))
            except Exception as e:
                app.logger.error(f"Error setting handle for {email}: {str(e)}")
                db.session.rollback()
                return render_template('set_handle.html', error="An error occurred while setting your handle. Please try again.")
    
    return render_template('set_handle.html')

@app.route('/chat')
def chat():
    app.logger.debug(f"Accessing chat route. Session: {session}")
    if 'email' not in session:
        app.logger.debug("No email in session, redirecting to index")
        return redirect(url_for('index'))
    
    email = session['email']
    member = Member.query.filter_by(email=email).first()
    if not member or not member.verified:
        app.logger.debug(f"Member not found or not verified: {email}")
        return redirect(url_for('index'))
    if not member.handle:
        app.logger.debug(f"Handle not set for user: {email}")
        return redirect(url_for('set_handle'))
    return render_template('chat.html', email=email, handle=member.handle)

@app.route('/logout')
def logout():
    email = session.pop('email', None)
    if email:
        app.logger.info(f"User logged out: {email}")
    app.logger.debug("Redirecting to index after logout")
    return redirect(url_for('index'))

@socketio.on('join')
def on_join(data):
    handle = data['handle']
    room = data['room']
    join_room(room)
    app.logger.info(f"User {handle} joined room {room}")
    emit('status', {'msg': f'{handle} has arrived.'}, to=room)

@socketio.on('leave')
def on_leave(data):
    handle = data['handle']
    room = data['room']
    leave_room(room)
    app.logger.info(f"User {handle} left room {room}")
    emit('status', {'msg': f'{handle} has left.'}, to=room)

@socketio.on('chat_message')
def handle_message(data):
    handle = data['handle']
    room = data['room']
    message = data['message']
    app.logger.info(f"Chat message in room {room} from {handle}: {message}")
    emit('message', {'handle': handle, 'message': message}, to=room)

@app.errorhandler(404)
def page_not_found(e):
    app.logger.warning(f"404 error: {request.url}")
    return render_template('error.html', message="Page not found"), 404

@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f"500 error: {str(e)}")
    return render_template('error.html', message="Internal server error"), 500

@app.before_request
def check_db_connection():
    try:
        db.session.execute(db.select(db.text('1')))
        app.logger.debug("Database connection successful")
    except SQLAlchemyError as e:
        app.logger.error(f"Database connection failed: {str(e)}")

if __name__ == '__main__':
    print("This file should be run via Gunicorn and not directly.")