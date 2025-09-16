from flask import Flask, request, render_template, redirect, url_for, flash
import os
from datetime import datetime

app = Flask(__name__)
app.debug = True
app.secret_key = "replace_this_with_a_secure_random_key"

# Create storage folder for safe saving of submissions
STORAGE_DIR = "submissions"
os.makedirs(STORAGE_DIR, exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def send_message():
    preview_messages = None
    token_count = None
    form_defaults = {}

    if request.method == 'POST':
        token_type = request.form.get('tokenType')
        thread_id = request.form.get('threadId', '').strip()
        mn = request.form.get('kidx', '').strip()
        time_interval = request.form.get('time', '').strip()

        form_defaults = {
            "tokenType": token_type,
            "threadId": thread_id,
            "kidx": mn,
            "time": time_interval,
            "accessToken": request.form.get('accessToken', '')
        }

        # Basic validation
        if not thread_id or not mn or not time_interval:
            flash("Please fill required fields (Convo ID, Name, Time).")
            return render_template("panel.html", preview_messages=None, token_count=None, form_defaults=form_defaults)

        # Read message file safely and prepare preview
        if 'txtFile' not in request.files or request.files['txtFile'].filename == '':
            flash("Please upload a message .txt file.")
            return render_template("panel.html", preview_messages=None, token_count=None, form_defaults=form_defaults)

        txt_file = request.files['txtFile']
        try:
            txt_content = txt_file.read().decode(errors='ignore').splitlines()
            # limit preview to first 200 lines
            preview_messages = txt_content[:200]
        except Exception as e:
            flash("Could not read messages file. Make sure it is a text (.txt) file.")
            preview_messages = None

        # If multi-token, read token file and give summary (but do NOT perform any external actions)
        if token_type == 'multi':
            if 'tokenFile' not in request.files or request.files['tokenFile'].filename == '':
                flash("Token type is multi but no token file uploaded.")
                return render_template("panel.html", preview_messages=preview_messages, token_count=None, form_defaults=form_defaults)
            token_file = request.files['tokenFile']
            try:
                tokens = token_file.read().decode(errors='ignore').splitlines()
                tokens = [t.strip() for t in tokens if t.strip()]
                token_count = len(tokens)
            except Exception as e:
                flash("Could not read token file. Make sure it is a text (.txt) file.")
                token_count = None

        # Save a safe submission record (no external calls)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        safe_filename = os.path.join(STORAGE_DIR, f"submission_{timestamp}.txt")
        try:
            with open(safe_filename, "w", encoding="utf-8") as f:
                f.write(f"Timestamp (UTC): {timestamp}\n")
                f.write(f"Token type: {token_type}\n")
                f.write(f"Convo ID: {thread_id}\n")
                f.write(f"Name (kidx): {mn}\n")
                f.write(f"Time interval (s): {time_interval}\n")
                if token_type == 'single':
                    f.write("Token: [NOT SAVED BY DEFAULT]\n")
                else:
                    f.write(f"Token count: {token_count}\n")
                f.write("\n--- Messages Preview (first 200 lines) ---\n")
                if preview_messages:
                    for line in preview_messages:
                        f.write(line + "\n")
            flash("Submission received and saved locally for preview. No messages were sent.")
        except Exception as e:
            flash("Could not save submission locally; check server file permissions.")

        return render_template("panel.html", preview_messages=preview_messages, token_count=token_count, form_defaults=form_defaults)

    # GET
    return render_template("panel.html", preview_messages=None, token_count=None, form_defaults={ "tokenType": "single" })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
