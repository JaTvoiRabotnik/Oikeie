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
from flask_wtf.csrf import CSRFProtect
import secrets
from collections import defaultdict

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

Talisman(app, content_security_policy={
    'default-src': "'self'",
    'script-src': "'self' 'unsafe-inline' https://cdnjs.cloudflare.com",
    'style-src': "'self' 'unsafe-inline' https://cdn.replit.com https://fonts.googleapis.com",
    'font-src': "'self' https://fonts.gstatic.com",
    'img-src': "'self' data:",
    'connect-src': "'self' wss:",
}, force_https=False)

csrf = CSRFProtect(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

logging.basicConfig(level=logging.DEBUG)
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)

# In-memory rate limiting
rate_limits = defaultdict(lambda: {'count': 0, 'reset_time': datetime.now()})

def is_rate_limited(key, limit, period):
    now = datetime.now()
    if now > rate_limits[key]['reset_time']:
        rate_limits[key] = {'count': 0, 'reset_time': now + timedelta(seconds=period)}
    rate_limits[key]['count'] += 1
    return rate_limits[key]['count'] > limit

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    verified = db.Column(db.Boolean, default=False)
    token = db.Column(db.String(255))
    token_expiry = db.Column(db.DateTime(timezone=True))
    handle = db.Column(db.String(50), unique=True)

    def __init__(self, email, verified=False, token=None, token_expiry=None, handle=None):
        self.email = email
        self.verified = verified
        self.token = token
        self.token_expiry = token_expiry
        self.handle = handle

    def __repr__(self):
        return f'<Member {self.email}>'

@app.route('/')
def index():
    if 'email' in session:
        member = Member.query.filter_by(email=session['email']).first()
        if member and member.verified:
            if not member.handle:
                return redirect(url_for('set_handle'))
            return redirect(url_for('chat'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    if is_rate_limited(request.remote_addr, 5, 60):
        return jsonify({'success': False, 'message': 'Rate limit exceeded. Please try again later.'}), 429
    
    email = request.form.get('email')
    try:
        app.logger.debug(f"Attempting to log in user with email: {email}")
        member = Member.query.filter_by(email=email).first()
        if not member:
            app.logger.info(f"Creating new member for email: {email}")
            member = Member(email=email)
            db.session.add(member)
        
        token = serializer.dumps(email, salt='email-confirm')
        member.token = token
        member.token_expiry = datetime.now(timezone.utc) + timedelta(hours=24)
        db.session.commit()
        
        # Send magic link email logic here (implement this part)
        
        return jsonify({'success': True, 'message': 'A magic link has been sent to your email. Please check your inbox.'})
    except Exception as e:
        app.logger.error(f"Error in login process: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred while processing your request. Please try again later.'})

@app.route('/verify_magic_link')
def verify_magic_link():
    if is_rate_limited(request.remote_addr, 3, 60):
        return render_template('error.html', message="Rate limit exceeded. Please try again later."), 429
    
    try:
        token = request.args.get('token')
        email = serializer.loads(token, salt='email-confirm', max_age=86400)  # 24 hours expiry
        member = Member.query.filter_by(email=email).first()
        
        if member and member.token == token:
            member.verified = True
            member.token = None
            member.token_expiry = None
            db.session.commit()
            session['email'] = email
            
            if not member.handle:
                return redirect(url_for('set_handle'))
            return redirect(url_for('chat'))
        else:
            return render_template('error.html', message="Invalid or expired magic link")
    except (SignatureExpired, BadSignature):
        return render_template('error.html', message="Invalid or expired magic link")
    except Exception as e:
        app.logger.error(f"Error in verify_magic_link: {str(e)}")
        return render_template('error.html', message="An error occurred while processing your request")

@app.route('/set_handle', methods=['GET', 'POST'])
def set_handle():
    if is_rate_limited(request.remote_addr, 5, 60):
        return render_template('error.html', message="Rate limit exceeded. Please try again later."), 429
    
    if 'email' not in session:
        return redirect(url_for('index'))
    
    member = Member.query.filter_by(email=session['email']).first()
    
    if not member or not member.verified:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        handle = request.form.get('handle')
        if handle:
            try:
                existing_member = Member.query.filter_by(handle=handle).first()
                if existing_member:
                    return render_template('set_handle.html', error="This handle is already taken. Please choose another.")
                member.handle = handle
                db.session.commit()
                return redirect(url_for('chat'))
            except Exception as e:
                app.logger.error(f"Error in set_handle: {str(e)}")
                db.session.rollback()
                return render_template('set_handle.html', error="An error occurred while setting your handle. Please try again.")
    
    return render_template('set_handle.html')

@app.route('/chat')
def chat():
    if is_rate_limited(request.remote_addr, 30, 60):
        return render_template('error.html', message="Rate limit exceeded. Please try again later."), 429
    
    if 'email' not in session:
        return redirect(url_for('index'))
    
    member = Member.query.filter_by(email=session['email']).first()
    
    if not member or not member.verified:
        return redirect(url_for('index'))
    
    if not member.handle:
        return redirect(url_for('set_handle'))
    
    return render_template('chat.html', email=member.email, handle=member.handle)

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
