from app import app, socketio
import eventlet

eventlet.monkey_patch()

if __name__ == "__main__":
    socketio.run(app)
