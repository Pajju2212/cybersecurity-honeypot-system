from app import app

if __name__ == '__main__':
    # Use socketio.run if socketio is started in app.py; otherwise fallback to Flask's run
    try:
        from app import socketio
        socketio.run(app, debug=True)
    except Exception:
        app.run(debug=True)
