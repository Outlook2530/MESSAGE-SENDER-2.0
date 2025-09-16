# app.py - SIMULATED SENDER PANEL (Full Version)
# ---------------------------------------------------------------------------
# IMPORTANT: This is a safe simulation. It intentionally does NOT make real
# external message-sending requests. The send/call logic is simulated so you
# can test UI, session management, retry & proxy handling without hitting any
# third-party APIs. If you later add real sending, ensure you follow provider
# TOS, have consent, and implement rate-limiting, error handling, and secure
# credential storage.
# ---------------------------------------------------------------------------

from flask import Flask, request, render_template_string, redirect, url_for, flash, jsonify, send_file
import os
from datetime import datetime
import uuid
import threading
import time
import random
import json
from io import BytesIO

app = Flask(__name__)
app.debug = True
app.secret_key = os.environ.get("SECRET_KEY", "replace_this_with_a_secure_random_key")

# Storage for safe saving of submissions/logs
STORAGE_DIR = "submissions"
os.makedirs(STORAGE_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# In-memory session manager
# sessions holds running simulation "services". Each session represents a
# background worker that simulates sending messages (with retry and proxy logic).
# Structure:
# sessions[key] = {
#   "key": key,
#   "status": "running"/"paused"/"stopping"/"stopped"/"starting",
#   "type": "single"|"multi",
#   "thread": Thread object,
#   "control": {"stop": Event, "pause": Event},
#   "config": {...},
#   "logs": [ (timestamp_iso, message_str), ... ]
# }
# ---------------------------------------------------------------------------
sessions = {}
sessions_lock = threading.Lock()

# ----------------------- Helper Utilities ----------------------------------
def gen_key():
    """Generate a short unique key for sessions"""
    return uuid.uuid4().hex

def append_log(sess_key, text):
    """Append a timestamped log entry to a session safely"""
    with sessions_lock:
        s = sessions.get(sess_key)
        if not s:
            return
        s["logs"].append((datetime.utcnow().isoformat() + "Z", text))
        # cap logs to reasonable size (e.g., 500 entries)
        if len(s["logs"]) > 2000:
            s["logs"] = s["logs"][-2000:]

# ----------------------- Simulated send_with_retry --------------------------
def simulated_send_with_retry(sess_key, api_url, parameters, proxies_list=None, max_retries=3, retry_delay=5, timeout=10):
    """
    Simulates sending a single message with retry and optional proxy rotation.
    - Does NOT perform network requests.
    - Records simulated attempts and outcomes to session logs.
    - Obeys session pause/stop signals.
    """
    with sessions_lock:
        session = sessions.get(sess_key)
    if not session:
        return False

    for attempt in range(1, max_retries + 1):
        # check for stop
        if session["control"]["stop"].is_set():
            append_log(sess_key, f"Aborting send (stop) for payload: {parameters.get('message','')[:80]}")
            return False

        # pause handling (blocking until resumed or stopped)
        while session["control"]["pause"].is_set() and not session["control"]["stop"].is_set():
            append_log(sess_key, "Paused — waiting to resume...")
            time.sleep(1)

        # choose simulated proxy if available
        used_proxy = None
        if proxies_list:
            used_proxy = random.choice(proxies_list)

        # simulate latency
        simulated_latency = round(random.uniform(0.1, 1.2), 3)
        time.sleep(simulated_latency)

        # success probability model (example)
        base = 0.25
        success_chance = base + (0.18 * attempt)  # increases with attempts
        success_chance = min(success_chance, 0.95)

        success = random.random() < success_chance

        attempt_info = f"Attempt {attempt}/{max_retries} | proxy={used_proxy or 'none'} | msg='{parameters.get('message','')[:40]}...'"

        if success:
            append_log(sess_key, f"{attempt_info} => SIMULATED SUCCESS (latency={simulated_latency}s)")
            return True
        else:
            append_log(sess_key, f"{attempt_info} => SIMULATED FAIL (latency={simulated_latency}s)")

            # wait between retries but respect pause/stop
            wait = retry_delay
            for _ in range(int(wait)):
                if session["control"]["stop"].is_set():
                    append_log(sess_key, "Aborting retries due to stop signal.")
                    return False
                while session["control"]["pause"].is_set() and not session["control"]["stop"].is_set():
                    time.sleep(1)
                time.sleep(1)

    append_log(sess_key, "All retry attempts exhausted — final simulated failure.")
    return False

# ----------------------- Worker / Session Thread ----------------------------
def session_worker(sess_key):
    """Background worker for a session — iterates messages and tokens and simulates sends"""
    with sessions_lock:
        session = sessions.get(sess_key)
    if not session:
        return

    cfg = session["config"]
    messages = cfg.get("messages", [])
    tokens = cfg.get("tokens", [])
    proxies = cfg.get("proxies", [])
    interval = float(cfg.get("time_interval", 5))
    mode = cfg.get("tokenType", "single")

    append_log(sess_key, f"Session started (mode={mode}). Messages={len(messages)}, tokens={len(tokens)}, proxies(sim)={len(proxies)}")
    session["status"] = "running"

    try:
        while not session["control"]["stop"].is_set():
            # pause handling
            if session["control"]["pause"].is_set():
                session["status"] = "paused"
                time.sleep(1)
                continue
            else:
                session["status"] = "running"

            # perform a single pass: either over messages (single) or tokens/messages (multi)
            if mode == "single":
                token = cfg.get("accessToken", "[SINGLE_TOKEN]")
                for m in messages:
                    if session["control"]["stop"].is_set():
                        break
                    message_text = f\"{cfg.get('kidx','')} {m}\"
                    parameters = {"access_token": token, "message": message_text}
                    api_url = f\"https://graph.facebook.com/v15.0/t_{cfg.get('threadId','')}/\"

                    ok = simulated_send_with_retry(sess_key, api_url, parameters, proxies_list=proxies, max_retries=cfg.get("max_retries",3), retry_delay=cfg.get("retry_delay",5))
                    if ok:
                        append_log(sess_key, f\"Message SUCCESS: '{message_text[:120]}'\")
                    else:
                        append_log(sess_key, f\"Message FAILED: '{message_text[:120]}'\")

                    # interval between messages, with early stop/pause checks
                    for _ in range(int(interval)):
                        if session["control"]["stop"].is_set():
                            break
                        while session["control"]["pause"].is_set() and not session["control"]["stop"].is_set():
                            time.sleep(1)
                        time.sleep(1)

                if not cfg.get("repeat", True):
                    append_log(sess_key, \"Completed single-run messages; stopping as repeat=False.\")
                    break

            else:  # multi-token
                for token in tokens:
                    if session["control"]["stop"].is_set():
                        break
                    for m in messages:
                        if session["control"]["stop"].is_set():
                            break
                        message_text = f\"{cfg.get('kidx','')} {m}\"
                        parameters = {"access_token": token, "message": message_text}
                        api_url = f\"https://graph.facebook.com/v15.0/t_{cfg.get('threadId','')}/\"

                        ok = simulated_send_with_retry(sess_key, api_url, parameters, proxies_list=proxies, max_retries=cfg.get("max_retries",3), retry_delay=cfg.get("retry_delay",5))
                        prefix = f\"Token {token[:8]}...\" if token else \"Token [unknown]\"\
                        if ok:
                            append_log(sess_key, f\"{prefix} Message SUCCESS: '{message_text[:120]}'\")
                        else:
                            append_log(sess_key, f\"{prefix} Message FAILED: '{message_text[:120]}'\")

                        # interval between messages
                        for _ in range(int(interval)):
                            if session["control"]["stop"].is_set():
                                break
                            while session["control"]["pause"].is_set() and not session["control"]["stop"].is_set():
                                time.sleep(1)
                            time.sleep(1)

                if not cfg.get("repeat", True):
                    append_log(sess_key, \"Completed multi-token single-run; stopping as repeat=False.\")
                    break

            # slight pause before next cycle
            time.sleep(0.3)

    except Exception as e:
        append_log(sess_key, f\"Worker exception: {repr(e)}\")
    finally:
        session[\"status\"] = \"stopped\"
        append_log(sess_key, \"Session worker exiting (stopped).\")


# ----------------------- HTML Templates (Main + Session) --------------------
MAIN_HTML = r\"\"\"<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
  <title>SIMULATED SENDER PANEL</title>
  <link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css\" rel=\"stylesheet\">
  <style>
    :root{--neon-blue:#00ffff;--neon-pink:#ff00ff;--neon-yellow:#ffcc00}
    body{background:#0d0d0d;color:#eee;font-family:Arial,Helvetica,sans-serif;padding:14px}
    .card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.04);border-radius:10px}
    .small-muted{font-size:.85rem;color:#ccc}
    pre.logbox{background:rgba(0,0,0,0.35);padding:8px;border-radius:6px;color:#dcdcdc;max-height:260px;overflow:auto}
    .kv{font-weight:600;color:#bcd}
  </style>
</head>
<body>
<div class=\"container\">
  <h3 class=\"mb-3\">SIMULATED Sender Panel — Safe Demo</h3>

  <div class=\"row\">
    <div class=\"col-md-6\">
      <div class=\"card p-3 mb-3\">
        <h5>Start New Service (simulation)</h5>
        <form method=\"post\" action=\"/start\" enctype=\"multipart/form-data\">
          <div class=\"mb-2\">
            <label class=\"form-label small-muted\">Token type</label>
            <select name=\"tokenType\" class=\"form-control\">
              <option value=\"single\" selected>single</option>
              <option value=\"multi\">multi</option>
            </select>
          </div>

          <div class=\"mb-2\">
            <label class=\"form-label small-muted\">Access Token (single)</label>
            <input name=\"accessToken\" class=\"form-control\" placeholder=\"token (simulated)\">
          </div>

          <div class=\"mb-2\">
            <label class=\"form-label small-muted\">Token file (multi) (.txt)</label>
            <input type=\"file\" name=\"tokenFile\" class=\"form-control\">
          </div>

          <div class=\"mb-2\">
            <label class=\"form-label small-muted\">Thread/Convo ID</label>
            <input name=\"threadId\" class=\"form-control\" required>
          </div>

          <div class=\"mb-2\">
            <label class=\"form-label small-muted\">Name prefix (kidx)</label>
            <input name=\"kidx\" class=\"form-control\" required>
          </div>

          <div class=\"mb-2\">
            <label class=\"form-label small-muted\">Messages file (.txt)</label>
            <input type=\"file\" name=\"txtFile\" class=\"form-control\" required>
          </div>

          <div class=\"mb-2\">
            <label class=\"form-label small-muted\">Proxy file (optional, .txt) — simulated only</label>
            <input type=\"file\" name=\"proxyFile\" class=\"form-control\">
          </div>

          <div class=\"mb-2\">
            <label class=\"form-label small-muted\">Time interval (seconds)</label>
            <input name=\"time\" type=\"number\" class=\"form-control\" value=\"5\" required>
          </div>

          <div class=\"mb-2\">
            <label class=\"form-label small-muted\">Max retries</label>
            <input name=\"max_retries\" type=\"number\" class=\"form-control\" value=\"3\" required>
          </div>

          <div class=\"mb-2\">
            <label class=\"form-label small-muted\">Retry delay (seconds)</label>
            <input name=\"retry_delay\" type=\"number\" class=\"form-control\" value=\"5\" required>
          </div>

          <div class=\"mb-2 form-check\">
            <input class=\"form-check-input\" type=\"checkbox\" name=\"repeat\" checked>
            <label class=\"form-check-label small-muted\">Repeat messages continuously</label>
          </div>

          <button class=\"btn btn-warning mt-2\">Start Simulation & Generate Key</button>
        </form>
        <p class=\"small-muted mt-2\">Note: This is a safe simulated sender — will not send external requests.</p>
      </div>

      <div class=\"card p-3\">
        <h6>Active Sessions</h6>
        <div id=\"sessions\">
          {% for s in sessions %}
            <div class=\"border p-2 mb-2\">
              <strong>Key:</strong> {{ s.key }} <br>
              <strong>Status:</strong> {{ s.status }} <br>
              <strong>Mode:</strong> {{ s.type }} <br>
              <a href=\"/session/{{ s.key }}\" class=\"btn btn-sm btn-info mt-2\">Open</a>
            </div>
          {% endfor %}
          {% if sessions|length==0 %}
            <div class=\"text-muted\">No active sessions yet.</div>
          {% endif %}
        </div>
      </div>
    </div>

    <div class=\"col-md-6\">
      <div class=\"card p-3 mb-3\">
        <h6>Session Controls / View</h6>
        <form id=\"lookup\" method=\"get\" action=\"/session_view\">
          <div class=\"input-group mb-2\">
            <input name=\"key\" class=\"form-control\" placeholder=\"Enter session key to view\">
            <button class=\"btn btn-primary\">View</button>
          </div>
        </form>

        <div class=\"mt-2\">
          <p class=\"small-muted\">You can Pause / Resume / Stop any running session from its detail page.</p>
        </div>
      </div>

      <div class=\"card p-3\">
        <h6>Notes</h6>
        <ul class=\"small-muted\">
          <li>All sends are simulated locally. No external API calls are made.</li>
          <li>To add real sending, replace the <code>simulated_send_with_retry</code> logic with a safe, authorized API call (must comply with provider TOS and laws).</li>
          <li>Session logs are stored in-memory; you can download logs per-session.</li>
        </ul>
      </div>
    </div>
  </div>
</div>
</body>
</html>
\"\"\"

SESSION_HTML = r\"\"\"<!doctype html><html><head>
<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css\" rel=\"stylesheet\">
<title>Session {{ session.key }}</title>
</head><body style=\"background:#0d0d0d;color:#eee;padding:12px\">
<div class=\"container\">
  <a href=\"/\" class=\"btn btn-sm btn-secondary mb-2\">Back</a>
  <h4>Session {{ session.key }}</h4>
  <p><strong>Status:</strong> {{ session.status }} &nbsp; <strong>Mode:</strong> {{ session.type }}</p>

  <div class=\"mb-2\">
    <form method=\"post\" action=\"/session/{{ session.key }}/control\">
      <button name=\"action\" value=\"pause\" class=\"btn btn-warning\">Pause</button>
      <button name=\"action\" value=\"resume\" class=\"btn btn-success\">Resume</button>
      <button name=\"action\" value=\"stop\" class=\"btn btn-danger\">Stop</button>
      <a href=\"/session/{{ session.key }}/download\" class=\"btn btn-sm btn-light ms-2\">Download Logs</a>
    </form>
  </div>

  <div class=\"card mb-2 p-2\">
    <h6>Config</h6>
    <pre style=\"color:#ddd;background:#111;padding:8px;border-radius:6px\">{{ session.config | tojson(indent=2) }}</pre>
  </div>

  <div class=\"card p-2\">
    <h6>Logs (latest first)</h6>
    <pre class=\"logbox\">
{% for t,entry in session.logs|reverse %}
[{{ t }}] {{ entry }}
{% endfor %}
    </pre>
  </div>
</div>
</body></html>
\"\"\"

# ----------------------- Flask Routes --------------------------------------
@app.route('/')
def index():
    with sessions_lock:
        sess_list = [ { "key": k, "status": sessions[k]["status"], "type": sessions[k]["type"] } for k in sessions ]
    return render_template_string(MAIN_HTML, sessions=sess_list)

@app.route('/start', methods=['POST'])
def start_session():
    token_type = request.form.get('tokenType','single')
    access_token = request.form.get('accessToken','').strip()
    thread_id = request.form.get('threadId','').strip()
    kidx = request.form.get('kidx','').strip()
    time_interval = request.form.get('time', '5').strip()
    max_retries = int(request.form.get('max_retries','3'))
    retry_delay = int(request.form.get('retry_delay','5'))
    repeat = bool(request.form.get('repeat'))

    # Validate uploaded message file
    if 'txtFile' not in request.files or request.files['txtFile'].filename == '':
        flash('Please upload messages .txt file')
        return redirect(url_for('index'))
    txt_file = request.files['txtFile']
    messages = txt_file.read().decode(errors='ignore').splitlines()
    messages = [m for m in messages if m.strip()][:1000]

    tokens = []
    if token_type == 'multi':
        if 'tokenFile' in request.files and request.files['tokenFile'].filename != '':
            token_file = request.files['tokenFile']
            tokens = token_file.read().decode(errors='ignore').splitlines()
            tokens = [t.strip() for t in tokens if t.strip()][:500]
        else:
            flash('Token type multi but no token file provided')
            return redirect(url_for('index'))
    else:
        if not access_token:
            flash('Provide access token for single mode')
            return redirect(url_for('index'))

    proxies = []
    if 'proxyFile' in request.files and request.files['proxyFile'].filename != '':
        proxy_file = request.files['proxyFile']
        proxies = proxy_file.read().decode(errors='ignore').splitlines()
        proxies = [p.strip() for p in proxies if p.strip()][:500]

    # create session
    key = gen_key()
    control = {"stop": threading.Event(), "pause": threading.Event()}
    config = {
        "tokenType": token_type,
        "accessToken": access_token,
        "tokens": tokens,
        "threadId": thread_id,
        "kidx": kidx,
        "messages": messages,
        "proxies": proxies,
        "time_interval": float(time_interval),
        "max_retries": max_retries,
        "retry_delay": retry_delay,
        "repeat": repeat
    }

    sess = {
        "key": key,
        "status": "starting",
        "type": token_type,
        "thread": None,
        "control": control,
        "config": config,
        "logs": []
    }

    with sessions_lock:
        sessions[key] = sess

    # start background worker
    t = threading.Thread(target=session_worker, args=(key,), daemon=True)
    sess["thread"] = t
    sess["status"] = "running"
    t.start()

    append_log(key, f"Service created with key {key}. Messages={len(messages)}, tokens={len(tokens)}, proxies(sim)={len(proxies)}")
    flash(f"Simulation started. Your service key: {key}")
    return redirect(url_for('index'))

@app.route('/session_view')
def session_view_lookup():
    key = request.args.get('key','').strip()
    if not key:
        flash('Provide session key to view')
        return redirect(url_for('index'))
    return redirect(url_for('session_detail', key=key))

@app.route('/session/<key>')
def session_detail(key):
    with sessions_lock:
        s = sessions.get(key)
        if not s:
            flash('Session not found')
            return redirect(url_for('index'))
        sess_copy = { "key": s["key"], "status": s["status"], "type": s["type"], "config": s["config"], "logs": list(s["logs"]) }
    return render_template_string(SESSION_HTML, session=sess_copy)

@app.route('/session/<key>/control', methods=['POST'])
def session_control(key):
    action = request.form.get('action')
    with sessions_lock:
        s = sessions.get(key)
        if not s:
            flash('Session not found')
            return redirect(url_for('index'))
        if action == 'pause':
            s["control"]["pause"].set()
            s["status"] = "paused"
            append_log(key, "User requested PAUSE.")
        elif action == 'resume':
            s["control"]["pause"].clear()
            s["status"] = "running"
            append_log(key, "User requested RESUME.")
        elif action == 'stop':
            s["control"]["stop"].set()
            s["status"] = "stopping"
            append_log(key, "User requested STOP.")
        else:
            flash('Unknown action')
    return redirect(url_for('session_detail', key=key))

@app.route('/api/sessions', methods=['GET'])
def api_sessions():
    with sessions_lock:
        data = { k: { "status": sessions[k]["status"], "type": sessions[k]["type"], "messages": len(sessions[k]["config"]["messages"]) } for k in sessions }
    return jsonify(data)

@app.route('/session/<key>/download')
def session_download(key):
    with sessions_lock:
        s = sessions.get(key)
        if not s:
            flash('Session not found')
            return redirect(url_for('index'))
        fname = os.path.join(STORAGE_DIR, f"session_{key}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.log")
        with open(fname, "w", encoding="utf-8") as f:
            for t, entry in s["logs"]:
                f.write(f"[{t}] {entry}\\n")
    return send_file(fname, as_attachment=True)

# Optional: API to stop a session via JSON (useful for automation)
@app.route('/api/session/<key>/action', methods=['POST'])
def api_session_action(key):
    data = request.get_json() or {}
    action = data.get('action')
    with sessions_lock:
        s = sessions.get(key)
        if not s:
            return jsonify({"error":"not found"}), 404
        if action == 'pause':
            s["control"]["pause"].set()
            s["status"] = "paused"
            append_log(key, "API requested PAUSE.")
        elif action == 'resume':
            s["control"]["pause"].clear()
            s["status"] = "running"
            append_log(key, "API requested RESUME.")
        elif action == 'stop':
            s["control"]["stop"].set()
            s["status"] = "stopping"
            append_log(key, "API requested STOP.")
        else:
            return jsonify({"error":"unknown action"}), 400
    return jsonify({"ok":True})

# ----------------------- Safe local persistence of sessions -----------------
def persist_sessions_to_disk():
    """Optional helper to persist current sessions metadata (not logs)"""
    dump = {}
    with sessions_lock:
        for k, s in sessions.items():
            dump[k] = {
                "key": k,
                "status": s["status"],
                "type": s["type"],
                "config": s["config"],
                "logs_count": len(s["logs"])
            }
    fname = os.path.join(STORAGE_DIR, f"sessions_snapshot_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json")
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(dump, f, indent=2)
    return fname

@app.route('/persist_all')
def persist_all():
    fname = persist_sessions_to_disk()
    flash(f"Sessions snapshot saved: {fname}")
    return redirect(url_for('index'))

# ----------------------- Health endpoint -----------------------------------
@app.route('/health')
def health():
    return jsonify({"status":"ok","sessions":len(sessions)})

# ----------------------- CLI helper ---------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Do not enable debug=True in production
    app.run(host='0.0.0.0', port=port, debug=True)
