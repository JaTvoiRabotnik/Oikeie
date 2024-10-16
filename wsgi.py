import eventlet
eventlet.monkey_patch()

from app import app, socketio

if __name__ == "__main__":
    with app.app_context():
        socketio.run(app)
