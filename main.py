import eventlet
eventlet.monkey_patch()

from app import app, socketio

# This file serves as the entry point for Gunicorn
# Gunicorn will import the 'app' object from here

if __name__ == "__main__":
    # This block will only be executed when running the file directly
    # It won't be used by Gunicorn, but can be helpful for local development
    socketio.run(app, host='0.0.0.0', port=5000, ssl_context='adhoc')
